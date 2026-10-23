from pathlib import Path
import ast
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

# ==================================================================================================
# PYTHON PROJECT INTELLIGENCE
# ANALYZER 07 - DATA FLOW
# VERSION 2.0 TEST
#
# READ ONLY rispetto al progetto analizzato.
# Scrive esclusivamente nella directory output di Python Project Intelligence.
# ==================================================================================================

ANALYZER_VERSION = "2.1-status-test"

THIS_FILE = Path(__file__).resolve()
ANALYZERS_DIR = THIS_FILE.parent
INTELLIGENCE_ROOT = ANALYZERS_DIR.parent
CORE_DIR = INTELLIGENCE_ROOT / "core"

if str(INTELLIGENCE_ROOT) not in sys.path:
    sys.path.insert(0, str(INTELLIGENCE_ROOT))

from core.project_context import (
    PROJECT_ROOT,
    PROJECT_NAME,
    PROJECT_OUTPUT_ROOT,
    iter_python_files,
)

OUTPUT_DIR = (
    PROJECT_OUTPUT_ROOT
    / "LATEST"
    / "07_DATA_FLOW"
)

OUTPUT_FILE = OUTPUT_DIR / "DATA_FLOW_MAP.json"


# ==================================================================================================
# HISTORICAL / BACKUP CLASSIFICATION
# ==================================================================================================

HISTORICAL_DIRS = {
    "backup",
    "backups",
    "archive",
    "archives",
    "old",
    "legacy",
    "deprecated",
    "history",
    "historical",
    "site_intelligence",
}

HISTORICAL_FILE_TOKENS = (
    "_backup",
    ".backup",
    "_old",
    ".old",
    "_legacy",
    "_deprecated",
    "_previous",
    "_prev",
    "_before_",
    "_before-",
    "-before-",
    "_archive",
    "_archived",
)


def relative(path: Path) -> str:
    try:
        return str(
            path.resolve().relative_to(
                PROJECT_ROOT.resolve()
            )
        )
    except Exception:
        return str(path)


def is_probably_historical(path: Path) -> bool:

    try:
        rel = path.resolve().relative_to(
            PROJECT_ROOT.resolve()
        )
    except Exception:
        rel = path

    parts = [
        part.lower()
        for part in rel.parts
    ]

    if any(
        part in HISTORICAL_DIRS
        for part in parts[:-1]
    ):
        return True

    stem = path.stem.lower()

    return any(
        token in stem
        for token in HISTORICAL_FILE_TOKENS
    )


# ==================================================================================================
# SOURCE READING
# ==================================================================================================

def read_source(path: Path):

    try:
        return path.read_text(
            encoding="utf-8-sig",
            errors="strict",
        ), None

    except UnicodeDecodeError:

        try:
            return path.read_text(
                encoding="utf-8",
                errors="replace",
            ), "DECODE_REPLACED"

        except Exception as exc:
            return None, str(exc)

    except Exception as exc:
        return None, str(exc)


# ==================================================================================================
# AST HELPERS
# ==================================================================================================

def dotted_name(node):

    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):

        parent = dotted_name(node.value)

        if parent:
            return f"{parent}.{node.attr}"

        return node.attr

    return None


def literal_string(node):

    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return node.value

    if isinstance(node, ast.JoinedStr):
        return "<dynamic-fstring>"

    return None


def call_name(node):

    if isinstance(node, ast.Call):
        return dotted_name(node.func)

    return None


def call_line(node):
    return getattr(node, "lineno", None)


# ==================================================================================================
# CLASSIFICATION HELPERS
# ==================================================================================================

NETWORK_LIBRARY_PREFIXES = (
    "requests.",
    "httpx.",
    "aiohttp.",
    "urllib.",
    "websocket.",
    "websockets.",
    "ccxt.",
    "ccxtpro.",
)

NETWORK_EXACT_CALLS = {
    "urlopen",
}

NETWORK_EXCHANGE_METHODS = {
    "fetch_ohlcv",
    "fetch_ticker",
    "fetch_tickers",
    "fetch_trades",
    "fetch_order_book",
    "fetch_order_books",
    "fetch_markets",
    "fetch_currencies",
    "fetch_status",
    "fetch_time",
    "fetch_balance",
    "fetch_bids_asks",
}

NETWORK_EXCHANGE_PREFIXES = (
    "watch_",
)

NETWORK_DB_EXCLUSIONS = {
    "fetchone",
    "fetchall",
    "fetchmany",
}

DB_CONNECT_HINTS = (
    "sqlite3.connect",
    "duckdb.connect",
    "psycopg",
    "psycopg2",
    "sqlalchemy",
    "pymysql",
    "mysql.connector",
    "motor.",
    "pymongo.",
    "redis.",
)

FILE_READ_METHODS = {
    "read_text",
    "read_bytes",
    "open",
    "read_csv",
    "read_json",
    "read_parquet",
    "read_pickle",
}

FILE_WRITE_METHODS = {
    "write_text",
    "write_bytes",
    "to_csv",
    "to_json",
    "to_parquet",
    "to_pickle",
}

DB_EXTENSIONS = (
    ".db",
    ".sqlite",
    ".sqlite3",
    ".duckdb",
)

DATA_EXTENSIONS = (
    ".csv",
    ".json",
    ".jsonl",
    ".ndjson",
    ".parquet",
    ".pkl",
    ".pickle",
    ".txt",
    ".log",
)


def confidence(
    confirmed=False,
    probable=False,
):

    if confirmed:
        return "CONFIRMED"

    if probable:
        return "PROBABLE"

    return "POSSIBLE"


# ==================================================================================================
# SQL EXTRACTION
# ==================================================================================================

SQL_PATTERN = re.compile(
    r"\b("
    r"SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|"
    r"CREATE\s+TABLE|DROP\s+TABLE|ALTER\s+TABLE|"
    r"REPLACE\s+INTO"
    r")\b",
    re.IGNORECASE,
)

