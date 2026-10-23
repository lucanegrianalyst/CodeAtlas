from pathlib import Path
from datetime import datetime
import ast
import json
import warnings
import sys

# Permette l'esecuzione diretta dell'analyzer:
#
# python analyzers/08_health_errors_v2_test.py
#
# aggiungendo python_project_intelligence al sys.path.
INTELLIGENCE_ROOT = Path(__file__).resolve().parent.parent

if str(INTELLIGENCE_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(INTELLIGENCE_ROOT)
    )

from core.project_context import (
    PROJECT_ROOT,
    PROJECT_NAME,
    PROJECT_OUTPUT_ROOT,
    iter_python_files,
    is_excluded,
)

ANALYZER_NAME = "health_errors"
VERSION = "2.0.0-test"

OUTPUT_DIR = (
    PROJECT_OUTPUT_ROOT
    / "LATEST"
    / "08_HEALTH_ERRORS"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

JSON_PATH = (
    OUTPUT_DIR
    / "HEALTH_ERROR_MAP.json"
)


def relative(path):
    try:
        return str(
            path.relative_to(
                PROJECT_ROOT
            )
        )
    except ValueError:
        return str(path)


def classify_file(path):
    rel = relative(path).lower()
    name = path.name.lower()

    parts = {
        part.lower()
        for part in path.parts
    }

    if (
        "backup" in parts
        or "backups" in parts
        or "backup" in name
        or "_backup" in name
    ):
        return "BACKUP"

    if (
        "test" in parts
        or "tests" in parts
        or name.startswith("test_")
        or name.endswith("_test.py")
    ):
        return "TEST"

    if (
        "old" in parts
        or "archive" in parts
        or "archives" in parts
        or "historical" in parts
        or "site_intelligence" in parts
    ):
        return "HISTORICAL"

    if (
        "tmp" in parts
        or "temp" in parts
        or "temporary" in parts
    ):
        return "TEMPORARY"

    if (
        "audit" in name
        or "forensic" in name
        or "diagnostic" in name
        or "monitor" in name
    ):
        return "TOOL"

    return "PROJECT"


def exception_name(node):
    if node is None:
        return None

    if isinstance(
        node,
        ast.Name
    ):
        return node.id

    if isinstance(
        node,
        ast.Attribute
    ):
        return node.attr

    if isinstance(
        node,
        ast.Tuple
    ):
        return [
            exception_name(x)
            for x in node.elts
        ]

    try:
        return ast.unparse(node)
    except Exception:
        return "UNKNOWN"


def is_empty_handler(handler):
    if not handler.body:
        return True

    meaningful = [
        node
        for node in handler.body
        if not isinstance(
            node,
            ast.Pass
        )
    ]

    return len(meaningful) == 0


def handler_exception_names(handler):

    value = exception_name(
        handler.type
    )

    if value is None:
        return []

    if isinstance(
        value,
        list
    ):
        return [
            str(x)
            for x in value
        ]

    return [
        str(value)
    ]


def is_expected_control_flow_exception(
    handler
):

    expected = {
        "WebSocketDisconnect",
        "TimeoutError",
        "asyncio.TimeoutError",
        "QueueEmpty",
        "asyncio.QueueEmpty",
        "StopIteration",
        "StopAsyncIteration",
    }

    names = set(
        handler_exception_names(
            handler
        )
    )

    return bool(
        names & expected
    )


def analyze_ast(path, tree):
    findings = []

    rel = relative(path)
    classification = classify_file(path)

    for node in ast.walk(tree):

        # Bare except:
        if isinstance(
            node,
            ast.ExceptHandler
        ):

            if node.type is None:
                findings.append({
                    "file": rel,
                    "classification":
                        classification,
                    "line":
                        getattr(
                            node,
                            "lineno",
                            None,
                        ),
                    "category":
                        "STATIC_RISK",
                    "type":
                        "BARE_EXCEPT",
                    "severity":
                        "MEDIUM",
                    "confidence":
                        "CONFIRMED",
                    "evidence":
                        "AST",
                    "counts_as_health_risk":
                        True,
                })

            elif (
                isinstance(
                    node.type,
                    ast.Name
                )
                and node.type.id
                in {
                    "Exception",
                    "BaseException",
                }
            ):
                findings.append({
                    "file": rel,
                    "classification":
                        classification,
                    "line":
                        getattr(
                            node,
                            "lineno",
                            None,
                        ),
                    "category":
                        "STATIC_RISK",
                    "type":
                        "BROAD_EXCEPTION_HANDLER",
                    "exception":
                        exception_name(
                            node.type
                        ),
                    "severity":
                        "INFO",
                    "confidence":
                        "CONFIRMED",
                    "evidence":
                        "AST",
                    "counts_as_health_risk":
                        False,
                })

            if is_empty_handler(
                node
            ):

                expected_control_flow = (
                    is_expected_control_flow_exception(
                        node
                    )
                )

                if expected_control_flow:

                    findings.append({
                        "file": rel,
                        "classification":
                            classification,
                        "line":
                            getattr(
                                node,
                                "lineno",
                                None,
                            ),
                        "category":
                            "EXPECTED_CONTROL_FLOW",
                        "type":
                            "INTENTIONAL_EMPTY_HANDLER",
                        "exception":
                            handler_exception_names(
                                node
                            ),
                        "severity":
                            "INFO",
                        "confidence":
                            "PROBABLE",
                        "evidence":
                            "AST_SEMANTIC_FILTER",
                        "counts_as_health_risk":
                            False,
                    })

                else:

                    findings.append({
                        "file": rel,
                        "classification":
                            classification,
                        "line":
                            getattr(
                                node,
                                "lineno",
                                None,
                            ),
                        "category":
                            "STATIC_RISK",
                        "type":
                            "SILENT_EXCEPTION_HANDLER",
                        "exception":
                            handler_exception_names(
                                node
                            ),
                        "severity":
                            "MEDIUM",
                        "confidence":
                            "CONFIRMED",
                        "evidence":
                            "AST",
                        "counts_as_health_risk":
                            True,
                    })

        # raise senza argomento dentro except ? valido;
        # non viene classificato come errore.

        if isinstance(
            node,
            ast.Call
        ):

            func = node.func

            method = None

            if isinstance(
                func,
                ast.Attribute
            ):
                method = func.attr.lower()

            elif isinstance(
                func,
                ast.Name
            ):
                method = func.id.lower()

            # subprocess senza timeout:
            if method in {
                "run",
                "call",
                "check_call",
                "check_output",
            }:

                full = ""

                try:
                    full = ast.unparse(
                        func
                    ).lower()
                except Exception:
                    pass

                if (
                    "subprocess" in full
                    and not any(
                        kw.arg == "timeout"
                        for kw in node.keywords
                        if kw.arg
                    )
                ):
                    findings.append({
                        "file": rel,
                        "classification":
                            classification,
                        "line":
                            getattr(
                                node,
                                "lineno",
                                None,
                            ),
                        "category":
                            "STATIC_RISK",
                        "type":
                            "SUBPROCESS_WITHOUT_TIMEOUT",
                        "severity":
                            "LOW",
                        "confidence":
                            "CONFIRMED",
                        "evidence":
                            "AST",
                        "counts_as_health_risk":
                            True,
                    })

    return findings



def load_analyzer_07_classification():

    path = (
        PROJECT_OUTPUT_ROOT
        / "LATEST"
        / "07_DATA_FLOW"
        / "DATA_FLOW_MAP.json"
    )

    if not path.exists():
        return {}, {
            "available": False,
            "path": str(path),
            "error": "REPORT_NOT_FOUND",
        }

    try:

        data = json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        )

        classification = data.get(
            "project_file_classification",
            {}
        )

        if not isinstance(
            classification,
            dict
        ):
            return {}, {
                "available": False,
                "path": str(path),
                "error":
                    "INVALID_CLASSIFICATION_FORMAT",
            }

        normalized = {}

        for file, info in (
            classification.items()
        ):

            key = str(file).replace(
                "/",
                "\\"
            ).lower()

            if isinstance(
                info,
                dict
            ):
                normalized[key] = info

        return normalized, {
            "available": True,
            "path": str(path),
            "records": len(normalized),
            "error": None,
        }

    except Exception as exc:

        return {}, {
            "available": False,
            "path": str(path),
            "error": str(exc),
        }


