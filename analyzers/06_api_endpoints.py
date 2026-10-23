from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


# =============================================================================
# PYTHON PROJECT INTELLIGENCE
# ANALYZER 06 - UNIVERSAL API / ENDPOINT ANALYZER
#
# READ ONLY
#
# Static analysis only.
# Runtime availability is NOT inferred from static code.
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
    iter_python_files,
    ensure_output_directories,
)


ANALYZER_NAME = "06_api_endpoints"
ANALYZER_VERSION = "2.1"


# =============================================================================
# HISTORICAL FILTER
# =============================================================================

HISTORICAL_DIRECTORY_NAMES = {
    "backup",
    "backups",
    "_deep_audit",
    "_runtime_report",
    "_forensic_report",
    "site_intelligence",
}

HISTORICAL_FILE_PATTERNS = (
    "backup",
    "_backup",
    ".backup",
    "audit",
    "forensic",
    "operational_map",
    "project_structure_report",
    "analisi_completa_sito",
    "struttura_crypto_scanner",
    "codice_runtime_sito",
    "market_data_operational_map",
    "crypto_scanner_full_audit",
)


def relative_string(path: Path) -> str:

    try:
        return str(
            path.resolve().relative_to(
                PROJECT_ROOT.resolve()
            )
        )
    except ValueError:
        return str(path.resolve())


def historical_reason(path: Path) -> str | None:

    try:
        relative = path.resolve().relative_to(
            PROJECT_ROOT.resolve()
        )
    except ValueError:
        return "outside_project"

    parts = [
        part.lower()
        for part in relative.parts
    ]

    for part in parts[:-1]:

        if part in HISTORICAL_DIRECTORY_NAMES:
            return f"historical_directory:{part}"

    filename = path.name.lower()

    for pattern in HISTORICAL_FILE_PATTERNS:

        if pattern in filename:
            return f"historical_filename:{pattern}"

    return None


def get_active_python_files():

    active = []
    historical = []

    for path in iter_python_files():

        reason = historical_reason(path)

        if reason:

            historical.append({
                "path": relative_string(path),
                "reason": reason,
            })

            continue

        active.append(path)

    return active, historical


# =============================================================================
# SAFE SOURCE READING
# =============================================================================

def read_source(path: Path) -> str | None:

    try:
        if path.stat().st_size > 10 * 1024 * 1024:
            return None
    except OSError:
        return None

    try:
        return path.read_text(
            encoding="utf-8-sig",
            errors="ignore",
        )
    except Exception:
        return None


# =============================================================================
# AST HELPERS
# =============================================================================

def literal_string(node) -> str | None:

    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return node.value

    try:
        value = ast.literal_eval(node)
    except Exception:
        return None

    if isinstance(value, str):
        return value

    return None


def literal_number(node):

    try:
        value = ast.literal_eval(node)
    except Exception:
        return None

    if isinstance(value, (int, float)):
        return value

    return None


def get_call_name(node) -> str | None:

    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):

        parent = get_call_name(node.value)

        if parent:
            return f"{parent}.{node.attr}"

        return node.attr

    return None


def decorator_name(node) -> str | None:

    if isinstance(node, ast.Call):
        return get_call_name(node.func)

    return get_call_name(node)


def keyword_value(call: ast.Call, name: str):

    for keyword in call.keywords:

        if keyword.arg == name:
            return keyword.value

    return None


# =============================================================================
# FRAMEWORK DETECTION
# =============================================================================

FRAMEWORK_IMPORTS = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "starlette": "Starlette",
    "sanic": "Sanic",
    "aiohttp": "aiohttp",
    "tornado": "Tornado",
    "falcon": "Falcon",
    "bottle": "Bottle",
    "litestar": "Litestar",
    "quart": "Quart",
}


def detect_frameworks(tree: ast.AST) -> set[str]:

    frameworks = set()

    for node in ast.walk(tree):

        if isinstance(node, ast.Import):

            for alias in node.names:

                root = alias.name.split(".")[0].lower()

                if root in FRAMEWORK_IMPORTS:
                    frameworks.add(
                        FRAMEWORK_IMPORTS[root]
                    )

        elif isinstance(node, ast.ImportFrom):

            if node.module:

                root = node.module.split(".")[0].lower()

                if root in FRAMEWORK_IMPORTS:
                    frameworks.add(
                        FRAMEWORK_IMPORTS[root]
                    )

    return frameworks


# =============================================================================
# IMPORT / ALIAS RESOLUTION
# =============================================================================