TABLE_PATTERNS = {
    "SELECT": re.compile(
        r"\bFROM\s+([A-Za-z_][A-Za-z0-9_]*)",
        re.IGNORECASE,
    ),
    "INSERT": re.compile(
        r"\bINSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)",
        re.IGNORECASE,
    ),
    "UPDATE": re.compile(
        r"\bUPDATE\s+([A-Za-z_][A-Za-z0-9_]*)",
        re.IGNORECASE,
    ),
    "DELETE": re.compile(
        r"\bDELETE\s+FROM\s+([A-Za-z_][A-Za-z0-9_]*)",
        re.IGNORECASE,
    ),
}



def is_standalone_sql_literal(text):
    """
    Validazione conservativa per stringhe Python analizzate
    come SQL_LITERAL indipendenti.

    Evita falsi positivi come:
        "UPDATE COMPLETATO"
        "Update ID: ..."

    Non viene usata per decidere se una chiamata execute()
    esiste: execute/executemany hanno evidenza propria.
    """

    if not isinstance(text, str):
        return False

    value = text.strip()

    if not value:
        return False

    upper = value.upper()

    structural_patterns = (
        r"^SELECT\s+.+\s+FROM\s+",
        r"^WITH\s+.+",
        r"^INSERT\s+(?:OR\s+\w+\s+)?INTO\s+",
        r"^UPDATE\s+[A-Za-z_][A-Za-z0-9_]*\s+SET\s+",
        r"^DELETE\s+FROM\s+",
        r"^CREATE\s+(?:TEMP(?:ORARY)?\s+)?TABLE\s+",
        r"^DROP\s+TABLE\s+",
        r"^ALTER\s+TABLE\s+",
        r"^REPLACE\s+INTO\s+",
        r"^PRAGMA(?:\s+|\()",
    )

    return any(
        re.search(
            pattern,
            value,
            re.IGNORECASE | re.DOTALL,
        )
        for pattern in structural_patterns
    )

def extract_sql_operation(text):

    if not isinstance(text, str):
        return None

    match = SQL_PATTERN.search(text)

    if not match:
        return None

    raw = match.group(1).upper()

    if raw.startswith("INSERT"):
        operation = "INSERT"

    elif raw.startswith("DELETE"):
        operation = "DELETE"

    elif raw.startswith("CREATE"):
        operation = "CREATE_TABLE"

    elif raw.startswith("DROP"):
        operation = "DROP_TABLE"

    elif raw.startswith("ALTER"):
        operation = "ALTER_TABLE"

    elif raw.startswith("REPLACE"):
        operation = "REPLACE"

    else:
        operation = raw

    table = None

    pattern = TABLE_PATTERNS.get(operation)

    if pattern:

        table_match = pattern.search(text)

        if table_match:
            table = table_match.group(1)

    direction = (
        "READ"
        if operation == "SELECT"
        else "WRITE"
    )

    return {
        "operation": operation,
        "direction": direction,
        "table": table,
    }


# ==================================================================================================
# PER-FILE ANALYSIS
# ==================================================================================================


def classify_network_call(name):

    if not name:
        return None

    lower = name.lower()

    method = (
        lower
        .split(".")[-1]
    )

    # --------------------------------------------------------
    # Esclusioni certe:
    # metodi tipici dei cursori/database.
    # --------------------------------------------------------

    if method in NETWORK_DB_EXCLUSIONS:
        return None

    # --------------------------------------------------------
    # Librerie/network client espliciti.
    # --------------------------------------------------------

    if lower.startswith(
        NETWORK_LIBRARY_PREFIXES
    ):
        return {
            "kind": "NETWORK_LIBRARY",
            "confidence": "CONFIRMED",
        }

    # La libreria pu? apparire dopo un prefisso/alias
    # nell'espressione dotted.
    if any(
        f".{prefix}" in lower
        for prefix in NETWORK_LIBRARY_PREFIXES
    ):
        return {
            "kind": "NETWORK_LIBRARY",
            "confidence": "PROBABLE",
        }

    # --------------------------------------------------------
    # Chiamate network esatte.
    # --------------------------------------------------------

    if (
        lower in NETWORK_EXACT_CALLS
        or method in NETWORK_EXACT_CALLS
    ):
        return {
            "kind": "NETWORK_CALL",
            "confidence": "PROBABLE",
        }

    # --------------------------------------------------------
    # Metodi standard exchange/API.
    #
    # exchange.fetch_ohlcv()
    # client.fetch_ticker()
    # ecc.
    # --------------------------------------------------------

    if method in NETWORK_EXCHANGE_METHODS:
        return {
            "kind": "EXCHANGE_API",
            "confidence": "PROBABLE",
        }

    if any(
        method.startswith(prefix)
        for prefix in NETWORK_EXCHANGE_PREFIXES
    ):
        return {
            "kind": "EXCHANGE_STREAM",
            "confidence": "PROBABLE",
        }

    return None


def sql_literals_inside_execute(tree):
    """
    Restituisce gli ID dei nodi ast.Constant stringa
    utilizzati come primo argomento diretto di
    execute()/executemany().

    Queste stringhe vengono gi? registrate come
    EXECUTE_LITERAL e non devono essere registrate
    nuovamente come SQL_LITERAL.
    """

    result = set()

    for node in ast.walk(tree):

        if not isinstance(
            node,
            ast.Call
        ):
            continue

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

        if method not in {
            "execute",
            "executemany",
        }:
            continue

        if not node.args:
            continue

        first_arg = node.args[0]

        # Stringa SQL letterale diretta:
        #
        # cursor.execute(
        #     "SELECT ..."
        # )
        #
        # oppure triple quoted.
        if (
            isinstance(
                first_arg,
                ast.Constant
            )
            and isinstance(
                first_arg.value,
                str
            )
        ):
            result.add(
                id(first_arg)
            )

        # Stringhe concatenate implicitamente dal parser
        # risultano normalmente gi? in ast.Constant.
        #
        # Per JoinedStr/f-string non facciamo dedup qui:
        # l'analisi dinamica deve restare conservativa.

    return result

