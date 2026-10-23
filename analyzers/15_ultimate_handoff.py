from __future__ import annotations

import ast
import json
import sys
from datetime import datetime, UTC
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_ROOT / "core"))

from project_context import PROJECT_ROOT, PROJECT_NAME, PROJECT_OUTPUT_ROOT
from functional_interpreter import interpret_python_file
from functional_interpreter_v2 import interpret_python_file_v2
from functional_interpreter_v31 import interpret_python_file_v31
from variable_dependency_analyzer_v4 import analyze_dependencies_v4
from cross_module_call_graph import analyze_project
from class_call_graph_json import analyze_classes_json

latest = PROJECT_OUTPUT_ROOT / "LATEST"

sources = {
    "01": "01_PROJECT_STRUCTURE/PROJECT_STRUCTURE.json",
    "02": "02_RUNTIME/RUNTIME_MAP.json",
    "03": "03_DATABASE/DATABASE_MAP.json",
    "04": "04_CODE_CONNECTIONS/CODE_CONNECTIONS.json",
    "05": "05_CONFIGURATION/CONFIGURATION_MAP.json",
    "06": "06_API_ENDPOINTS/API_ENDPOINTS_MAP.json",
    "07": "07_DATA_FLOW/DATA_FLOW_MAP.json",
    "08": "08_HEALTH_ERRORS/HEALTH_ERROR_MAP.json",
    "09": "09_PERFORMANCE_BOTTLENECK/PERFORMANCE_MAP.json",
    "10": "10_CROSS_ANALYSIS/CROSS_ANALYSIS_MAP.json",
    "11": "11_FINAL_PROJECT_INTELLIGENCE/FINAL_PROJECT_INTELLIGENCE.json",
    "12": "12_PROJECT_ORGANIZATION/ORGANIZATION_REFACTORING_MAP.json",
    "13": "13_HARDWARE_RESOURCE/HARDWARE_RESOURCE_MAP.json",
    "14": "14_FINAL_ARCHITECTURE_ADVISOR/FINAL_ARCHITECTURE_MAP.json",
}

reports = {}
errors = {}

print("=" * 100)
print("PYTHON PROJECT INTELLIGENCE - ANALYZER 15 V2 TEST")
print("=" * 100)
print("Project:", PROJECT_NAME)
print("Root:", PROJECT_ROOT)
print("Mode: READ ONLY / UNIVERSAL PROJECT HANDOFF")
print()
print("[1/6] Loading source reports...")

for number, relative_path in sources.items():
    path = latest / relative_path

    try:
        with path.open("r", encoding="utf-8-sig") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise ValueError("Expected JSON object")

        reports[number] = data
        print(f"Analyzer {number}: OK")

    except (OSError, ValueError) as exc:
        errors[number] = str(exc)
        print(f"Analyzer {number}: ERROR - {exc}")

print()
print("Reports loaded:", len(reports), "/", len(sources))
print("Errors:", len(errors))
print("Generated UTC:", datetime.now(UTC).isoformat())

if errors:
    print("HANDOFF BLOCKED: incomplete source reports")
    raise SystemExit(1)

print("STAGE 1 COMPLETE")

# ============================================================
# STAGE 2 - FUNCTIONAL MODULE INVENTORY
# ============================================================

print()
print("[2/6] Building functional module inventory...")

code = reports["04"]
runtime = reports["02"]
api = reports["06"]
flow = reports["07"]
cross = reports["10"]

def normalize_path(value):
    return str(value or "").replace("\\", "/").removeprefix("./").lower()

def safe_list(value):
    return value if isinstance(value, list) else []

registry = {
    normalize_path(item.get("file")): item
    for item in safe_list(cross.get("component_registry"))
    if isinstance(item, dict) and item.get("file")
}

endpoints = safe_list(api.get("endpoints"))
db_operations = safe_list(flow.get("database_operations"))
external_sources = safe_list(flow.get("external_sources"))
connections = safe_list(code.get("internal_connections"))
processes = safe_list(runtime.get("project_processes"))

functional_modules = []

