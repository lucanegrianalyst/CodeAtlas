from __future__ import annotations

import json
import sys
from datetime import datetime, UTC
from pathlib import Path

TOOL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_ROOT / 'core'))

from project_context import PROJECT_ROOT, PROJECT_NAME, PROJECT_OUTPUT_ROOT


project_root = PROJECT_ROOT
project_name = PROJECT_NAME

latest = TOOL_ROOT / "output" / project_name / "LATEST"

sources = {
    "10": "10_CROSS_ANALYSIS/CROSS_ANALYSIS_MAP.json",
    "11": "11_FINAL_PROJECT_INTELLIGENCE/FINAL_PROJECT_INTELLIGENCE.json",
    "12": "12_PROJECT_ORGANIZATION/ORGANIZATION_REFACTORING_MAP.json",
    "13": "13_HARDWARE_RESOURCE/HARDWARE_RESOURCE_MAP.json",
}

reports = {}
errors = {}

print("=" * 100)
print("PYTHON PROJECT INTELLIGENCE - ANALYZER 14 V2 TEST")
print("=" * 100)
print("Project:", project_name)
print("Root   :", project_root)
print("Mode   : READ ONLY / ARCHITECTURE ADVISOR")
print()
print("[1/5] Loading source reports...")

for number, relative_path in sources.items():
    path = latest / relative_path
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            reports[number] = json.load(f)
        print(f"Analyzer {number}: OK")
    except (OSError, ValueError) as exc:
        errors[number] = str(exc)
        print(f"Analyzer {number}: ERROR - {exc}")

print()
print("Loaded:", len(reports), "/", len(sources))
print("Errors:", len(errors))
print("Timestamp UTC:", datetime.now(UTC).isoformat())

if errors:
    raise SystemExit(1)

print("STAGE 1 COMPLETE")


# ============================================================
# STAGE 2 - CURRENT ARCHITECTURE
# ============================================================

print()
print("[2/5] Reconstructing current architecture...")

model = reports["11"].get("project_intelligence_model", {})
cross = reports["10"]
organization = reports["12"]
resources = reports["13"]

architecture = {
    "identity": model.get("identity", {}),
    "project_structure": model.get("project_structure", {}),
    "operational_nucleus": model.get("operational_nucleus", {}),
    "runtime": model.get("runtime", {}),
    "code_architecture": model.get("code_architecture", {}),
    "databases": model.get("databases", {}),
    "configuration": model.get("configuration", {}),
    "api": model.get("api", {}),
    "data_flow": model.get("data_flow", {}),
    "health": model.get("health", {}),
    "performance": model.get("performance", {}),
    "evidence_state": model.get("evidence_state", {}),
}

component_summary = cross.get("component_summary", {})
cross_synthesis = cross.get("cross_synthesis", {})

organization_summary = organization.get("organization", {})
refactoring_pressure = organization.get("refactoring_pressure", {})
safety = organization.get("safety", {})

hardware = resources.get("hardware", {})
project_resources = resources.get("project_resources", {})
database_resources = resources.get("databases", {})

current_architecture = {
    "project": {
        "name": project_name,
        "root": str(project_root),
    },
    "architecture": architecture,
    "components": component_summary,
    "cross_synthesis": cross_synthesis,
    "organization": organization_summary,
    "refactoring_pressure": refactoring_pressure,
    "safety": safety,
    "hardware": hardware,
    "project_resources": project_resources,
    "database_resources": database_resources,
}

print("Architecture sections:", len(architecture))
print("Registered components:", component_summary.get("total_components", "UNKNOWN"))
print("Runtime-confirmed components:", component_summary.get("runtime_confirmed", "UNKNOWN"))
print("Active Python files:", organization_summary.get("active_python_files", "UNKNOWN"))
print("Historical Python files:", organization_summary.get("historical_python_files", "UNKNOWN"))
print("Refactoring pressure:", refactoring_pressure.get("score_0_100", "UNKNOWN"))
print("Protected components:", safety.get("protected_components_found", "UNKNOWN"))
print("Project processes:", project_resources.get("processes", "UNKNOWN"))
print("Databases:", database_resources.get("count", "UNKNOWN"))
print("Cross-analysis contradictions:", len(cross_synthesis.get("contradictions", [])))

print("STAGE 2 COMPLETE")

# ============================================================
# STAGE 3 - ARCHITECTURAL DECISIONS
# ============================================================

print()
print("[3/5] Building architectural decisions...")

decisions = []

def add_decision(code, priority, confidence, evidence, action):
    decisions.append({
        "code": code,
        "priority": priority,
        "confidence": confidence,
        "evidence": evidence,
        "recommended_action": action,
        "automatic_change": False,
    })

protected = safety.get("protected_components_found", 0)
pressure = refactoring_pressure.get("score_0_100", 0)
historical = organization_summary.get("historical_python_files", 0)
contradictions = cross_synthesis.get("contradictions", [])

