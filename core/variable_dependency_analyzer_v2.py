from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


def inspect_expression(node):
    calls = sorted({
        ast.unparse(child.func)
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
    })

    call_name_nodes = {
        id(child.func)
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
    }

    variables = sorted({
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name)
        and isinstance(child.ctx, ast.Load)
        and id(child) not in call_name_nodes
    })

    return {
        "variables": variables,
        "function_calls": calls,
    }


def analyze_dependencies_v2(path):
    path = Path(path)

    result = {
        "file": str(path),
        "status": "STATIC_DEPENDENCIES_V2",
        "functions": [],
        "limitations": [
            "Analisi statica: nessun codice del progetto viene eseguito.",
            "Le chiamate indirette e gli alias non sono risolti.",
            "Gli attributi e le chiamate dinamiche possono produrre classificazioni incomplete.",
            "Le condizioni, i cicli e le mutazioni non sono ancora analizzati.",
        ],
    }

    try:
        tree = ast.parse(
            path.read_text(encoding="utf-8-sig"),
            filename=str(path),
        )
    except (OSError, UnicodeError, SyntaxError) as exc:
        result["status"] = "ANALYSIS_ERROR"
        result["error"] = str(exc)
        return result

    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        dependencies = []

        for statement in node.body:
            if isinstance(statement, ast.Assign):
                targets = [
                    target.id
                    for target in statement.targets
                    if isinstance(target, ast.Name)
                ]

                details = inspect_expression(statement.value)

                for target in targets:
                    dependencies.append({
                        "target": target,
                        "depends_on_variables": details["variables"],
                        "calls": details["function_calls"],
                        "expression": ast.unparse(statement.value),
                        "line": statement.lineno,
                    })

            elif isinstance(statement, ast.Return) and statement.value:
                details = inspect_expression(statement.value)

                dependencies.append({
                    "target": "<return>",
                    "depends_on_variables": details["variables"],
                    "calls": details["function_calls"],
                    "expression": ast.unparse(statement.value),
                    "line": statement.lineno,
                })

        result["functions"].append({
            "name": node.name,
            "dependencies": dependencies,
        })

    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python variable_dependency_analyzer_v2.py PERCORSO_FILE"
        )

    print(json.dumps(
        analyze_dependencies_v2(sys.argv[1]),
        indent=2,
        ensure_ascii=False,
    ))
