from __future__ import annotations

import json
import sys
from pathlib import Path

from entrypoint_flow_analyzer import analyze_entrypoint
from variable_dependency_analyzer_v4 import analyze_dependencies_v4


def link_flow(path):
    path = Path(path)

    entrypoint = analyze_entrypoint(path)
    dependencies = analyze_dependencies_v4(path)

    result = {
        "file": str(path),
        "status": "STATIC_LINKED_FLOW",
        "entrypoint_detected": entrypoint.get(
            "entrypoint_detected", False
        ),
        "steps": [],
        "limitations": [
            "Analisi statica: il codice non viene eseguito.",
            "Le chiamate sono collegate per nome nello stesso modulo.",
            "Non vengono risolte chiamate dinamiche o import esterni.",
            "Il collegamento non dimostra il comportamento runtime.",
        ],
    }

    if entrypoint.get("status") == "ANALYSIS_ERROR":
        result["status"] = "ANALYSIS_ERROR"
        result["error"] = entrypoint.get("error")
        return result

    if dependencies.get("status") == "ANALYSIS_ERROR":
        result["status"] = "ANALYSIS_ERROR"
        result["error"] = dependencies.get("error")
        return result

    functions = {
        function.get("name"): function
        for function in dependencies.get("functions", [])
    }

    variable_sources = {}

    for step in entrypoint.get("steps", []):
        linked = {
            "line": step.get("line"),
            "type": step.get("type"),
            "expression": step.get("expression"),
            "targets": step.get("targets", []),
            "uses": step.get("uses", []),
            "calls": step.get("calls", []),
            "input_origins": {},
            "local_functions": [],
        }

        for name in step.get("uses", []):
            if name in variable_sources:
                linked["input_origins"][name] = variable_sources[name]

        for call_name in step.get("calls", []):
            function = functions.get(call_name)

            if function is None:
                continue

            linked["local_functions"].append({
                "name": call_name,
                "events": function.get("events", []),
            })

        result["steps"].append(linked)

        for target in step.get("targets", []):
            variable_sources[target] = {
                "line": step.get("line"),
                "expression": step.get("expression"),
            }

    return result


def describe_flow(result):
    lines = [
        "# FLUSSO FUNZIONALE COLLEGATO",
        "",
        f"File: `{result['file']}`",
        "",
        "Analisi statica: nessuna esecuzione del codice.",
        "",
    ]

    for number, step in enumerate(result["steps"], 1):
        lines.append(
            f"## Passaggio {number} — riga {step['line']}"
        )
        lines.append("")
        lines.append(
            f"- Istruzione: `{step['expression']}`"
        )

        if step["targets"]:
            lines.append(
                "- Variabili assegnate: "
                + ", ".join(step["targets"])
            )

        for variable, origin in step["input_origins"].items():
            lines.append(
                f"- La variabile `{variable}` proviene "
                f"dalla riga {origin['line']}: "
                f"`{origin['expression']}`"
            )

        for function in step["local_functions"]:
            lines.append(
                f"- Funzione locale collegata: "
                f"`{function['name']}`"
            )

            for event in function["events"]:
                expression = event.get("expression")

                if expression:
                    lines.append(
                        f"  - {event.get('type')}: "
                        f"`{expression}`"
                    )

        lines.append("")

    lines.append("## Limiti")
    lines.append("")

    for limitation in result["limitations"]:
        lines.append(f"- {limitation}")

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python functional_flow_linker.py FILE_PYTHON"
        )

    result = link_flow(sys.argv[1])

    if result["status"] == "ANALYSIS_ERROR":
        print(json.dumps(result, indent=2, ensure_ascii=False))
        raise SystemExit(1)

    print(describe_flow(result))
