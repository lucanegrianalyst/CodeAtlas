import contextlib
import io
from class_call_graph_analyzer import analyze


def analyze_classes_json(root, entry):
    buffer = io.StringIO()

    with contextlib.redirect_stdout(buffer):
        analyze(root, entry)

    lines = buffer.getvalue().splitlines()

    result = {
        "entrypoint": entry,
        "status": "STATIC_CLASS_CALL_GRAPH",
        "instances": {},
        "calls": [],
        "limitations": [
            "Analisi statica: il codice del progetto non viene eseguito.",
            "Il riconoscimento delle istanze copre solo i casi supportati dal motore.",
            "Le chiamate esterne e i metodi dinamici non sono risolti.",
        ],
    }

    current_call = None

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("ISTANZE:"):
            import ast
            try:
                result["instances"] = ast.literal_eval(
                    stripped.split(":", 1)[1].strip()
                )
            except (ValueError, SyntaxError):
                result["status"] = "PARTIAL_ANALYSIS"

        elif stripped.startswith("CHIAMATA:"):
            current_call = {
                "expression": stripped.split(":", 1)[1].strip(),
                "methods": [],
                "other_calls": [],
            }
            result["calls"].append(current_call)

        elif current_call is not None:
            if stripped.startswith("METODO:"):
                current_call["methods"].append(
                    stripped.split(":", 1)[1].strip()
                )
            elif stripped.startswith("ALTRA CHIAMATA:"):
                current_call["other_calls"].append(
                    stripped.split(":", 1)[1].strip()
                )

    return result
