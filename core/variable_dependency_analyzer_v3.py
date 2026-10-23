from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from variable_dependency_analyzer_v2 import inspect_expression


def dependency(node, target, value, context):
    details = inspect_expression(value)

    return {
        "target": target,
        "depends_on_variables": details["variables"],
        "calls": details["function_calls"],
        "expression": ast.unparse(value),
        "line": node.lineno,
        "context": list(context),
    }


def walk_block(statements, context=()):
    results = []

    for node in statements:

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    results.append(
                        dependency(
                            node,
                            target.id,
                            node.value,
                            context,
                        )
                    )

        elif isinstance(node, ast.AnnAssign) and node.value:
            if isinstance(node.target, ast.Name):
                results.append(
                    dependency(
                        node,
                        node.target.id,
                        node.value,
                        context,
                    )
                )

        elif isinstance(node, ast.Return) and node.value:
            results.append(
                dependency(
                    node,
                    "<return>",
                    node.value,
                    context,
                )
            )

        elif isinstance(node, (ast.Try, ast.TryStar)):
            results.extend(
                walk_block(node.body, (*context, "try"))
            )

            for index, handler in enumerate(node.handlers):
                results.extend(
                    walk_block(
                        handler.body,
                        (*context, f"except_{index}"),
                    )
                )

            results.extend(
                walk_block(node.orelse, (*context, "try_else"))
            )

            results.extend(
                walk_block(node.finalbody, (*context, "finally"))
            )

        elif isinstance(node, ast.If):
            condition = ast.unparse(node.test)

            results.extend(
                walk_block(
                    node.body,
                    (*context, f"if: {condition}"),
                )
            )

            results.extend(
                walk_block(
                    node.orelse,
                    (*context, f"else: {condition}"),
                )
            )

        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            results.extend(
                walk_block(
                    node.body,
                    (*context, type(node).__name__),
                )
            )

            results.extend(
                walk_block(
                    node.orelse,
                    (*context, f"{type(node).__name__}_else"),
                )
            )

        elif isinstance(node, (ast.With, ast.AsyncWith)):
            results.extend(
                walk_block(
                    node.body,
                    (*context, type(node).__name__),
                )
            )

    return results


def analyze_dependencies_v3(path):
    path = Path(path)

    result = {
        "file": str(path),
        "status": "STATIC_DEPENDENCIES_V3",
        "functions": [],
        "limitations": [
            "Analisi statica: il codice non viene eseguito.",
            "I context indicano rami sintattici, non percorsi eseguiti.",
            "Le dipendenze dei cicli non sono simulate.",
            "Le condizioni e le mutazioni non sono risolte.",
            "Non vengono analizzate tutte le forme di assegnazione.",
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
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result["functions"].append({
                "name": node.name,
                "line": node.lineno,
                "dependencies": walk_block(node.body),
            })

    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python variable_dependency_analyzer_v3.py PERCORSO_FILE"
        )

    print(
        json.dumps(
            analyze_dependencies_v3(sys.argv[1]),
            indent=2,
            ensure_ascii=False,
        )
    )