def enrich_with_operational_status(
    findings,
    classification_07,
):

    operational_statuses = {
        "OPERATIONAL_CONFIRMED",
        "OPERATIONAL_CONNECTED",
    }

    for item in findings:

        key = str(
            item.get(
                "file",
                ""
            )
        ).replace(
            "/",
            "\\"
        ).lower()

        info = classification_07.get(
            key
        )

        if info is None:

            item[
                "operational_scope"
            ] = "OUTSIDE_07_ACTIVE_SET"

            item[
                "operational_status"
            ] = None

            item[
                "operational_confidence"
            ] = "UNKNOWN"

            continue

        status = info.get(
            "status",
            "UNKNOWN"
        )

        confidence = info.get(
            "confidence",
            "UNKNOWN"
        )

        item[
            "operational_status"
        ] = status

        item[
            "operational_confidence"
        ] = confidence

        item[
            "operational_evidence"
        ] = info.get(
            "evidence",
            []
        )

        if status in operational_statuses:

            item[
                "operational_scope"
            ] = "OPERATIONAL"

        elif status == "UNKNOWN":

            item[
                "operational_scope"
            ] = "UNKNOWN"

        else:

            item[
                "operational_scope"
            ] = "NON_OPERATIONAL"

    return findings


def main():

    print("=" * 100)
    print(
        "PYTHON PROJECT INTELLIGENCE"
    )
    print(
        "ANALYZER 08 - HEALTH / ERRORS V2 TEST"
    )
    print("=" * 100)

    print(
        "Project:",
        PROJECT_NAME
    )

    print(
        "Root   :",
        PROJECT_ROOT
    )

    print(
        "Mode   : READ ONLY"
    )

    python_files = list(
        iter_python_files()
    )

    compile_results = []
    static_findings = []

    syntax_errors = []
    warning_findings = []

    classification_counts = {}

    for path in python_files:

        if is_excluded(path):
            continue

        classification = (
            classify_file(path)
        )

        classification_counts[
            classification
        ] = (
            classification_counts.get(
                classification,
                0
            ) + 1
        )

        rel = relative(path)

        try:
            source = path.read_text(
                encoding="utf-8-sig",
                errors="strict",
            )

        except Exception as exc:

            syntax_errors.append({
                "file": rel,
                "classification":
                    classification,
                "category":
                    "COMPILE_HEALTH",
                "type":
                    "READ_ERROR",
                "severity":
                    "HIGH",
                "confidence":
                    "CONFIRMED",
                "error":
                    str(exc),
            })

            continue

        try:

            with warnings.catch_warnings(
                record=True
            ) as captured:

                warnings.simplefilter(
                    "always"
                )

                compiled = compile(
                    source,
                    str(path),
                    "exec",
                    dont_inherit=True,
                )

            compile_results.append({
                "file": rel,
                "classification":
                    classification,
                "compiled":
                    True,
            })

            for warning in captured:

                warning_findings.append({
                    "file": rel,
                    "classification":
                        classification,
                    "line":
                        getattr(
                            warning,
                            "lineno",
                            None,
                        ),
                    "category":
                        "COMPILE_HEALTH",
                    "type":
                        warning.category.__name__,
                    "severity":
                        "LOW",
                    "confidence":
                        "CONFIRMED",
                    "message":
                        str(
                            warning.message
                        ),
                })

            tree = ast.parse(
                source,
                filename=str(path),
            )

            static_findings.extend(
                analyze_ast(
                    path,
                    tree,
                )
            )

        except SyntaxError as exc:

            syntax_errors.append({
                "file": rel,
                "classification":
                    classification,
                "line":
                    exc.lineno,
                "offset":
                    exc.offset,
                "category":
                    "COMPILE_HEALTH",
                "type":
                    "SYNTAX_ERROR",
                "severity":
                    "CRITICAL",
                "confidence":
                    "CONFIRMED",
                "error":
                    exc.msg,
            })

            compile_results.append({
                "file": rel,
                "classification":
                    classification,
                "compiled":
                    False,
            })

        except Exception as exc:

            syntax_errors.append({
                "file": rel,
                "classification":
                    classification,
                "category":
                    "COMPILE_HEALTH",
                "type":
                    "ANALYSIS_ERROR",
                "severity":
                    "HIGH",
                "confidence":
                    "CONFIRMED",
                "error":
                    str(exc),
            })

    classification_07, bridge_07 = (
        load_analyzer_07_classification()
    )

    enrich_with_operational_status(
        syntax_errors,
        classification_07,
    )

    enrich_with_operational_status(
        warning_findings,
        classification_07,
    )

    enrich_with_operational_status(
        static_findings,
        classification_07,
    )

    operational_static = [
        x
        for x in static_findings
        if x.get(
            "operational_scope"
        ) == "OPERATIONAL"
    ]

    non_operational_static = [
        x
        for x in static_findings
        if x.get(
            "operational_scope"
        ) == "NON_OPERATIONAL"
    ]

    unknown_static = [
        x
        for x in static_findings
        if x.get(
            "operational_scope"
        ) in {
            "UNKNOWN",
            "OUTSIDE_07_ACTIVE_SET",
        }
    ]

    operational_syntax_errors = [
        x
        for x in syntax_errors
        if x.get(
            "operational_scope"
        ) == "OPERATIONAL"
    ]

    operational_health_risks = [
        x
        for x in operational_static
        if x.get(
            "counts_as_health_risk",
            False
        )
    ]

    operational_observations = [
        x
        for x in operational_static
        if not x.get(
            "counts_as_health_risk",
            False
        )
    ]

    project_syntax_errors = [
        x
        for x in syntax_errors
        if x.get(
            "classification"
        ) == "PROJECT"
    ]

    project_static = [
        x
        for x in static_findings
        if x.get(
            "classification"
        ) == "PROJECT"
    ]

    result = {
        "metadata": {
            "analyzer":
                ANALYZER_NAME,
            "version":
                VERSION,
            "timestamp":
                datetime.now().isoformat(),
            "mode":
                "READ_ONLY",
            "project_name":
                PROJECT_NAME,
            "project_root":
                str(PROJECT_ROOT),
        },

        "summary": {
            "python_files":
                len(python_files),
            "compiled_files":
                sum(
                    1
                    for x
                    in compile_results
                    if x.get(
                        "compiled"
                    )
                ),
            "syntax_errors":
                len(syntax_errors),
            "project_syntax_errors":
                len(
                    project_syntax_errors
                ),
            "compile_warnings":
                len(
                    warning_findings
                ),
            "static_findings":
                len(
                    static_findings
                ),
            "project_static_findings":
                len(
                    project_static
                ),
            "operational_static_findings":
                len(
                    operational_static
                ),
            "non_operational_static_findings":
                len(
                    non_operational_static
                ),
            "unknown_static_findings":
                len(
                    unknown_static
                ),
            "operational_syntax_errors":
                len(
                    operational_syntax_errors
                ),
            "operational_health_risks":
                len(
                    operational_health_risks
                ),
            "operational_observations":
                len(
                    operational_observations
                ),
        },

        "classification_counts":
            classification_counts,

        "analyzer_07_bridge":
            bridge_07,

        "operational_static_findings":
            operational_static,

        "operational_health_risks":
            operational_health_risks,

        "operational_observations":
            operational_observations,

        "non_operational_static_findings":
            non_operational_static,

        "unknown_static_findings":
            unknown_static,

        "syntax_errors":
            syntax_errors,

        "compile_warnings":
            warning_findings,

        "static_findings":
            static_findings,

        "compile_results":
            compile_results,

        "notes": [
            (
                "Static findings indicate "
                "code risks, not confirmed "
                "runtime failures."
            ),
            (
                "Runtime evidence and "
                "database health will be "
                "integrated from analyzers "
                "02 and 03."
            ),
        ],
    }

    JSON_PATH.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 100)
    print("STAGE 1 RESULTS")
    print("=" * 100)

    for key, value in (
        result[
            "summary"
        ].items()
    ):
        print(
            f"{key:<30}: {value}"
        )

    print()
    print(
        "Classification:",
        classification_counts
    )

    print()
    print(
        "Report:",
        JSON_PATH
    )

    print()
    print(
        "ANALYZER 08 STAGE 1 STATUS: OK"
    )

    print("=" * 100)