def detect_import_aliases(tree: ast.AST) -> dict[str, dict]:

    aliases = {}

    for node in tree.body:

        if isinstance(node, ast.Import):

            for alias in node.names:

                local_name = (
                    alias.asname
                    or alias.name.split(".")[0]
                )

                aliases[local_name] = {
                    "kind": "module",
                    "module": alias.name,
                    "imported_name": None,
                    "alias": alias.asname,
                    "line": getattr(
                        node,
                        "lineno",
                        None,
                    ),
                }

        elif isinstance(node, ast.ImportFrom):

            module = node.module

            if not module:
                continue

            for alias in node.names:

                local_name = (
                    alias.asname
                    or alias.name
                )

                aliases[local_name] = {
                    "kind": "from_import",
                    "module": module,
                    "imported_name": alias.name,
                    "alias": alias.asname,
                    "line": getattr(
                        node,
                        "lineno",
                        None,
                    ),
                }

    return aliases


def module_to_project_file(
    module_name: str | None,
) -> str | None:

    if not module_name:
        return None

    parts = [
        part
        for part in module_name.split(".")
        if part
    ]

    if not parts:
        return None

    candidate_py = (
        PROJECT_ROOT.joinpath(*parts)
        .with_suffix(".py")
    )

    if candidate_py.is_file():
        return relative_string(candidate_py)

    candidate_package = (
        PROJECT_ROOT.joinpath(*parts)
        / "__init__.py"
    )

    if candidate_package.is_file():
        return relative_string(
            candidate_package
        )

    return None


def resolve_router_connections(
    connections,
    import_aliases,
):

    resolved = []

    for connection in connections:

        item = dict(connection)

        router_name = item.get("router")

        evidence = None
        target_file = None
        target_module = None
        imported_name = None

        if router_name:

            root_name = router_name.split(".")[0]

            evidence = import_aliases.get(
                root_name
            )

        if evidence:

            target_module = evidence.get(
                "module"
            )

            imported_name = evidence.get(
                "imported_name"
            )

            target_file = module_to_project_file(
                target_module
            )

        item["target_module"] = target_module
        item["target_file"] = target_file
        item["imported_name"] = imported_name

        if target_file:
            item["resolution"] = (
                "CONFIRMED_PROJECT_IMPORT"
            )
        elif evidence:
            item["resolution"] = (
                "IMPORT_FOUND_TARGET_UNRESOLVED"
            )
        else:
            item["resolution"] = (
                "UNRESOLVED"
            )

        resolved.append(item)

    return resolved



# =============================================================================
# ROUTER PREFIX DISCOVERY
# =============================================================================

def detect_router_prefixes(tree: ast.AST) -> dict[str, str]:

    prefixes = {}

    for node in ast.walk(tree):

        if not isinstance(node, ast.Assign):
            continue

        if not isinstance(node.value, ast.Call):
            continue

        call_name = get_call_name(
            node.value.func
        )

        if not call_name:
            continue

        if not (
            call_name.endswith("APIRouter")
            or call_name.endswith("Blueprint")
        ):
            continue

        prefix_node = (
            keyword_value(
                node.value,
                "prefix",
            )
            or keyword_value(
                node.value,
                "url_prefix",
            )
        )

        prefix = (
            literal_string(prefix_node)
            if prefix_node is not None
            else ""
        )

        for target in node.targets:

            if isinstance(target, ast.Name):
                prefixes[target.id] = prefix or ""

    return prefixes


# =============================================================================
# DECORATOR ENDPOINTS
# =============================================================================

HTTP_METHODS = {
    "get",
    "post",
    "put",
    "delete",
    "patch",
    "options",
    "head",
    "trace",
}

WEBSOCKET_METHODS = {
    "websocket",
    "websocket_route",
}


def normalize_path(path: str) -> str:

    if not path:
        return "/"

    if not path.startswith("/"):
        path = "/" + path

    while "//" in path:
        path = path.replace("//", "/")

    return path


def join_paths(prefix: str, path: str) -> str:

    prefix = prefix or ""
    path = path or ""

    if not prefix:
        return normalize_path(path)

    return normalize_path(
        prefix.rstrip("/")
        + "/"
        + path.lstrip("/")
    )


def extract_decorator_endpoint(
    decorator,
    router_prefixes,
):

    if not isinstance(decorator, ast.Call):
        return None

    name = decorator_name(decorator)

    if not name:
        return None

    parts = name.split(".")

    if not parts:
        return None

    method = parts[-1].lower()

    if (
        method not in HTTP_METHODS
        and method not in WEBSOCKET_METHODS
        and method != "route"
        and method != "api_route"
    ):
        return None

    owner = (
        parts[-2]
        if len(parts) >= 2
        else None
    )

    route_path = None

    if decorator.args:
        route_path = literal_string(
            decorator.args[0]
        )

    if route_path is None:

        path_kw = keyword_value(
            decorator,
            "path",
        )

        if path_kw is not None:
            route_path = literal_string(
                path_kw
            )

    if route_path is None:
        return None

    prefix = ""

    if owner:
        prefix = router_prefixes.get(
            owner,
            "",
        )

    full_path = join_paths(
        prefix,
        route_path,
    )

    methods = []

    endpoint_type = "HTTP"

    if method in HTTP_METHODS:

        methods = [method.upper()]

    elif method in WEBSOCKET_METHODS:

        methods = ["WEBSOCKET"]
        endpoint_type = "WEBSOCKET"

    elif method in {"route", "api_route"}:

        methods_kw = keyword_value(
            decorator,
            "methods",
        )

        if methods_kw is not None:

            try:
                values = ast.literal_eval(
                    methods_kw
                )

                if isinstance(
                    values,
                    (list, tuple, set),
                ):
                    methods = [
                        str(value).upper()
                        for value in values
                    ]

            except Exception:
                pass

        if not methods:
            methods = ["UNKNOWN"]

    return {
        "owner": owner,
        "decorator": name,
        "path": full_path,
        "methods": methods,
        "type": endpoint_type,
    }


