from pathlib import Path
import sys
import json
from datetime import datetime, timezone

ANALYZER_DIR = Path(__file__).resolve().parent
INTELLIGENCE_ROOT = ANALYZER_DIR.parent
CORE_DIR = INTELLIGENCE_ROOT / "core"

if str(CORE_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(CORE_DIR)
    )

from project_context import (
    PROJECT_ROOT,
    PROJECT_NAME,
    PROJECT_OUTPUT_ROOT,
)

LATEST = (
    PROJECT_OUTPUT_ROOT
    / "LATEST"
)

OUTPUT_DIR = (
    LATEST
    / "11_FINAL_PROJECT_INTELLIGENCE"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "FINAL_PROJECT_INTELLIGENCE.json"
)

REPORTS = {
    "01":
        LATEST
        / "01_PROJECT_STRUCTURE"
        / "PROJECT_STRUCTURE.json",

    "02":
        LATEST
        / "02_RUNTIME"
        / "RUNTIME_MAP.json",

    "03":
        LATEST
        / "03_DATABASE"
        / "DATABASE_MAP.json",

    "04":
        LATEST
        / "04_CODE_CONNECTIONS"
        / "CODE_CONNECTIONS.json",

    "05":
        LATEST
        / "05_CONFIGURATION"
        / "CONFIGURATION_MAP.json",

    "06":
        LATEST
        / "06_API_ENDPOINTS"
        / "API_ENDPOINTS_MAP.json",

    "07":
        LATEST
        / "07_DATA_FLOW"
        / "DATA_FLOW_MAP.json",

    "08":
        LATEST
        / "08_HEALTH_ERRORS"
        / "HEALTH_ERROR_MAP.json",

    "09":
        LATEST
        / "09_PERFORMANCE_BOTTLENECK"
        / "PERFORMANCE_MAP.json",

    "10":
        LATEST
        / "10_CROSS_ANALYSIS"
        / "CROSS_ANALYSIS_MAP.json",
}


def load_json(path):

    try:

        data = json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        )

        if not isinstance(
            data,
            dict
        ):

            return None, (
                "ROOT_NOT_DICT"
            )

        return data, None

    except Exception as exc:

        return None, (
            f"{type(exc).__name__}: "
            f"{exc}"
        )


def schema_of(data):

    schema = {}

    for key, value in data.items():

        if isinstance(
            value,
            dict
        ):

            schema[key] = (
                f"DICT[{len(value)}]"
            )

        elif isinstance(
            value,
            list
        ):

            schema[key] = (
                f"LIST[{len(value)}]"
            )

        else:

            schema[key] = (
                type(value).__name__
            )

    return schema


