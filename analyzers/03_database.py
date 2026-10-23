from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


# =============================================================================
# PYTHON PROJECT INTELLIGENCE
# ANALYZER 03 - UNIVERSAL DATABASE & SCHEMA
# VERSION 2.1
#
# DATABASE ACCESS: READ ONLY
# =============================================================================

THIS_FILE = Path(__file__).resolve()
INTELLIGENCE_ROOT = THIS_FILE.parent.parent
CORE_DIR = INTELLIGENCE_ROOT / "core"

if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from project_context import (
    PROJECT_NAME,
    PROJECT_ROOT,
    INTELLIGENCE_ROOT,
    PROJECT_OUTPUT_ROOT,
    iter_project_files,
    iter_python_files,
    ensure_output_directories,
)


ANALYZER_NAME = "03_database"
ANALYZER_VERSION = "2.1"

DATABASE_EXTENSIONS = {
    ".db": "sqlite_candidate",
    ".sqlite": "sqlite_candidate",
    ".sqlite3": "sqlite_candidate",
    ".duckdb": "duckdb_candidate",
    ".mdb": "access_candidate",
    ".accdb": "access_candidate",
}

# Budget massimo per un singolo COUNT(*) su tabella.
COUNT_TIME_BUDGET_SECONDS = 15.0

# Ogni N opcodes SQLite viene controllato il tempo.
SQLITE_PROGRESS_OPCODES = 100_000


