from __future__ import annotations

import json
import sys
from pathlib import Path

CORE = Path(__file__).resolve().parent
sys.path.insert(0, str(CORE))

from functional_interpreter_v2 import interpret_python_file_v2
from functional_interpreter_v31 import interpret_python_file_v31
from variable_dependency_analyzer_v4 import analyze_dependencies_v4


def test_project_file(path):
    path = Path(path)

    v2 = interpret_python_file_v2(path)
    v31 = interpret_python_file_v31(path)
    v4 = analyze_dependencies_v4(path)

    statuses = [
        v2.get("status"),
        v31.get("status"),
        v4.get("status"),
    ]

    if statuses != [
        "STATIC_ANALYSIS_V2",
        "STATIC_CONTROL_FLOW_V31",
        "STATIC_OPERATIONS_V4",
    ]:
        raise RuntimeError(
            f"Stato analisi non valido: {statuses}"
        )

    names_v2 = {item["name"] for item in v2["functions"]}
    names_v31 = {item["name"] for item in v31["functions"]}
    names_v4 = {item["name"] for item in v4["functions"]}

    if not (names_v2 == names_v31 == names_v4):
        raise RuntimeError(
            "Le versioni restituiscono elenchi di funzioni differenti."
        )

    report = {
        "file": str(path),
        "integration_status": "PASS",
        "functions": sorted(names_v2),
        "v2": v2["status"],
        "v31": v31["status"],
        "v4": v4["status"],
        "total_events": sum(
            len(item["events"])
            for item in v4["functions"]
        ),
    }

    print(json.dumps(
        report,
        indent=2,
        ensure_ascii=False,
    ))

    return v4


def main():
    root = Path(r"C:\project_intelligence_test")

    print("\n=== TEST INTEGRAZIONE: SQLITE ===")
    sqlite_result = test_project_file(root / "main.py")

    save_result = next(
        item
        for item in sqlite_result["functions"]
        if item["name"] == "save_result"
    )

    events = save_result["events"]

    if len(events) != 5:
        raise RuntimeError(
            f"Attesi 5 eventi SQLite, trovati {len(events)}"
        )

    if events[-1]["context"] != ["finally"]:
        raise RuntimeError(
            "Chiusura connessione non riconosciuta in finally."
        )

    print("\n=== TEST INTEGRAZIONE: FUNZIONI COLLEGATE ===")
    linked_result = test_project_file(
        root / "functional_v2_test.py"
    )

    process_order = next(
        item
        for item in linked_result["functions"]
        if item["name"] == "process_order"
    )

    events = process_order["events"]

    if len(events) != 3:
        raise RuntimeError(
            f"Attesi 3 eventi in process_order, trovati {len(events)}"
        )

    if [item["target"] for item in events] != [
        "subtotal",
        "final_price",
        "<return>",
    ]:
        raise RuntimeError(
            "Sequenza dipendenze non corretta."
        )

    print("\nTUTTI I TEST DI INTEGRAZIONE SUPERATI")


if __name__ == "__main__":
    main()