# =============================================================================
# DJANGO PATH DISCOVERY
# =============================================================================

def extract_django_paths(tree: ast.AST):

    endpoints = []

    for node in ast.walk(tree):

        if not isinstance(node, ast.Call):
            continue

        name = get_call_name(node.func)

        if not name:
            continue

        if name.split(".")[-1] not in {
            "path",
            "re_path",
        }:
            continue

        if not node.args:
            continue

        route = literal_string(
            node.args[0]
        )

        if route is None:
            continue

        handler = None

        if len(node.args) >= 2:
            handler = get_call_name(
                node.args[1]
            )

        endpoints.append({
            "framework": "Django",
            "type": "HTTP",
            "methods": ["UNKNOWN"],
            "path": normalize_path(route),
            "function": handler,
            "line": getattr(
                node,
                "lineno",
                None,
            ),
            "source": "django_url_pattern",
            "confidence": "CONFIRMED_STATIC",
        })

    return endpoints


# =============================================================================
# APP / ROUTER CREATION
# =============================================================================

def detect_app_objects(tree: ast.AST):

    apps = []

    interesting = {
        "FastAPI",
        "Flask",
        "Starlette",
        "Sanic",
        "Bottle",
        "Falcon",
        "Litestar",
        "Quart",
        "APIRouter",
        "Blueprint",
    }

    for node in ast.walk(tree):

        if not isinstance(node, ast.Assign):
            continue

        if not isinstance(node.value, ast.Call):
            continue

        call_name = get_call_name(
            node.value.func
        )

        if not call_name:
            continue

        constructor = call_name.split(".")[-1]

        if constructor not in interesting:
            continue

        for target in node.targets:

            if not isinstance(
                target,
                ast.Name,
            ):
                continue

            apps.append({
                "variable": target.id,
                "constructor": constructor,
                "line": getattr(
                    node,
                    "lineno",
                    None,
                ),
            })

    return apps


# =============================================================================
# SERVER CONFIGURATION
# =============================================================================

SERVER_CALL_NAMES = {
    "uvicorn.run",
    "hypercorn.run",
    "app.run",
    "web.run_app",
}


def detect_server_calls(tree: ast.AST):

    servers = []

    for node in ast.walk(tree):

        if not isinstance(node, ast.Call):
            continue

        name = get_call_name(
            node.func
        )

        if not name:
            continue

        lower = name.lower()

        interesting = (
            lower in SERVER_CALL_NAMES
            or lower.endswith(".run")
            or lower == "run_app"
        )

        if not interesting:
            continue

        host = None
        port = None

        host_node = keyword_value(
            node,
            "host",
        )

        port_node = keyword_value(
            node,
            "port",
        )

        if host_node is not None:
            host = literal_string(
                host_node
            )

        if port_node is not None:
            port = literal_number(
                port_node
            )

        # Keep only server-like calls with useful evidence.
        if (
            host is None
            and port is None
            and "uvicorn" not in lower
            and "hypercorn" not in lower
            and "run_app" not in lower
        ):
            continue

        servers.append({
            "call": name,
            "host": host,
            "port": port,
            "line": getattr(
                node,
                "lineno",
                None,
            ),
            "confidence": "CONFIRMED_STATIC",
        })

    return servers


# =============================================================================
# INCLUDE ROUTER / BLUEPRINT CONNECTIONS
# =============================================================================

def detect_router_connections(tree: ast.AST):

    connections = []

    for node in ast.walk(tree):

        if not isinstance(node, ast.Call):
            continue

        name = get_call_name(
            node.func
        )

        if not name:
            continue

        method = name.split(".")[-1]

        if method not in {
            "include_router",
            "register_blueprint",
            "include",
        }:
            continue

        router = None

        if node.args:
            router = get_call_name(
                node.args[0]
            )

        prefix = None

        prefix_node = (
            keyword_value(
                node,
                "prefix",
            )
            or keyword_value(
                node,
                "url_prefix",
            )
        )

        if prefix_node is not None:
            prefix = literal_string(
                prefix_node
            )

        connections.append({
            "call": name,
            "router": router,
            "prefix": prefix,
            "line": getattr(
                node,
                "lineno",
                None,
            ),
            "confidence": "CONFIRMED_STATIC",
        })

    return connections


