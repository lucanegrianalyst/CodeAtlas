from __future__ import annotations

import ast
import json
import sys
from pathlib import Path


def analyze_call_graph(path):
    path = Path(path)

    result = {
        "file": str(path),
        "status": "STATIC_CALL_GRAPH",
        "functions": {},
        "entrypoint_calls": [],
        "call_trees": [],
        "limitations": [
            "Analisi statica: nessuna esecuzione del codice.",
            "Sono collegate soltanto funzioni definite nello stesso modulo.",
            "Non sono risolti metodi dinamici, import o dispatch runtime.",
            "L'ordine delle chiamate rappresenta l'ordine nel codice, non una traccia runtime.",
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

    definitions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    def calls_in(node):
        calls = []

        for item in ast.walk(node):
            if isinstance(item, ast.Call):
                if isinstance(item.func, ast.Name):
                    calls.append({
                        "name": item.func.id,
                        "line": item.lineno,
                        "expression": ast.unparse(item),
                    })

        return sorted(calls, key=lambda item: item["line"])

    for name, node in definitions.items():
        result["functions"][name] = {
            "line": node.lineno,
            "parameters": [
                argument.arg
                for argument in node.args.args
            ],
            "calls": calls_in(node),
        }

    for node in tree.body:
        if not isinstance(node, ast.If):
            continue

        if ast.unparse(node.test) != "__name__ == '__main__'":
            continue

        for statement in node.body:
            result["entrypoint_calls"].extend(
                calls_in(statement)
            )

    def expand(name, stack):
        if name not in definitions:
            return {
                "function": name,
                "status": "EXTERNAL_OR_UNKNOWN",
                "children": [],
            }

        if name in stack:
            return {
                "function": name,
                "status": "RECURSIVE_REFERENCE",
                "children": [],
            }

        next_stack = stack + (name,)

        children = []

        for call in result["functions"][name]["calls"]:
            children.append({
                "line": call["line"],
                "expression": call["expression"],
                "callee": expand(
                    call["name"],
                    next_stack,
                ),
            })

        return {
            "function": name,
            "status": "LOCAL_FUNCTION",
            "children": children,
        }

    for call in result["entrypoint_calls"]:
        result["call_trees"].append({
            "entrypoint_line": call["line"],
            "expression": call["expression"],
            "tree": expand(call["name"], ()),
        })

    return result


def describe_graph(result):
    lines = [
        "# GRAFO DELLE CHIAMATE",
        "",
        f"File: `{result['file']}`",
        "",
        "Analisi statica, senza esecuzione.",
        "",
    ]

    def describe_node(node, depth=0):
        indent = "  " * depth

        lines.append(
            f"{indent}- {node['function']} "
            f"[{node['status']}]"
        )

        for child in node["children"]:
            lines.append(
                f"{indent}  Chiamata riga "
                f"{child['line']}: "
                f"`{child['expression']}`"
            )

            describe_node(
                child["callee"],
                depth + 1,
            )

    for item in result["call_trees"]:
        lines.append(
            f"## Entrypoint riga {item['entrypoint_line']}"
        )
        lines.append("")
        lines.append(
            f"Istruzione: `{item['expression']}`"
        )
        lines.append("")

        describe_node(item["tree"])
        lines.append("")

    lines.append("## Limiti")
    lines.append("")

    for limitation in result["limitations"]:
        lines.append(f"- {limitation}")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python recursive_call_graph_analyzer.py FILE_PYTHON"
        )

    result = analyze_call_graph(sys.argv[1])

    if result["status"] == "ANALYSIS_ERROR":
        print(json.dumps(result, indent=2, ensure_ascii=False))
        raise SystemExit(1)

    print(describe_graph(result))