if protected:
    add_decision(
        "PROTECT_OPERATIONAL_NUCLEUS",
        "HIGH",
        "CONFIRMED",
        f"{protected} protected components identified",
        "Require backups, dependency checks and runtime tests before changes.",
    )

if historical:
    add_decision(
        "SEPARATE_HISTORICAL_CODE",
        "MEDIUM",
        "CONFIRMED",
        f"{historical} historical Python files identified",
        "Review historical files before proposing archival; do not move automatically.",
    )

if isinstance(pressure, (int, float)) and pressure >= 40:
    add_decision(
        "PLAN_INCREMENTAL_REFACTORING",
        "MEDIUM",
        "PROBABLE",
        f"Structural refactoring pressure: {pressure}/100",
        "Refactor incrementally, starting with independently testable components.",
    )

if database_resources.get("count", 0):
    add_decision(
        "PROTECT_DATABASES",
        "HIGH",
        "CONFIRMED",
        f"{database_resources['count']} databases identified",
        "Verify backups, schemas and recovery procedures before migrations.",
    )

if project_resources.get("processes", 0):
    add_decision(
        "PRESERVE_RUNTIME",
        "HIGH",
        "CONFIRMED",
        f"{project_resources['processes']} project processes observed",
        "Preserve startup commands, ports and service dependencies.",
    )

if contradictions:
    add_decision(
        "RESOLVE_EVIDENCE_CONTRADICTIONS",
        "HIGH",
        "CONFIRMED",
        f"{len(contradictions)} cross-analysis contradictions",
        "Resolve contradictory evidence before architectural changes.",
    )

for finding in resources.get("findings", []):
    if not isinstance(finding, dict):
        continue
    code = str(finding.get("code", "RESOURCE_FINDING"))
    add_decision(
        "REVIEW_" + code,
        "LOW",
        str(finding.get("confidence", "POSSIBLE")),
        str(finding.get("evidence", "See Analyzer 13")),
        "Verify resource behavior over time before capacity changes.",
    )

priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
decisions.sort(key=lambda d: priority_order.get(d["priority"], 5))

print("Architectural decisions:", len(decisions))

for item in decisions:
    print(
        item["priority"],
        "|",
        item["confidence"],
        "|",
        item["code"],
    )

print("Automatic changes:", sum(d["automatic_change"] for d in decisions))
print("STAGE 3 COMPLETE")

# ============================================================
# STAGE 4 - TARGET ARCHITECTURE AND SAFE MIGRATION
# ============================================================

print()
print("[4/5] Designing target architecture and migration plan...")

target_structure = {
    "status": "PROPOSED_NOT_IMPLEMENTED",
    "confidence": "POSSIBLE",
    "principle": "Separate responsibilities only when justified by actual dependencies.",
    "suggested_layers": [
        {
            "name": "entrypoints",
            "responsibility": "Application startup and command interfaces",
        },
        {
            "name": "services",
            "responsibility": "Application logic and orchestration",
        },
        {
            "name": "integrations",
            "responsibility": "External APIs and data providers",
        },
        {
            "name": "storage",
            "responsibility": "Database access and persistence",
        },
        {
            "name": "interfaces",
            "responsibility": "Web dashboards and user interfaces",
        },
        {
            "name": "tests",
            "responsibility": "Regression and integration verification",
        },
        {
            "name": "docs",
            "responsibility": "Architecture, operations and recovery documentation",
        },
    ],
    "implementation_rule": (
        "Do not create or move folders without a component-level "
        "dependency and compatibility assessment."
    ),
}

migration_plan = [
    {
        "phase": 0,
        "name": "FREEZE AND BASELINE",
        "risk": "LOW",
        "action": "Capture current files, runtime, database and configuration state.",
        "verification": "Baseline reports and backups are available.",
    },
    {
        "phase": 1,
        "name": "PROTECT OPERATIONAL COMPONENTS",
        "risk": "LOW",
        "action": "Identify protected components, startup commands and dependencies.",
        "verification": "Protected components and dependencies are documented.",
    },
    {
        "phase": 2,
        "name": "ADD REGRESSION TESTS",
        "risk": "MEDIUM",
        "action": "Introduce tests around existing behavior without changing it.",
        "verification": "Existing behavior passes baseline tests.",
    },
    {
        "phase": 3,
        "name": "REFACTOR ONE COMPONENT",
        "risk": "MEDIUM",
        "action": "Refactor one independently testable component at a time.",
        "verification": "Imports, API, database and runtime behavior remain compatible.",
    },
    {
        "phase": 4,
        "name": "REVIEW HISTORICAL CODE",
        "risk": "MEDIUM",
        "action": "Review historical files and their references before archiving.",
        "verification": "No runtime or source dependency is lost.",
    },
    {
        "phase": 5,
        "name": "VALIDATE AND DOCUMENT",
        "risk": "LOW",
        "action": "Repeat analyzers, compare baselines and update documentation.",
        "verification": "No unexplained regressions remain.",
    },
]