for item in safe_list(code.get("files")):
    if not isinstance(item, dict):
        continue

    path = str(item.get("path", ""))
    key = normalize_path(path)
    component = registry.get(key, {})

    module_endpoints = [
        e for e in endpoints
        if isinstance(e, dict)
        and normalize_path(e.get("file")) == key
    ]

    module_db = [
        e for e in db_operations
        if isinstance(e, dict)
        and normalize_path(e.get("file")) == key
    ]

    module_external = [
        e for e in external_sources
        if isinstance(e, dict)
        and normalize_path(e.get("file")) == key
    ]

    module_connections = [
        e for e in connections
        if isinstance(e, dict)
        and normalize_path(e.get("source_file")) == key
    ]

    runtime_matches = [
        proc for proc in processes
        if isinstance(proc, dict)
        and key
        and key in normalize_path(proc.get("command_line"))
    ]

    functional_modules.append({
        "file": path,
        "module": item.get("module"),
        "parse_status": item.get("parse_status"),
        "functions": item.get("functions", []),
        "classes": item.get("classes", []),
        "imports": item.get("imports", []),
        "calls": item.get("calls", []),
        "internal_connections": module_connections,
        "api_endpoints": module_endpoints,
        "database_operations": module_db,
        "external_sources": module_external,
        "runtime_processes": runtime_matches,
        "component_state": component.get("state", "UNKNOWN"),
        "component_confidence": component.get("confidence", "UNKNOWN"),
        "runtime_confirmed": component.get("runtime_confirmed", False),
        "functional_description_status": "STATIC_INTERPRETATION",
        "functional_interpretation": interpret_python_file(PROJECT_ROOT / path),
        "functional_interpretation_v2": interpret_python_file_v2(PROJECT_ROOT / path),
        "functional_interpretation_v31": interpret_python_file_v31(PROJECT_ROOT / path),
        "variable_dependencies_v4": analyze_dependencies_v4(PROJECT_ROOT / path),
    })

print("Python modules documented:", len(functional_modules))
print(
    "Modules with API endpoints:",
    sum(bool(m["api_endpoints"]) for m in functional_modules),
)
print(
    "Modules with database operations:",
    sum(bool(m["database_operations"]) for m in functional_modules),
)
print(
    "Modules with internal connections:",
    sum(bool(m["internal_connections"]) for m in functional_modules),
)
print(
    "Modules with runtime evidence:",
    sum(bool(m["runtime_processes"]) for m in functional_modules),
)

print("STAGE 2 COMPLETE")

# ============================================================
# STAGE 3 - RUNTIME ACTIVITY SNAPSHOT
# ============================================================

print()
print("[3/6] Building runtime activity snapshot...")

runtime_report = reports["02"]
database_report = reports["03"]
api_report = reports["06"]
health_report = reports["08"]

runtime_snapshot = {
    "source": "ANALYZER_02",
    "observation_type": "PREVIOUS_ANALYZER_SNAPSHOT",
    "captured_at": runtime_report.get("metadata", {}).get("generated_utc"),
    "processes": [],
    "listening_ports": safe_list(
        runtime_report.get("project_listening_ports")
    ),
    "database_summary": database_report.get("summary", {}),
    "api_summary": api_report.get("summary", {}),
    "health_summary": health_report.get("summary", {}),
    "limitations": [
        "A running process does not prove successful data collection.",
        "Database freshness is not independently verified here.",
        "Runtime information may have changed since Analyzer 02.",
        "No process is started, stopped or modified.",
    ],
}

for proc in safe_list(runtime_report.get("project_processes")):
    if not isinstance(proc, dict):
        continue

    command = str(proc.get("command_line") or "")
    matched_modules = [
        module["file"]
        for module in functional_modules
        if normalize_path(module["file"])
        and normalize_path(module["file"]) in normalize_path(command)
    ]

    runtime_snapshot["processes"].append({
        "pid": proc.get("pid"),
        "parent_pid": proc.get("parent_pid"),
        "name": proc.get("name"),
        "command_line": command,
        "creation_date": proc.get("creation_date"),
        "listening_ports": proc.get("listening_ports", []),
        "resources": proc.get("resources", {}),
        "matched_modules": matched_modules,
        "execution_observed": True,
        "functional_health_confirmed": False,
        "data_freshness_confirmed": False,
    })

