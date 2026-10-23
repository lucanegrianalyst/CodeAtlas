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
    / "10_CROSS_ANALYSIS"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "CROSS_ANALYSIS_MAP.json"
)

REPORTS = {
    "01": (
        LATEST
        / "01_PROJECT_STRUCTURE"
        / "PROJECT_STRUCTURE.json"
    ),

    "02": (
        LATEST
        / "02_RUNTIME"
        / "RUNTIME_MAP.json"
    ),

    "03": (
        LATEST
        / "03_DATABASE"
        / "DATABASE_MAP.json"
    ),

    "04": (
        LATEST
        / "04_CODE_CONNECTIONS"
        / "CODE_CONNECTIONS.json"
    ),

    "05": (
        LATEST
        / "05_CONFIGURATION"
        / "CONFIGURATION_MAP.json"
    ),

    "06": (
        LATEST
        / "06_API_ENDPOINTS"
        / "API_ENDPOINTS_MAP.json"
    ),

    "07": (
        LATEST
        / "07_DATA_FLOW"
        / "DATA_FLOW_MAP.json"
    ),

    "08": (
        LATEST
        / "08_HEALTH_ERRORS"
        / "HEALTH_ERROR_MAP.json"
    ),

    "09": (
        LATEST
        / "09_PERFORMANCE_BOTTLENECK"
        / "PERFORMANCE_MAP.json"
    ),
}


def load_json(path):

    try:

        return json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        ), None

    except Exception as exc:

        return None, repr(exc)


def describe_value(value):

    if isinstance(value, dict):
        return {
            "type": "dict",
            "size": len(value),
        }

    if isinstance(value, list):
        return {
            "type": "list",
            "size": len(value),
        }

    return {
        "type":
            type(value).__name__,

        "value_preview":
            str(value)[:160],
    }