# =============================================================================
# FILE ANALYSIS
# =============================================================================

def analyze_python_file(path: Path):

    source = read_source(path)

    if source is None:

        return {
            "file": relative_string(path),
            "status": "UNREADABLE",
        }

    try:
        tree = ast.parse(
            source,
            filename=str(path),
        )

    except Exception as exc:

        return {
            "file": relative_string(path),
            "status": "PARSE_ERROR",
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
        }

    frameworks = detect_frameworks(
        tree
    )

    import_aliases = detect_import_aliases(
        tree
    )

    router_prefixes = (
        detect_router_prefixes(tree)
    )

    app_objects = detect_app_objects(
        tree
    )

    endpoints = []

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

            endpoint = (
                extract_decorator_endpoint(
                    decorator,
                    router_prefixes,
                )
            )

            if endpoint is None:
                continue

            framework = "UNKNOWN"

            if "FastAPI" in frameworks:
                framework = "FastAPI"

            elif "Flask" in frameworks:
                framework = "Flask"

            elif "Starlette" in frameworks:
                framework = "Starlette"

            elif frameworks:
                framework = sorted(
                    frameworks
                )[0]

            endpoint.update({
                "framework": framework,
                "function": node.name,
                "line": node.lineno,
                "source": "decorator",
                "confidence":
                    "CONFIRMED_STATIC",
            })

            endpoints.append(
                endpoint
            )

    if "Django" in frameworks:

        endpoints.extend(
            extract_django_paths(
                tree
            )
        )

    return {
        "file": relative_string(path),
        "status": "OK",
        "frameworks": sorted(
            frameworks
        ),
        "router_prefixes":
            router_prefixes,
        "app_objects":
            app_objects,
        "endpoints":
            endpoints,
        "server_calls":
            detect_server_calls(tree),
        "import_aliases":
            import_aliases,
        "router_connections":
            resolve_router_connections(
                detect_router_connections(
                    tree
                ),
                import_aliases,
            ),
    }


# =============================================================================
# RUNTIME 02 INTEGRATION
# =============================================================================

def runtime_report_path() -> Path:

    return (
        PROJECT_OUTPUT_ROOT
        / "LATEST"
        / "02_RUNTIME"
        / "RUNTIME_MAP.json"
    )


def load_runtime_report():

    path = runtime_report_path()

    if not path.is_file():

        return {
            "available": False,
            "path": str(path),
            "project_processes": [],
        }

    try:

        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:

        return {
            "available": False,
            "path": str(path),
            "error":
                f"{type(exc).__name__}: {exc}",
            "project_processes": [],
        }

    processes = []

    def walk(value):

        if isinstance(value, dict):

            command = (
                value.get("command_line")
                or value.get("command")
                or value.get("CommandLine")
            )

            if command:

                processes.append({
                    "pid":
                        value.get("pid")
                        or value.get("process_id")
                        or value.get("ProcessId"),
                    "command_line":
                        str(command),
                    "ports":
                        value.get(
                            "listening_ports",
                            value.get(
                                "ports",
                                [],
                            ),
                        ),
                })

            for child in value.values():
                walk(child)

        elif isinstance(value, list):

            for child in value:
                walk(child)

    # Prefer the project-process section when its
    # schema is available. Otherwise fall back to
    # generic discovery.
    preferred = None

    for key in (
        "project_processes",
        "processes_project",
        "python_project_processes",
    ):

        if isinstance(data.get(key), list):
            preferred = data[key]
            break

    if preferred is not None:
        walk(preferred)
    else:
        walk(data)

    unique = {}

    for process in processes:

        key = (
            process.get("pid"),
            process.get("command_line"),
        )

        unique[key] = process

    return {
        "available": True,
        "path": str(path),
        "project_processes":
            list(unique.values()),
    }


def normalize_relative_file(value: str) -> str:

    return str(value).replace(
        "/",
        "\\",
    ).lower()


