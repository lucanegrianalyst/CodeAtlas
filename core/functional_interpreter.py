from __future__ import annotations

import ast
from pathlib import Path


def call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def interpret_python_file(path):
    path = Path(path)
    result = {
        "file": str(path),
        "status": "STATIC_ANALYSIS",
        "functions": [],
        "operations": [],
        "summary": [],
        "limitations": [
            "Analisi statica: il codice non viene eseguito.",
            "Le operazioni rilevate non dimostrano il funzionamento runtime."
        ],
    }

    try:
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        result["status"] = "ANALYSIS_ERROR"
        result["error"] = str(exc)
        return result

    imports = set()
    operations = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)

        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result["functions"].append({
                "name": node.name,
                "line": node.lineno,
                "async": isinstance(node, ast.AsyncFunctionDef),
            })

        elif isinstance(node, ast.Call):
            name = call_name(node.func)

            if name == "print":
                operations.add("Produzione di output sul terminale.")

            if name.endswith(".connect") and "sqlite3" in imports:
                operations.add("Apertura di una connessione SQLite.")

            if name.endswith(".execute") or name.endswith(".executemany"):
                operations.add("Esecuzione di istruzioni tramite un'interfaccia database.")

            if name in {"sum", "math.fsum"}:
                operations.add("Calcolo di una somma numerica.")

        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            operations.add("Presenza di operazioni di addizione.")

        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            sql = node.value.strip().upper()

            if sql.startswith("CREATE TABLE"):
                operations.add("Presenza di un'istruzione SQL per creare una tabella.")

            if sql.startswith("INSERT INTO"):
                operations.add("Presenza di un'istruzione SQL per inserire dati.")

            if sql.startswith("SELECT"):
                operations.add("Presenza di un'istruzione SQL per leggere dati.")

            if sql.startswith("UPDATE"):
                operations.add("Presenza di un'istruzione SQL per aggiornare dati.")

            if sql.startswith("DELETE FROM"):
                operations.add("Presenza di un'istruzione SQL per eliminare dati.")

    result["operations"] = sorted(operations)

    if result["functions"]:
        names = ", ".join(item["name"] for item in result["functions"])
        result["summary"].append(f"Il modulo definisce le funzioni: {names}.")

    result["summary"].extend(result["operations"])

    if not result["summary"]:
        result["summary"].append(
            "Non sono state individuate operazioni descrivibili con le regole disponibili."
        )

    return result