print("Observed project processes:", len(runtime_snapshot["processes"]))
print("Listening ports:", len(runtime_snapshot["listening_ports"]))
print(
    "Processes with module match:",
    sum(bool(p["matched_modules"]) for p in runtime_snapshot["processes"]),
)
print("Functional health independently confirmed: NO")
print("Database freshness independently confirmed: NO")
print("STAGE 3 COMPLETE")

# ============================================================
# STAGE 4 - FUNCTIONAL KNOWLEDGE AND CONTINUITY
# ============================================================

print()
print("[4/6] Building functional knowledge and continuity...")

architecture_report = reports["14"]
intelligence_report = reports["11"]
organization_report = reports["12"]

project_model = intelligence_report.get(
    "project_intelligence_model", {}
)

functional_knowledge = {
    "project_identity": project_model.get("identity", {}),
    "project_structure": project_model.get("project_structure", {}),
    "operational_nucleus": project_model.get("operational_nucleus", {}),
    "code_architecture": project_model.get("code_architecture", {}),
    "api": project_model.get("api", {}),
    "data_flow": project_model.get("data_flow", {}),
    "databases": project_model.get("databases", {}),
    "modules": functional_modules,
    "interpretation_policy": {
        "source_code_structure": "CONFIRMED_WHEN_PARSED",
        "runtime": "OBSERVED_AT_SNAPSHOT",
        "functional_intent": "NOT_AUTOMATICALLY_CONFIRMED",
        "business_purpose": "REQUIRES_DOCUMENTATION_OR_REVIEW",
    },
}

development_continuity = {
    "project_name": PROJECT_NAME,
    "project_root": str(PROJECT_ROOT),
    "runtime_snapshot": runtime_snapshot,
    "health": project_model.get("health", {}),
    "performance": project_model.get("performance", {}),
    "organization": organization_report.get("organization", {}),
    "refactoring_pressure": organization_report.get(
        "refactoring_pressure", {}
    ),
    "architectural_decisions": architecture_report.get(
        "architectural_decisions", []
    ),
    "migration_plan": architecture_report.get(
        "migration_plan", []
    ),
    "safety_rules": architecture_report.get("safety_rules", {}),
    "development_history_status": "NOT_RECONSTRUCTED_FROM_CHAT",
    "current_development_task": "UNKNOWN_UNLESS_DOCUMENTED",
    "recommended_next_step": (
        "Review the latest project reports, verify runtime "
        "freshness and confirm the current development objective."
    ),
}

knowledge_checks = {
    "modules": len(functional_knowledge["modules"]),
    "architecture_sections": len(project_model),
    "architectural_decisions": len(
        development_continuity["architectural_decisions"]
    ),
    "migration_phases": len(
        development_continuity["migration_plan"]
    ),
    "runtime_processes": len(
        runtime_snapshot["processes"]
    ),
}

for name, value in knowledge_checks.items():
    print(name + ":", value)

print("Development task automatically known: NO")
print("Chat history automatically reconstructed: NO")
print("STAGE 4 COMPLETE")

# ============================================================
# STAGE 5 - DOCUMENT GENERATION
# ============================================================

print()
print("[5/6] Generating handoff documents...")

output_dir = PROJECT_OUTPUT_ROOT / "LATEST" / "15_ULTIMATE_HANDOFF"
output_dir.mkdir(parents=True, exist_ok=True)

def markdown_value(value):
    if value is None:
        return "Non disponibile"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)

def markdown_safe(value):
    return markdown_value(value).replace("\n", " ").replace("\r", " ")

def write_document(name, lines):
    path = output_dir / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path