def analyze_file(path: Path):

    source, read_warning = read_source(path)

    result = {
        "file": relative(path),
        "historical_signal":
            is_probably_historical(path),
        "read_warning": read_warning,
        "parse_error": None,
        "external_sources": [],
        "network_calls": [],
        "database_connections": [],
        "database_operations": [],
        "database_literals": [],
        "file_operations": [],
        "api_outputs": [],
        "queues_caches": [],
    }

    if source is None:
        result["parse_error"] = (
            read_warning
            or "SOURCE_READ_FAILED"
        )
        return result

    try:
        tree = ast.parse(
            source,
            filename=str(path),
        )

    except SyntaxError as exc:

        result["parse_error"] = {
            "line": exc.lineno,
            "message": exc.msg,
        }

        return result

    execute_sql_literal_ids = (
        sql_literals_inside_execute(
            tree
        )
    )

    # ----------------------------------------------------------------------------------------------
    # String literals:
    # SQL, DB paths, URLs, data file paths
    # ----------------------------------------------------------------------------------------------

    for node in ast.walk(tree):

        if not isinstance(
            node,
            ast.Constant,
        ):
            continue

        if not isinstance(
            node.value,
            str,
        ):
            continue

        value = node.value
        lower = value.lower()

        sql = extract_sql_operation(
            value
        )

        if (
            sql
            and id(node)
            not in execute_sql_literal_ids
            and is_standalone_sql_literal(
                value
            )
        ):

            result[
                "database_operations"
            ].append({
                **sql,
                "line":
                    getattr(
                        node,
                        "lineno",
                        None,
                    ),
                "confidence":
                    "CONFIRMED",
                "evidence":
                    "SQL_LITERAL",
            })

        if lower.endswith(
            DB_EXTENSIONS
        ):

            result[
                "database_literals"
            ].append({
                "value": value,
                "line":
                    getattr(
                        node,
                        "lineno",
                        None,
                    ),
                "confidence":
                    "CONFIRMED",
            })

        if (
            lower.startswith("http://")
            or lower.startswith("https://")
            or lower.startswith("ws://")
            or lower.startswith("wss://")
        ):

            result[
                "external_sources"
            ].append({
                "value": value,
                "line":
                    getattr(
                        node,
                        "lineno",
                        None,
                    ),
                "confidence":
                    "CONFIRMED",
            })

    # ----------------------------------------------------------------------------------------------
    # Calls
    # ----------------------------------------------------------------------------------------------

    for node in ast.walk(tree):

        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        name = call_name(node)

        if not name:
            continue

        name_lower = name.lower()

        # NETWORK / EXTERNAL INPUT

        network_info = classify_network_call(
            name
        )

        if network_info:

            args = [
                literal_string(arg)
                for arg in node.args
            ]

            result[
                "network_calls"
            ].append({
                "call": name,
                "line": call_line(node),
                "arguments": [
                    value
                    for value in args
                    if value is not None
                ],
                "direction":
                    "INPUT_OR_EXTERNAL",
                "kind":
                    network_info[
                        "kind"
                    ],
                "confidence":
                    network_info[
                        "confidence"
                    ],
            })

        # DATABASE CONNECTION

        if any(
            hint in name_lower
            for hint in DB_CONNECT_HINTS
        ):

            args = [
                literal_string(arg)
                for arg in node.args
            ]

            result[
                "database_connections"
            ].append({
                "call": name,
                "line": call_line(node),
                "arguments": [
                    value
                    for value in args
                    if value is not None
                ],
                "confidence":
                    confidence(
                        confirmed=bool(
                            args
                        )
                    ),
            })

        # SQL passed to execute/executemany

        if (
            name_lower.endswith(
                ".execute"
            )
            or name_lower.endswith(
                ".executemany"
            )
        ):

            if node.args:

                sql_literal = literal_string(
                    node.args[0]
                )

                sql = extract_sql_operation(
                    sql_literal
                )

                if sql:

                    result[
                        "database_operations"
                    ].append({
                        **sql,
                        "line":
                            call_line(node),
                        "confidence":
                            "CONFIRMED",
                        "evidence":
                            "EXECUTE_LITERAL",
                    })

                else:

                    result[
                        "database_operations"
                    ].append({
                        "operation":
                            "DYNAMIC_SQL",
                        "direction":
                            "UNKNOWN",
                        "table":
                            None,
                        "line":
                            call_line(node),
                        "confidence":
                            "POSSIBLE",
                        "evidence":
                            "EXECUTE_DYNAMIC",
                    })

        # FILE READ / WRITE

        method = name_lower.split(
            "."
        )[-1]

        if method in FILE_READ_METHODS:

            result[
                "file_operations"
            ].append({
                "operation": "READ",
                "call": name,
                "line": call_line(node),
                "confidence":
                    "PROBABLE",
            })

        if method in FILE_WRITE_METHODS:

            result[
                "file_operations"
            ].append({
                "operation": "WRITE",
                "call": name,
                "line": call_line(node),
                "confidence":
                    "PROBABLE",
            })

        # QUEUE / CACHE
        #
        # Conservativo:
        # non classifichiamo .get() / .put() generici
        # perch? possono appartenere a dict, HTTP client,
        # FastAPI e molti altri oggetti.

        queue_cache_kind = None
        queue_cache_confidence = None

        parts = name_lower.split(".")

        owner = (
            ".".join(parts[:-1])
            if len(parts) > 1
            else ""
        )

        method_name = parts[-1]

        # Redis esplicito.
        if (
            "redis" in name_lower
        ):
            queue_cache_kind = "CACHE_REDIS"
            queue_cache_confidence = "PROBABLE"

        # Costruttori Queue espliciti.
        elif name_lower in {
            "asyncio.queue",
            "queue.queue",
            "multiprocessing.queue",
        }:
            queue_cache_kind = "QUEUE_CONSTRUCTOR"
            queue_cache_confidence = "CONFIRMED"

        # Operazioni su oggetti che dichiarano semanticamente
        # di essere queue.
        elif (
            "queue" in owner
            and method_name in {
                "put",
                "put_nowait",
                "get",
                "get_nowait",
                "task_done",
                "join",
                "empty",
                "full",
                "qsize",
            }
        ):
            queue_cache_kind = "QUEUE_OPERATION"
            queue_cache_confidence = "PROBABLE"

        if queue_cache_kind:

            result[
                "queues_caches"
            ].append({
                "call": name,
                "line": call_line(node),
                "kind":
                    queue_cache_kind,
                "confidence":
                    queue_cache_confidence,
            })

    # ----------------------------------------------------------------------------------------------
    # FastAPI / API output decorators
    # ----------------------------------------------------------------------------------------------

    for node in ast.walk(tree):

        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        for decorator in node.decorator_list:

            if not isinstance(
                decorator,
                ast.Call,
            ):
                continue

            dec_name = dotted_name(
                decorator.func
            )

            if not dec_name:
                continue

            method = dec_name.lower().split(
                "."
            )[-1]

            if method not in {
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "options",
                "head",
                "websocket",
            }:
                continue

            route = None

            if decorator.args:
                route = literal_string(
                    decorator.args[0]
                )

            result[
                "api_outputs"
            ].append({
                "function": node.name,
                "method": method.upper(),
                "route": route,
                "line":
                    getattr(
                        node,
                        "lineno",
                        None,
                    ),
                "direction": "OUTPUT",
                "confidence":
                    "CONFIRMED",
            })

    return result


