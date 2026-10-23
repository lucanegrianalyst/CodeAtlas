from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

from functional_interpreter_v3 import (
    analyze_statement,
    expression,
)


def analyze_block(statements):
    return [analyze_recursive(node) for node in statements]


def analyze_recursive(node):
    if isinstance(node, (ast.Try, ast.TryStar)):
        return {
            "type": "try",
            "line": node.lineno,
            "body": analyze_block(node.body),
            "handlers": [
                {
                    "exception": expression(handler.type),
                    "name": handler.name,
                    "body": analyze_block(handler.body),
                }
                for handler in node.handlers
            ],
            "else": analyze_block(node.orelse),
            "finally": analyze_block(node.finalbody),
        }

    if isinstance(node, ast.If):
        return {
            "type": "if",
            "line": node.lineno,
            "condition": expression(node.test),
            "body": analyze_block(node.body),
            "else": analyze_block(node.orelse),
        }

    if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
        return {
            "type": type(node).__name__.lower(),
            "line": node.lineno,
            "condition_or_iterator": expression(
                node.test if isinstance(node, ast.While) else node.iter
            ),
            "body": analyze_block(node.body),
            "else": analyze_block(node.orelse),
        }

    if isinstance(node, (ast.With, ast.AsyncWith)):
        return {
            "type": "with",
            "line": node.lineno,
            "contexts": [
                expression(item.context_expr)
                for item in node.items
            ],
            "body": analyze_block(node.body),
        }

    return analyze_statement(node)


def interpret_python_file_v31(path):
    path = Path(path)

    result = {
        "file": str(path),
        "status": "STATIC_CONTROL_FLOW_V31",
        "functions": [],
        "entrypoint": [],
        "limitations": [
            "Analisi statica: il codice non viene eseguito.",
            "I rami condizionali non sono valutati.",
            "I cicli non vengono simulati.",
            "L'ordine rappresenta la struttura del codice, non una traccia runtime.",
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
            parameters = [
                arg.arg
                for arg in (
                    node.args.posonlyargs
                    + node.args.args
                    + node.args.kwonlyargs
                )
            ]

            result["functions"].append({
                "name": node.name,
                "line": node.lineno,
                "parameters": parameters,
                "steps": analyze_block(node.body),
            })

        elif isinstance(node, ast.If):
            condition = expression(node.test)

            if condition in {
                "__name__ == '__main__'",
                '__name__ == "__main__"',
            }:
                result["entrypoint"] = analyze_block(node.body)

    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python functional_interpreter_v31.py PERCORSO_FILE"
        )

    print(json.dumps(
        interpret_python_file_v31(sys.argv[1]),
        indent=2,
        ensure_ascii=False,
    ))
