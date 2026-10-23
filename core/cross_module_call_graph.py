from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


def analyze_project(root, entry_file="app.py"):
    root = Path(root).resolve()

    result = {
        "project": str(root),
        "entry_file": entry_file,
        "status": "STATIC_CROSS_MODULE_GRAPH",
        "modules": {},
        "call_trees": [],
        "limitations": [
            "Il codice non viene eseguito.",
            "Sono risolti solo import statici verso moduli del progetto.",
            "Gli import relativi, i package complessi e il dispatch dinamico richiedono ulteriori sviluppi.",
            "Le chiamate a metodi di oggetti non sono risolte.",
            "Il grafo non dimostra che le chiamate avvengano durante l'esecuzione.",
        ],
    }

    if not root.is_dir():
        result["status"] = "ANALYSIS_ERROR"
        result["error"] = "Cartella progetto non trovata."
        return result

    paths = sorted(root.rglob("*.py"))

    # Esclusioni centralizzate del progetto.
    from project_context import is_excluded

    paths = [
        path for path in paths
        if not is_excluded(path)
    ]

    trees = {}

    for path in paths:
        relative = path.relative_to(root)
        module_name = ".".join(relative.with_suffix("").parts)

        if relative.name == "__init__.py":
            module_name = ".".join(relative.parent.parts)

        try:
            tree = ast.parse(
                path.read_text(encoding="utf-8-sig"),
                filename=str(path),
            )
        except (OSError, UnicodeError, SyntaxError) as exc:
            result["modules"][module_name] = {
                "file": str(relative),
                "status": "ANALYSIS_ERROR",
                "error": str(exc),
            }
            continue

        trees[module_name] = tree

        functions = {
            node.name: node
            for node in tree.body
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            )
        }

        imports = {}

        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    if not node.module:
                        continue

                    target_module = node.module

                else:
                    # Il percorso relativo parte dal package
                    # che contiene il modulo corrente.
                    if relative.name == "__init__.py":
                        package_parts = list(relative.parent.parts)
                    else:
                        package_parts = list(relative.parent.parts)

                    # Un punto mantiene il package corrente;
                    # due punti risalgono di un livello.
                    levels_up = node.level - 1

                    if levels_up > len(package_parts):
                        continue

                    if levels_up:
                        package_parts = package_parts[:-levels_up]

                    if node.module:
                        package_parts.extend(node.module.split("."))

                    target_module = ".".join(package_parts)

                    if not target_module:
                        continue

                for alias in node.names:
                    imports[alias.asname or alias.name] = {
                        "module": target_module,
                        "symbol": alias.name,
                    }

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports[alias.asname or alias.name.split(".")[0]] = {
                        "module": alias.name,
                        "symbol": None,
                    }

        result["modules"][module_name] = {
            "file": str(relative),
            "status": "PARSED",
            "functions": sorted(functions),
            "imports": imports,
        }

    def resolve_import_module(current_module, imported_module):
        if imported_module in result["modules"]:
            return imported_module

        parts = current_module.split(".")

        for depth in range(len(parts) - 1, 0, -1):
            candidate = ".".join(
                parts[:depth] + [imported_module]
            )

            if candidate in result["modules"]:
                return candidate

        return imported_module

    def resolve_call(current_module, call):
        if isinstance(call.func, ast.Name):
            name = call.func.id

            info = result["modules"].get(current_module, {})

            if name in info.get("functions", []):
                return current_module, name

            imported = info.get("imports", {}).get(name)

            if imported and imported["symbol"]:
                target_module = resolve_import_module(
                    current_module,
                    imported["module"]
                )
                target_function = imported["symbol"]

                if target_function in result["modules"].get(
                    target_module, {}
                ).get("functions", []):
                    return target_module, target_function

        if isinstance(call.func, ast.Attribute):
            if isinstance(call.func.value, ast.Name):
                alias = call.func.value.id

                info = result["modules"].get(current_module, {})
                imported = info.get("imports", {}).get(alias)

                if imported and imported["symbol"] is None:
                    target_module = resolve_import_module(
                        current_module,
                        imported["module"]
                    )
                    target_function = call.func.attr

                    if target_function in result["modules"].get(
                        target_module, {}
                    ).get("functions", []):
                        return target_module, target_function

        return None

    def get_function(module_name, function_name):
        tree = trees.get(module_name)

        if tree is None:
            return None

        for node in tree.body:
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ) and node.name == function_name:
                return node

        return None

    def expand(module_name, function_name, stack=()):
        key = (module_name, function_name)

        if key in stack:
            return {
                "module": module_name,
                "function": function_name,
                "status": "RECURSIVE_REFERENCE",
                "children": [],
            }

        node = get_function(module_name, function_name)

        if node is None:
            return {
                "module": module_name,
                "function": function_name,
                "status": "UNRESOLVED",
                "children": [],
            }

        children = []

        calls = sorted(
            (
                item
                for item in ast.walk(node)
                if isinstance(item, ast.Call)
            ),
            key=lambda item: (
                item.lineno,
                item.col_offset,
            ),
        )

        for call in calls:
            target = resolve_call(module_name, call)

            if target is None:
                children.append({
                    "line": call.lineno,
                    "expression": ast.unparse(call),
                    "status": "EXTERNAL_OR_UNRESOLVED",
                })
            else:
                children.append({
                    "line": call.lineno,
                    "expression": ast.unparse(call),
                    "status": "RESOLVED",
                    "callee": expand(
                        target[0],
                        target[1],
                        stack + (key,),
                    ),
                })

        return {
            "module": module_name,
            "function": function_name,
            "status": "RESOLVED",
            "children": children,
        }

    entry_path = Path(entry_file)
    entry_module = ".".join(entry_path.with_suffix("").parts)

    tree = trees.get(entry_module)

    if tree is None:
        result["status"] = "ANALYSIS_ERROR"
        result["error"] = f"Entrypoint non trovato: {entry_file}"
        return result

    for node in tree.body:
        if not isinstance(node, ast.If):
            continue

        if ast.unparse(node.test) != "__name__ == '__main__'":
            continue

        calls = sorted(
            (
                item
                for statement in node.body
                for item in ast.walk(statement)
                if isinstance(item, ast.Call)
            ),
            key=lambda item: (
                item.lineno,
                item.col_offset,
            ),
        )

        for call in calls:
            target = resolve_call(entry_module, call)

            item = {
                "line": call.lineno,
                "expression": ast.unparse(call),
            }

            if target is None:
                item["status"] = "EXTERNAL_OR_UNRESOLVED"
            else:
                item["status"] = "RESOLVED"
                item["tree"] = expand(
                    target[0],
                    target[1],
                )

            result["call_trees"].append(item)

    return result