# ==================================================================================================
# PROJECT STATUS / OPERATIONAL EVIDENCE
# ==================================================================================================

def load_json_report(*parts):

    path = (
        PROJECT_OUTPUT_ROOT
        / "LATEST"
    )

    for part in parts:
        path = path / part

    if not path.exists():
        return {}

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        )
    except Exception:
        return {}


def normalize_file(value):

    if not value:
        return None

    return str(
        Path(str(value))
    ).replace("/", "\\").lower()


def runtime_files():

    report = load_json_report(
        "02_RUNTIME",
        "RUNTIME_MAP.json",
    )

    found = set()

    for proc in report.get(
        "project_processes",
        []
    ):

        # --------------------------------------------------
        # Eventuale percorso gi? risolto da Analyzer 02
        # --------------------------------------------------

        value = (
            proc.get("project_file")
            or proc.get("file")
            or proc.get("script")
        )

        if value:
            found.add(
                normalize_file(value)
            )

        command = str(
            proc.get(
                "command_line",
                ""
            )
        )

        command_norm = (
            command
            .replace("/", "\\")
            .lower()
        )

        # --------------------------------------------------
        # Argomenti .py REALI della command line
        # --------------------------------------------------

        command_tokens = (
            command_norm
            .replace('"', " ")
            .replace("'", " ")
            .split()
        )

        python_arguments = {
            token
            for token in command_tokens
            if token.endswith(".py")
        }

        python_argument_names = {
            Path(token).name.lower()
            for token in python_arguments
        }

        # --------------------------------------------------
        # Modulo esatto dopo -m
        # --------------------------------------------------

        module_argument = None

        for index, token in enumerate(
            command_tokens
        ):

            if (
                token == "-m"
                and index + 1
                < len(command_tokens)
            ):
                module_argument = (
                    command_tokens[
                        index + 1
                    ]
                    .strip()
                    .lower()
                )
                break

        # --------------------------------------------------
        # Confronto con i file reali del progetto
        # --------------------------------------------------

        for path in iter_python_files():

            rel = relative(path)

            rel_norm = normalize_file(
                rel
            )

            name_norm = (
                path.name.lower()
            )

            matched = False

            # Script Python:
            # confronto ESATTO.
            #
            # Esempio:
            # dashboard.py NON deve corrispondere a
            # crypto_news_dashboard.py.

            if (
                "\\" in rel_norm
            ):

                for argument in python_arguments:

                    argument_norm = (
                        argument
                        .replace("/", "\\")
                        .lower()
                    )

                    if (
                        argument_norm
                        == rel_norm
                        or argument_norm.endswith(
                            "\\" + rel_norm
                        )
                    ):
                        matched = True
                        break

            else:

                if (
                    name_norm
                    in python_argument_names
                ):
                    matched = True

            # python -m package.module:
            # confronto ESATTO del modulo.

            module = (
                Path(rel)
                .with_suffix("")
                .as_posix()
                .replace("/", ".")
                .lower()
            )

            if (
                module_argument
                and module_argument
                == module
            ):
                matched = True

            if matched:
                found.add(
                    rel_norm
                )

    return found


def api_status_map():

    report = load_json_report(
        "06_API_ENDPOINTS",
        "API_ENDPOINTS_MAP.json",
    )

    output = {}

    for filename, info in report.get(
        "file_runtime_classification",
        {}
    ).items():

        output[
            normalize_file(filename)
        ] = info.get(
            "classification",
            "UNKNOWN",
        )

    return output


def connected_files(runtime_set=None):

    report = load_json_report(
        "04_CODE_CONNECTIONS",
        "CODE_CONNECTIONS.json",
    )

    connections = report.get(
        "internal_connections",
        [],
    )

    if runtime_set is None:
        runtime_set = runtime_files()

    runtime_set = {
        normalize_file(x)
        for x in runtime_set
        if x
    }

    graph = {}

    for edge in connections:

        source = normalize_file(
            edge.get("source_file")
        )

        target = normalize_file(
            edge.get("target_file")
        )

        if not source or not target:
            continue

        graph.setdefault(
            source,
            []
        ).append(
            (
                target,
                edge,
            )
        )

    visited = set(runtime_set)
    queue = list(runtime_set)

    while queue:

        source = queue.pop(0)

        for target, edge in graph.get(
            source,
            []
        ):

            if target in visited:
                continue

            visited.add(target)
            queue.append(target)

    return visited - runtime_set