def relative_string(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def safe_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def sqlite_uri(path: Path) -> str:
    return f"file:{path.resolve().as_posix()}?mode=ro"


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


# =============================================================================
# DISCOVERY
# =============================================================================

def discover_databases() -> list[dict]:

    result = []

    for path in iter_project_files():

        suffix = path.suffix.lower()

        if suffix not in DATABASE_EXTENSIONS:
            continue

        size = safe_size(path)

        result.append({
            "path": path,
            "relative_path": relative_string(path),
            "extension": suffix,
            "candidate_type": DATABASE_EXTENSIONS[suffix],
            "size_bytes": size,
            "size_mb": round(size / 1024 / 1024, 2),
        })

    return sorted(
        result,
        key=lambda item: item["relative_path"].lower(),
    )


# =============================================================================
# SAFE EXACT COUNT WITH SQLITE INTERRUPT
# =============================================================================

def safe_exact_count(
    connection: sqlite3.Connection,
    table_name: str,
) -> dict:

    started = time.monotonic()
    interrupted_by_budget = False

    def progress_handler():

        nonlocal interrupted_by_budget

        if (
            time.monotonic() - started
            > COUNT_TIME_BUDGET_SECONDS
        ):
            interrupted_by_budget = True
            return 1

        return 0

    connection.set_progress_handler(
        progress_handler,
        SQLITE_PROGRESS_OPCODES,
    )

    quoted = quote_identifier(table_name)

    try:

        row = connection.execute(
            f"SELECT COUNT(*) FROM {quoted};"
        ).fetchone()

        elapsed = time.monotonic() - started

        return {
            "row_count":
                int(row[0]) if row else 0,

            "row_count_status":
                "confirmed",

            "confidence":
                "CONFIRMED",

            "elapsed_seconds":
                round(elapsed, 3),

            "error":
                None,
        }

    except sqlite3.OperationalError as exc:

        elapsed = time.monotonic() - started

        if interrupted_by_budget:

            return {
                "row_count": None,
                "row_count_status":
                    "time_budget_exceeded",

                "confidence":
                    "UNKNOWN",

                "elapsed_seconds":
                    round(elapsed, 3),

                "error":
                    "COUNT(*) interrotto dal limite temporale",
            }

        return {
            "row_count": None,
            "row_count_status": "failed",
            "confidence": "UNKNOWN",
            "elapsed_seconds": round(elapsed, 3),
            "error": str(exc),
        }

    except Exception as exc:

        elapsed = time.monotonic() - started

        return {
            "row_count": None,
            "row_count_status": "failed",
            "confidence": "UNKNOWN",
            "elapsed_seconds": round(elapsed, 3),
            "error": str(exc),
        }

    finally:

        connection.set_progress_handler(None, 0)


# =============================================================================
# SQLITE
# =============================================================================

def analyze_sqlite_database(path: Path) -> dict:

    result = {
        "readable": False,
        "confirmed_type": None,
        "confidence": "UNKNOWN",

        "integrity_check": None,
        "page_count": None,
        "page_size": None,
        "calculated_size_bytes": None,

        "journal_mode": None,
        "user_version": None,
        "application_id": None,

        "tables": [],
        "views": [],
        "indexes": [],
        "triggers": [],
        "errors": [],
    }

    connection = None

    try:

        connection = sqlite3.connect(
            sqlite_uri(path),
            uri=True,
            timeout=5,
        )

        connection.row_factory = sqlite3.Row

        cursor = connection.cursor()

        result["readable"] = True
        result["confirmed_type"] = "sqlite"
        result["confidence"] = "CONFIRMED"

        # ---------------------------------------------------------------------
        # READ-ONLY METADATA
        # ---------------------------------------------------------------------

        try:
            row = cursor.execute(
                "PRAGMA integrity_check;"
            ).fetchone()

            if row:
                result["integrity_check"] = row[0]

        except Exception as exc:
            result["errors"].append(
                f"integrity_check: {exc}"
            )

        for pragma in (
            "page_count",
            "page_size",
            "journal_mode",
            "user_version",
            "application_id",
        ):

            try:

                row = cursor.execute(
                    f"PRAGMA {pragma};"
                ).fetchone()

                result[pragma] = (
                    row[0] if row else None
                )

            except Exception as exc:

                result["errors"].append(
                    f"{pragma}: {exc}"
                )

        if (
            isinstance(result["page_count"], int)
            and isinstance(result["page_size"], int)
        ):
            result["calculated_size_bytes"] = (
                result["page_count"]
                * result["page_size"]
            )

        # ---------------------------------------------------------------------
        # OBJECTS
        # ---------------------------------------------------------------------

        objects = cursor.execute(
            """
            SELECT
                type,
                name,
                tbl_name,
                sql
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
            ORDER BY type, name;
            """
        ).fetchall()

        table_names = []

        for obj in objects:

            record = {
                "name": obj["name"],
                "table_name": obj["tbl_name"],
                "sql": obj["sql"],
            }

            if obj["type"] == "table":
                table_names.append(obj["name"])

            elif obj["type"] == "view":
                result["views"].append(record)

            elif obj["type"] == "index":
                result["indexes"].append(record)

            elif obj["type"] == "trigger":
                result["triggers"].append(record)

        # ---------------------------------------------------------------------
        # TABLES
        # ---------------------------------------------------------------------

        for table_name in table_names:

            quoted = quote_identifier(table_name)

            table = {
                "name": table_name,

                "columns": [],
                "foreign_keys": [],
                "indexes": [],

                "row_count": None,
                "row_count_status": "not_checked",
                "row_count_confidence": "UNKNOWN",
                "row_count_elapsed_seconds": None,

                "errors": [],
            }

            # Columns
            try:

                rows = cursor.execute(
                    f"PRAGMA table_info({quoted});"
                ).fetchall()

                for row in rows:

                    table["columns"].append({
                        "cid": row["cid"],
                        "name": row["name"],
                        "type": row["type"],
                        "not_null": bool(row["notnull"]),
                        "default_value": row["dflt_value"],
                        "primary_key_position": row["pk"],
                    })

            except Exception as exc:

                table["errors"].append(
                    f"table_info: {exc}"
                )

            # Foreign keys
            try:

                rows = cursor.execute(
                    f"PRAGMA foreign_key_list({quoted});"
                ).fetchall()

                for row in rows:

                    table["foreign_keys"].append({
                        key: row[key]
                        for key in row.keys()
                    })

            except Exception as exc:

                table["errors"].append(
                    f"foreign_key_list: {exc}"
                )

            # Indexes
            try:

                rows = cursor.execute(
                    f"PRAGMA index_list({quoted});"
                ).fetchall()

                for row in rows:

                    table["indexes"].append({
                        key: row[key]
                        for key in row.keys()
                    })

            except Exception as exc:

                table["errors"].append(
                    f"index_list: {exc}"
                )

            # -------------------------------------------------------------
            # Exact COUNT(*) with time budget
            # -------------------------------------------------------------

            count_result = safe_exact_count(
                connection,
                table_name,
            )

            table["row_count"] = (
                count_result["row_count"]
            )

            table["row_count_status"] = (
                count_result["row_count_status"]
            )

            table["row_count_confidence"] = (
                count_result["confidence"]
            )

            table["row_count_elapsed_seconds"] = (
                count_result["elapsed_seconds"]
            )

            if count_result["error"]:

                table["errors"].append(
                    count_result["error"]
                )

            result["tables"].append(table)

    except Exception as exc:

        result["errors"].append(str(exc))

    finally:

        if connection is not None:

            try:
                connection.close()
            except Exception:
                pass

    return result


# =============================================================================
# CODE -> DATABASE REFERENCES
# =============================================================================

def scan_code_database_references(
    databases: list[dict],
) -> dict:

    references = defaultdict(list)

    names = {
        item["relative_path"]:
            Path(item["relative_path"]).name.lower()

        for item in databases
    }

    for python_file in iter_python_files():

        try:

            text = python_file.read_text(
                encoding="utf-8",
                errors="ignore",
            )

        except Exception:
            continue

        text_lower = text.lower()

        for db_relative, db_name in names.items():

            if db_name not in text_lower:
                continue

            matches = []

            for line_number, line in enumerate(
                text.splitlines(),
                start=1,
            ):

                if db_name in line.lower():

                    clean = line.strip()

                    if len(clean) > 500:
                        clean = clean[:500] + "..."

                    matches.append({
                        "line": line_number,
                        "text": clean,
                    })

            if matches:

                references[db_relative].append({
                    "python_file":
                        relative_string(python_file),

                    "confidence":
                        "PROBABLE",

                    "matches":
                        matches[:50],
                })

    return dict(references)


# =============================================================================
# TECHNOLOGY DETECTION
# =============================================================================

def detect_database_technologies() -> dict:

    patterns = {
        "sqlite": [
            r"\bsqlite3\b",
            r"\baiosqlite\b",
        ],

        "duckdb": [
            r"\bduckdb\b",
        ],

        "postgresql": [
            r"\bpsycopg\b",
            r"\bpsycopg2\b",
            r"\basyncpg\b",
            r"postgresql://",
            r"postgres://",
        ],

        "mysql_mariadb": [
            r"\bpymysql\b",
            r"\bmysql\.connector\b",
            r"\baiomysql\b",
            r"mysql://",
        ],

        "sqlalchemy": [
            r"\bsqlalchemy\b",
        ],

        "mongodb": [
            r"\bpymongo\b",
            r"\bmotor\b",
            r"mongodb://",
            r"mongodb\+srv://",
        ],

        "redis": [
            r"\bredis\b",
            r"redis://",
        ],
    }

    findings = {}

    for technology, expressions in patterns.items():

        files = []

        for python_file in iter_python_files():

            try:

                text = python_file.read_text(
                    encoding="utf-8",
                    errors="ignore",
                )

            except Exception:
                continue

            if any(
                re.search(
                    expression,
                    text,
                    flags=re.IGNORECASE,
                )
                for expression in expressions
            ):
                files.append(
                    relative_string(python_file)
                )

        if files:

            # Static code detection alone does NOT prove
            # the technology is active at runtime.
            findings[technology] = {
                "confidence": "POSSIBLE",
                "files": files,
                "file_count": len(files),
            }

    return findings


# =============================================================================
# COMPLETE ANALYSIS
# =============================================================================

def analyze_databases() -> dict:

    discovered = discover_databases()

    database_records = []

    readable = 0
    total_tables = 0
    total_indexes = 0

    confirmed_rows = 0
    confirmed_table_counts = 0
    unknown_table_counts = 0

    integrity_problems = 0

    for item in discovered:

        path = item["path"]

        record = {
            key: value
            for key, value in item.items()
            if key != "path"
        }

        if path.suffix.lower() in {
            ".db",
            ".sqlite",
            ".sqlite3",
        }:

            analysis = analyze_sqlite_database(
                path
            )

            record["analysis"] = analysis

            if analysis["readable"]:
                readable += 1

            if (
                analysis["integrity_check"]
                not in (None, "ok")
            ):
                integrity_problems += 1

            total_tables += len(
                analysis["tables"]
            )

            total_indexes += len(
                analysis["indexes"]
            )

            for table in analysis["tables"]:

                if (
                    table["row_count_status"]
                    == "confirmed"
                    and table["row_count"] is not None
                ):

                    confirmed_rows += (
                        table["row_count"]
                    )

                    confirmed_table_counts += 1

                else:

                    unknown_table_counts += 1

        else:

            record["analysis"] = {
                "readable": False,
                "confirmed_type": None,
                "confidence": "POSSIBLE",
                "analysis_status":
                    "detailed_parser_not_available",
                "errors": [],
            }

        database_records.append(record)

    references = scan_code_database_references(
        discovered
    )

    technologies = detect_database_technologies()

    total_size = sum(
        item["size_bytes"]
        for item in discovered
    )

    return {
        "metadata": {
            "analyzer": ANALYZER_NAME,
            "version": ANALYZER_VERSION,

            "generated_utc":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "project_name":
                PROJECT_NAME,

            "project_root":
                str(PROJECT_ROOT),

            "intelligence_root":
                str(INTELLIGENCE_ROOT),

            "mode":
                "READ_ONLY",

            "confidence_levels": {
                "CONFIRMED":
                    "Verified directly from runtime/database/file evidence.",

                "PROBABLE":
                    "Strong evidence but not fully runtime-confirmed.",

                "POSSIBLE":
                    "Static indication requiring confirmation.",

                "UNKNOWN":
                    "Insufficient evidence or analysis intentionally limited.",
            },
        },

        "summary": {
            "database_files":
                len(discovered),

            "readable_databases":
                readable,

            "total_database_size_bytes":
                total_size,

            "total_database_size_mb":
                round(
                    total_size / 1024 / 1024,
                    2,
                ),

            "tables":
                total_tables,

            "tables_with_confirmed_row_count":
                confirmed_table_counts,

            "tables_with_unknown_row_count":
                unknown_table_counts,

            "confirmed_rows":
                confirmed_rows,

            "indexes":
                total_indexes,

            "integrity_problems":
                integrity_problems,

            "databases_with_code_references":
                len(references),

            "database_technologies_detected":
                len(technologies),
        },

        "database_technologies":
            technologies,

        "code_database_references":
            references,

        "databases":
            database_records,
    }


# =============================================================================
# OUTPUT
# =============================================================================

def write_report(result: dict) -> Path:

    ensure_output_directories()

    output_dir = (
        PROJECT_OUTPUT_ROOT
        / "LATEST"
        / "03_DATABASE"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        output_dir
        / "DATABASE_MAP.json"
    )

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            result,
            handle,
            indent=2,
            ensure_ascii=False,
        )

    return output_file