manual = [
    f"# PROJECT FUNCTIONAL MANUAL — {PROJECT_NAME}",
    "",
    f"Project root: `{PROJECT_ROOT}`",
    f"Generated UTC: {datetime.now(UTC).isoformat()}",
    "",
    "## Metodo di analisi",
    "",
    "Questo documento descrive evidenze tecniche raccolte dagli Analyzer 01-14.",
    "Le funzioni individuate non sono automaticamente considerate funzionanti.",
    "Il comportamento operativo richiede verifica del codice e test runtime.",
    "",
    f"## Inventario dei moduli ({len(functional_modules)})",
    "",
]

for index, module in enumerate(functional_modules, 1):
    manual.extend([
        f"### {index}. `{markdown_safe(module['file'])}`",
        "",
        f"- Modulo: `{markdown_safe(module['module'])}`",
        f"- Parsing: {markdown_safe(module['parse_status'])}",
        f"- Stato componente: {markdown_safe(module['component_state'])}",
        f"- Conferma runtime: {markdown_safe(module['runtime_confirmed'])}",
        f"- Interpretazione funzionale: {module['functional_description_status']}",
        "",
        "**Analisi dettagliata delle funzioni ? V2**",
        "",
        *[
            "- Funzione `" + markdown_safe(fn.get("name")) + "`"
            + " | Parametri: " + markdown_safe(fn.get("parameters", []))
            + " | " + markdown_safe("; ".join(fn.get("description", [])))
            for fn in module.get("functional_interpretation_v2", {}).get("functions", [])
        ],
        "",
        "**Operazioni e dipendenze statiche - V4**",
        "",
        *[
            "- Funzione `" + markdown_safe(fn.get("name")) + "`: "
            + markdown_safe(
                "; ".join(
                    str(event.get("target") or event.get("type"))
                    + " = "
                    + str(event.get("expression"))
                    + " ["
                    + "/".join(event.get("context", []))
                    + "]"
                    for event in fn.get("events", [])[:12]
                )
            )
            for fn in module.get("variable_dependencies_v4", {}).get("functions", [])
        ],
        "",
        "**Interpretazione funzionale statica**",
        "",
        *[
            "- " + markdown_safe(description)
            for description in module.get("functional_interpretation", {}).get("summary", [])
        ],
        "",
        "**Funzioni individuate**",
        "",
    ])

    functions = module.get("functions") or []
    if functions:
        for function in functions:
            manual.append(
                "- `" + markdown_safe(function) + "`"
            )
    else:
        manual.append("- Nessuna funzione riportata dall'Analyzer 04.")

    manual.extend(["", "**Classi individuate**", ""])

    classes = module.get("classes") or []
    if classes:
        for cls in classes:
            manual.append("- `" + markdown_safe(cls) + "`")
    else:
        manual.append("- Nessuna classe riportata dall'Analyzer 04.")

    manual.extend([
        "",
        f"- Collegamenti interni: {len(module['internal_connections'])}",
        f"- Endpoint API: {len(module['api_endpoints'])}",
        f"- Operazioni database: {len(module['database_operations'])}",
        f"- Sorgenti esterne: {len(module['external_sources'])}",
        f"- Processi runtime associati: {len(module['runtime_processes'])}",
        "",
    ])

    for title, key in [
        ("Collegamenti", "internal_connections"),
        ("Endpoint API", "api_endpoints"),
        ("Operazioni database", "database_operations"),
        ("Sorgenti esterne", "external_sources"),
    ]:
        records = module.get(key) or []
        if records:
            manual.append(f"**{title} — evidenze**")
            manual.append("")
            for record in records:
                manual.append(
                    "- `" + markdown_safe(record) + "`"
                )
            manual.append("")

manual_path = write_document(
    "PROJECT_FUNCTIONAL_MANUAL.md",
    manual,
)

handoff = [
    f"# START HERE — {PROJECT_NAME}",
    "",
    "## Identità",
    "",
    f"- Project root: `{PROJECT_ROOT}`",
    f"- Moduli documentati: {len(functional_modules)}",
    f"- Report sorgente caricati: {len(reports)}/14",
    "",
    "## Stato operativo osservato",
    "",
    "Queste informazioni provengono da una scansione precedente.",
    "Non costituiscono una verifica in tempo reale.",
    "",
]