TEST_DIR_NAMES = {
    "test",
    "tests",
    "testing",
}

SUPPORT_DIR_NAMES = {
    "scripts",
    "tools",
    "utilities",
}

MAINTENANCE_PREFIXES = (
    "create_",
    "setup_",
    "init_",
    "initialize_",
    "backfill_",
    "migrate_",
    "migration_",
    "repair_",
    "rebuild_",
    "cleanup_",
    "install_",
    "apply_",
    "optimize_",
    "validate_",
)

TOOL_TOKENS = (
    "audit",
    "forensic",
    "diagnostic",
    "benchmark",
    "profiler",
    "profiling",
    "explorer",
    "project_structure",
    "scan_project",
)

TEMPORARY_TOKENS = (
    "_for_chatgpt",
    "_copy",
    "_temp",
    "_tmp",
)


def generic_file_role(filename):

    path = Path(filename)

    parts = [
        part.lower()
        for part in path.parts
    ]

    name = path.name.lower()
    stem = path.stem.lower()

    if (
        any(
            part in TEST_DIR_NAMES
            for part in parts[:-1]
        )
        or name.startswith("test_")
        or name.endswith("_test.py")
    ):
        return "TEST"

    if any(
        token in stem
        for token in TEMPORARY_TOKENS
    ):
        return "SUPPORT"

    if stem.startswith(
        MAINTENANCE_PREFIXES
    ):
        return "MAINTENANCE"

    if any(
        token in stem
        for token in TOOL_TOKENS
    ):
        return "TOOL"

    if any(
        part in SUPPORT_DIR_NAMES
        for part in parts[:-1]
    ):
        return "SUPPORT"

    return "UNKNOWN"


def classify_project_files(
    results,
    historical_files,
):

    runtime = runtime_files()
    api_map = api_status_map()
    connected = connected_files()

    historical = {
        normalize_file(
            relative(path)
        )
        for path in historical_files
    }

    classifications = {}

    for item in results:

        filename = item["file"]
        key = normalize_file(
            filename
        )

        evidence = []
        status = None
        confidence_level = None

        # ------------------------------------------------------------------
        # Strong evidence always wins over filename heuristics.
        # ------------------------------------------------------------------

        api_status = api_map.get(key)

        if (
            key in runtime
            or api_status
            == "CONFIRMED_RUNTIME"
        ):

            status = (
                "OPERATIONAL_CONFIRMED"
            )

            confidence_level = (
                "CONFIRMED"
            )

            evidence.append(
                "RUNTIME_PROCESS"
            )

        elif api_status == (
            "CONFIRMED_CONNECTED"
        ):

            status = (
                "OPERATIONAL_CONNECTED"
            )

            confidence_level = (
                "CONFIRMED"
            )

            evidence.append(
                "ACTIVE_API_CONNECTION"
            )

        elif key in connected:

            status = (
                "OPERATIONAL_CONNECTED"
            )

            confidence_level = (
                "PROBABLE"
            )

            evidence.append(
                "CODE_CONNECTION_GRAPH"
            )

        # ------------------------------------------------------------------
        # API 06 historical/static evidence.
        # ------------------------------------------------------------------

        elif api_status == (
            "PROBABLE_HISTORICAL"
        ):

            status = "HISTORICAL"
            confidence_level = "PROBABLE"

            evidence.append(
                "API_HISTORICAL_SIGNAL"
            )

        elif api_status == "STATIC_ONLY":

            status = "STATIC_ONLY"
            confidence_level = "CONFIRMED"

            evidence.append(
                "API_STATIC_ONLY"
            )

        # ------------------------------------------------------------------
        # Historical inventory.
        # ------------------------------------------------------------------

        elif key in historical:

            status = "HISTORICAL"
            confidence_level = "PROBABLE"

            evidence.append(
                "HISTORICAL_NAMING_OR_DIRECTORY"
            )

        # ------------------------------------------------------------------
        # Generic support/test/tool classification.
        # ------------------------------------------------------------------

        else:

            role = generic_file_role(
                filename
            )

            if role == "TEST":

                status = "TEST"
                confidence_level = "CONFIRMED"
                evidence.append(
                    "TEST_NAMING_OR_DIRECTORY"
                )

            elif role == "MAINTENANCE":

                status = "MAINTENANCE"
                confidence_level = "PROBABLE"
                evidence.append(
                    "MAINTENANCE_NAMING"
                )

            elif role == "TOOL":

                status = "TOOL"
                confidence_level = "PROBABLE"
                evidence.append(
                    "TOOL_NAMING"
                )

            elif role == "SUPPORT":

                status = "SUPPORT"
                confidence_level = "PROBABLE"
                evidence.append(
                    "SUPPORT_NAMING_OR_DIRECTORY"
                )

            else:

                status = "UNKNOWN"
                confidence_level = "UNKNOWN"

        classifications[
            filename
        ] = {
            "status": status,
            "confidence":
                confidence_level,
            "evidence": evidence,
            "runtime":
                key in runtime,
            "api_status":
                api_status,
            "connected":
                key in connected,
        }

    return classifications


# ==================================================================================================
# AGGREGATION
# ==================================================================================================


# =============================================================================
# STAGE 2 - EVIDENCE-BASED DATA LINEAGE
# =============================================================================


