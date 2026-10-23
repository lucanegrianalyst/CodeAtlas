from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


def get_names(node):
    return sorted({
        item.id
        for item in ast.walk(node)
        if isinstance(item, ast.Name)
        and isinstance(item.ctx, ast.Load)
        and not (
            isinstance(node, ast.Call)
            and item is node.func
        )
    })


def analyze_entrypoint(path):
    path = Path(path)

    result = {
        "file": str(path),
        "status": "STATIC_ENTRYPOINT_FLOW",
        "entrypoint_detected": False,
        "steps": [],
        "limitations": [
            "Il codice non viene eseguito.",
            "Il flusso rappresenta istruzioni sintattiche.",
            "Le dipendenze dinamiche non sono risolte.",
            "I blocchi annidati non sono ancora espansi.",
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
        if not isinstance(node, ast.If):
            continue

        if ast.unparse(node.test) not in {
            "__name__ == '__main__'",
            '__name__ == "__main__"',
        }:
            continue

        result["entrypoint_detected"] = True

        for statement in node.body:
            if isinstance(statement, ast.Assign):
                result["steps"].append({
                    "type": "assignment",
                    "line": statement.lineno,
                    "targets": [
                        ast.unparse(target)
                        for target in statement.targets
                    ],
                    "expression": ast.unparse(statement.value),
                    "uses": get_names(statement.value),
                    "calls": [
                        ast.unparse(item.func)
                        for item in ast.walk(statement.value)
                        if isinstance(item, ast.Call)
                    ],
                })

            elif isinstance(statement, ast.Expr):
                result["steps"].append({
                    "type": "expression",
                    "line": statement.lineno,
                    "expression": ast.unparse(statement.value),
                    "uses": get_names(statement.value),
                    "calls": [
                        ast.unparse(item.func)
                        for item in ast.walk(statement.value)
                        if isinstance(item, ast.Call)
                    ],
                })

    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python entrypoint_flow_analyzer.py PERCORSO_FILE"
        )

    print(json.dumps(
        analyze_entrypoint(sys.argv[1]),
        indent=2,
        ensure_ascii=False,
    ))