handoff.extend([
    "## Sintesi funzionale del progetto",
    "",
])

for module in functional_modules:
    handoff.append(f"### `{markdown_safe(module['file'])}`")
    handoff.append("")

    interpretation_v2 = module.get("functional_interpretation_v2", {})

    for fn in interpretation_v2.get("functions", []):
        handoff.append(
            "- Funzione `" + markdown_safe(fn.get("name")) + "`: "
            + markdown_safe("; ".join(fn.get("description", [])))
        )

    entrypoint = interpretation_v2.get("entrypoint", {})
    if entrypoint.get("detected"):
        handoff.append(
            "- Chiamate individuate nel blocco principale: "
            + markdown_safe(" -> ".join(entrypoint.get("calls", [])))
        )

    dependencies_v4 = module.get("variable_dependencies_v4", {})

    for fn in dependencies_v4.get("functions", []):
        events = fn.get("events", [])
        if events:
            handoff.append(
                "- Flusso statico `" + markdown_safe(fn.get("name")) + "`: "
                + markdown_safe(
                    " -> ".join(
                        str(event.get("target") or event.get("type"))
                        for event in events[:8]
                    )
                )
            )

    interpretation = module.get("functional_interpretation", {})

    for description in interpretation.get("summary", []):
        handoff.append("- " + markdown_safe(description))

    handoff.extend([
        "",
        f"- Stato componente: {markdown_safe(module['component_state'])}",
        f"- Runtime confermato: {markdown_safe(module['runtime_confirmed'])}",
        "",
    ])

for proc in runtime_snapshot["processes"]:
    handoff.extend([
        f"### PID {proc.get('pid')}",
        "",
        f"- Comando: `{markdown_safe(proc.get('command_line'))}`",
        f"- Moduli associati: {markdown_safe(proc.get('matched_modules'))}",
        f"- Porte: {markdown_safe(proc.get('listening_ports'))}",
        "- Esecuzione osservata: sì, alla data del report",
        "- Funzionamento applicativo confermato: no",
        "",
    ])

handoff.extend([
    "## Architettura e sviluppo",
    "",
    f"- Decisioni architetturali: {len(development_continuity['architectural_decisions'])}",
    f"- Fasi di migrazione: {len(development_continuity['migration_plan'])}",
    "",
    "## Indicazioni per una nuova chat",
    "",
    "1. Leggere PROJECT_FUNCTIONAL_MANUAL.md.",
    "2. Consultare FUNCTIONAL_KNOWLEDGE.json per i dettagli strutturati.",
    "3. Verificare lo stato runtime attuale prima di intervenire.",
    "4. Non modificare automaticamente file, database o processi.",
    "5. Chiedere quale attività di sviluppo deve essere proseguita.",
    "",
    "## Limiti",
    "",
    "- La cronologia delle chat non è ricostruita automaticamente.",
    "- L'obiettivo di sviluppo corrente non è determinabile dai soli report.",
    "- Lo stato dei processi potrebbe essere cambiato.",
    "- La freschezza dei database non è stata verificata in questo Stage.",
    "",
])

handoff_path = write_document(
    "START_HERE_NEW_CHAT.md",
    handoff,
)

knowledge_path = output_dir / "FUNCTIONAL_KNOWLEDGE.json"