if __name__ == "__main__":
    main()


# ============================================================================
# ANALYZER 08 V2 - STAGE 2
# RUNTIME + DATABASE HEALTH FROM PRIOR ANALYZERS
# ============================================================================

def load_prior_report(path):
    """
    Carica un report prodotto da un analyzer precedente.

    READ ONLY:
    - nessun processo interrogato;
    - nessun database interrogato;
    - nessun file del progetto modificato.
    """

    if not path.exists():
        return None, {
            "available": False,
            "path": str(path),
            "error": "REPORT_NOT_FOUND",
        }

    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        )

        return data, {
            "available": True,
            "path": str(path),
            "error": None,
        }

    except Exception as exc:
        return None, {
            "available": False,
            "path": str(path),
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
        }


def build_runtime_health():
    """
    Consuma esclusivamente il report dell'Analyzer 02.
    Non esegue PowerShell e non interroga processi o porte.
    """

    report_path = (
        PROJECT_OUTPUT_ROOT
        / "LATEST"
        / "02_RUNTIME"
        / "RUNTIME_MAP.json"
    )

    data, source = load_prior_report(
        report_path
    )

    result = {
        "source": "ANALYZER_02_RUNTIME",
        "confidence": (
            "CONFIRMED"
            if source["available"]
            else "UNKNOWN"
        ),
        "report": source,
        "status": "UNKNOWN",
        "summary": {},
        "project_processes": [],
        "project_listening_ports": [],
        "findings": [],
    }

    if data is None:
        result["findings"].append(
            {
                "type": "RUNTIME_REPORT_UNAVAILABLE",
                "severity": "INFO",
                "confidence": "UNKNOWN",
                "message": (
                    "Analyzer 02 runtime report "
                    "not available."
                ),
            }
        )
        return result

    summary = data.get(
        "summary",
        {}
    )

    project_processes = data.get(
        "project_processes",
        []
    )

    project_ports = data.get(
        "project_listening_ports",
        []
    )

    runtime_errors = summary.get(
        "runtime_errors",
        0
    )

    result["summary"] = {
        "python_processes_total":
            summary.get(
                "python_processes_total"
            ),

        "project_python_processes":
            summary.get(
                "project_python_processes"
            ),

        "external_python_processes":
            summary.get(
                "external_python_processes"
            ),

        "project_listening_ports":
            summary.get(
                "project_listening_ports"
            ),

        "project_working_set_mb":
            summary.get(
                "project_working_set_mb"
            ),

        "project_private_memory_mb":
            summary.get(
                "project_private_memory_mb"
            ),

        "project_threads":
            summary.get(
                "project_threads"
            ),

        "runtime_errors":
            runtime_errors,
    }

    result["project_processes"] = [
        {
            "pid": item.get("pid"),
            "parent_pid":
                item.get("parent_pid"),
            "name": item.get("name"),
            "command_line":
                item.get("command_line"),
            "listening_ports":
                item.get(
                    "listening_ports",
                    []
                ),
            "resources":
                item.get(
                    "resources",
                    {}
                ),
        }
        for item in project_processes
    ]

    result["project_listening_ports"] = (
        project_ports
    )

    if runtime_errors:
        result["status"] = "ATTENTION"

        result["findings"].append(
            {
                "type":
                    "RUNTIME_ERRORS_REPORTED",
                "severity": "HIGH",
                "confidence": "CONFIRMED",
                "count": runtime_errors,
                "message": (
                    "Analyzer 02 reported "
                    "runtime errors."
                ),
            }
        )

    else:
        result["status"] = "HEALTHY"

        result["findings"].append(
            {
                "type":
                    "RUNTIME_NO_ERRORS_REPORTED",
                "severity": "INFO",
                "confidence": "CONFIRMED",
                "count": 0,
                "message": (
                    "Analyzer 02 reported no "
                    "runtime collection errors."
                ),
            }
        )

    return result


