from __future__ import annotations

import ast
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


# =============================================================================
# PYTHON PROJECT INTELLIGENCE
# ANALYZER 04 - UNIVERSAL CODE CONNECTIONS / CALL GRAPH
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


ANALYZER_NAME = "04_code_connections"
ANALYZER_VERSION = "2.0"


def relative_string(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def module_name_from_path(path: Path) -> str:

    relative = path.resolve().relative_to(PROJECT_ROOT.resolve())

    parts = list(relative.parts)

    if not parts:
        return ""

    filename = parts[-1]

    if filename == "__init__.py":
        parts = parts[:-1]
    else:
        parts[-1] = Path(filename).stem

    return ".".join(parts)


def build_local_module_map(files: list[Path]) -> dict[str, str]:

    result = {}

    for path in files:

        module = module_name_from_path(path)

        if module:
            result[module] = relative_string(path)

        # Permette di riconoscere anche import del modulo root.
        stem = path.stem

        if stem != "__init__":
            result.setdefault(
                stem,
                relative_string(path),
            )

    return result


def get_top_module(module: str) -> str:

    if not module:
        return ""

    return module.split(".")[0]


def classify_import(
    module: str,
    local_modules: dict[str, str],
) -> tuple[str, str | None]:

    if not module:
        return "unknown", None

    # Match esatto.
    if module in local_modules:
        return "internal", local_modules[module]

    # Match gerarchico.
    candidates = sorted(
        local_modules.keys(),
        key=len,
        reverse=True,
    )

    for candidate in candidates:

        if module.startswith(candidate + "."):
            return "internal", local_modules[candidate]

    top = get_top_module(module)

    if top in sys.stdlib_module_names:
        return "standard_library", None

    # Staticamente non possiamo ancora sapere con certezza
    # se è installato nell'ambiente.
    return "external_or_unresolved", None


def resolve_relative_import(
    current_module: str,
    level: int,
    imported_module: str | None,
) -> str:

    parts = current_module.split(".")

    # Il file stesso non è un package.
    if parts:
        parts = parts[:-1]

    if level > 1:
        remove_count = level - 1

        if remove_count <= len(parts):
            parts = parts[:-remove_count]
        else:
            parts = []

    if imported_module:
        parts.extend(imported_module.split("."))

    return ".".join(
        part for part in parts if part
    )


def dotted_call_name(node: ast.AST) -> str | None:

    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):

        parent = dotted_call_name(node.value)

        if parent:
            return f"{parent}.{node.attr}"

        return node.attr

    return None


class CodeVisitor(ast.NodeVisitor):

    def __init__(
        self,
        current_module: str,
        local_modules: dict[str, str],
    ):

        self.current_module = current_module
        self.local_modules = local_modules

        self.imports = []
        self.functions = []
        self.classes = []
        self.calls = Counter()

        self.async_functions = 0

    def visit_Import(self, node: ast.Import):

        for alias in node.names:

            module = alias.name

            classification, target = classify_import(
                module,
                self.local_modules,
            )

            self.imports.append({
                "module": module,
                "name": None,
                "alias": alias.asname,
                "level": 0,
                "classification": classification,
                "target_file": target,
                "line": node.lineno,
            })

        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):

        base_module = node.module or ""

        if node.level:

            resolved_base = resolve_relative_import(
                self.current_module,
                node.level,
                base_module,
            )

        else:
            resolved_base = base_module

        for alias in node.names:

            candidate = resolved_base

            # from package import module
            possible_child = (
                f"{resolved_base}.{alias.name}"
                if resolved_base
                else alias.name
            )

            if possible_child in self.local_modules:
                candidate = possible_child

            classification, target = classify_import(
                candidate,
                self.local_modules,
            )

            self.imports.append({
                "module": candidate,
                "name": alias.name,
                "alias": alias.asname,
                "level": node.level,
                "classification": classification,
                "target_file": target,
                "line": node.lineno,
            })

        self.generic_visit(node)

    def visit_FunctionDef(
        self,
        node: ast.FunctionDef,
    ):

        self.functions.append({
            "name": node.name,
            "line": node.lineno,
            "async": False,
        })

        self.generic_visit(node)

    def visit_AsyncFunctionDef(
        self,
        node: ast.AsyncFunctionDef,
    ):

        self.async_functions += 1

        self.functions.append({
            "name": node.name,
            "line": node.lineno,
            "async": True,
        })

        self.generic_visit(node)

    def visit_ClassDef(
        self,
        node: ast.ClassDef,
    ):

        self.classes.append({
            "name": node.name,
            "line": node.lineno,
        })

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):

        name = dotted_call_name(node.func)

        if name:
            self.calls[name] += 1

        self.generic_visit(node)


