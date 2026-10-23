from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


def expression(node):
    return ast.unparse(node) if node is not None else None


def analyze_statement(node):
    if isinstance(node, ast.Assign):
        targets = [expression(target) for target in node.targets]
        value = expression(node.value)

        calls = [
            expression(child.func)
            for child in ast.walk(node.value)
            if isinstance(child, ast.Call)
        ]

        return {
            "type": "assignment",
            "line": node.lineno,
            "targets": targets,
            "expression": value,
            "calls": calls,
        }

    if isinstance(node, ast.AnnAssign):
        return {
            "type": "annotated_assignment",
            "line": node.lineno,
            "targets": [expression(node.target)],
            "expression": expression(node.value),
        }

    if isinstance(node, ast.Return):
        return {
            "type": "return",
            "line": node.lineno,
            "expression": expression(node.value),
        }

    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        return {
            "type": "call",
            "line": node.lineno,
            "expression": expression(node.value),
        }

    return {
        "type": "control_or_other",
        "line": getattr(node, "lineno", None),
        "node_type": type(node).__name__,
        "expression": expression(node),
    }


def analyze_function(node):
    parameters = [
        arg.arg
        for arg in (
            node.args.posonlyargs
            + node.args.args
            + node.args.kwonlyargs
        )
    ]

    if node.args.vararg:
        parameters.append("*" + node.args.vararg.arg)

    if node.args.kwarg:
        parameters.append("**" + node.args.kwarg.arg)

    return {
        "name": node.name,
        "line": node.lineno,
        "parameters": parameters,
        "steps": [
            analyze_statement(statement)
            for statement in node.body
        ],
        "limitations": [
            "I passaggi sono ricavati dalla struttura sintattica.",
            "Le istruzioni condizionali e i cicli non sono espansi.",
            "Non viene eseguito il codice.",
        ],
    }


def interpret_python_file_v3(path):
    path = Path(path)

    result = {
        "file": str(path),
        "status": "STATIC_DATA_FLOW_V3",
        "functions": [],
        "entrypoint": [],
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
            result["functions"].append(analyze_function(node))

        elif isinstance(node, ast.If):
            condition = expression(node.test)

            if condition in {
                "__name__ == '__main__'",
                '__name__ == "__main__"',
            }:
                result["entrypoint"] = [
                    analyze_statement(statement)
                    for statement in node.body
                ]

    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python functional_interpreter_v3.py PERCORSO_FILE"
        )

    print(
        json.dumps(
            interpret_python_file_v3(sys.argv[1]),
            indent=2,
            ensure_ascii=False,
        )
    )