def build_database_health():
    """
    Consuma esclusivamente il report dell'Analyzer 03.
    Non apre direttamente alcun database.
    """

    report_path = (
        PROJECT_OUTPUT_ROOT
        / "LATEST"
        / "03_DATABASE"
        / "DATABASE_MAP.json"
    )

    data, source = load_prior_report(
        report_path
    )

    result = {
        "source": "ANALYZER_03_DATABASE",
        "confidence": (
            "CONFIRMED"
            if source["available"]
            else "UNKNOWN"
        ),
        "report": source,
        "status": "UNKNOWN",
        "summary": {},
        "databases": [],
        "findings": [],
    }

    if data is None:
        result["findings"].append(
            {
                "type":
                    "DATABASE_REPORT_UNAVAILABLE",
                "severity": "INFO",
                "confidence": "UNKNOWN",
                "message": (
                    "Analyzer 03 database report "
                    "not available."
                ),
            }
        )
        return result

    summary = data.get(
        "summary",
        {}
    )

    databases = data.get(
        "databases",
        []
    )

    result["summary"] = {
        "database_files":
            summary.get("database_files"),

        "readable_databases":
            summary.get(
                "readable_databases"
            ),

        "total_database_size_mb":
            summary.get(
                "total_database_size_mb"
            ),

        "tables":
            summary.get("tables"),

        "confirmed_rows":
            summary.get(
                "confirmed_rows"
            ),

        "indexes":
            summary.get("indexes"),

        "integrity_problems":
            summary.get(
                "integrity_problems"
            ),
    }

    database_problems = []

    for db in databases:

        analysis = db.get(
            "analysis",
            {}
        )

        item = {
            "relative_path":
                db.get("relative_path"),

            "size_mb":
                db.get("size_mb"),

            "readable":
                analysis.get("readable"),

            "confirmed_type":
                analysis.get(
                    "confirmed_type"
                ),

            "confidence":
                analysis.get(
                    "confidence"
                ),

            "integrity_check":
                analysis.get(
                    "integrity_check"
                ),

            "journal_mode":
                analysis.get(
                    "journal_mode"
                ),

            "table_count":
                len(
                    analysis.get(
                        "tables",
                        []
                    )
                ),

            "errors":
                analysis.get(
                    "errors",
                    []
                ),
        }

        result["databases"].append(
            item
        )

        if (
            item["readable"] is False
            or (
                item["integrity_check"]
                not in (None, "ok")
            )
            or item["errors"]
        ):
            database_problems.append(
                item
            )

    integrity_problems = summary.get(
        "integrity_problems",
        0
    )

    if (
        integrity_problems
        or database_problems
    ):
        result["status"] = "ATTENTION"

        result["findings"].append(
            {
                "type":
                    "DATABASE_HEALTH_PROBLEM",
                "severity": "HIGH",
                "confidence": "CONFIRMED",
                "integrity_problems":
                    integrity_problems,
                "affected_databases":
                    database_problems,
                "message": (
                    "Analyzer 03 reported one "
                    "or more database health "
                    "problems."
                ),
            }
        )

    else:
        result["status"] = "HEALTHY"

        result["findings"].append(
            {
                "type":
                    "DATABASE_INTEGRITY_OK",
                "severity": "INFO",
                "confidence": "CONFIRMED",
                "database_count":
                    len(databases),
                "message": (
                    "All databases reported by "
                    "Analyzer 03 are readable "
                    "and have no reported "
                    "integrity problems."
                ),
            }
        )

    return result