def describe_graph(result):
    lines = [
        "# GRAFO DELLE CHIAMATE TRA MODULI",
        "",
        f"Progetto: `{result['project']}`",
        f"Entrypoint: `{result['entry_file']}`",
        "",
    ]

    def describe_node(node, depth=0):
        prefix = "  " * depth

        lines.append(
            f"{prefix}- "
            f"{node['module']}.{node['function']} "
            f"[{node['status']}]"
        )

        for child in node["children"]:
            lines.append(
                f"{prefix}  - Riga {child['line']}: "
                f"`{child['expression']}` "
                f"[{child['status']}]"
            )

            if "callee" in child:
                describe_node(
                    child["callee"],
                    depth + 2,
                )

    for call in result["call_trees"]:
        lines.append(
            f"## Riga {call['line']}: "
            f"`{call['expression']}`"
        )
        lines.append("")

        if "tree" in call:
            describe_node(call["tree"])
        else:
            lines.append(
                f"- {call['status']}"
            )

        lines.append("")

    lines.append("## Limiti")
    lines.append("")

    for limitation in result["limitations"]:
        lines.append(f"- {limitation}")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(
            "Uso: python cross_module_call_graph.py "
            "CARTELLA_PROGETTO ENTRYPOINT"
        )

    result = analyze_project(
        sys.argv[1],
        sys.argv[2],
    )

    if result["status"] == "ANALYSIS_ERROR":
        print(json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        ))
        raise SystemExit(1)

    print(describe_graph(result))
