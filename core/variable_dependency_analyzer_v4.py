from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from variable_dependency_analyzer_v2 import inspect_expression


def make_event(node, kind, value, context, target=None):
    details = inspect_expression(value)

    return {
        "type": kind,
        "target": target,
        "depends_on_variables": details["variables"],
        "calls": details["function_calls"],
        "expression": ast.unparse(value),
        "line": node.lineno,
        "context": list(context),
    }


def walk_block(statements, context=()):
    events = []

    for node in statements:

        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    events.append(
                        make_event(
                            node, "assignment",
                            node.value, context, target.id
                        )
                    )

        elif isinstance(node, ast.AnnAssign) and node.value:
            if isinstance(node.target, ast.Name):
                events.append(
                    make_event(
                        node, "assignment",
                        node.value, context, node.target.id
                    )
                )

        elif isinstance(node, ast.Return) and node.value:
            events.append(
                make_event(
                    node, "return",
                    node.value, context, "<return>"
                )
            )

        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            events.append(
                make_event(
                    node, "call",
                    node.value, context
                )
            )

        elif isinstance(node, (ast.Try, ast.TryStar)):
            events.extend(
                walk_block(node.body, (*context, "try"))
            )

            for index, handler in enumerate(node.handlers):
                events.extend(
                    walk_block(
                        handler.body,
                        (*context, f"except_{index}")
                    )
                )

            events.extend(
                walk_block(node.orelse, (*context, "try_else"))
            )

            events.extend(
                walk_block(node.finalbody, (*context, "finally"))
            )

        elif isinstance(node, ast.If):
            condition = ast.unparse(node.test)

            events.extend(
                walk_block(
                    node.body,
                    (*context, f"if: {condition}")
                )
            )

            events.extend(
                walk_block(
                    node.orelse,
                    (*context, f"else: {condition}")
                )
            )

        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            kind = type(node).__name__

            events.extend(
                walk_block(node.body, (*context, kind))
            )

            events.extend(
                walk_block(node.orelse, (*context, f"{kind}_else"))
            )

        elif isinstance(node, (ast.With, ast.AsyncWith)):
            events.extend(
                walk_block(
                    node.body,
                    (*context, type(node).__name__)
                )
            )

    return events


def analyze_dependencies_v4(path):
    path = Path(path)

    result = {
        "file": str(path),
        "status": "STATIC_OPERATIONS_V4",
        "functions": [],
        "limitations": [
            "Il codice non viene eseguito.",
            "Gli eventi rappresentano istruzioni presenti nel sorgente.",
            "I rami condizionali non sono valutati.",
            "I cicli non vengono simulati.",
            "Non tutte le forme di assegnazione sono supportate.",
            "Le chiamate non provano che le operazioni avvengano a runtime.",
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
                "events": walk_block(node.body),
            })

    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python variable_dependency_analyzer_v4.py PERCORSO_FILE"
        )

    print(json.dumps(
        analyze_dependencies_v4(sys.argv[1]),
        indent=2,
        ensure_ascii=False,
    ))