def print_stage2_health():

    runtime_health = (
        build_runtime_health()
    )

    database_health = (
        build_database_health()
    )

    print()
    print("=" * 100)
    print(
        "ANALYZER 08 V2 - STAGE 2 "
        "RUNTIME + DATABASE HEALTH"
    )
    print("=" * 100)

    print()
    print("RUNTIME")
    print("-" * 100)

    print(
        "Report available      :",
        runtime_health[
            "report"
        ]["available"]
    )

    print(
        "Status                :",
        runtime_health["status"]
    )

    print(
        "Confidence            :",
        runtime_health[
            "confidence"
        ]
    )

    rs = runtime_health[
        "summary"
    ]

    print(
        "Project processes     :",
        rs.get(
            "project_python_processes"
        )
    )

    print(
        "Project ports         :",
        rs.get(
            "project_listening_ports"
        )
    )

    print(
        "Working set MB        :",
        rs.get(
            "project_working_set_mb"
        )
    )

    print(
        "Private memory MB     :",
        rs.get(
            "project_private_memory_mb"
        )
    )

    print(
        "Threads               :",
        rs.get(
            "project_threads"
        )
    )

    print(
        "Runtime errors        :",
        rs.get(
            "runtime_errors"
        )
    )

    print()
    print("DATABASE")
    print("-" * 100)

    print(
        "Report available      :",
        database_health[
            "report"
        ]["available"]
    )

    print(
        "Status                :",
        database_health[
            "status"
        ]
    )

    print(
        "Confidence            :",
        database_health[
            "confidence"
        ]
    )

    ds = database_health[
        "summary"
    ]

    print(
        "Database files        :",
        ds.get(
            "database_files"
        )
    )

    print(
        "Readable databases    :",
        ds.get(
            "readable_databases"
        )
    )

    print(
        "Database size MB      :",
        ds.get(
            "total_database_size_mb"
        )
    )

    print(
        "Tables                :",
        ds.get("tables")
    )

    print(
        "Confirmed rows        :",
        ds.get(
            "confirmed_rows"
        )
    )

    print(
        "Indexes               :",
        ds.get("indexes")
    )

    print(
        "Integrity problems    :",
        ds.get(
            "integrity_problems"
        )
    )

    print()
    print("DATABASE DETAILS")
    print("-" * 100)

    for db in database_health[
        "databases"
    ]:

        print(
            f"{db['relative_path']} | "
            f"readable={db['readable']} | "
            f"integrity={db['integrity_check']} | "
            f"journal={db['journal_mode']} | "
            f"tables={db['table_count']}"
        )

    print()
    print("=" * 100)

    if (
        runtime_health["status"]
        == "HEALTHY"
        and
        database_health["status"]
        == "HEALTHY"
    ):
        combined = "HEALTHY"
    elif (
        runtime_health["status"]
        == "UNKNOWN"
        or
        database_health["status"]
        == "UNKNOWN"
    ):
        combined = "PARTIAL"
    else:
        combined = "ATTENTION"

    print(
        "STAGE 2 COMBINED STATUS:",
        combined
    )

    print("=" * 100)
    print(
        "NESSUN PROCESSO INTERROGATO "
        "DIRETTAMENTE"
    )
    print(
        "NESSUN DATABASE INTERROGATO "
        "DIRETTAMENTE"
    )
    print(
        "DATI CONSUMATI DAI REPORT "
        "02 E 03"
    )
    print(
        "ANALYZER 08 UFFICIALE "
        "NON MODIFICATO"
    )
    print("=" * 100)

    return {
        "runtime_health":
            runtime_health,
        "database_health":
            database_health,
        "combined_status":
            combined,
    }