def analyze_file(
    path: Path,
    local_modules: dict[str, str],
) -> dict:

    relative = relative_string(path)
    module = module_name_from_path(path)

    result = {
        "path": relative,
        "module": module,
        "parse_status": "UNKNOWN",
        "parse_error": None,
        "imports": [],
        "functions": [],
        "classes": [],
        "calls": [],
    }

    try:

        text = path.read_text(
            encoding="utf-8-sig",
            errors="ignore",
        )

        tree = ast.parse(
            text,
            filename=str(path),
        )

        visitor = CodeVisitor(
            module,
            local_modules,
        )

        visitor.visit(tree)

        result["parse_status"] = "CONFIRMED"

        result["imports"] = visitor.imports
        result["functions"] = visitor.functions
        result["classes"] = visitor.classes

        result["calls"] = [
            {
                "name": name,
                "count": count,
            }
            for name, count in visitor.calls.most_common()
        ]

    except SyntaxError as exc:

        result["parse_status"] = "FAILED"

        result["parse_error"] = {
            "type": "SyntaxError",
            "line": exc.lineno,
            "message": str(exc),
        }

    except Exception as exc:

        result["parse_status"] = "FAILED"

        result["parse_error"] = {
            "type": type(exc).__name__,
            "line": None,
            "message": str(exc),
        }

    return result


def analyze_connections() -> dict:

    # -------------------------------------------------------------------------
    # Python files belonging to the actual target project.
    #
    # project_context already excludes python_project_intelligence itself.
    # During the V1 -> V2 migration we also exclude the legacy
    # site_intelligence directory, otherwise the old analyzer source code
    # contaminates the project dependency graph.
    # -------------------------------------------------------------------------

    legacy_intelligence_root = (
        PROJECT_ROOT / "site_intelligence"
    ).resolve()

    python_files = []

    for path in iter_python_files():

        resolved = path.resolve()

        try:
            resolved.relative_to(
                legacy_intelligence_root
            )

            # File belongs to legacy Site Intelligence.
            continue

        except ValueError:
            pass

        python_files.append(path)

    python_files = sorted(
        python_files,
        key=lambda path: str(path).lower(),
    )

    local_modules = build_local_module_map(
        python_files
    )

    file_results = []

    internal_edges = []
    external_imports = defaultdict(set)
    standard_imports = defaultdict(set)

    parse_errors = []

    reverse_dependencies = defaultdict(set)

    total_imports = 0

    for path in python_files:

        result = analyze_file(
            path,
            local_modules,
        )

        file_results.append(result)

        if result["parse_status"] != "CONFIRMED":

            parse_errors.append({
                "file": result["path"],
                "error": result["parse_error"],
            })

            continue

        for item in result["imports"]:

            total_imports += 1

            classification = item[
                "classification"
            ]

            if classification == "internal":

                edge = {
                    "source_file": result["path"],
                    "target_file": item["target_file"],
                    "module": item["module"],
                    "line": item["line"],
                    "confidence": "CONFIRMED",
                }

                internal_edges.append(edge)

                reverse_dependencies[
                    item["target_file"]
                ].add(result["path"])

            elif classification == "standard_library":

                standard_imports[
                    item["module"]
                ].add(result["path"])

            else:

                external_imports[
                    item["module"]
                ].add(result["path"])

    # -------------------------------------------------------------------------
    # Centralità semplice:
    # quanti altri file dipendono da ogni file.
    # -------------------------------------------------------------------------

    most_depended_on = []

    for target, sources in reverse_dependencies.items():

        most_depended_on.append({
            "file": target,
            "dependent_files": len(sources),
            "dependents": sorted(sources),
        })

    most_depended_on.sort(
        key=lambda item: (
            -item["dependent_files"],
            item["file"].lower(),
        )
    )

    return {
        "metadata": {
            "analyzer": ANALYZER_NAME,
            "version": ANALYZER_VERSION,

            "generated_utc":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "project_name": PROJECT_NAME,
            "project_root": str(PROJECT_ROOT),
            "intelligence_root":
                str(INTELLIGENCE_ROOT),

            "analysis_type":
                "STATIC_AST_ANALYSIS",

            "important_note":
                (
                    "Static analysis cannot prove every dynamic import "
                    "or runtime call. external_or_unresolved does not "
                    "automatically mean missing dependency."
                ),
        },

        "summary": {
            "python_files": len(python_files),

            "parsed_files": (
                len(python_files)
                - len(parse_errors)
            ),

            "parse_errors":
                len(parse_errors),

            "total_import_statements":
                total_imports,

            "internal_connections":
                len(internal_edges),

            "external_or_unresolved_modules":
                len(external_imports),

            "standard_library_modules":
                len(standard_imports),

            "files_with_incoming_dependencies":
                len(reverse_dependencies),
        },

        "internal_connections":
            internal_edges,

        "reverse_dependencies": {
            target: sorted(sources)
            for target, sources
            in reverse_dependencies.items()
        },

        "most_depended_on":
            most_depended_on,

        "external_or_unresolved": {
            module: sorted(files)
            for module, files
            in sorted(external_imports.items())
        },

        "standard_library": {
            module: sorted(files)
            for module, files
            in sorted(standard_imports.items())
        },

        "parse_errors":
            parse_errors,

        "files":
            file_results,
    }