def main():

    print("=" * 100)
    print(
        "PYTHON PROJECT INTELLIGENCE"
    )
    print(
        "ANALYZER 11 - "
        "FINAL PROJECT INTELLIGENCE V2 TEST"
    )
    print("=" * 100)

    print(
        "Project:",
        PROJECT_NAME
    )

    print(
        "Root   :",
        PROJECT_ROOT
    )

    print(
        "Mode   : SYNTHESIS ONLY / READ ONLY PROJECT"
    )

    print()

    inventory = {}
    loaded = {}

    print("=" * 100)
    print(
        "STAGE 1 - OFFICIAL REPORT INVENTORY"
    )
    print("=" * 100)

    for number, path in REPORTS.items():

        exists = path.exists()

        item = {
            "analyzer":
                number,

            "path":
                str(path),

            "exists":
                exists,

            "loaded":
                False,

            "error":
                None,

            "root_schema":
                {},
        }

        if exists:

            data, error = load_json(
                path
            )

            if error is None:

                loaded[
                    number
                ] = data

                item[
                    "loaded"
                ] = True

                item[
                    "root_schema"
                ] = schema_of(
                    data
                )

                print(
                    f"{number} | OK      | "
                    f"{path.name} | "
                    f"keys={len(data)}"
                )

            else:

                item[
                    "error"
                ] = error

                print(
                    f"{number} | ERROR   | "
                    f"{path.name} | "
                    f"{error}"
                )

        else:

            item[
                "error"
            ] = "MISSING"

            print(
                f"{number} | MISSING | "
                f"{path.name}"
            )

        inventory[
            number
        ] = item

    print()

    expected = len(
        REPORTS
    )

    found = sum(
        1
        for item in inventory.values()
        if item[
            "exists"
        ]
    )

    loaded_count = len(
        loaded
    )

    errors = sum(
        1
        for item in inventory.values()
        if (
            item[
                "exists"
            ]
            and not item[
                "loaded"
            ]
        )
    )

    missing = (
        expected
        - found
    )

    all_available = (
        expected
        == loaded_count
    )

    # ------------------------------------------------------------
    # Analyzer 10 is the principal cross-synthesis source.
    # Analyzer 11 must not silently invent a second interpretation.
    # ------------------------------------------------------------

    cross = loaded.get(
        "10",
        {}
    )

    cross_synthesis = cross.get(
        "cross_synthesis",
        {}
    )

    cross_summary = (
        cross_synthesis.get(
            "summary",
            {}
        )
    )

    cross_methodology = (
        cross_synthesis.get(
            "methodology",
            {}
        )
    )

    component_registry = cross.get(
        "component_registry",
        []
    )

    source_status = {
        "reports_expected":
            expected,

        "reports_found":
            found,

        "reports_loaded":
            loaded_count,

        "reports_missing":
            missing,

        "report_load_errors":
            errors,

        "all_reports_available":
            all_available,

        "cross_synthesis_available":
            bool(
                cross_synthesis
            ),

        "component_registry_available":
            bool(
                component_registry
            ),
    }

    result = {
        "metadata": {
            "analyzer":
                "11",

            "name":
                "FINAL_PROJECT_INTELLIGENCE",

            "version":
                "V2_STAGE1",

            "project_name":
                PROJECT_NAME,

            "project_root":
                str(
                    PROJECT_ROOT
                ),

            "generated_utc":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "mode":
                "SYNTHESIS_ONLY",

            "read_only_project":
                True,
        },

        "source_status":
            source_status,

        "report_inventory":
            inventory,

        "cross_source": {
            "status":
                cross_synthesis.get(
                    "status"
                ),

            "summary":
                cross_summary,

            "methodology":
                cross_methodology,

            "confirmed_facts":
                cross_synthesis.get(
                    "confirmed_facts",
                    []
                ),

            "findings":
                cross_synthesis.get(
                    "findings",
                    []
                ),

            "contradictions":
                cross_synthesis.get(
                    "contradictions",
                    []
                ),

            "limitations":
                cross_synthesis.get(
                    "limitations",
                    []
                ),

            "component_registry_count":
                len(
                    component_registry
                ),
        },

        "final_intelligence_status":
            (
                "SOURCE_LAYER_READY"
                if (
                    all_available
                    and cross_synthesis
                    and component_registry
                )
                else
                "SOURCE_LAYER_INCOMPLETE"
            ),

        "methodology": {
            "primary_cross_source":
                "ANALYZER_10",

            "supporting_sources":
                "ANALYZERS_01_TO_09",

            "direct_project_scan":
                False,

            "direct_process_query":
                False,

            "direct_database_query":
                False,

            "new_runtime_measurement":
                False,

            "new_static_analysis":
                False,

            "interpretation_policy":
                (
                    "Analyzer 11 synthesizes "
                    "official Analyzer 01-10 "
                    "evidence and preserves "
                    "their confidence and "
                    "severity semantics."
                ),
        },
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print("=" * 100)
    print(
        "STAGE 1 RESULTS"
    )
    print("=" * 100)

    for key, value in (
        source_status.items()
    ):

        print(
            f"{key:<35}: "
            f"{value}"
        )

    print()

    print(
        "Cross status                  :",
        cross_synthesis.get(
            "status"
        )
    )

    print(
        "Operational nucleus           :",
        cross_summary.get(
            "operational_nucleus"
        )
    )

    print(
        "Runtime components            :",
        cross_summary.get(
            "runtime_components"
        )
    )

    print(
        "Health risks                  :",
        cross_summary.get(
            "health_risks"
        )
    )

    print(
        "Performance risks             :",
        cross_summary.get(
            "performance_risks"
        )
    )

    print(
        "Confirmed bottlenecks         :",
        cross_summary.get(
            "confirmed_bottlenecks"
        )
    )

    print(
        "Confirmed problems            :",
        cross_summary.get(
            "confirmed_problems"
        )
    )

    print(
        "Cross contradictions          :",
        cross_summary.get(
            "cross_analyzer_contradictions"
        )
    )

    print(
        "Component registry            :",
        len(
            component_registry
        )
    )

    print()

    print(
        "Report:",
        OUTPUT_FILE
    )

    print()

    print(
        "FINAL INTELLIGENCE STATUS:",
        result[
            "final_intelligence_status"
        ]
    )

    print("=" * 100)


if __name__ == "__main__":
    main()


# ============================================================================
# STAGE 2 - UNIVERSAL PROJECT INTELLIGENCE MODEL
# ============================================================================

def safe_dict(value):

    return (
        value
        if isinstance(value, dict)
        else {}
    )


def safe_list(value):

    return (
        value
        if isinstance(value, list)
        else []
    )


def build_project_intelligence_model():

    reports = {}

    for number, path in REPORTS.items():

        data, error = load_json(
            path
        )

        if (
            error is None
            and isinstance(data, dict)
        ):
            reports[number] = data

    a01 = reports.get("01", {})
    a02 = reports.get("02", {})
    a03 = reports.get("03", {})
    a04 = reports.get("04", {})
    a05 = reports.get("05", {})
    a06 = reports.get("06", {})
    a07 = reports.get("07", {})
    a08 = reports.get("08", {})
    a09 = reports.get("09", {})
    a10 = reports.get("10", {})

    cross = safe_dict(
        a10.get(
            "cross_synthesis"
        )
    )

    cross_summary = safe_dict(
        cross.get(
            "summary"
        )
    )

    components = safe_list(
        a10.get(
            "component_registry"
        )
    )

    active_components = [
        item
        for item in components
        if item.get("state")
        == "ACTIVE_CONFIRMED"
    ]

    connected_components = [
        item
        for item in components
        if item.get("state")
        == "CONNECTED_CONFIRMED"
    ]

    runtime_components = [
        item
        for item in components
        if item.get(
            "runtime_confirmed"
        )
    ]

    project_structure = {
        "summary":
            safe_dict(
                a01.get(
                    "summary"
                )
            ),

        "categories":
            safe_dict(
                a01.get(
                    "categories"
                )
            ),

        "extensions":
            safe_dict(
                a01.get(
                    "extensions"
                )
            ),

        "entrypoint_candidates":
            len(
                safe_list(
                    a01.get(
                        "entrypoint_candidates"
                    )
                )
            ),

        "backup_candidates":
            len(
                safe_list(
                    a01.get(
                        "backup_candidates"
                    )
                )
            ),

        "test_files":
            len(
                safe_list(
                    a01.get(
                        "test_files"
                    )
                )
            ),

        "large_files":
            safe_list(
                a01.get(
                    "large_files"
                )
            ),

        "zero_byte_files":
            safe_list(
                a01.get(
                    "zero_byte_files"
                )
            ),

        "exact_duplicate_groups":
            len(
                safe_list(
                    a01.get(
                        "exact_duplicate_groups"
                    )
                )
            ),
    }

    runtime = {
        "summary":
            safe_dict(
                a02.get(
                    "summary"
                )
            ),

        "project_processes":
            safe_list(
                a02.get(
                    "project_processes"
                )
            ),

        "project_listening_ports":
            safe_list(
                a02.get(
                    "project_listening_ports"
                )
            ),

        "collection_errors":
            safe_list(
                a02.get(
                    "errors"
                )
            ),
    }

    databases = {
        "summary":
            safe_dict(
                a03.get(
                    "summary"
                )
            ),

        "technologies":
            safe_dict(
                a03.get(
                    "database_technologies"
                )
            ),

        "databases":
            safe_list(
                a03.get(
                    "databases"
                )
            ),

        "code_references":
            safe_dict(
                a03.get(
                    "code_database_references"
                )
            ),
    }

    code_architecture = {
        "summary":
            safe_dict(
                a04.get(
                    "summary"
                )
            ),

        "internal_connections":
            safe_list(
                a04.get(
                    "internal_connections"
                )
            ),

        "most_depended_on":
            safe_list(
                a04.get(
                    "most_depended_on"
                )
            ),

        "reverse_dependencies":
            safe_dict(
                a04.get(
                    "reverse_dependencies"
                )
            ),

        "parse_errors":
            safe_list(
                a04.get(
                    "parse_errors"
                )
            ),
    }

    configuration = {
        "summary":
            safe_dict(
                a05.get(
                    "summary"
                )
            ),

        "runtime_configuration":
            safe_dict(
                a05.get(
                    "runtime_configuration"
                )
            ),

        "possible_secret_locations_count":
            len(
                safe_list(
                    a05.get(
                        "possible_secret_locations"
                    )
                )
            ),

        "python_constants_count":
            len(
                safe_list(
                    a05.get(
                        "python_constants"
                    )
                )
            ),

        "duplicated_constant_names_count":
            len(
                safe_list(
                    a05.get(
                        "duplicated_constant_names"
                    )
                )
            ),
    }

    api = {
        "summary":
            safe_dict(
                a06.get(
                    "summary"
                )
            ),

        "frameworks":
            safe_dict(
                a06.get(
                    "frameworks"
                )
            ),

        "endpoints":
            safe_list(
                a06.get(
                    "endpoints"
                )
            ),

        "router_connections":
            safe_list(
                a06.get(
                    "router_connections"
                )
            ),

        "server_calls":
            safe_list(
                a06.get(
                    "server_calls"
                )
            ),

        "runtime_integration":
            safe_dict(
                a06.get(
                    "runtime_integration"
                )
            ),

        "endpoint_overlaps":
            safe_dict(
                a06.get(
                    "endpoint_overlaps"
                )
            ),

        "parse_errors":
            safe_list(
                a06.get(
                    "parse_errors"
                )
            ),
    }

    data_flow = {
        "summary":
            safe_dict(
                a07.get(
                    "summary"
                )
            ),

        "classification_summary":
            safe_dict(
                a07.get(
                    "classification_summary"
                )
            ),

        "external_sources_count":
            len(
                safe_list(
                    a07.get(
                        "external_sources"
                    )
                )
            ),

        "network_calls_count":
            len(
                safe_list(
                    a07.get(
                        "network_calls"
                    )
                )
            ),

        "database_connections_count":
            len(
                safe_list(
                    a07.get(
                        "database_connections"
                    )
                )
            ),

        "database_operations_count":
            len(
                safe_list(
                    a07.get(
                        "database_operations"
                    )
                )
            ),

        "file_operations_count":
            len(
                safe_list(
                    a07.get(
                        "file_operations"
                    )
                )
            ),

        "api_outputs_count":
            len(
                safe_list(
                    a07.get(
                        "api_outputs"
                    )
                )
            ),

        "queue_cache_operations_count":
            len(
                safe_list(
                    a07.get(
                        "queue_cache_operations"
                    )
                )
            ),

        "lineage":
            safe_dict(
                a07.get(
                    "stage2_lineage"
                )
            ),

        "flow_chains":
            safe_list(
                a07.get(
                    "flow_chains"
                )
            ),
    }

    health = {
        "summary":
            safe_dict(
                a08.get(
                    "health_summary"
                )
            ),

        "operational_health_risks":
            safe_list(
                a08.get(
                    "operational_health_risks"
                )
            ),

        "runtime_health":
            safe_dict(
                a08.get(
                    "runtime_health"
                )
            ),

        "database_health":
            safe_dict(
                a08.get(
                    "database_health"
                )
            ),

        "log_health":
            safe_dict(
                a08.get(
                    "log_health"
                )
            ),

        "syntax_errors":
            safe_list(
                a08.get(
                    "syntax_errors"
                )
            ),

        "compile_warnings":
            safe_list(
                a08.get(
                    "compile_warnings"
                )
            ),

        "methodology":
            safe_dict(
                a08.get(
                    "health_methodology"
                )
            ),
    }

    performance = {
        "summary":
            safe_dict(
                a09.get(
                    "summary"
                )
            ),

        "status":
            safe_dict(
                a09.get(
                    "performance_status"
                )
            ),

        "risks":
            safe_list(
                a09.get(
                    "performance_risks"
                )
            ),

        "confirmed_bottlenecks":
            safe_list(
                a09.get(
                    "confirmed_bottlenecks"
                )
            ),

        "database_index_analysis":
            safe_dict(
                a09.get(
                    "database_index_analysis"
                )
            ),

        "methodology":
            safe_dict(
                a09.get(
                    "methodology"
                )
            ),
    }

    operational_nucleus = {
        "active_confirmed":
            active_components,

        "connected_confirmed":
            connected_components,

        "runtime_confirmed":
            runtime_components,

        "active_count":
            len(
                active_components
            ),

        "connected_count":
            len(
                connected_components
            ),

        "runtime_count":
            len(
                runtime_components
            ),

        "total_operational":
            (
                len(active_components)
                + len(connected_components)
            ),
    }

    evidence_state = {
        "cross_status":
            cross.get(
                "status"
            ),

        "confirmed_facts":
            safe_list(
                cross.get(
                    "confirmed_facts"
                )
            ),

        "identified_findings":
            safe_list(
                cross.get(
                    "findings"
                )
            ),

        "contradictions":
            safe_list(
                cross.get(
                    "contradictions"
                )
            ),

        "limitations":
            safe_list(
                cross.get(
                    "limitations"
                )
            ),

        "confirmed_problem_count":
            cross_summary.get(
                "confirmed_problems"
            ),

        "confirmed_bottleneck_count":
            cross_summary.get(
                "confirmed_bottlenecks"
            ),

        "health_risk_count":
            cross_summary.get(
                "health_risks"
            ),

        "performance_risk_count":
            cross_summary.get(
                "performance_risks"
            ),
    }

    model = {
        "identity": {
            "project_name":
                PROJECT_NAME,

            "project_root":
                str(
                    PROJECT_ROOT
                ),

            "intelligence_type":
                "UNIVERSAL_PYTHON_PROJECT",

            "evidence_sources":
                "ANALYZERS_01_TO_10",
        },

        "project_structure":
            project_structure,

        "operational_nucleus":
            operational_nucleus,

        "runtime":
            runtime,

        "code_architecture":
            code_architecture,

        "databases":
            databases,

        "configuration":
            configuration,

        "api":
            api,

        "data_flow":
            data_flow,

        "health":
            health,

        "performance":
            performance,

        "evidence_state":
            evidence_state,
    }

    return model


def run_stage2():

    existing, error = load_json(
        OUTPUT_FILE
    )

    if (
        error is not None
        or not isinstance(
            existing,
            dict
        )
    ):
        existing = {}

    model = (
        build_project_intelligence_model()
    )

    existing[
        "project_intelligence_model"
    ] = model

    existing[
        "final_intelligence_status"
    ] = (
        "PROJECT_INTELLIGENCE_MODEL_READY"
    )

    existing[
        "stage"
    ] = 2

    OUTPUT_FILE.write_text(
        json.dumps(
            existing,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    return existing


def print_stage2():

    result = run_stage2()

    model = result[
        "project_intelligence_model"
    ]

    nucleus = model[
        "operational_nucleus"
    ]

    evidence = model[
        "evidence_state"
    ]

    print()
    print("=" * 100)
    print(
        "ANALYZER 11 V2 - "
        "STAGE 2 PROJECT INTELLIGENCE MODEL"
    )
    print("=" * 100)

    print(
        "Project                     :",
        model[
            "identity"
        ][
            "project_name"
        ]
    )

    print(
        "Operational active          :",
        nucleus[
            "active_count"
        ]
    )

    print(
        "Operational connected       :",
        nucleus[
            "connected_count"
        ]
    )

    print(
        "Operational total           :",
        nucleus[
            "total_operational"
        ]
    )

    print(
        "Runtime confirmed           :",
        nucleus[
            "runtime_count"
        ]
    )

    print(
        "Health risks                :",
        evidence[
            "health_risk_count"
        ]
    )

    print(
        "Performance risks           :",
        evidence[
            "performance_risk_count"
        ]
    )

    print(
        "Confirmed bottlenecks       :",
        evidence[
            "confirmed_bottleneck_count"
        ]
    )

    print(
        "Confirmed problems          :",
        evidence[
            "confirmed_problem_count"
        ]
    )

    print(
        "Contradictions              :",
        len(
            evidence[
                "contradictions"
            ]
        )
    )

    print(
        "Evidence limitations        :",
        len(
            evidence[
                "limitations"
            ]
        )
    )

    print()

    print(
        "Sections                    :",
        len(model)
    )

    for key in model:
        print(
            "  -",
            key
        )

    print()

    print(
        "Report:",
        OUTPUT_FILE
    )

    print()

    print(
        "FINAL INTELLIGENCE STATUS:",
        result[
            "final_intelligence_status"
        ]
    )

    print("=" * 100)


print_stage2()



# STAGE 3 - FINAL PACKAGE

def build_final_package():

    result, error = load_json(
        OUTPUT_FILE
    )

    if error is not None:
        raise RuntimeError(
            "Stage 3: FINAL_PROJECT_INTELLIGENCE.json non disponibile"
        )

    if not isinstance(result, dict):
        raise RuntimeError(
            "Stage 3: JSON finale non valido"
        )

    model = result.get(
        "project_intelligence_model"
    )

    if not isinstance(model, dict):
        raise RuntimeError(
            "Stage 3: project_intelligence_model non disponibile"
        )

    package = (
        OUTPUT_DIR
        / "PROJECT_INTELLIGENCE_PACKAGE"
    )

    package.mkdir(
        parents=True,
        exist_ok=True
    )

    sections = [
        ("identity", "IDENTITY"),
        ("project_structure", "PROJECT STRUCTURE"),
        ("operational_nucleus", "OPERATIONAL NUCLEUS"),
        ("runtime", "RUNTIME"),
        ("code_architecture", "CODE ARCHITECTURE"),
        ("databases", "DATABASES"),
        ("configuration", "CONFIGURATION"),
        ("api", "API"),
        ("data_flow", "DATA FLOW"),
        ("health", "HEALTH"),
        ("performance", "PERFORMANCE"),
        ("evidence_state", "EVIDENCE STATE"),
    ]

    def dump(value):

        return json.dumps(
            value,
            indent=2,
            ensure_ascii=False,
            default=str
        )

    files = {}

    files["00_READ_ME_FIRST.txt"] = (
        "PYTHON PROJECT INTELLIGENCE\n"
        "FINAL PROJECT INTELLIGENCE PACKAGE\n"
        "\n"
        f"PROJECT: {PROJECT_NAME}\n"
        f"PROJECT ROOT: {PROJECT_ROOT}\n"
        "\n"
        "This package is generated exclusively from the "
        "Project Intelligence Model produced by Analyzer 11 "
        "Stage 2.\n"
        "\n"
        "The package is a synthesis of Analyzer 01-10 evidence.\n"
        "It does not perform a new project scan.\n"
        "It does not modify the operational project.\n"
    )

    files["01_EXECUTIVE_SUMMARY.md"] = (
        "# Executive Summary\n\n"
        f"## Project\n\n"
        f"- Name: `{PROJECT_NAME}`\n"
        f"- Root: `{PROJECT_ROOT}`\n\n"
        "## Evidence Status\n\n"
        f"```json\n{dump(model.get('evidence_state', {}))}\n```\n\n"
        "## Operational Nucleus\n\n"
        f"```json\n{dump(model.get('operational_nucleus', {}))}\n```\n"
    )

    files["02_OPERATIONAL_ARCHITECTURE.md"] = (
        "# Operational Architecture\n\n"
        "## Identity\n\n"
        f"```json\n{dump(model.get('identity', {}))}\n```\n\n"
        "## Code Architecture\n\n"
        f"```json\n{dump(model.get('code_architecture', {}))}\n```\n"
    )

    files["03_RUNTIME.md"] = (
        "# Runtime\n\n"
        f"```json\n{dump(model.get('runtime', {}))}\n```\n"
    )

    files["04_DATABASE.md"] = (
        "# Database\n\n"
        f"```json\n{dump(model.get('databases', {}))}\n```\n"
    )

    files["05_API_AND_DATA_FLOW.md"] = (
        "# API and Data Flow\n\n"
        "## API\n\n"
        f"```json\n{dump(model.get('api', {}))}\n```\n\n"
        "## Data Flow\n\n"
        f"```json\n{dump(model.get('data_flow', {}))}\n```\n"
    )

    files["06_HEALTH_AND_RELIABILITY.md"] = (
        "# Health and Reliability\n\n"
        f"```json\n{dump(model.get('health', {}))}\n```\n"
    )

    files["07_PERFORMANCE.md"] = (
        "# Performance\n\n"
        f"```json\n{dump(model.get('performance', {}))}\n```\n"
    )

    files["08_STRUCTURE_AND_CONFIGURATION.md"] = (
        "# Structure and Configuration\n\n"
        "## Project Structure\n\n"
        f"```json\n{dump(model.get('project_structure', {}))}\n```\n\n"
        "## Configuration\n\n"
        f"```json\n{dump(model.get('configuration', {}))}\n```\n"
    )

    files["09_RISKS_AND_LIMITATIONS.md"] = (
        "# Risks and Limitations\n\n"
        "## Health\n\n"
        f"```json\n{dump(model.get('health', {}))}\n```\n\n"
        "## Performance\n\n"
        f"```json\n{dump(model.get('performance', {}))}\n```\n\n"
        "## Evidence Limitations\n\n"
        f"```json\n{dump(model.get('evidence_state', {}))}\n```\n"
    )

    files["10_AI_CONTEXT.md"] = (
        "# AI Context\n\n"
        f"Project: `{PROJECT_NAME}`\n\n"
        f"Root: `{PROJECT_ROOT}`\n\n"
        "The following Project Intelligence Model represents "
        "the synthesized evidence available at the end of "
        "Analyzer 11 Stage 2.\n\n"
        f"```json\n{dump(model)}\n```\n"
    )

    written = []

    for name, content in files.items():

        path = package / name

        path.write_text(
            content,
            encoding="utf-8"
        )

        written.append(path)

    manifest = {
        "project_name": PROJECT_NAME,
        "project_root": str(PROJECT_ROOT),
        "package": "PROJECT_INTELLIGENCE_PACKAGE",
        "source": "ANALYZER_11_STAGE_2",
        "file_count": len(written) + 1,
        "files": [
            path.name
            for path in written
        ],
    }

    manifest_path = package / "MANIFEST.json"

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    written.append(manifest_path)

    result["final_package"] = {
        "directory": str(package),
        "files": [
            path.name
            for path in written
        ],
        "file_count": len(written),
    }

    result["stage"] = 3

    result["final_intelligence_status"] = (
        "FINAL_PROJECT_INTELLIGENCE_READY"
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    return result, package, written


def print_stage3():

    result, package, written = (
        build_final_package()
    )

    required = [
        "00_READ_ME_FIRST.txt",
        "01_EXECUTIVE_SUMMARY.md",
        "02_OPERATIONAL_ARCHITECTURE.md",
        "03_RUNTIME.md",
        "04_DATABASE.md",
        "05_API_AND_DATA_FLOW.md",
        "06_HEALTH_AND_RELIABILITY.md",
        "07_PERFORMANCE.md",
        "08_STRUCTURE_AND_CONFIGURATION.md",
        "09_RISKS_AND_LIMITATIONS.md",
        "10_AI_CONTEXT.md",
        "MANIFEST.json",
    ]

    missing = [
        name
        for name in required
        if not (
            package / name
        ).is_file()
    ]

    empty = [
        name
        for name in required
        if (
            package / name
        ).is_file()
        and (
            package / name
        ).stat().st_size == 0
    ]

    print()
    print("=" * 100)
    print("ANALYZER 11 - STAGE 3 FINAL PACKAGE")
    print("=" * 100)

    print("Package :", package)
    print("Files   :", len(written))
    print("Missing :", len(missing))
    print("Empty   :", len(empty))

    if missing:
        raise RuntimeError(
            "Stage 3 missing: "
            + ", ".join(missing)
        )

    if empty:
        raise RuntimeError(
            "Stage 3 empty: "
            + ", ".join(empty)
        )

    print(
        "FINAL INTELLIGENCE STATUS:",
        result[
            "final_intelligence_status"
        ]
    )

    print("=" * 100)


print_stage3()