def deduplicate_database_operations(
    operations,
):
    """
    Deduplicazione conservativa.

    Elimina esclusivamente record che descrivono
    la stessa operazione SQL sulla stessa riga dello
    stesso file.

    Non unisce operazioni su righe differenti.
    """

    result = []
    seen = {}

    evidence_priority = {
        "EXECUTE_LITERAL": 3,
        "SQL_LITERAL": 2,
        "EXECUTE_DYNAMIC": 1,
    }

    for item in operations:

        key = (
            str(
                item.get(
                    "file",
                    ""
                )
            ),
            item.get(
                "line"
            ),
            str(
                item.get(
                    "operation",
                    ""
                )
            ).upper(),
            str(
                item.get(
                    "direction",
                    ""
                )
            ).upper(),
            str(
                item.get(
                    "table",
                    ""
                )
            ).lower(),
        )

        if key not in seen:

            new_item = dict(item)

            new_item[
                "merged_evidence"
            ] = [
                item.get(
                    "evidence",
                    "UNKNOWN"
                )
            ]

            seen[key] = len(result)

            result.append(
                new_item
            )

            continue

        index = seen[key]

        existing = result[index]

        evidence = item.get(
            "evidence",
            "UNKNOWN"
        )

        if evidence not in existing[
            "merged_evidence"
        ]:
            existing[
                "merged_evidence"
            ].append(
                evidence
            )

        old_evidence = existing.get(
            "evidence",
            "UNKNOWN"
        )

        if (
            evidence_priority.get(
                evidence,
                0
            )
            >
            evidence_priority.get(
                old_evidence,
                0
            )
        ):
            existing[
                "evidence"
            ] = evidence

        existing[
            "deduplicated"
        ] = True

    return result