def write_report(result: dict) -> Path:

    ensure_output_directories()

    output_dir = (
        PROJECT_OUTPUT_ROOT
        / "LATEST"
        / "04_CODE_CONNECTIONS"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        output_dir
        / "CODE_CONNECTIONS.json"
    )

    with output_file.open(
        "w",
        encoding="utf-8-sig",
    ) as handle:

        json.dump(
            result,
            handle,
            indent=2,
            ensure_ascii=False,
        )

    return output_file


def main() -> int:

    print("=" * 100)
    print("PYTHON PROJECT INTELLIGENCE")
    print("ANALYZER 04 - CODE CONNECTIONS / CALL GRAPH")
    print("=" * 100)

    print(f"Project name       : {PROJECT_NAME}")
    print(f"Project root       : {PROJECT_ROOT}")

    print()
    print(
        "Analisi AST di import, funzioni, "
        "classi e connessioni interne..."
    )
    print()

    result = analyze_connections()
    summary = result["summary"]

    print(
        f"File Python        : "
        f"{summary['python_files']}"
    )

    print(
        f"File analizzati    : "
        f"{summary['parsed_files']}"
    )

    print(
        f"Parse error        : "
        f"{summary['parse_errors']}"
    )

    print(
        f"Import             : "
        f"{summary['total_import_statements']}"
    )

    print(
        f"Connessioni interne: "
        f"{summary['internal_connections']}"
    )

    print(
        f"Moduli standard    : "
        f"{summary['standard_library_modules']}"
    )

    print(
        f"Esterni/unresolved : "
        f"{summary['external_or_unresolved_modules']}"
    )

    print(
        f"Target dipendenze  : "
        f"{summary['files_with_incoming_dependencies']}"
    )

    print()
    print("MODULI INTERNI PIU' UTILIZZATI:")

    top = result["most_depended_on"][:15]

    if top:

        for item in top:

            print(
                f"  {item['dependent_files']:>3} <- "
                f"{item['file']}"
            )

    else:

        print("  Nessuna connessione interna rilevata.")

    if result["parse_errors"]:

        print()
        print("PARSE ERROR:")

        for item in result["parse_errors"][:20]:

            error = item["error"] or {}

            print(
                f"  {item['file']} "
                f"| line={error.get('line')} "
                f"| {error.get('message')}"
            )

    output_file = write_report(result)

    print()
    print(
        f"Report JSON         : {output_file}"
    )

    print()

    if summary["parse_errors"]:

        print(
            "ANALYZER STATUS: ATTENTION "
            "(alcuni file non analizzabili via AST)"
        )

    else:

        print("ANALYZER STATUS: OK")

    print("=" * 100)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