# =============================================================================
# MAIN
# =============================================================================

def main() -> int:

    print("=" * 100)
    print("PYTHON PROJECT INTELLIGENCE")
    print("ANALYZER 03 - DATABASE & SCHEMA V2.1")
    print("=" * 100)

    print(f"Project name       : {PROJECT_NAME}")
    print(f"Project root       : {PROJECT_ROOT}")
    print("Mode               : READ ONLY")

    print()
    print(
        "Analisi database, schema e "
        "conteggio controllato delle tabelle..."
    )
    print()

    result = analyze_databases()
    summary = result["summary"]

    print(
        f"Database trovati   : "
        f"{summary['database_files']}"
    )

    print(
        f"Database leggibili : "
        f"{summary['readable_databases']}"
    )

    print(
        f"Dimensione DB      : "
        f"{summary['total_database_size_mb']} MB"
    )

    print(
        f"Tabelle            : "
        f"{summary['tables']}"
    )

    print(
        f"Conteggi confermati: "
        f"{summary['tables_with_confirmed_row_count']}"
    )

    print(
        f"Conteggi unknown   : "
        f"{summary['tables_with_unknown_row_count']}"
    )

    print(
        f"Righe confermate   : "
        f"{summary['confirmed_rows']:,}"
    )

    print(
        f"Indici             : "
        f"{summary['indexes']}"
    )

    print(
        f"Problemi integrita : "
        f"{summary['integrity_problems']}"
    )

    print()

    for database in result["databases"]:

        analysis = database["analysis"]

        print("-" * 100)

        print(
            f"{database['relative_path']} "
            f"| {database['size_mb']} MB"
        )

        print(
            f"Tipo: "
            f"{analysis.get('confirmed_type') or database['candidate_type']} "
            f"| confidence="
            f"{analysis.get('confidence', 'UNKNOWN')}"
        )

        if analysis.get(
            "confirmed_type"
        ) == "sqlite":

            print(
                f"Integrita: "
                f"{analysis.get('integrity_check')} "
                f"| Journal: "
                f"{analysis.get('journal_mode')}"
            )

            for table in analysis.get(
                "tables",
                []
            ):

                rows = table["row_count"]

                if rows is not None:
                    rows_text = f"{rows:,}"
                else:
                    rows_text = "UNKNOWN"

                print(
                    f"    {table['name']:<28} "
                    f"rows={rows_text:<14} "
                    f"{table['row_count_confidence']:<10} "
                    f"time={table['row_count_elapsed_seconds']}s "
                    f"cols={len(table['columns'])} "
                    f"idx={len(table['indexes'])}"
                )

    print()
    print("TECNOLOGIE DATABASE STATICHE:")

    technologies = result[
        "database_technologies"
    ]

    if technologies:

        for name, information in sorted(
            technologies.items()
        ):

            print(
                f"  {name:<18} "
                f"{information['file_count']} file "
                f"| {information['confidence']}"
            )

    else:
        print("  Nessuna.")

    output_file = write_report(result)

    print()
    print(
        f"Report JSON         : {output_file}"
    )

    print()

    if summary["integrity_problems"]:

        print(
            "ANALYZER STATUS: ATTENTION"
        )

    else:

        print(
            "ANALYZER STATUS: OK"
        )

    print("=" * 100)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
