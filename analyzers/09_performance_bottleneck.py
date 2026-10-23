"""Universal, read-only performance analysis for Python Project Intelligence.

Only project source files and existing project-specific reports are read.
Findings are static heuristics, never claims of measured runtime slowness.
"""
from __future__ import annotations

import ast
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

INTELLIGENCE_ROOT = Path(__file__).resolve().parent.parent
if str(INTELLIGENCE_ROOT) not in sys.path:
    sys.path.insert(0, str(INTELLIGENCE_ROOT))

from core.project_context import PROJECT_ROOT, PROJECT_NAME, PROJECT_OUTPUT_ROOT

PROJECT_ROOT = Path(PROJECT_ROOT).resolve()
OUTPUT_DIR = Path(PROJECT_OUTPUT_ROOT) / "LATEST" / "09_PERFORMANCE_BOTTLENECK"
OUTPUT_FILE = OUTPUT_DIR / "PERFORMANCE_MAP.json"
LATEST = Path(PROJECT_OUTPUT_ROOT) / "LATEST"
EXCLUDED_DIRS = {".git", ".venv", "venv", "env", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache", ".tox", "site-packages", "dist", "build"}
MAX_SOURCE_BYTES = 3_000_000


def load_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else None
    except (OSError, UnicodeError, ValueError):
        return None


def normalize_command(command):
    return " ".join(str(command or "").lower().split())


def iter_project_python():
    """Walk the selected project, never following directory symlinks."""
    import os
    for directory, subdirs, filenames in os.walk(PROJECT_ROOT, followlinks=False):
        subdirs[:] = sorted(d for d in subdirs if d not in EXCLUDED_DIRS and not (Path(directory) / d).is_symlink() and not (Path(directory) / d).resolve().is_relative_to(INTELLIGENCE_ROOT))
        for filename in sorted(filenames):
            if not filename.endswith(".py"):
                continue
            path = Path(directory) / filename
            if path.is_symlink():
                continue
            try:
                if path.stat().st_size > MAX_SOURCE_BYTES:
                    continue
                if not path.resolve().is_relative_to(PROJECT_ROOT):
                    continue
            except OSError:
                continue
            yield path


def call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = call_name(node.value)
        return (prefix + "." if prefix else "") + node.attr
    return ""


def enclosing_function(parents, node):
    cursor = node
    while cursor in parents:
        cursor = parents[cursor]
        if isinstance(cursor, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cursor.name
    return None


def loop_depth(parents, node):
    depth = 0
    cursor = node
    while cursor in parents:
        cursor = parents[cursor]
        if isinstance(cursor, (ast.For, ast.AsyncFor, ast.While)):
            depth += 1
    return depth


def analyze_source(path):
    relative = str(path.relative_to(PROJECT_ROOT)).replace("/", "\\")
    try:
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=relative)
    except (OSError, UnicodeError, SyntaxError, ValueError) as exc:
        return [], [], {"file": relative, "reason": type(exc).__name__}
    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent

    observations, risks = [], []
    seen = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = call_name(node.func)
        method = name.rsplit(".", 1)[-1].lower()
        depth = loop_depth(parents, node)
        if not depth:
            if method in {"executemany", "to_thread"}:
                key = (method, node.lineno)
                if key not in seen:
                    observations.append({
                        "type": "BATCHED_DATABASE_WRITE" if method == "executemany" else "ASYNC_THREAD_OFFLOAD",
                        "category": "STATIC", "file": relative, "line": node.lineno,
                        "function": enclosing_function(parents, node),
                        "severity": "INFO", "confidence": "STATIC_PATTERN",
                        "counts_as_performance_risk": False,
                        "reason": f"Call to {name} detected; effectiveness not measured."
                    })
                    seen.add(key)
            continue
        # SQL statements may be in variables; do not claim an actual SQL query without evidence.
        sql_literal = ""
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            sql_literal = node.args[0].value.lstrip().upper()
        if method == "execute":
            is_write = sql_literal.startswith(("INSERT", "UPDATE", "DELETE", "REPLACE"))
            typ = "ROW_BY_ROW_DATABASE_WRITE" if is_write else "DATABASE_EXECUTE_INSIDE_LOOP"
            severity = "MEDIUM" if depth >= 2 else "LOW"
            reason = "Database execute call is inside a loop; review batching and query frequency."
        elif method in {"executemany"}:
            typ, severity = "BATCHED_WRITE_INSIDE_LOOP", "LOW"
            reason = "executemany is called inside a loop; check batch size and iteration frequency."
        elif method in {"fetchone", "fetchall", "fetchmany"}:
            typ, severity = "DATABASE_FETCH_INSIDE_LOOP", "LOW"
            reason = "Database fetch call is inside a loop; verify whether repeated access is necessary."
        else:
            continue
        key = (typ, node.lineno)
        if key in seen:
            continue
        seen.add(key)
        risks.append({
            "type": typ, "category": "STATIC", "file": relative,
            "line": node.lineno, "function": enclosing_function(parents, node),
            "severity": severity, "confidence": "POSSIBLE", "counts_as_performance_risk": True,
            "loop_depth": depth, "reason": reason,
            "index_support": "NOT_ASSESSED",
        })
    return observations, risks, None


def database_indexes(database):
    """Return only index evidence actually present in Analyzer 03 report."""
    evidence = []
    if not isinstance(database, dict):
        return evidence
    for db in database.get("databases", []):
        if not isinstance(db, dict):
            continue
        analysis = db.get("analysis") or {}
        if not isinstance(analysis, dict):
            continue
        for table in analysis.get("tables", []):
            if not isinstance(table, dict):
                continue
            for index in table.get("indexes", []):
                if not isinstance(index, dict):
                    continue
                evidence.append({
                    "database": db.get("relative_path"),
                    "table": table.get("name"),
                    "rows": table.get("row_count"),
                    "index": index.get("name"),
                    "columns": index.get("columns", []),
                    "confidence": "REPORTED_BY_ANALYZER_03",
                })
    return evidence


def main():
    runtime_path = LATEST / "02_RUNTIME" / "RUNTIME_MAP.json"
    database_path = LATEST / "03_DATABASE" / "DATABASE_MAP.json"
    runtime = load_json(runtime_path)
    database = load_json(database_path)
    runtime_available = isinstance(runtime, dict)
    database_available = isinstance(database, dict)
    observations, risks, confirmed = [], [], []
    processes = runtime.get("project_processes", []) if runtime_available else []
    if not isinstance(processes, list):
        processes = []
    groups = {}
    for item in processes:
        if not isinstance(item, dict):
            continue
        resources = item.get("resources") or {}
        observations.append({
            "type": "RUNTIME_PROCESS_RESOURCE_SNAPSHOT", "category": "RUNTIME",
            "severity": "INFO", "confidence": "REPORTED_BY_ANALYZER_02",
            "pid": item.get("pid"), "command_line": item.get("command_line"),
            "working_set_mb": resources.get("working_set_mb"),
            "private_memory_mb": resources.get("private_memory_mb"),
            "cpu_seconds": resources.get("cpu_seconds"),
            "thread_count": resources.get("thread_count"),
            "note": "Single snapshot; cumulative CPU time is not current CPU utilization.",
        })
        command = normalize_command(item.get("command_line"))
        if command:
            groups.setdefault(command, []).append(item)
    for command, items in groups.items():
        if len(items) > 1:
            risks.append({
                "type": "DUPLICATE_RUNTIME_COMMAND", "category": "RUNTIME",
                "severity": "MEDIUM", "confidence": "REPORTED_BY_ANALYZER_02",
                "count": len(items), "pids": [p.get("pid") for p in items],
                "command_line": command,
                "reason": "Multiple project processes have the same normalized command.",
            })

    databases = database.get("databases", []) if database_available else []
    if not isinstance(databases, list):
        databases = []
    for db in databases:
        if not isinstance(db, dict):
            continue
        size = db.get("size_mb")
        if isinstance(size, (int, float)) and size >= 500:
            observations.append({
                "type": "LARGE_DATABASE", "category": "CAPACITY", "severity": "INFO",
                "confidence": "REPORTED_BY_ANALYZER_03", "database": db.get("relative_path"),
                "size_mb": size, "note": "Size alone is not evidence of a bottleneck.",
            })
        analysis = db.get("analysis") or {}
        if not isinstance(analysis, dict):
            continue
        for table in analysis.get("tables", []):
            if not isinstance(table, dict):
                continue
            count = table.get("row_count")
            if isinstance(count, int) and count >= 1_000_000:
                observations.append({
                    "type": "LARGE_TABLE", "category": "CAPACITY", "severity": "INFO",
                    "confidence": "REPORTED_BY_ANALYZER_03", "database": db.get("relative_path"),
                    "table": table.get("name"), "rows": count,
                    "note": "Row count alone does not prove query slowness.",
                })

    static_observations, static_risks, errors = [], [], []
    file_count = 0
    for path in iter_project_python():
        file_count += 1
        found_obs, found_risks, error = analyze_source(path)
        static_observations.extend(found_obs)
        static_risks.extend(found_risks)
        if error:
            errors.append(error)
    observations.extend(static_observations)
    risks.extend(static_risks)
    evidence = database_indexes(database)
    status = "NO_CONFIRMED_BOTTLENECKS" if not confirmed else "BOTTLENECKS_CONFIRMED"
    counts = Counter(r.get("severity", "UNKNOWN") for r in risks)
    runtime_summary = runtime.get("summary") or {} if runtime_available else {}
    db_summary = database.get("summary") or {} if database_available else {}
    result = {
        "metadata": {
            "analyzer": "performance_bottleneck", "version": "3.0.0-universal",
            "timestamp": datetime.now(timezone.utc).isoformat(), "mode": "READ_ONLY",
            "project_name": PROJECT_NAME, "project_root": str(PROJECT_ROOT),
        },
        "methodology": {
            "runtime_source": "ANALYZER_02_RUNTIME", "database_source": "ANALYZER_03_DATABASE",
            "static_source": "PROJECT_PYTHON_AST", "direct_process_query": False,
            "direct_database_query": False, "runtime_profiling": False,
            "cpu_interpretation": "Cumulative CPU seconds do not establish current CPU load.",
            "capacity_interpretation": "Database size and row counts are not measured bottlenecks.",
            "index_interpretation": "Reported indexes are listed, not attributed to queries without proof.",
        },
        "sources": {
            "analyzer_02": {"available": runtime_available, "path": str(runtime_path)},
            "analyzer_03": {"available": database_available, "path": str(database_path)},
        },
        "summary": {
            "project_processes": len(processes),
            "project_listening_ports": runtime_summary.get("project_listening_ports"),
            "project_working_set_mb": runtime_summary.get("project_working_set_mb"),
            "project_private_memory_mb": runtime_summary.get("project_private_memory_mb"),
            "project_threads": runtime_summary.get("project_threads"),
            "database_files": db_summary.get("database_files"),
            "database_size_mb": db_summary.get("total_database_size_mb"),
            "confirmed_rows": db_summary.get("confirmed_rows"),
            "performance_observations": len(observations),
            "performance_risks": len(risks),
            "confirmed_bottlenecks": len(confirmed),
            "static_semantic_observations": len(static_observations),
            "static_semantic_risks": len(static_risks),
            "high_or_critical_risks": counts["HIGH"] + counts["CRITICAL"],
            "medium_risks": counts["MEDIUM"], "low_risks": counts["LOW"],
            "missing_index_bottlenecks": None,
            "python_files_scanned": file_count, "python_files_unreadable": len(errors),
        },
        "performance_observations": observations,
        "performance_risks": risks,
        "confirmed_bottlenecks": confirmed,
        "static_performance_analysis": {
            "observations": static_observations, "risks": static_risks,
            "confirmed_bottlenecks": [], "parse_errors": errors[:100],
        },
        "database_index_analysis": {
            "database_report_available": database_available,
            "database_report": str(database_path),
            "index_evidence": evidence,
            "large_table_index_status": "NOT_ASSESSED",
            "confirmed_missing_index_bottlenecks": None,
            "interpretation": "Indexes are reported from Analyzer 03 only. Query/index matching is not inferred.",
        },
        "performance_status": {
            "status": status, "confirmed_bottlenecks": len(confirmed),
            "probable_static_risks": len(static_risks),
            "database_index_status": "NOT_ASSESSED",
            "interpretation": "Static findings are possible risks, not measured bottlenecks.",
            "final_interpretation": "Runtime profiling is required to confirm performance bottlenecks.",
        },
        "notes": [
            "Only project files and project-specific reports are read.",
            "Static checks use Python AST; dynamic SQL, indirect calls and library-specific APIs may be missed.",
            "No query/index linkage or runtime bottleneck is claimed without evidence.",
        ],
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ANALYZER 09 UNIVERSAL - STATUS: OK")
    print("Project:", PROJECT_ROOT)
    print("Python files scanned:", file_count)
    print("Static risks:", len(static_risks))
    print("Static observations:", len(static_observations))
    print("Database indexes reported:", len(evidence))
    print("Report:", OUTPUT_FILE)
    return result


if __name__ == "__main__":
    main()

