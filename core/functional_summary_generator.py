from __future__ import annotations

import json
import sys
from pathlib import Path


def describe_function(function):
    name = function.get("name", "unknown")
    events = function.get("events", [])

    lines = [f"Funzione {name}:"]

    for event in events:
        expression = event.get("expression", "")
        target = event.get("target")
        context = event.get("context", [])

        prefix = (
            f"Nel blocco {'/'.join(context)}, "
            if context else ""
        )

        if event.get("type") == "assignment":
            lines.append(
                f"- {prefix}assegna a {target} "
                f"il risultato di {expression}."
            )

        elif event.get("type") == "return":
            lines.append(
                f"- {prefix}restituisce {expression}."
            )

        elif event.get("type") == "call":
            lines.append(
                f"- {prefix}contiene la chiamata {expression}."
            )

    return lines


def generate_summary(data):
    modules = (
        data.get("functional_knowledge", {})
        .get("modules", [])
    )

    lines = [
        "# SINTESI FUNZIONALE DEL PROGETTO",
        "",
        "Analisi statica del codice sorgente.",
        "Le operazioni descritte non sono necessariamente state eseguite.",
        "",
    ]

    for module in modules:
        lines.append(
            f"## Modulo: {module.get('file', 'unknown')}"
        )
        lines.append("")

        v4 = module.get("variable_dependencies_v4", {})

        for function in v4.get("functions", []):
            lines.extend(describe_function(function))
            lines.append("")

        v2 = module.get("functional_interpretation_v2", {})
        entrypoint = v2.get("entrypoint", {})

        if entrypoint.get("detected"):
            calls = entrypoint.get("calls", [])

            lines.append("Blocco principale:")
            lines.append(
                "- Chiamate individuate: "
                + " -> ".join(calls)
            )
            lines.append(
                "- La sequenza è sintattica, "
                "non una traccia di esecuzione."
            )
            lines.append("")

    lines.extend([
        "## Limiti",
        "",
        "- Il codice non viene eseguito.",
        "- Le condizioni non vengono valutate.",
        "- Le chiamate dinamiche possono non essere riconosciute.",
        "- La sintesi non sostituisce la lettura del codice.",
    ])

    return "\n".join(lines) + "\n"


def main():
    if len(sys.argv) != 2:
        raise SystemExit(
            "Uso: python functional_summary_generator.py "
            "FUNCTIONAL_KNOWLEDGE.json"
        )

    source = Path(sys.argv[1])

    data = json.loads(
        source.read_text(encoding="utf-8-sig")
    )

    summary = generate_summary(data)

    print(summary)


if __name__ == "__main__":
    main()
