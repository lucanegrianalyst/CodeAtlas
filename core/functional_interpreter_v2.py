from __future__ import annotations

import ast
import json
from pathlib import Path


def name_of(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = name_of(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def literal_of(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, RecursionError, MemoryError):
        return None


def calls_in(node):
    return [
        name_of(child.func)
        for child in ast.walk(node)
        if isinstance(child, ast.Call)
    ]


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

    calls = calls_in(node)

    result = {
        "name": node.name,
        "line": node.lineno,
        "parameters": parameters,
        "calls": sorted(set(calls)),
        "returns": [],
        "database": {
            "connections": [],
            "sql": [],
            "commit": False,
            "close": False,
        },
        "description": [],
    }

    for child in ast.walk(node):
        if isinstance(child, ast.Return):
            if child.value is not None:
                result["returns"].append(
                    ast.unparse(child.value)
                )

        elif isinstance(child, ast.Call):
            call = name_of(child.func)

            if call == "sqlite3.connect" and child.args:
                database = literal_of(child.args[0])
                if isinstance(database, str):
                    result["database"]["connections"].append(database)

            elif call.endswith(".execute") and child.args:
                sql = literal_of(child.args[0])
                if isinstance(sql, str):
                    result["database"]["sql"].append(
                        " ".join(sql.split())
                    )

            elif call.endswith(".commit"):
                result["database"]["commit"] = True

            elif call.endswith(".close"):
                result["database"]["close"] = True

    if "sum" in calls:
        result["description"].append(
            "Contiene una chiamata alla funzione sum()."
        )

    for database in result["database"]["connections"]:
        result["description"].append(
            f"Apre una connessione SQLite al database {database}."
        )

    for sql in result["database"]["sql"]:
        result["description"].append(
            f"Contiene l'istruzione SQL: {sql}"
        )

    if result["database"]["commit"]:
        result["description"].append(
            "Contiene una chiamata di conferma della transazione."
        )

    if result["database"]["close"]:
        result["description"].append(
            "Contiene una chiamata di chiusura della connessione."
        )

    for expression in result["returns"]:
        result["description"].append(
            f"Restituisce l'espressione: {expression}."
        )

    if not result["description"]:
        result["description"].append(
            "Comportamento non classificato dalle regole V2."
        )

    return result


def interpret_python_file_v2(path):
    path = Path(path)

    result = {
        "file": str(path),
        "status": "STATIC_ANALYSIS_V2",
        "functions": [],
        "entrypoint": {
            "detected": False,
            "calls": [],
        },
        "limitations": [
            "Il codice sorgente non viene eseguito.",
            "Le chiamate rilevate non provano che vengano eseguite.",
            "L'ordine delle chiamate è una sequenza sintattica, non una traccia runtime.",
            "Non vengono risolti tutti i flussi condizionali o dinamici.",
        ],
    }

    try:
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        result["status"] = "ANALYSIS_ERROR"
        result["error"] = str(exc)
        return result

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result["functions"].append(analyze_function(node))

        elif isinstance(node, ast.If):
            condition = ast.unparse(node.test)

            if condition in {
                "__name__ == '__main__'",
                "__name__ == \"__main__\"",
            }:
                result["entrypoint"]["detected"] = True

                for statement in node.body:
                    result["entrypoint"]["calls"].extend(
                        calls_in(statement)
                    )

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python functional_interpreter_v2.py PERCORSO_FILE"
        )

    print(
        json.dumps(
            interpret_python_file_v2(sys.argv[1]),
            indent=2,
            ensure_ascii=False,
        )
    )