def build_stage2_lineage(
    project_file_classification,
    database_operations,
):

    # -------------------------------------------------------------------------
    # Report gi? prodotti dagli analyzer precedenti.
    # Nessun database viene riaperto.
    # -------------------------------------------------------------------------

    runtime_report = load_json_report(
        "02_RUNTIME",
        "RUNTIME_MAP.json",
    )

    database_report = load_json_report(
        "03_DATABASE",
        "DATABASE_MAP.json",
    )

    connections_report = load_json_report(
        "04_CODE_CONNECTIONS",
        "CODE_CONNECTIONS.json",
    )

    api_report = load_json_report(
        "06_API_ENDPOINTS",
        "API_ENDPOINTS_MAP.json",
    )

    # -------------------------------------------------------------------------
    # NUCLEO OPERATIVO
    # -------------------------------------------------------------------------

    operational = {}

    for filename, info in (
        project_file_classification.items()
    ):

        status = info.get(
            "status",
            "UNKNOWN",
        )

        if status not in {
            "OPERATIONAL_CONFIRMED",
            "OPERATIONAL_CONNECTED",
        }:
            continue

        key = normalize_file(
            filename
        )

        operational[key] = {
            "file": filename,
            "status": status,
            "confidence": info.get(
                "confidence",
                "UNKNOWN",
            ),
            "evidence": info.get(
                "evidence",
                [],
            ),
        }

    # -------------------------------------------------------------------------
    # DATABASE E TABELLE REALMENTE CONFERMATI DA ANALYZER 03
    # -------------------------------------------------------------------------

    confirmed_databases = {}

    table_to_databases = {}

    for db in database_report.get(
        "databases",
        []
    ):

        analysis = db.get(
            "analysis",
            {},
        )

        if not analysis.get(
            "readable",
            False,
        ):
            continue

        db_path = db.get(
            "relative_path"
        )

        if not db_path:
            continue

        tables = []

        for table in analysis.get(
            "tables",
            []
        ):

            table_name = table.get(
                "name"
            )

            if not table_name:
                continue

            tables.append(
                {
                    "name": table_name,
                    "row_count": table.get(
                        "row_count"
                    ),
                    "row_count_status": table.get(
                        "row_count_status"
                    ),
                    "confidence": table.get(
                        "row_count_confidence",
                        "UNKNOWN",
                    ),
                }
            )

            table_key = (
                str(table_name)
                .lower()
            )

            table_to_databases.setdefault(
                table_key,
                set(),
            ).add(
                db_path
            )

        confirmed_databases[
            db_path
        ] = {
            "database": db_path,
            "type": analysis.get(
                "confirmed_type"
            ),
            "confidence": analysis.get(
                "confidence",
                "UNKNOWN",
            ),
            "journal_mode": analysis.get(
                "journal_mode"
            ),
            "tables": tables,
        }

    # -------------------------------------------------------------------------
    # FILE -> DATABASE
    # Basato sui riferimenti confermati/probabili di Analyzer 03.
    # -------------------------------------------------------------------------

    file_database_refs = {}

    for db_path, refs in (
        database_report
        .get(
            "code_database_references",
            {},
        )
        .items()
    ):

        for ref in refs:

            filename = normalize_file(
                ref.get(
                    "python_file"
                )
            )

            if filename not in operational:
                continue

            file_database_refs.setdefault(
                filename,
                set(),
            ).add(
                db_path
            )

    # -------------------------------------------------------------------------
    # CODE EDGES OPERATIVI
    # -------------------------------------------------------------------------

    code_edges_map = {}

    for edge in connections_report.get(
        "internal_connections",
        []
    ):

        source = normalize_file(
            edge.get(
                "source_file"
            )
        )

        target = normalize_file(
            edge.get(
                "target_file"
            )
        )

        if (
            source not in operational
            or target not in operational
        ):
            continue

        key = (
            source,
            target,
        )

        record = {
            "source": operational[
                source
            ]["file"],
            "target": operational[
                target
            ]["file"],
            "relation": "CODE_IMPORT",
            "confidence": edge.get(
                "confidence",
                "CONFIRMED",
            ),
            "evidence": [
                "ANALYZER_04_INTERNAL_CONNECTION"
            ],
        }

        code_edges_map.setdefault(
            key,
            record,
        )

    code_edges = list(
        code_edges_map.values()
    )

    # -------------------------------------------------------------------------
    # DATABASE EDGES
    #
    # Accettiamo una tabella solo se Analyzer 03 conferma che esiste davvero.
    # Questo elimina falsi positivi SQL come "COMPLETATO".
    # -------------------------------------------------------------------------

    database_edges_map = {}

    for operation in database_operations:

        filename = normalize_file(
            operation.get(
                "file"
            )
        )

        if filename not in operational:
            continue

        table = operation.get(
            "table"
        )

        if not table:
            continue

        table_key = (
            str(table)
            .lower()
        )

        real_database_candidates = set(
            table_to_databases.get(
                table_key,
                set(),
            )
        )

        if not real_database_candidates:
            continue

        referenced_databases = set(
            file_database_refs.get(
                filename,
                set(),
            )
        )

        resolved_databases = (
            real_database_candidates
            & referenced_databases
        )

        resolution = (
            "FILE_DB_REFERENCE_AND_SCHEMA"
        )

        confidence = operation.get(
            "confidence",
            "UNKNOWN",
        )

        # Se il file non contiene un riferimento DB
        # direttamente risolto, possiamo ancora associare
        # la tabella quando esiste in un solo DB reale.
        if not resolved_databases:

            if len(
                real_database_candidates
            ) == 1:

                resolved_databases = (
                    real_database_candidates
                )

                resolution = (
                    "UNIQUE_CONFIRMED_TABLE"
                )

                if confidence == "CONFIRMED":
                    confidence = "PROBABLE"

            else:
                # Ambiguo: non inventiamo il DB.
                continue

        for db_path in sorted(
            resolved_databases
        ):

            direction = operation.get(
                "direction",
                "UNKNOWN",
            )

            op_name = operation.get(
                "operation",
                "UNKNOWN",
            )

            key = (
                filename,
                normalize_file(
                    db_path
                ),
                table_key,
                direction,
                op_name,
            )

            database_edges_map.setdefault(
                key,
                {
                    "file": operational[
                        filename
                    ]["file"],
                    "database": db_path,
                    "table": table,
                    "operation": op_name,
                    "direction": direction,
                    "confidence": confidence,
                    "resolution": resolution,
                    "evidence": [
                        operation.get(
                            "evidence",
                            "UNKNOWN",
                        ),
                        "ANALYZER_03_CONFIRMED_SCHEMA",
                    ],
                },
            )

    database_edges = list(
        database_edges_map.values()
    )

    # -------------------------------------------------------------------------
    # API EDGES
    # -------------------------------------------------------------------------

    api_edges = []

    for endpoint in api_report.get(
        "endpoints",
        []
    ):

        filename = normalize_file(
            endpoint.get(
                "file"
            )
        )

        if filename not in operational:
            continue

        runtime_classification = (
            endpoint.get(
                "runtime_classification",
                "",
            )
        )

        if runtime_classification not in {
            "CONFIRMED_RUNTIME",
            "CONFIRMED_CONNECTED",
        }:
            continue

        methods = endpoint.get(
            "methods"
        )

        if not methods:

            method = endpoint.get(
                "method",
                "UNKNOWN",
            )

            methods = [
                method
            ]

        for method in methods:

            api_edges.append(
                {
                    "file": operational[
                        filename
                    ]["file"],
                    "method": method,
                    "path": endpoint.get(
                        "path"
                    ),
                    "function": endpoint.get(
                        "function"
                    ),
                    "runtime_classification":
                        runtime_classification,
                    "confidence": endpoint.get(
                        "confidence",
                        "CONFIRMED",
                    ),
                    "evidence": [
                        "ANALYZER_06_API"
                    ],
                }
            )

    # -------------------------------------------------------------------------
    # RUNTIME NODES
    # -------------------------------------------------------------------------

    runtime_nodes = []

    for proc in runtime_report.get(
        "project_processes",
        []
    ):

        runtime_nodes.append(
            {
                "pid": proc.get(
                    "pid"
                ),
                "command_line": proc.get(
                    "command_line"
                ),
                "listening_ports": proc.get(
                    "listening_ports",
                    [],
                ),
                "confidence": "CONFIRMED",
                "evidence": [
                    "ANALYZER_02_RUNTIME"
                ],
            }
        )

    # -------------------------------------------------------------------------
    # TABLE FLOW
    #
    # Writer -> database::table -> Reader
    #
    # Non affermiamo che un reader sia chiamato direttamente dal writer.
    # Descriviamo solo la lineage dei dati condivisi.
    # -------------------------------------------------------------------------

    table_flows = []

    grouped = {}

    for edge in database_edges:

        key = (
            edge["database"],
            str(
                edge["table"]
            ).lower(),
        )

        grouped.setdefault(
            key,
            {
                "database": edge[
                    "database"
                ],
                "table": edge[
                    "table"
                ],
                "writers": set(),
                "readers": set(),
            },
        )

        if edge[
            "direction"
        ] == "WRITE":

            grouped[
                key
            ]["writers"].add(
                edge["file"]
            )

        elif edge[
            "direction"
        ] == "READ":

            grouped[
                key
            ]["readers"].add(
                edge["file"]
            )

    for value in grouped.values():

        table_flows.append(
            {
                "database": value[
                    "database"
                ],
                "table": value[
                    "table"
                ],
                "writers": sorted(
                    value[
                        "writers"
                    ]
                ),
                "readers": sorted(
                    value[
                        "readers"
                    ]
                ),
                "confidence": "CONFIRMED",
                "relation":
                    "SHARED_DATA_LINEAGE",
            }
        )

    # -------------------------------------------------------------------------
    # RESULT
    # -------------------------------------------------------------------------

    return {
        "operational_nucleus": {
            "file_count": len(
                operational
            ),
            "files": sorted(
                operational.values(),
                key=lambda x: (
                    x["file"].lower()
                ),
            ),
        },

        "runtime_nodes": runtime_nodes,

        "confirmed_databases": list(
            confirmed_databases.values()
        ),

        "code_edges": code_edges,

        "database_edges": database_edges,

        "api_edges": api_edges,

        "table_flows": table_flows,

        "notes": [
            (
                "Stage 2 correlates existing analyzer "
                "evidence; it does not execute project code."
            ),
            (
                "Database tables are accepted only when "
                "confirmed by Analyzer 03."
            ),
            (
                "Table flows represent shared data lineage, "
                "not direct function calls."
            ),
            (
                "Ambiguous database associations are not "
                "invented."
            ),
        ],
    }