def command_matches_file(
    command_line: str,
    relative_file: str,
) -> bool:

    import shlex

    relative_norm = normalize_relative_file(
        relative_file
    )

    absolute_norm = str(
        (
            PROJECT_ROOT
            / relative_file
        ).resolve()
    ).replace(
        "/",
        "\\",
    ).lower()

    try:
        tokens = shlex.split(
            command_line,
            posix=False,
        )
    except ValueError:
        tokens = command_line.split()

    clean_tokens = []

    for token in tokens:

        clean = str(token).strip(
            ' "\''
        )

        clean = clean.replace(
            "/",
            "\\",
        ).lower()

        clean_tokens.append(clean)

    # Absolute script invocation.
    if absolute_norm in clean_tokens:
        return True

    # Relative script invocation.
    relative_candidates = {
        relative_norm,
        relative_norm.replace(
            "\\",
            "/",
        ),
    }

    for token in clean_tokens:

        if token in relative_candidates:
            return True

    # Bare filename is accepted only when the
    # analyzed file itself is in PROJECT_ROOT.
    relative_path = Path(relative_file)

    if len(relative_path.parts) == 1:

        script_name = relative_path.name.lower()

        if script_name in clean_tokens:
            return True

    # Module invocation:
    # python -m package.module
    if relative_norm.endswith(".py"):

        module = relative_norm[:-3].replace(
            "\\",
            ".",
        )

        for index, token in enumerate(
            clean_tokens
        ):

            if token != "-m":
                continue

            if index + 1 >= len(clean_tokens):
                continue

            if clean_tokens[index + 1] == module:
                return True

    return False


def runtime_matches_for_file(
    relative_file: str,
    runtime_info,
):

    matches = []

    for process in runtime_info.get(
        "project_processes",
        [],
    ):

        command = process.get(
            "command_line",
            "",
        )

        if command_matches_file(
            command,
            relative_file,
        ):

            matches.append(process)

    return matches