knowledge_path.write_text(
    json.dumps(
        {
            "metadata": {
                "project": PROJECT_NAME,
                "project_root": str(PROJECT_ROOT),
                "generated_utc": datetime.now(UTC).isoformat(),
                "source_reports": list(reports),
            },
            "functional_knowledge": functional_knowledge,
            "development_continuity": development_continuity,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    ),
    encoding="utf-8",
)

for path in [manual_path, handoff_path, knowledge_path]:
    print(path.name, ":", path.stat().st_size, "bytes")

print("STAGE 5 COMPLETE")


# ============================================================
# STAGE 28ZM - MASTER SITE INTELLIGENCE JSON
# ============================================================

master_site_intelligence_path = (
    output_dir / "MASTER_SITE_INTELLIGENCE.json"
)


# ============================================================
# CROSS MODULE CALL GRAPH - STATIC ANALYSIS
# ============================================================

print("Building cross-module call graphs...")

cross_module_call_graphs = []

entrypoint_candidates = []

for candidate in PROJECT_ROOT.rglob("*.py"):
    relative = candidate.relative_to(PROJECT_ROOT)

    if any(
        part in {
            ".venv", "venv", "__pycache__",
            ".git", "node_modules", "site-packages"
        }
        for part in relative.parts
    ):
        continue

    if "python_project_intelligence_PORTABLE" in relative.parts:
        continue

    try:
        tree = ast.parse(
            candidate.read_text(encoding="utf-8-sig")
        )
    except (OSError, UnicodeError, SyntaxError):
        continue

    for node in tree.body:
        if isinstance(node, ast.If):
            if ast.unparse(node.test) == "__name__ == '__main__'":
                entrypoint_candidates.append(
                    relative.as_posix()
                )
                break

for entrypoint in entrypoint_candidates[:10]:
    try:
        graph = analyze_project(PROJECT_ROOT, entrypoint)

        cross_module_call_graphs.append({
            "entrypoint": entrypoint,
            "result": graph,
        })

    except Exception as exc:
        cross_module_call_graphs.append({
            "entrypoint": entrypoint,
            "error": str(exc),
        })

print(
    "Cross-module entrypoints analyzed:",
    len(cross_module_call_graphs),
)

# ============================================================
# CLASS CALL GRAPHS - STATIC ANALYSIS
# ============================================================

print("Building class call graphs...")

class_call_graphs = []

for entrypoint in entrypoint_candidates[:10]:
    try:
        graph = analyze_classes_json(PROJECT_ROOT, entrypoint)

        class_call_graphs.append({
            "entrypoint": entrypoint,
            "result": graph,
        })

    except Exception as exc:
        class_call_graphs.append({
            "entrypoint": entrypoint,
            "error": str(exc),
        })

print(
    "Class entrypoints analyzed:",
    len(class_call_graphs),
)

master_site_intelligence = {
    "metadata": {
        "analyzer": "15_ultimate_handoff",
        "analyzer_version": "2.0",
        "project": PROJECT_NAME,
        "project_root": str(PROJECT_ROOT),
        "generated_utc": datetime.now(UTC).isoformat(),
        "report_type": "MASTER_SITE_INTELLIGENCE",
        "source_report_count": len(reports),
        "source_reports": list(reports.keys()),
    },

    "project": {
        "name": PROJECT_NAME,
        "root": str(PROJECT_ROOT),
    },

    "functional_modules": functional_modules,
    "cross_module_call_graphs": cross_module_call_graphs,
    "class_call_graphs": class_call_graphs,

    "functional_knowledge": functional_knowledge,

    "runtime_snapshot": runtime_snapshot,

    "development_continuity": development_continuity,

    "handoff_documents": {
        "PROJECT_FUNCTIONAL_MANUAL.md": str(manual_path),
        "START_HERE_NEW_CHAT.md": str(handoff_path),
        "FUNCTIONAL_KNOWLEDGE.json": str(knowledge_path),
        "MASTER_SITE_INTELLIGENCE.json": str(
            master_site_intelligence_path
        ),
    },

    "methodology": {
        "mode": "READ ONLY / UNIVERSAL PROJECT HANDOFF",
        "evidence_based": True,
        "runtime_is_historical": True,
        "automatic_modification_of_operational_project": False,
        "source_analyzers": "01-14",
    },
}

master_site_intelligence_path.write_text(
    json.dumps(
        master_site_intelligence,
        ensure_ascii=False,
        indent=2,
        default=str,
    ),
    encoding="utf-8",
)

print(
    "MASTER_SITE_INTELLIGENCE.json :",
    master_site_intelligence_path.stat().st_size,
    "bytes",
)

print("STAGE 28ZM JSON COMPLETE")