safety_rules = {
    "read_only_project": True,
    "automatic_file_moves": False,
    "automatic_file_deletions": False,
    "automatic_database_changes": False,
    "automatic_process_changes": False,
    "automatic_configuration_changes": False,
    "backup_before_modification": True,
    "require_runtime_verification": True,
    "require_database_verification": True,
    "require_dependency_verification": True,
    "protected_components": safety.get("protected_components_found", 0),
}

print("Proposed layers:", len(target_structure["suggested_layers"]))
print("Migration phases:", len(migration_plan))
print("Protected components:", safety_rules["protected_components"])
print("Automatic moves:", safety_rules["automatic_file_moves"])
print("Automatic deletions:", safety_rules["automatic_file_deletions"])
print("Database changes:", safety_rules["automatic_database_changes"])
print("STAGE 4 COMPLETE")

# ============================================================
# STAGE 5 - FINAL REPORTS
# ============================================================

print()
print("[5/5] Generating architecture reports...")

output_dir = latest / "14_FINAL_ARCHITECTURE_ADVISOR"
output_dir.mkdir(parents=True, exist_ok=True)

result = {
    "metadata": {
        "analyzer": "14",
        "name": "Final Architecture Advisor",
        "version": "2.0-test",
        "project_name": project_name,
        "project_root": str(project_root),
        "generated_utc": datetime.now(UTC).isoformat(),
        "read_only_project": True,
    },
    "source_reports": {
        number: str(latest / relative)
        for number, relative in sources.items()
    },
    "current_architecture": current_architecture,
    "architectural_decisions": decisions,
    "target_structure": target_structure,
    "migration_plan": migration_plan,
    "safety_rules": safety_rules,
}

json_path = output_dir / "FINAL_ARCHITECTURE_MAP.json"
md_path = output_dir / "14_FINAL_ARCHITECTURE_ADVISOR.md"
migration_path = output_dir / "SAFE_MIGRATION_PLAN.txt"

json_path.write_text(
    json.dumps(result, indent=2, ensure_ascii=False, default=str),
    encoding="utf-8",
)

md = [
    f"# Final Architecture Advisor — {project_name}",
    "",
    f"Generated UTC: {result['metadata']['generated_utc']}",
    "",
    "**Mode:** Read-only project analysis",
    "",
    "## Current architecture",
    "",
    f"- Registered components: {component_summary.get('total_components', 'UNKNOWN')}",
    f"- Runtime-confirmed components: {component_summary.get('runtime_confirmed', 'UNKNOWN')}",
    f"- Active Python files: {organization_summary.get('active_python_files', 'UNKNOWN')}",
    f"- Historical Python files: {organization_summary.get('historical_python_files', 'UNKNOWN')}",
    f"- Protected components: {safety.get('protected_components_found', 'UNKNOWN')}",
    f"- Refactoring pressure: {refactoring_pressure.get('score_0_100', 'UNKNOWN')}/100",
    f"- Project processes: {project_resources.get('processes', 'UNKNOWN')}",
    f"- Databases: {database_resources.get('count', 'UNKNOWN')}",
    "",
    "## Architectural decisions",
    "",
]

for item in decisions:
    md.extend([
        f"### {item['code']}",
        "",
        f"- Priority: {item['priority']}",
        f"- Confidence: {item['confidence']}",
        f"- Evidence: {item['evidence']}",
        f"- Recommendation: {item['recommended_action']}",
        "",
    ])

md.extend([
    "## Proposed architecture",
    "",
    "**Status: PROPOSED — NOT IMPLEMENTED**",
    "",
])

for layer in target_structure["suggested_layers"]:
    md.append(
        f"- **{layer['name']}**: {layer['responsibility']}"
    )

md.extend([
    "",
    "## Safe migration plan",
    "",
])

for phase in migration_plan:
    md.extend([
        f"### Phase {phase['phase']} — {phase['name']}",
        "",
        f"- Risk: {phase['risk']}",
        f"- Action: {phase['action']}",
        f"- Verification: {phase['verification']}",
        "",
    ])

md.extend([
    "## Safety rules",
    "",
    "- No automatic file moves or deletions.",
    "- No automatic database or process modifications.",
    "- Backups and compatibility checks required before changes.",
    "",
    "## Evidence limitations",
    "",
    "Recommendations are based on existing analyzer reports.",
    "A proposed architecture is not proof that migration is necessary.",
    "Runtime and resource observations represent measured snapshots.",
])

md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

migration_lines = [
    f"SAFE MIGRATION PLAN — {project_name}",
    "=" * 72,
    "PROPOSAL ONLY — NO AUTOMATIC CHANGES",
    "",
]

for phase in migration_plan:
    migration_lines.extend([
        f"PHASE {phase['phase']} — {phase['name']}",
        f"RISK: {phase['risk']}",
        f"ACTION: {phase['action']}",
        f"VERIFY: {phase['verification']}",
        "",
    ])

migration_path.write_text(
    "\n".join(migration_lines) + "\n",
    encoding="utf-8",
)

for path in (json_path, md_path, migration_path):
    print("OK", path.name, "|", path.stat().st_size, "bytes")

print("ANALYZER 14 V2 TEST COMPLETE")