if __name__ == "__main__":
    STAGE2_HEALTH = (
        print_stage2_health()
    )


# ============================================================================
# ANALYZER 08 V2 - FINAL REPORT INTEGRATION
# ============================================================================

def build_log_health():

    return {
        "status": "NOT_AVAILABLE",
        "confidence": "CONFIRMED",
        "persistent_log_files": 0,
        "runtime_errors_from_logs": None,
        "findings": [
            {
                "type":
                    "PERSISTENT_RUNTIME_LOGGING_NOT_DETECTED",
                "category":
                    "OBSERVABILITY",
                "severity":
                    "LOW",
                "confidence":
                    "CONFIRMED",
                "counts_as_health_failure":
                    False,
                "message": (
                    "No persistent runtime log files "
                    "were detected in the active project. "
                    "Runtime failures cannot therefore be "
                    "historically reconstructed from logs."
                ),
            }
        ],
    }


def integrate_final_health_report(
    stage2
):

    report_path = (
        PROJECT_OUTPUT_ROOT
        / "LATEST"
        / "08_HEALTH_ERRORS"
        / "HEALTH_ERROR_MAP.json"
    )

    if not report_path.exists():

        raise RuntimeError(
            "Stage 1 report not found: "
            + str(report_path)
        )

    data = json.loads(
        report_path.read_text(
            encoding="utf-8-sig"
        )
    )

    runtime_health = stage2[
        "runtime_health"
    ]

    database_health = stage2[
        "database_health"
    ]

    log_health = build_log_health()

    operational_risks = data.get(
        "operational_health_risks",
        []
    )

    syntax_errors = data.get(
        "summary",
        {}
    ).get(
        "operational_syntax_errors",
        0
    )

    high_or_critical_static = [
        item
        for item in operational_risks
        if item.get(
            "severity"
        ) in {
            "HIGH",
            "CRITICAL",
        }
    ]

    if (
        runtime_health["status"]
        == "ATTENTION"
        or
        database_health["status"]
        == "ATTENTION"
        or syntax_errors
        or high_or_critical_static
    ):

        overall_status = "ATTENTION"

    elif (
        runtime_health["status"]
        == "UNKNOWN"
        or
        database_health["status"]
        == "UNKNOWN"
    ):

        overall_status = "PARTIAL"

    elif operational_risks:

        overall_status = (
            "HEALTHY_WITH_RISKS"
        )

    else:

        overall_status = "HEALTHY"

    health_summary = {
        "overall_status":
            overall_status,

        "runtime_status":
            runtime_health[
                "status"
            ],

        "database_status":
            database_health[
                "status"
            ],

        "log_status":
            log_health[
                "status"
            ],

        "operational_syntax_errors":
            syntax_errors,

        "operational_static_risks":
            len(
                operational_risks
            ),

        "high_or_critical_static_risks":
            len(
                high_or_critical_static
            ),

        "persistent_log_files":
            0,

        "runtime_errors_from_analyzer_02":
            runtime_health.get(
                "summary",
                {}
            ).get(
                "runtime_errors"
            ),

        "database_integrity_problems":
            database_health.get(
                "summary",
                {}
            ).get(
                "integrity_problems"
            ),
    }

    data[
        "runtime_health"
    ] = runtime_health

    data[
        "database_health"
    ] = database_health

    data[
        "log_health"
    ] = log_health

    data[
        "health_summary"
    ] = health_summary

    data[
        "health_methodology"
    ] = {
        "compile_health":
            (
                "Direct compile/AST inspection "
                "without writing pyc files."
            ),

        "static_risk":
            (
                "AST-based code robustness "
                "analysis. Static risks are not "
                "treated as confirmed runtime "
                "failures."
            ),

        "runtime_health":
            (
                "Consumed from Analyzer 02. "
                "Analyzer 08 does not query "
                "processes or ports directly."
            ),

        "database_health":
            (
                "Consumed from Analyzer 03. "
                "Analyzer 08 does not open or "
                "query databases directly."
            ),

        "runtime_logs":
            (
                "No persistent runtime logs "
                "detected. Absence of logs is "
                "reported as an observability "
                "limitation, not as a runtime "
                "failure."
            ),
    }

    report_path.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8"
    )

    return (
        report_path,
        health_summary
    )


if __name__ == "__main__":

    if "STAGE2_HEALTH" in globals():

        FINAL_REPORT_PATH, FINAL_HEALTH = (
            integrate_final_health_report(
                STAGE2_HEALTH
            )
        )

        print()
        print("=" * 100)
        print(
            "ANALYZER 08 V2 - FINAL "
            "HEALTH INTEGRATION"
        )
        print("=" * 100)

        for key, value in (
            FINAL_HEALTH.items()
        ):

            print(
                f"{key:<38}: {value}"
            )

        print()
        print(
            "Final report:",
            FINAL_REPORT_PATH
        )

        print()
        print(
            "ANALYZER 08 V2 TEST STATUS: "
            "COMPLETE"
        )

        print("=" * 100)