def probable_historical_file(
    relative_file: str,
) -> bool:

    path = Path(relative_file)

    parts = [
        part.lower()
        for part in path.parts
    ]

    stem = path.stem.lower()

    historical_dirs = {
        "backup",
        "backups",
        "archive",
        "archives",
        "old",
        "legacy",
        "deprecated",
        "history",
        "historical",
    }

    if any(
        part in historical_dirs
        for part in parts[:-1]
    ):
        return True

    historical_tokens = (
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

    if any(
        token in stem
        for token in historical_tokens
    ):
        return True

    return False


def build_runtime_classification(
    file_results,
    runtime_info,
):

    classification = {}

    # -------------------------------------------------------------
    # 1. Direct runtime evidence
    # -------------------------------------------------------------

    for result in file_results:

        if result.get("status") != "OK":
            continue

        file_name = result.get("file")

        # Analyzer 06 must classify only components
        # that actually participate in the API/web layer.
        #
        # Other running project processes remain available
        # through Analyzer 02 / runtime_integration.
        has_api_role = bool(
            result.get("endpoints")
            or result.get("app_objects")
            or result.get("server_calls")
            or result.get("router_connections")
        )

        if not has_api_role:
            continue

        matches = runtime_matches_for_file(
            file_name,
            runtime_info,
        )

        if matches:

            classification[file_name] = {
                "classification":
                    "CONFIRMED_RUNTIME",
                "reason":
                    "api_file_matches_running_project_process",
                "runtime_processes":
                    matches,
                "connected_from":
                    [],
            }

    # -------------------------------------------------------------
    # 2. Router/import evidence from confirmed runtime applications
    # -------------------------------------------------------------

    changed = True

    while changed:

        changed = False

        for result in file_results:

            if result.get("status") != "OK":
                continue

            source_file = result.get("file")

            source_class = classification.get(
                source_file,
                {},
            ).get("classification")

            if source_class not in {
                "CONFIRMED_RUNTIME",
                "CONFIRMED_CONNECTED",
            }:
                continue

            for connection in result.get(
                "router_connections",
                [],
            ):

                target = connection.get(
                    "target_file"
                )

                if not target:
                    continue

                if target in classification:
                    continue

                classification[target] = {
                    "classification":
                        "CONFIRMED_CONNECTED",
                    "reason":
                        "router_imported_by_active_service",
                    "runtime_processes": [],
                    "connected_from": [
                        source_file
                    ],
                }

                changed = True

    # -------------------------------------------------------------
    # 3. Static-only API files
    # -------------------------------------------------------------

    for result in file_results:

        if result.get("status") != "OK":
            continue

        file_name = result.get("file")

        has_api_evidence = bool(
            result.get("endpoints")
            or result.get("app_objects")
            or result.get("server_calls")
            or result.get("router_connections")
        )

        if (
            has_api_evidence
            and file_name not in classification
        ):

            if probable_historical_file(
                file_name
            ):

                classification[file_name] = {
                    "classification":
                        "PROBABLE_HISTORICAL",
                    "reason":
                        "historical_naming_or_directory_signal_without_runtime_evidence",
                    "runtime_processes": [],
                    "connected_from": [],
                }

            else:

                classification[file_name] = {
                    "classification":
                        "STATIC_ONLY",
                    "reason":
                        "api_code_found_without_runtime_or_active_router_evidence",
                    "runtime_processes": [],
                    "connected_from": [],
                }

    return classification


def classify_endpoints(
    endpoints,
    file_classification,
):

    classified = []

    for endpoint in endpoints:

        item = dict(endpoint)

        evidence = file_classification.get(
            item.get("file"),
            {},
        )

        item["runtime_classification"] = (
            evidence.get(
                "classification",
                "UNKNOWN",
            )
        )

        item["runtime_reason"] = (
            evidence.get("reason")
        )

        classified.append(item)

    return classified



def service_ids_for_endpoint(
    endpoint,
    file_classification,
):

    file_name = endpoint.get("file")

    info = file_classification.get(
        file_name,
        {},
    )

    classification = info.get(
        "classification"
    )

    service_ids = []

    # Direct runtime application.
    if classification == "CONFIRMED_RUNTIME":

        for process in info.get(
            "runtime_processes",
            [],
        ):

            pid = process.get("pid")

            ports = process.get(
                "ports",
                [],
            ) or []

            if ports:

                for port in ports:

                    service_ids.append(
                        f"runtime:{pid}:port:{port}"
                    )

            elif pid is not None:

                service_ids.append(
                    f"runtime:{pid}"
                )

    # Router connected to an active application.
    elif classification == "CONFIRMED_CONNECTED":

        for source_file in info.get(
            "connected_from",
            [],
        ):

            source_info = (
                file_classification.get(
                    source_file,
                    {},
                )
            )

            for process in source_info.get(
                "runtime_processes",
                [],
            ):

                pid = process.get("pid")

                ports = process.get(
                    "ports",
                    [],
                ) or []

                if ports:

                    for port in ports:

                        service_ids.append(
                            f"runtime:{pid}:port:{port}"
                        )

                elif pid is not None:

                    service_ids.append(
                        f"runtime:{pid}"
                    )

    return sorted(set(service_ids))


def attach_service_ids(
    endpoints,
    file_classification,
):

    result = []

    for endpoint in endpoints:

        item = dict(endpoint)

        item["service_ids"] = (
            service_ids_for_endpoint(
                item,
                file_classification,
            )
        )

        result.append(item)

    return result


def detect_endpoint_overlaps(endpoints):

    mapping = defaultdict(list)

    for endpoint in endpoints:

        for method in endpoint.get(
            "methods",
            ["UNKNOWN"],
        ):

            key = (
                str(method).upper(),
                endpoint.get(
                    "path",
                    "/",
                ),
            )

            mapping[key].append(endpoint)

    same_service_conflicts = []
    cross_service_overlaps = []
    static_overlaps = []

    for (
        method,
        path,
    ), items in mapping.items():

        if len(items) < 2:
            continue

        active_items = [
            item
            for item in items
            if item.get(
                "runtime_classification"
            )
            in {
                "CONFIRMED_RUNTIME",
                "CONFIRMED_CONNECTED",
            }
        ]

        service_map = defaultdict(list)

        for item in active_items:

            for service_id in item.get(
                "service_ids",
                [],
            ):

                service_map[
                    service_id
                ].append(item)

        # Real candidate conflict:
        # same method + same path + same runtime service.
        for service_id, service_items in (
            service_map.items()
        ):

            unique_locations = {
                (
                    item.get("file"),
                    item.get("function"),
                    item.get("line"),
                )
                for item in service_items
            }

            if len(unique_locations) >= 2:

                same_service_conflicts.append({
                    "method": method,
                    "path": path,
                    "service_id":
                        service_id,
                    "occurrences":
                        len(unique_locations),
                    "locations": [
                        {
                            "file":
                                item.get("file"),
                            "function":
                                item.get(
                                    "function"
                                ),
                            "line":
                                item.get("line"),
                        }
                        for item in service_items
                    ],
                    "classification":
                        "SAME_SERVICE_ENDPOINT_CONFLICT",
                })

        active_service_ids = sorted({
            service_id
            for item in active_items
            for service_id in item.get(
                "service_ids",
                [],
            )
        })

        # Same URL exists, but on separate services.
        if len(active_service_ids) >= 2:

            cross_service_overlaps.append({
                "method": method,
                "path": path,
                "services":
                    active_service_ids,
                "classification":
                    "CROSS_SERVICE_ENDPOINT_REUSE",
            })

        if len(active_items) < 2:

            static_overlaps.append({
                "method": method,
                "path": path,
                "occurrences": len(items),
                "classification":
                    "STATIC_OR_INACTIVE_OVERLAP",
            })

    return {
        "same_service_conflicts":
            same_service_conflicts,
        "cross_service_overlaps":
            cross_service_overlaps,
        "static_or_inactive_overlaps":
            static_overlaps,
    }



# =============================================================================
# DUPLICATE ENDPOINTS
# =============================================================================

def detect_duplicates(endpoints):

    mapping = defaultdict(list)

    for endpoint in endpoints:

        methods = endpoint.get(
            "methods",
            ["UNKNOWN"],
        )

        path = endpoint.get(
            "path",
            "/",
        )

        for method in methods:

            key = (
                str(method).upper(),
                path,
            )

            mapping[key].append({
                "file": endpoint.get(
                    "file"
                ),
                "function": endpoint.get(
                    "function"
                ),
                "line": endpoint.get(
                    "line"
                ),
            })

    duplicates = []

    for (
        method,
        path,
    ), locations in mapping.items():

        if len(locations) < 2:
            continue

        duplicates.append({
            "method": method,
            "path": path,
            "occurrences":
                len(locations),
            "locations":
                locations,
            "classification":
                "POSSIBLE_DUPLICATE_ENDPOINT",
        })

    duplicates.sort(
        key=lambda item: (
            -item["occurrences"],
            item["path"],
            item["method"],
        )
    )

    return duplicates


# =============================================================================
# COMPLETE ANALYSIS
# =============================================================================

def analyze_api():

    active_files, historical_files = (
        get_active_python_files()
    )

    file_results = []

    all_endpoints = []
    all_server_calls = []
    all_router_connections = []
    all_app_objects = []

    framework_counter = Counter()

    parse_errors = []

    for path in active_files:

        result = analyze_python_file(
            path
        )

        file_results.append(
            result
        )

        if result.get("status") == "PARSE_ERROR":

            parse_errors.append({
                "file": result["file"],
                "error": result.get(
                    "error"
                ),
            })

            continue

        if result.get("status") != "OK":
            continue

        for framework in result.get(
            "frameworks",
            [],
        ):
            framework_counter[
                framework
            ] += 1

        for endpoint in result.get(
            "endpoints",
            [],
        ):

            endpoint = dict(endpoint)

            endpoint["file"] = (
                result["file"]
            )

            all_endpoints.append(
                endpoint
            )

        for server in result.get(
            "server_calls",
            [],
        ):

            server = dict(server)
            server["file"] = result["file"]

            all_server_calls.append(
                server
            )

        for connection in result.get(
            "router_connections",
            [],
        ):

            connection = dict(
                connection
            )

            connection["file"] = (
                result["file"]
            )

            all_router_connections.append(
                connection
            )

        for app_object in result.get(
            "app_objects",
            [],
        ):

            app_object = dict(
                app_object
            )

            app_object["file"] = (
                result["file"]
            )

            all_app_objects.append(
                app_object
            )

    runtime_info = load_runtime_report()

    file_classification = (
        build_runtime_classification(
            file_results,
            runtime_info,
        )
    )

    all_endpoints = classify_endpoints(
        all_endpoints,
        file_classification,
    )

    all_endpoints = attach_service_ids(
        all_endpoints,
        file_classification,
    )

    endpoint_overlaps = (
        detect_endpoint_overlaps(
            all_endpoints
        )
    )

    duplicates = detect_duplicates(
        all_endpoints
    )

    method_counter = Counter()

    websocket_count = 0

    for endpoint in all_endpoints:

        for method in endpoint.get(
            "methods",
            [],
        ):

            method_counter[
                method
            ] += 1

            if method == "WEBSOCKET":
                websocket_count += 1

    files_with_endpoints = len({
        endpoint["file"]
        for endpoint in all_endpoints
    })

    return {
        "metadata": {
            "analyzer":
                ANALYZER_NAME,

            "version":
                ANALYZER_VERSION,

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

            "analysis_type":
                "STATIC",

            "runtime_warning":
                (
                    "Static endpoint detection does "
                    "not prove that an endpoint is "
                    "currently active at runtime."
                ),
        },

        "summary": {
            "active_python_files":
                len(active_files),

            "historical_python_files_excluded":
                len(historical_files),

            "files_analyzed":
                sum(
                    1
                    for item in file_results
                    if item.get("status")
                    == "OK"
                ),

            "parse_errors":
                len(parse_errors),

            "files_with_endpoints":
                files_with_endpoints,

            "endpoints":
                len(all_endpoints),

            "websocket_endpoints":
                websocket_count,

            "app_router_objects":
                len(all_app_objects),

            "router_connections":
                len(
                    all_router_connections
                ),

            "server_calls":
                len(all_server_calls),

            "possible_duplicate_endpoints":
                len(duplicates),

            "runtime_report_available":
                runtime_info.get(
                    "available",
                    False,
                ),

            "confirmed_runtime_files":
                sum(
                    1
                    for item in
                    file_classification.values()
                    if item.get(
                        "classification"
                    )
                    == "CONFIRMED_RUNTIME"
                ),

            "confirmed_connected_files":
                sum(
                    1
                    for item in
                    file_classification.values()
                    if item.get(
                        "classification"
                    )
                    == "CONFIRMED_CONNECTED"
                ),

            "static_only_files":
                sum(
                    1
                    for item in
                    file_classification.values()
                    if item.get(
                        "classification"
                    )
                    == "STATIC_ONLY"
                ),

            "probable_historical_files":
                sum(
                    1
                    for item in
                    file_classification.values()
                    if item.get(
                        "classification"
                    )
                    == "PROBABLE_HISTORICAL"
                ),

            "same_service_endpoint_conflicts":
                len(
                    endpoint_overlaps[
                        "same_service_conflicts"
                    ]
                ),

            "cross_service_endpoint_reuse":
                len(
                    endpoint_overlaps[
                        "cross_service_overlaps"
                    ]
                ),
        },

        "frameworks":
            dict(framework_counter),

        "http_methods":
            dict(method_counter),

        "endpoints":
            all_endpoints,

        "app_router_objects":
            all_app_objects,

        "router_connections":
            all_router_connections,

        "server_calls":
            all_server_calls,

        "possible_duplicate_endpoints":
            duplicates,

        "runtime_integration":
            runtime_info,

        "file_runtime_classification":
            file_classification,

        "endpoint_overlaps":
            endpoint_overlaps,

        "parse_errors":
            parse_errors,

        "historical_files_excluded":
            historical_files,

        "file_analysis":
            file_results,
    }


# =============================================================================
# OUTPUT
# =============================================================================

def write_report(result):

    ensure_output_directories()

    output_dir = (
        PROJECT_OUTPUT_ROOT
        / "LATEST"
        / "06_API_ENDPOINTS"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        output_dir
        / "API_ENDPOINTS_MAP.json"
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

def main():

    print("=" * 100)
    print(
        "PYTHON PROJECT INTELLIGENCE"
    )
    print(
        "ANALYZER 06 - "
        "API / ENDPOINTS"
    )
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
    print(
        "Analisi API, router, endpoint "
        "e configurazioni server..."
    )
    print()

    result = analyze_api()

    summary = result["summary"]

    print(
        f"File Python attivi : "
        f"{summary['active_python_files']}"
    )

    print(
        f"Storici esclusi    : "
        f"{summary['historical_python_files_excluded']}"
    )

    print(
        f"File analizzati    : "
        f"{summary['files_analyzed']}"
    )

    print(
        f"Parse error        : "
        f"{summary['parse_errors']}"
    )

    print(
        f"File con endpoint  : "
        f"{summary['files_with_endpoints']}"
    )

    print(
        f"Endpoint statici   : "
        f"{summary['endpoints']}"
    )

    print(
        f"WebSocket          : "
        f"{summary['websocket_endpoints']}"
    )

    print(
        f"App/router objects : "
        f"{summary['app_router_objects']}"
    )

    print(
        f"Router connections : "
        f"{summary['router_connections']}"
    )

    print(
        f"Server calls       : "
        f"{summary['server_calls']}"
    )

    print(
        f"Overlap statici     : "
        f"{summary['possible_duplicate_endpoints']}"
    )

    if result["frameworks"]:

        print()
        print("FRAMEWORK RILEVATI:")

        for framework, count in sorted(
            result["frameworks"].items(),
            key=lambda item: (
                -item[1],
                item[0],
            ),
        ):

            print(
                f"  {count:>3} file <- "
                f"{framework}"
            )

    if result["http_methods"]:

        print()
        print("METODI / ENDPOINT:")

        for method, count in sorted(
            result["http_methods"].items()
        ):

            print(
                f"  {method:<10} "
                f"{count}"
            )

    if result["endpoints"]:

        print()
        print("PRIMI ENDPOINT RILEVATI:")

        for endpoint in result[
            "endpoints"
        ][:30]:

            methods = ",".join(
                endpoint.get(
                    "methods",
                    ["UNKNOWN"],
                )
            )

            print(
                f"  {methods:<12} "
                f"{endpoint.get('path', ''):<35} "
                f"<- {endpoint.get('file', '')}:"
                f"{endpoint.get('line', '')}"
            )

    if result[
        "possible_duplicate_endpoints"
    ]:

        print()
        print(
            "OVERLAP STATICI RILEVATI NEL CODICE:"
        )

        for duplicate in result[
            "possible_duplicate_endpoints"
        ][:20]:

            print(
                f"  {duplicate['method']:<10} "
                f"{duplicate['path']} "
                f"({duplicate['occurrences']}x)"
            )

    output_file = write_report(
        result
    )

    print()
    print(
        f"Report JSON         : "
        f"{output_file}"
    )

    print()
    print(
        "NOTA               : endpoint "
        "CONFIRMED_STATIC = presente nel "
        "codice, NON necessariamente attivo "
        "a runtime."
    )

    print()
    print(
        "ANALYZER STATUS: "
        + (
            "OK"
            if not result["parse_errors"]
            else "ATTENTION"
        )
    )

    print("=" * 100)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