def main():

    print("=" * 100)
    print("PYTHON PROJECT INTELLIGENCE")
    print("ANALYZER 07 - DATA FLOW V2 TEST")
    print("=" * 100)
    print(
        f"Project name       : "
        f"{PROJECT_NAME}"
    )
    print(
        f"Project root       : "
        f"{PROJECT_ROOT}"
    )
    print(
        "Mode               : "
        "READ ONLY / STATIC ANALYSIS"
    )
    print()

    files = list(
        iter_python_files()
    )

    active_files = []
    historical_files = []

    for path in files:

        if is_probably_historical(
            path
        ):
            historical_files.append(
                path
            )
        else:
            active_files.append(
                path
            )

    print(
        f"File Python totali : "
        f"{len(files)}"
    )

    print(
        f"File attivi        : "
        f"{len(active_files)}"
    )

    print(
        f"Storici esclusi    : "
        f"{len(historical_files)}"
    )

    print()
    print(
        "Analisi operazioni dati..."
    )

    results = []

    for path in active_files:

        results.append(
            analyze_file(path)
        )

    classifications = classify_project_files(
        results,
        historical_files,
    )

    parse_errors = [
        item
        for item in results
        if item.get(
            "parse_error"
        )
    ]

    external_sources = []
    network_calls = []
    db_connections = []
    db_operations = []
    db_literals = []
    file_operations = []
    api_outputs = []
    queues_caches = []

    for item in results:

        filename = item["file"]

        for key, target in (
            (
                "external_sources",
                external_sources,
            ),
            (
                "network_calls",
                network_calls,
            ),
            (
                "database_connections",
                db_connections,
            ),
            (
                "database_operations",
                db_operations,
            ),
            (
                "database_literals",
                db_literals,
            ),
            (
                "file_operations",
                file_operations,
            ),
            (
                "api_outputs",
                api_outputs,
            ),
            (
                "queues_caches",
                queues_caches,
            ),
        ):

            for value in item.get(
                key,
                []
            ):

                target.append({
                    "file": filename,
                    **value,
                })

    db_operations_raw_count = len(
        db_operations
    )

    db_operations = (
        deduplicate_database_operations(
            db_operations
        )
    )

    db_operations_duplicates_removed = (
        db_operations_raw_count
        - len(db_operations)
    )

    db_direction = Counter(
        item.get(
            "direction",
            "UNKNOWN",
        )
        for item in db_operations
    )

    status_counts = Counter(
        info.get(
            "status",
            "UNKNOWN",
        )
        for info in classifications.values()
    )

    stage2_lineage = build_stage2_lineage(
        classifications,
        db_operations,
    )

    report = {
        "metadata": {
            "analyzer":
                "07_DATA_FLOW",
            "version":
                ANALYZER_VERSION,
            "generated_at_utc":
                datetime.now(
                    timezone.utc
                ).isoformat(),
            "project_name":
                PROJECT_NAME,
            "project_root":
                str(PROJECT_ROOT),
            "mode":
                "READ_ONLY_STATIC_ANALYSIS",
        },

        "summary": {
            "python_files_total":
                len(files),
            "active_python_files":
                len(active_files),
            "historical_python_files":
                len(historical_files),
            "files_analyzed":
                len(results),
            "parse_errors":
                len(parse_errors),
            "external_sources":
                len(external_sources),
            "network_calls":
                len(network_calls),
            "database_connections":
                len(db_connections),
            "database_operations":
                len(db_operations),
            "database_operations_raw":
                db_operations_raw_count,
            "database_duplicates_removed":
                db_operations_duplicates_removed,
            "database_reads":
                db_direction.get(
                    "READ",
                    0,
                ),
            "database_writes":
                db_direction.get(
                    "WRITE",
                    0,
                ),
            "database_literals":
                len(db_literals),
            "file_operations":
                len(file_operations),
            "api_outputs":
                len(api_outputs),
            "queue_cache_operations":
                len(queues_caches),
        },

        "project_file_classification":
            classifications,

        "classification_summary":
            dict(
                sorted(
                    status_counts.items()
                )
            ),

        "historical_files_excluded": [
            relative(path)
            for path in historical_files
        ],

        "parse_errors":
            parse_errors,

        "external_sources":
            external_sources,

        "network_calls":
            network_calls,

        "database_connections":
            db_connections,

        "database_operations":
            db_operations,

        "database_literals":
            db_literals,

        "file_operations":
            file_operations,

        "api_outputs":
            api_outputs,

        "queue_cache_operations":
            queues_caches,

        "files":
            results,

        "stage2_lineage":
            stage2_lineage,

        # Reserved for true evidence-backed multi-hop
        # end-to-end chains.
        #
        # Stage 2 table_flows are shared-data lineage
        # relationships and must not be presented as
        # direct end-to-end execution chains.
        "flow_chains": [],

        "notes": [
            (
                "Stage 1 inventories raw data operations. "
                "Stage 2 correlates evidence from runtime, "
                "database, code-connections and API analyzers."
            ),
            (
                "CONFIRMED means direct static evidence. "
                "PROBABLE and POSSIBLE require correlation "
                "with other analyzers."
            ),
        ],
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=" * 100)
    print("RISULTATI STAGE 1")
    print("=" * 100)

    for key, value in report[
        "summary"
    ].items():

        print(
            f"{key:<30}: {value}"
        )

    print()
    print(
        f"Report JSON         : "
        f"{OUTPUT_FILE}"
    )

    print()
    print(
        "STAGE 2: lineage costruita solo da "
        "evidenze correlate e confermate."
    )

    print()
    print(
        "ANALYZER STATUS: OK"
    )

    print("=" * 100)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