def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    loaded = {}
    inventory = {}
    errors = []

    print("=" * 100)
    print(
        "PYTHON PROJECT INTELLIGENCE"
    )
    print(
        "ANALYZER 10 - CROSS ANALYZER V2 TEST"
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
        "Mode   : READ ONLY"
    )

    print()
    print("=" * 100)
    print(
        "STAGE 1 - OFFICIAL REPORT INVENTORY"
    )
    print("=" * 100)

    for analyzer, path in REPORTS.items():

        exists = path.exists()

        entry = {
            "analyzer":
                analyzer,

            "path":
                str(path),

            "exists":
                exists,

            "loaded":
                False,

            "root_keys":
                [],

            "root_schema":
                {},
        }

        if not exists:

            entry[
                "error"
            ] = "REPORT_NOT_FOUND"

            errors.append({
                "analyzer":
                    analyzer,

                "type":
                    "REPORT_NOT_FOUND",

                "path":
                    str(path),
            })

            inventory[
                analyzer
            ] = entry

            print(
                f"{analyzer} | MISSING | "
                f"{path.name}"
            )

            continue

        data, error = load_json(
            path
        )

        if error is not None:

            entry[
                "error"
            ] = error

            errors.append({
                "analyzer":
                    analyzer,

                "type":
                    "REPORT_LOAD_ERROR",

                "path":
                    str(path),

                "error":
                    error,
            })

            inventory[
                analyzer
            ] = entry

            print(
                f"{analyzer} | ERROR   | "
                f"{path.name}"
            )

            continue

        loaded[
            analyzer
        ] = data

        entry[
            "loaded"
        ] = True

        if isinstance(
            data,
            dict
        ):

            entry[
                "root_keys"
            ] = list(
                data.keys()
            )

            entry[
                "root_schema"
            ] = {
                key:
                    describe_value(value)

                for key, value
                in data.items()
            }

        inventory[
            analyzer
        ] = entry

        print(
            f"{analyzer} | OK      | "
            f"{path.name} | "
            f"keys="
            f"{len(entry['root_keys'])}"
        )

    all_available = (
        len(loaded)
        == len(REPORTS)
    )

    result = {
        "metadata": {
            "analyzer":
                "10_CROSS_ANALYZER_V2",

            "stage":
                1,

            "project_name":
                PROJECT_NAME,

            "project_root":
                str(PROJECT_ROOT),

            "generated_at_utc":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "mode":
                "READ_ONLY",

            "direct_project_scan":
                False,

            "direct_process_query":
                False,

            "direct_database_query":
                False,

            "source_of_truth":
                "ANALYZERS_01_TO_09",
        },

        "summary": {
            "reports_expected":
                len(REPORTS),

            "reports_found":
                sum(
                    1
                    for item
                    in inventory.values()
                    if item["exists"]
                ),

            "reports_loaded":
                len(loaded),

            "reports_missing":
                sum(
                    1
                    for item
                    in inventory.values()
                    if not item["exists"]
                ),

            "report_load_errors":
                len(errors),

            "all_reports_available":
                all_available,
        },

        "report_inventory":
            inventory,

        "load_errors":
            errors,

        "cross_analysis": {
            "status":
                "NOT_RUN_STAGE_1",

            "reason":
                (
                    "Stage 1 validates official "
                    "Analyzer 01-09 reports before "
                    "cross-correlation."
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

    print()
    print("=" * 100)
    print("STAGE 1 RESULTS")
    print("=" * 100)

    for key, value in (
        result[
            "summary"
        ].items()
    ):

        print(
            f"{key:<30}: {value}"
        )

    print()
    print("=" * 100)
    print("ROOT SCHEMAS")
    print("=" * 100)

    for analyzer in sorted(
        inventory
    ):

        item = inventory[
            analyzer
        ]

        if not item[
            "loaded"
        ]:
            continue

        print()
        print(
            f"ANALYZER {analyzer}"
        )

        print("-" * 100)

        for key, info in (
            item[
                "root_schema"
            ].items()
        ):

            if (
                info["type"]
                in {
                    "dict",
                    "list",
                }
            ):

                print(
                    f"{key:<40} "
                    f"{info['type'].upper()}"
                    f"[{info['size']}]"
                )

            else:

                print(
                    f"{key:<40} "
                    f"{info['type']}"
                )

    print()
    print(
        "Report:",
        OUTPUT_FILE
    )

    print()

    if all_available and not errors:

        print(
            "ANALYZER 10 STAGE 1 STATUS: OK"
        )

    else:

        print(
            "ANALYZER 10 STAGE 1 STATUS: "
            "INCOMPLETE"
        )

    print("=" * 100)


if __name__ == "__main__":
    main()


# ============================================================================
# STAGE 2 - UNIVERSAL COMPONENT EVIDENCE REGISTRY
# ============================================================================

def normalize_file(value):

    if not value:
        return ""

    value = str(value).strip()

    value = value.replace(
        "/",
        "\\"
    )

    try:

        path = Path(value)

        if path.is_absolute():

            try:
                value = str(
                    path.relative_to(
                        PROJECT_ROOT
                    )
                )

            except ValueError:
                pass

    except Exception:
        pass

    return value.lower()


def looks_like_python_file(value):

    value = normalize_file(
        value
    )

    return value.endswith(
        ".py"
    )


def extract_file_from_item(item):

    if isinstance(
        item,
        str
    ):

        if looks_like_python_file(
            item
        ):
            return normalize_file(
                item
            )

        return ""

    if not isinstance(
        item,
        dict
    ):
        return ""

    candidate_keys = (
        "file",
        "path",
        "script",
        "source",
        "source_file",
        "relative_path",
        "module_file",
    )

    for key in candidate_keys:

        value = item.get(
            key
        )

        if (
            isinstance(
                value,
                str
            )
            and looks_like_python_file(
                value
            )
        ):

            return normalize_file(
                value
            )

    return ""


def add_evidence(
    registry,
    file,
    analyzer,
    evidence_type,
    detail=None,
):

    file = normalize_file(
        file
    )

    if not looks_like_python_file(
        file
    ):
        return

    component = registry.setdefault(
        file,
        {
            "file":
                file,

            "evidence":
                [],

            "analyzers":
                set(),

            "evidence_types":
                set(),

            "runtime_confirmed":
                False,

            "operational_confirmed":
                False,

            "operational_connected":
                False,

            "api_evidence":
                False,

            "database_evidence":
                False,

            "data_flow_evidence":
                False,

            "health_risk_count":
                0,

            "performance_risk_count":
                0,
        }
    )

    component[
        "analyzers"
    ].add(
        analyzer
    )

    component[
        "evidence_types"
    ].add(
        evidence_type
    )

    evidence = {
        "analyzer":
            analyzer,

        "type":
            evidence_type,
    }

    if detail is not None:
        evidence[
            "detail"
        ] = detail

    component[
        "evidence"
    ].append(
        evidence
    )


def build_component_registry(
    reports
):

    registry = {}

    # ------------------------------------------------------------
    # Analyzer 01 - physical project inventory
    # ------------------------------------------------------------

    a01 = reports.get(
        "01",
        {}
    )

    for item in a01.get(
        "files",
        []
    ):

        file = extract_file_from_item(
            item
        )

        if file:

            add_evidence(
                registry,
                file,
                "01",
                "PHYSICAL_FILE",
            )

    # ------------------------------------------------------------
    # Analyzer 02 - runtime
    # ------------------------------------------------------------

    a02 = reports.get(
        "02",
        {}
    )

    for item in a02.get(
        "project_processes",
        []
    ):

        command = (
            item.get(
                "command_line",
                ""
            )
            if isinstance(
                item,
                dict
            )
            else ""
        )

        matched = []

        normalized_command = (
            str(command)
            .replace(
                "/",
                "\\"
            )
            .lower()
        )

        # --------------------------------------------------------
        # Exact runtime matching.
        #
        # Supported forms:
        #
        #   python script.py
        #   python C:\\project\\script.py
        #   python -m package.module
        #
        # A filename is NEVER matched as a generic substring.
        # This prevents:
        #
        #   dashboard.py
        #
        # from matching:
        #
        #   crypto_news_dashboard.py
        #   minmax_dashboard.py
        # --------------------------------------------------------

        command_tokens = (
            normalized_command
            .replace(
                '"',
                " "
            )
            .split()
        )

        module_name = None

        if "-m" in command_tokens:

            module_index = (
                command_tokens.index(
                    "-m"
                )
            )

            if (
                module_index + 1
                < len(command_tokens)
            ):

                module_name = (
                    command_tokens[
                        module_index + 1
                    ]
                    .strip()
                )

        for file in list(
            registry.keys()
        ):

            file_normalized = (
                file
                .replace(
                    "/",
                    "\\"
                )
                .lower()
            )

            file_name = Path(
                file_normalized
            ).name

            absolute_file = str(
                PROJECT_ROOT
                / Path(
                    file_normalized
                )
            ).replace(
                "/",
                "\\"
            ).lower()

            exact_script_match = False

            for token in command_tokens:

                token_clean = (
                    token
                    .strip()
                    .strip('"')
                    .replace(
                        "/",
                        "\\"
                    )
                )

                if (
                    token_clean
                    == file_normalized
                    or token_clean
                    == absolute_file
                ):

                    exact_script_match = True
                    break

                if (
                    "\\" not in token_clean
                    and token_clean == file_name
                    and "\\" not in file_normalized
                ):

                    exact_script_match = True
                    break

            module_match = False

            if (
                module_name
                and file_normalized.endswith(
                    ".py"
                )
            ):

                expected_module = (
                    file_normalized[:-3]
                    .replace(
                        "\\",
                        "."
                    )
                )

                module_match = (
                    module_name
                    == expected_module
                )

            if (
                exact_script_match
                or module_match
            ):

                matched.append(
                    file
                )

        for file in matched:

            add_evidence(
                registry,
                file,
                "02",
                "RUNTIME_PROCESS",
                {
                    "pid":
                        item.get(
                            "pid"
                        ),

                    "ports":
                        item.get(
                            "listening_ports",
                            []
                        ),
                },
            )

            registry[
                file
            ][
                "runtime_confirmed"
            ] = True

    # ------------------------------------------------------------
    # Analyzer 04 - code connections
    # ------------------------------------------------------------

    a04 = reports.get(
        "04",
        {}
    )

    for item in a04.get(
        "internal_connections",
        []
    ):

        if not isinstance(
            item,
            dict
        ):
            continue

        source = (
            item.get("source")
            or item.get("from")
            or item.get("source_file")
        )

        target = (
            item.get("target")
            or item.get("to")
            or item.get("target_file")
        )

        if source:

            add_evidence(
                registry,
                source,
                "04",
                "CODE_CONNECTION_SOURCE",
            )

        if target:

            add_evidence(
                registry,
                target,
                "04",
                "CODE_CONNECTION_TARGET",
            )

    # ------------------------------------------------------------
    # Analyzer 06 - API
    # ------------------------------------------------------------

    a06 = reports.get(
        "06",
        {}
    )

    for item in a06.get(
        "endpoints",
        []
    ):

        file = extract_file_from_item(
            item
        )

        if file:

            add_evidence(
                registry,
                file,
                "06",
                "API_ENDPOINT",
            )

            registry[
                file
            ][
                "api_evidence"
            ] = True

    for file, info in (
        a06.get(
            "file_runtime_classification",
            {}
        ).items()
    ):

        if not isinstance(
            info,
            dict
        ):
            continue

        add_evidence(
            registry,
            file,
            "06",
            "API_RUNTIME_CLASSIFICATION",
            {
                "status":
                    info.get(
                        "status"
                    )
            },
        )

    # ------------------------------------------------------------
    # Analyzer 07 - operational classification + data flow
    # ------------------------------------------------------------

    a07 = reports.get(
        "07",
        {}
    )

    for file, info in (
        a07.get(
            "project_file_classification",
            {}
        ).items()
    ):

        if not isinstance(
            info,
            dict
        ):
            continue

        status = info.get(
            "status"
        )

        add_evidence(
            registry,
            file,
            "07",
            "PROJECT_CLASSIFICATION",
            {
                "status":
                    status
            },
        )

        normalized = normalize_file(
            file
        )

        if normalized in registry:

            if (
                status
                == "OPERATIONAL_CONFIRMED"
            ):

                registry[
                    normalized
                ][
                    "operational_confirmed"
                ] = True

            elif (
                status
                == "OPERATIONAL_CONNECTED"
            ):

                registry[
                    normalized
                ][
                    "operational_connected"
                ] = True

    flow_sections = (
        "network_calls",
        "database_connections",
        "database_operations",
        "file_operations",
        "api_outputs",
        "queue_cache_operations",
    )

    for section in flow_sections:

        for item in a07.get(
            section,
            []
        ):

            file = extract_file_from_item(
                item
            )

            if not file:
                continue

            add_evidence(
                registry,
                file,
                "07",
                "DATA_FLOW_" +
                section.upper(),
            )

            registry[
                file
            ][
                "data_flow_evidence"
            ] = True

            if section in {
                "database_connections",
                "database_operations",
            }:

                registry[
                    file
                ][
                    "database_evidence"
                ] = True

    # ------------------------------------------------------------
    # Analyzer 08 - operational health risks
    # ------------------------------------------------------------

    a08 = reports.get(
        "08",
        {}
    )

    for item in a08.get(
        "operational_health_risks",
        []
    ):

        file = extract_file_from_item(
            item
        )

        if not file:
            continue

        add_evidence(
            registry,
            file,
            "08",
            "HEALTH_RISK",
            {
                "severity":
                    item.get(
                        "severity"
                    ),

                "type":
                    item.get(
                        "type"
                    ),
            },
        )

        registry[
            file
        ][
            "health_risk_count"
        ] += 1

    # ------------------------------------------------------------
    # Analyzer 09 - performance risks
    # ------------------------------------------------------------

    a09 = reports.get(
        "09",
        {}
    )

    for item in a09.get(
        "performance_risks",
        []
    ):

        file = extract_file_from_item(
            item
        )

        if not file:
            continue

        add_evidence(
            registry,
            file,
            "09",
            "PERFORMANCE_RISK",
            {
                "severity":
                    item.get(
                        "severity"
                    ),

                "confidence":
                    item.get(
                        "confidence"
                    ),

                "type":
                    item.get(
                        "type"
                    ),
            },
        )

        registry[
            file
        ][
            "performance_risk_count"
        ] += 1

    # ------------------------------------------------------------
    # Final confidence / state
    # ------------------------------------------------------------

    final = []

    for file, component in (
        registry.items()
    ):

        evidence_sources = len(
            component[
                "analyzers"
            ]
        )

        if (
            component[
                "runtime_confirmed"
            ]
            or component[
                "operational_confirmed"
            ]
        ):

            state = (
                "ACTIVE_CONFIRMED"
            )

        elif component[
            "operational_connected"
        ]:

            state = (
                "CONNECTED_CONFIRMED"
            )

        elif evidence_sources >= 3:

            state = (
                "MULTI_SOURCE_COMPONENT"
            )

        else:

            state = (
                "INVENTORY_ONLY"
            )

        if evidence_sources >= 4:

            confidence = "CONFIRMED"

        elif evidence_sources >= 2:

            confidence = "PROBABLE"

        elif evidence_sources == 1:

            confidence = "POSSIBLE"

        else:

            confidence = "UNKNOWN"

        component[
            "state"
        ] = state

        component[
            "confidence"
        ] = confidence

        component[
            "evidence_source_count"
        ] = evidence_sources

        component[
            "analyzers"
        ] = sorted(
            component[
                "analyzers"
            ]
        )

        component[
            "evidence_types"
        ] = sorted(
            component[
                "evidence_types"
            ]
        )

        final.append(
            component
        )

    final.sort(
        key=lambda item: (
            -item[
                "evidence_source_count"
            ],
            item[
                "file"
            ],
        )
    )

    return final


def run_stage2():

    reports = {}

    for analyzer, path in (
        REPORTS.items()
    ):

        data, error = load_json(
            path
        )

        if (
            error is None
            and isinstance(
                data,
                dict
            )
        ):

            reports[
                analyzer
            ] = data

    components = (
        build_component_registry(
            reports
        )
    )

    counts = {}

    for item in components:

        state = item[
            "state"
        ]

        counts[
            state
        ] = (
            counts.get(
                state,
                0
            )
            + 1
        )

    runtime_confirmed = sum(
        1
        for item in components
        if item[
            "runtime_confirmed"
        ]
    )

    health_components = sum(
        1
        for item in components
        if item[
            "health_risk_count"
        ] > 0
    )

    performance_components = sum(
        1
        for item in components
        if item[
            "performance_risk_count"
        ] > 0
    )

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

    existing[
        "component_registry"
    ] = components

    existing[
        "component_summary"
    ] = {
        "total_components":
            len(components),

        "states":
            counts,

        "runtime_confirmed":
            runtime_confirmed,

        "components_with_health_risks":
            health_components,

        "components_with_performance_risks":
            performance_components,
    }

    existing[
        "cross_analysis"
    ] = {
        "status":
            "COMPONENT_REGISTRY_BUILT",

        "stage":
            2,

        "interpretation":
            (
                "Components are correlated "
                "across Analyzer 01-09 evidence. "
                "No global problem is inferred "
                "from evidence count alone."
            ),
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            existing,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    return existing


if __name__ == "__main__":

    stage2 = run_stage2()

    print()
    print("=" * 100)
    print(
        "ANALYZER 10 V2 - "
        "STAGE 2 COMPONENT REGISTRY"
    )
    print("=" * 100)

    summary = stage2[
        "component_summary"
    ]

    print(
        "Total components              :",
        summary[
            "total_components"
        ]
    )

    print(
        "Runtime confirmed             :",
        summary[
            "runtime_confirmed"
        ]
    )

    print(
        "Components with health risks  :",
        summary[
            "components_with_health_risks"
        ]
    )

    print(
        "Components with perf. risks   :",
        summary[
            "components_with_performance_risks"
        ]
    )

    print()
    print("STATES")
    print("-" * 100)

    for key, value in sorted(
        summary[
            "states"
        ].items()
    ):

        print(
            f"{key:<30}: {value}"
        )

    print()
    print("TOP CROSS-CONFIRMED COMPONENTS")
    print("-" * 100)

    for item in stage2[
        "component_registry"
    ][:20]:

        print(
            f"{item['evidence_source_count']} sources | "
            f"{item['state']:<22} | "
            f"{item['confidence']:<10} | "
            f"H={item['health_risk_count']} "
            f"P={item['performance_risk_count']} | "
            f"{item['file']}"
        )

    print()
    print(
        "ANALYZER 10 STAGE 2 STATUS: OK"
    )

    print("=" * 100)


# ============================================================================
# STAGE 3 - CROSS EVIDENCE SYNTHESIS
# ============================================================================

def build_cross_synthesis():

    reports = {}

    for analyzer, path in REPORTS.items():

        data, error = load_json(path)

        if (
            error is None
            and isinstance(data, dict)
        ):
            reports[analyzer] = data

    cross, error = load_json(
        OUTPUT_FILE
    )

    if (
        error is not None
        or not isinstance(cross, dict)
    ):
        cross = {}

    components = cross.get(
        "component_registry",
        []
    )

    findings = []
    contradictions = []
    limitations = []
    confirmed_facts = []

    # ------------------------------------------------------------
    # FACT 1 - operational nucleus
    # ------------------------------------------------------------

    active = [
        item
        for item in components
        if item.get("state")
        == "ACTIVE_CONFIRMED"
    ]

    connected = [
        item
        for item in components
        if item.get("state")
        == "CONNECTED_CONFIRMED"
    ]

    runtime = [
        item
        for item in components
        if item.get("runtime_confirmed")
    ]

    confirmed_facts.append({
        "type":
            "OPERATIONAL_NUCLEUS",

        "confidence":
            "CONFIRMED",

        "active_components":
            len(active),

        "connected_components":
            len(connected),

        "total_components":
            len(active) + len(connected),

        "runtime_components":
            len(runtime),

        "evidence":
            ["02", "06", "07", "10"],
    })

    # ------------------------------------------------------------
    # FACT 2 - runtime ports
    # ------------------------------------------------------------

    a02 = reports.get("02", {})

    runtime_ports = a02.get(
        "project_listening_ports",
        []
    )

    confirmed_facts.append({
        "type":
            "PROJECT_RUNTIME_PORTS",

        "confidence":
            "CONFIRMED",

        "count":
            len(runtime_ports),

        "ports":
            runtime_ports,

        "evidence":
            ["02"],
    })

    # ------------------------------------------------------------
    # FACT 3 - database state
    # ------------------------------------------------------------

    a03 = reports.get("03", {})

    db_summary = a03.get(
        "summary",
        {}
    )

    confirmed_facts.append({
        "type":
            "DATABASE_STATE",

        "confidence":
            "CONFIRMED",

        "database_files":
            db_summary.get(
                "database_files",
                db_summary.get(
                    "databases_found"
                )
            ),

        "database_size_mb":
            db_summary.get(
                "database_size_mb",
                db_summary.get(
                    "total_size_mb"
                )
            ),

        "confirmed_rows":
            db_summary.get(
                "confirmed_rows",
                db_summary.get(
                    "total_confirmed_rows"
                )
            ),

        "integrity_problems":
            db_summary.get(
                "integrity_problems"
            ),

        "evidence":
            ["03"],
    })

    # ------------------------------------------------------------
    # FACT 4 - health
    # ------------------------------------------------------------

    a08 = reports.get("08", {})

    health_risks = a08.get(
        "operational_health_risks",
        []
    )

    health_by_severity = {}

    for item in health_risks:

        severity = (
            str(
                item.get(
                    "severity",
                    "UNKNOWN"
                )
            ).upper()
        )

        health_by_severity[
            severity
        ] = (
            health_by_severity.get(
                severity,
                0
            )
            + 1
        )

    confirmed_facts.append({
        "type":
            "OPERATIONAL_HEALTH_RISK_INVENTORY",

        "confidence":
            "CONFIRMED",

        "risk_count":
            len(health_risks),

        "severity_counts":
            health_by_severity,

        "evidence":
            ["08"],
    })

    # ------------------------------------------------------------
    # PERFORMANCE - preserve confidence semantics
    # ------------------------------------------------------------

    a09 = reports.get("09", {})

    perf_risks = a09.get(
        "performance_risks",
        []
    )

    confirmed_bottlenecks = (
        a09.get(
            "confirmed_bottlenecks",
            []
        )
    )

    for item in perf_risks:

        findings.append({
            "domain":
                "PERFORMANCE",

            "type":
                item.get(
                    "type",
                    "PERFORMANCE_RISK"
                ),

            "severity":
                item.get(
                    "severity",
                    "INFO"
                ),

            "confidence":
                item.get(
                    "confidence",
                    "UNKNOWN"
                ),

            "file":
                extract_file_from_item(
                    item
                ),

            "confirmed_problem":
                False,

            "source_analyzer":
                "09",

            "interpretation":
                (
                    "Static performance risk. "
                    "Not promoted to confirmed "
                    "bottleneck without runtime "
                    "measurement evidence."
                ),
        })

    for item in confirmed_bottlenecks:

        findings.append({
            "domain":
                "PERFORMANCE",

            "type":
                item.get(
                    "type",
                    "CONFIRMED_BOTTLENECK"
                )
                if isinstance(item, dict)
                else "CONFIRMED_BOTTLENECK",

            "severity":
                item.get(
                    "severity",
                    "MEDIUM"
                )
                if isinstance(item, dict)
                else "MEDIUM",

            "confidence":
                "CONFIRMED",

            "confirmed_problem":
                True,

            "source_analyzer":
                "09",
        })

    # ------------------------------------------------------------
    # HEALTH - confirmed static findings remain risks,
    # not proof of runtime failure.
    # ------------------------------------------------------------

    for item in health_risks:

        findings.append({
            "domain":
                "HEALTH",

            "type":
                item.get(
                    "type",
                    "HEALTH_RISK"
                ),

            "severity":
                item.get(
                    "severity",
                    "INFO"
                ),

            "confidence":
                item.get(
                    "confidence",
                    "CONFIRMED"
                ),

            "file":
                extract_file_from_item(
                    item
                ),

            "confirmed_problem":
                False,

            "source_analyzer":
                "08",

            "interpretation":
                (
                    "Confirmed code-level risk "
                    "or weakness; not equivalent "
                    "to confirmed runtime failure."
                ),
        })

    # ------------------------------------------------------------
    # OBSERVABILITY LIMITATIONS
    # ------------------------------------------------------------

    log_health = a08.get(
        "log_health",
        {}
    )

    if (
        log_health.get("status")
        == "NOT_AVAILABLE"
    ):

        limitations.append({
            "domain":
                "LOGGING",

            "severity":
                "MEDIUM",

            "confidence":
                "CONFIRMED",

            "type":
                "PERSISTENT_RUNTIME_LOGS_NOT_AVAILABLE",

            "impact":
                (
                    "Runtime application failures "
                    "cannot be confirmed or excluded "
                    "from persistent logs."
                ),

            "source_analyzer":
                "08",
        })

    perf_status = a09.get(
        "performance_status",
        {}
    )

    if (
        perf_status.get("status")
        == "NO_CONFIRMED_BOTTLENECKS"
    ):

        limitations.append({
            "domain":
                "PERFORMANCE",

            "severity":
                "INFO",

            "confidence":
                "CONFIRMED",

            "type":
                "NO_RUNTIME_PERFORMANCE_PROOF",

            "impact":
                (
                    "No bottleneck is confirmed by "
                    "available evidence. This does "
                    "not prove absence of bottlenecks."
                ),

            "source_analyzer":
                "09",
        })

    # ------------------------------------------------------------
    # CROSS-ANALYZER CONTRADICTION CHECK
    # ------------------------------------------------------------

    a07_class = reports.get(
        "07",
        {}
    ).get(
        "project_file_classification",
        {}
    )

    registry_by_file = {
        item.get("file"):
            item

        for item in components
        if item.get("file")
    }

    for file, info in (
        a07_class.items()
    ):

        if not isinstance(
            info,
            dict
        ):
            continue

        normalized = normalize_file(
            file
        )

        component = registry_by_file.get(
            normalized
        )

        if component is None:
            continue

        status = info.get(
            "status"
        )

        if (
            status == "STATIC_ONLY"
            and component.get(
                "runtime_confirmed"
            )
        ):

            contradictions.append({
                "file":
                    normalized,

                "type":
                    "STATIC_RUNTIME_CONTRADICTION",

                "severity":
                    "HIGH",

                "confidence":
                    "CONFIRMED",

                "analyzer_07_status":
                    status,

                "analyzer_10_runtime":
                    True,
            })

        if (
            status
            == "OPERATIONAL_CONFIRMED"
            and component.get("state")
            != "ACTIVE_CONFIRMED"
        ):

            contradictions.append({
                "file":
                    normalized,

                "type":
                    "OPERATIONAL_STATE_MISMATCH",

                "severity":
                    "MEDIUM",

                "confidence":
                    "CONFIRMED",

                "analyzer_07_status":
                    status,

                "analyzer_10_state":
                    component.get(
                        "state"
                    ),
            })

        if (
            status
            == "OPERATIONAL_CONNECTED"
            and component.get("state")
            != "CONNECTED_CONFIRMED"
        ):

            contradictions.append({
                "file":
                    normalized,

                "type":
                    "CONNECTED_STATE_MISMATCH",

                "severity":
                    "MEDIUM",

                "confidence":
                    "CONFIRMED",

                "analyzer_07_status":
                    status,

                "analyzer_10_state":
                    component.get(
                        "state"
                    ),
            })

    # ------------------------------------------------------------
    # Overall synthesis
    # ------------------------------------------------------------

    confirmed_problem_count = sum(
        1
        for item in findings
        if item.get(
            "confirmed_problem"
        )
    )

    high_critical = sum(
        1
        for item in findings
        if str(
            item.get(
                "severity",
                ""
            )
        ).upper()
        in {
            "HIGH",
            "CRITICAL",
        }
    )

    if contradictions:

        status = (
            "CROSS_ANALYSIS_INCONSISTENT"
        )

    elif confirmed_problem_count:

        status = (
            "CONFIRMED_PROBLEMS_PRESENT"
        )

    else:

        status = (
            "CONSISTENT_WITH_IDENTIFIED_RISKS"
        )

    synthesis = {
        "status":
            status,

        "confirmed_facts":
            confirmed_facts,

        "findings":
            findings,

        "contradictions":
            contradictions,

        "limitations":
            limitations,

        "summary": {
            "active_components":
                len(active),

            "connected_components":
                len(connected),

            "operational_nucleus":
                len(active)
                + len(connected),

            "runtime_components":
                len(runtime),

            "health_risks":
                len(health_risks),

            "performance_risks":
                len(perf_risks),

            "confirmed_bottlenecks":
                len(
                    confirmed_bottlenecks
                ),

            "confirmed_problems":
                confirmed_problem_count,

            "high_or_critical_findings":
                high_critical,

            "cross_analyzer_contradictions":
                len(
                    contradictions
                ),

            "observability_limitations":
                len(
                    limitations
                ),
        },

        "methodology": {
            "source_of_truth":
                "ANALYZERS_01_TO_09",

            "direct_project_scan":
                False,

            "direct_process_query":
                False,

            "direct_database_query":
                False,

            "performance_risk_promotion":
                (
                    "PROBABLE static risks are "
                    "not promoted to confirmed "
                    "bottlenecks."
                ),

            "health_interpretation":
                (
                    "Code-level health risks are "
                    "not treated as proof of "
                    "runtime failure."
                ),
        },
    }

    cross[
        "cross_synthesis"
    ] = synthesis

    cross[
        "cross_analysis"
    ] = {
        "status":
            status,

        "stage":
            3,

        "interpretation":
            (
                "Analyzer 10 correlates evidence "
                "from Analyzer 01-09 without "
                "promoting observations or "
                "probable risks to confirmed "
                "failures."
            ),
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            cross,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    return cross


def print_stage3():

    result = build_cross_synthesis()

    synthesis = result[
        "cross_synthesis"
    ]

    summary = synthesis[
        "summary"
    ]

    print()
    print("=" * 100)
    print(
        "ANALYZER 10 V2 - "
        "STAGE 3 CROSS SYNTHESIS"
    )
    print("=" * 100)

    print(
        "Operational nucleus          :",
        summary[
            "operational_nucleus"
        ]
    )

    print(
        "Runtime components           :",
        summary[
            "runtime_components"
        ]
    )

    print(
        "Health risks                 :",
        summary[
            "health_risks"
        ]
    )

    print(
        "Performance risks            :",
        summary[
            "performance_risks"
        ]
    )

    print(
        "Confirmed bottlenecks        :",
        summary[
            "confirmed_bottlenecks"
        ]
    )

    print(
        "Confirmed problems           :",
        summary[
            "confirmed_problems"
        ]
    )

    print(
        "High/Critical findings       :",
        summary[
            "high_or_critical_findings"
        ]
    )

    print(
        "Cross contradictions         :",
        summary[
            "cross_analyzer_contradictions"
        ]
    )

    print(
        "Observability limitations    :",
        summary[
            "observability_limitations"
        ]
    )

    print()
    print(
        "CROSS STATUS:",
        synthesis[
            "status"
        ]
    )

    print()

    if synthesis[
        "contradictions"
    ]:

        print("CONTRADICTIONS")
        print("-" * 100)

        for item in synthesis[
            "contradictions"
        ]:

            print(
                item
            )

    else:

        print(
            "No cross-analyzer "
            "contradictions detected."
        )

    print()
    print(
        "ANALYZER 10 STAGE 3 STATUS: OK"
    )
    print("=" * 100)


print_stage3()
