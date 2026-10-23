from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


def read_names(node):
    return sorted({
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name)
        and isinstance(child.ctx, ast.Load)
    })


def analyze_dependencies(path):
    path = Path(path)

    result = {
        "file": str(path),
        "status": "STATIC_VARIABLE_DEPENDENCIES",
        "functions": [],
        "limitations": [
            "Dipendenze ricavate sintatticamente, senza eseguire il codice.",
            "Non vengono risolte condizioni, cicli, alias o mutazioni.",
            "Le dipendenze non dimostrano il passaggio effettivo dei dati a runtime.",
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

                for target in targets:
                    dependencies.append({
                        "target": target,
                        "depends_on": read_names(statement.value),
                        "expression": ast.unparse(statement.value),
                        "line": statement.lineno,
                    })

            elif isinstance(statement, ast.Return) and statement.value:
                dependencies.append({
                    "target": "<return>",
                    "depends_on": read_names(statement.value),
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
            "Uso: python variable_dependency_analyzer.py PERCORSO_FILE"
        )

    print(json.dumps(
        analyze_dependencies(sys.argv[1]),
        indent=2,
        ensure_ascii=False,
    ))
