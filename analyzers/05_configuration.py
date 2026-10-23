from __future__ import annotations

import ast
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


# =============================================================================
# PYTHON PROJECT INTELLIGENCE
# ANALYZER 05 - UNIVERSAL CONFIGURATION & ENVIRONMENT
#
# READ ONLY
# SECRET SAFE:
#   - detects possible secrets
#   - NEVER writes secret values to reports
# =============================================================================

THIS_FILE = Path(__file__).resolve()
INTELLIGENCE_ROOT = THIS_FILE.parent.parent
CORE_DIR = INTELLIGENCE_ROOT / "core"

if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from project_context import (
    PROJECT_NAME,
    PROJECT_ROOT,
    INTELLIGENCE_ROOT,
    PROJECT_OUTPUT_ROOT,
    iter_project_files,
    iter_python_files,
    ensure_output_directories,
)


ANALYZER_NAME = "05_configuration"
ANALYZER_VERSION = "2.0"


# =============================================================================
# CONFIG
# =============================================================================

TEXT_SUFFIXES = {
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".env",
    ".txt",
    ".md",
    ".html",
    ".js",
    ".ts",
    ".css",
    ".ps1",
    ".bat",
    ".cmd",
    ".sh",
}

CONFIG_FILENAMES = {
    "pyproject.toml",
    "requirements.txt",
    "pipfile",
    "pipfile.lock",
    "poetry.lock",
    "setup.py",
    "setup.cfg",
    "tox.ini",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "package.json",
    "package-lock.json",
    ".env",
    ".env.example",
    ".env.sample",
    ".gitignore",
}

SECRET_NAME_PATTERN = re.compile(
    r"""
    (
        api[_-]?key
        |secret
        |token
        |password
        |passwd
        |pwd
        |private[_-]?key
        |access[_-]?key
        |auth[_-]?key
        |client[_-]?secret
        |webhook[_-]?secret
        |bearer
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

URL_PATTERN = re.compile(
    r"""(?i)\b(?:https?|wss?)://[^\s"'<>]+"""
)

LOCALHOST_PATTERN = re.compile(
    r"""(?i)\b(?:127\.0\.0\.1|localhost)(?::(\d{1,5}))?"""
)

WINDOWS_PATH_PATTERN = re.compile(
    r"""(?i)\b[A-Z]:\\(?:[^<>"|?*\r\n]+)"""
)

ENV_REFERENCE_PATTERNS = [
    re.compile(
        r"""os\.getenv\(\s*["']([^"']+)["']""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""os\.environ\.get\(\s*["']([^"']+)["']""",
        re.IGNORECASE,
    ),
    re.compile(
        r"""os\.environ\[\s*["']([^"']+)["']\s*\]""",
        re.IGNORECASE,
    ),
]


# =============================================================================
# HELPERS
# =============================================================================

def relative_string(path: Path) -> str:
    try:
        return str(
            path.resolve().relative_to(PROJECT_ROOT.resolve())
        )
    except ValueError:
        return str(path.resolve())


def is_legacy_intelligence(path: Path) -> bool:

    legacy = (
        PROJECT_ROOT / "site_intelligence"
    ).resolve()

    try:
        path.resolve().relative_to(legacy)
        return True
    except ValueError:
        return False


# =============================================================================
# ACTIVE PROJECT FILTER
#
# Historical material remains physically part of the project and Analyzer 01
# can inventory it, but it must not contaminate operational configuration.
# =============================================================================

HISTORICAL_DIRECTORY_NAMES = {
    "backup",
    "backups",
    "_deep_audit",
    "_runtime_report",
    "_forensic_report",
    "site_intelligence",
}

HISTORICAL_FILE_PATTERNS = (
    "backup",
    "_backup",
    ".backup",
    "audit",
    "forensic",
    "operational_map",
    "project_structure_report",
    "analisi_completa_sito",
    "struttura_crypto_scanner",
    "codice_runtime_sito",
    "market_data_operational_map",
    "crypto_scanner_full_audit",
)


def historical_reason(path: Path) -> str | None:

    try:
        relative = path.resolve().relative_to(
            PROJECT_ROOT.resolve()
        )
    except ValueError:
        return "outside_project"

    parts_lower = [
        part.lower()
        for part in relative.parts
    ]

    # Directory-based classification.
    for part in parts_lower[:-1]:

        if part in HISTORICAL_DIRECTORY_NAMES:
            return f"historical_directory:{part}"

    filename = path.name.lower()

    # Filename-based classification.
    for pattern in HISTORICAL_FILE_PATTERNS:

        if pattern in filename:
            return f"historical_filename:{pattern}"

    return None


def classify_project_files():

    active = []
    historical = []

    for path in iter_project_files():

        # Current Python Project Intelligence is already excluded
        # by project_context. Legacy intelligence is historical.
        reason = historical_reason(path)

        if reason:

            historical.append({
                "path": relative_string(path),
                "reason": reason,
            })

            continue

        active.append(path)

    return active, historical


def safe_project_files():

    active, _ = classify_project_files()

    yield from active


def safe_python_files():

    for path in iter_python_files():

        reason = historical_reason(path)

        if reason:
            continue

        yield path


def is_probably_text_file(path: Path) -> bool:

    if path.name.lower() in CONFIG_FILENAMES:
        return True

    if path.suffix.lower() in TEXT_SUFFIXES:
        return True

    if path.name.lower().startswith(".env"):
        return True

    return False


def safe_read_text(path: Path) -> str | None:

    # Configuration scanning does not need to load giant files.
    try:
        if path.stat().st_size > 10 * 1024 * 1024:
            return None
    except OSError:
        return None

    try:
        return path.read_text(
            encoding="utf-8-sig",
            errors="ignore",
        )
    except Exception:
        return None


def sanitize_url(url: str) -> str:
    """
    Remove possible credentials from:
        protocol://user:password@host/path
    """

    return re.sub(
        r"(?i)(://)[^/@\s]+@",
        r"\1[REDACTED]@",
        url,
    )


def classify_config_file(path: Path) -> str:

    name = path.name.lower()
    suffix = path.suffix.lower()

    if name.startswith(".env"):
        return "environment"

    if name.startswith("requirements"):
        return "python_dependencies"

    if name in {
        "pyproject.toml",
        "setup.py",
        "setup.cfg",
        "pipfile",
        "pipfile.lock",
        "poetry.lock",
    }:
        return "python_project"

    if name.startswith("docker"):
        return "container"

    if name in {
        "package.json",
        "package-lock.json",
    }:
        return "javascript_project"

    if suffix in {
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
    }:
        return "configuration"

    if name == ".gitignore":
        return "git"

    return "other_configuration"


# =============================================================================
# CONFIG FILE DISCOVERY
# =============================================================================

def discover_config_files() -> list[dict]:

    result = []

    for path in safe_project_files():

        name = path.name.lower()
        suffix = path.suffix.lower()

        is_config = (
            name in CONFIG_FILENAMES
            or name.startswith(".env")
            or suffix in {
                ".yaml",
                ".yml",
                ".toml",
                ".ini",
                ".cfg",
                ".conf",
            }
        )

        if not is_config:
            continue

        try:
            size = path.stat().st_size
        except OSError:
            size = None

        result.append({
            "path": relative_string(path),
            "type": classify_config_file(path),
            "size_bytes": size,
        })

    return sorted(
        result,
        key=lambda item: item["path"].lower(),
    )


# =============================================================================
# ENV FILE SCAN - NEVER STORE VALUES
# =============================================================================

def analyze_env_files() -> list[dict]:

    result = []

    for path in safe_project_files():

        if not path.name.lower().startswith(".env"):
            continue

        text = safe_read_text(path)

        if text is None:
            continue

        variables = []

        for line_number, line in enumerate(
            text.splitlines(),
            start=1,
        ):

            stripped = line.strip()

            if (
                not stripped
                or stripped.startswith("#")
                or "=" not in stripped
            ):
                continue

            key = stripped.split("=", 1)[0].strip()

            if not key:
                continue

            variables.append({
                "name": key,
                "line": line_number,
                "possible_secret":
                    bool(
                        SECRET_NAME_PATTERN.search(
                            key
                        )
                    ),
                # VALUE INTENTIONALLY NOT STORED
            })

        result.append({
            "file": relative_string(path),
            "variables": variables,
            "variable_count": len(variables),
        })

    return result


# =============================================================================
# PYTHON ENV REFERENCES
# =============================================================================

def scan_environment_references() -> dict:

    variables = defaultdict(set)

    for path in safe_python_files():

        text = safe_read_text(path)

        if text is None:
            continue

        for pattern in ENV_REFERENCE_PATTERNS:

            for match in pattern.finditer(text):

                variable = match.group(1)

                variables[variable].add(
                    relative_string(path)
                )

    return {
        variable: sorted(files)
        for variable, files
        in sorted(variables.items())
    }


# =============================================================================
# SECRET NAME DETECTION
# =============================================================================

def detect_possible_secrets() -> list[dict]:
    """
    Detects suspicious variable/key NAMES.

    IMPORTANT:
    Never stores the assigned value.
    """

    findings = []

    assignment_pattern = re.compile(
        r"""
        \b
        ([A-Z0-9_.-]*
        (?:
            API[_-]?KEY
            |SECRET
            |TOKEN
            |PASSWORD
            |PASSWD
            |PRIVATE[_-]?KEY
            |ACCESS[_-]?KEY
            |CLIENT[_-]?SECRET
        )
        [A-Z0-9_.-]*)
        \s*
        [:=]
        """,
        re.IGNORECASE | re.VERBOSE,
    )

    for path in safe_project_files():

        if not is_probably_text_file(path):
            continue

        text = safe_read_text(path)

        if text is None:
            continue

        for line_number, line in enumerate(
            text.splitlines(),
            start=1,
        ):

            matches = assignment_pattern.findall(
                line
            )

            for variable_name in matches:

                findings.append({
                    "file": relative_string(path),
                    "line": line_number,
                    "name": variable_name,
                    "classification":
                        "POSSIBLE_SECRET",
                    "value": "[REDACTED]",
                })

    return findings


# =============================================================================
# URL / PORT / ABSOLUTE PATH DETECTION
# =============================================================================

def scan_runtime_configuration() -> dict:

    urls = defaultdict(set)
    ports = defaultdict(set)
    absolute_paths = defaultdict(set)

    for path in safe_project_files():

        if not is_probably_text_file(path):
            continue

        text = safe_read_text(path)

        if text is None:
            continue

        relative = relative_string(path)

        # URLs
        for match in URL_PATTERN.finditer(text):

            url = sanitize_url(
                match.group(0)
            )

            # Prevent gigantic malformed matches.
            if len(url) > 500:
                url = url[:500] + "..."

            urls[url].add(relative)

        # localhost / 127.0.0.1 ports
        for match in LOCALHOST_PATTERN.finditer(text):

            port = match.group(1)

            if port:
                try:
                    numeric_port = int(port)
                except ValueError:
                    continue

                if 1 <= numeric_port <= 65535:
                    ports[numeric_port].add(relative)

        # Windows absolute paths
        for match in WINDOWS_PATH_PATTERN.finditer(text):

            value = match.group(0).strip()

            if len(value) > 500:
                value = value[:500] + "..."

            absolute_paths[value].add(relative)

    return {
        "urls": [
            {
                "value": value,
                "files": sorted(files),
                "confidence": "CONFIRMED_STATIC",
            }
            for value, files in sorted(
                urls.items()
            )
        ],

        "ports": [
            {
                "port": port,
                "files": sorted(files),
                "confidence": "CONFIRMED_STATIC",
            }
            for port, files in sorted(
                ports.items()
            )
        ],

        "absolute_paths": [
            {
                "value": value,
                "files": sorted(files),
                "confidence": "CONFIRMED_STATIC",
            }
            for value, files in sorted(
                absolute_paths.items()
            )
        ],
    }


# =============================================================================
# PYTHON CONSTANTS
# =============================================================================

def safe_constant_value(value):
    """
    Only non-sensitive primitive values are returned.
    """

    if isinstance(
        value,
        (int, float, bool, type(None)),
    ):
        return value

    if isinstance(value, str):

        if len(value) > 250:
            return "[LONG_STRING]"

        return value

    return "[COMPLEX_VALUE]"


def scan_python_constants() -> list[dict]:

    results = []

    for path in safe_python_files():

        text = safe_read_text(path)

        if text is None:
            continue

        try:
            tree = ast.parse(
                text,
                filename=str(path),
            )
        except Exception:
            continue

        constants = []

        for node in tree.body:

            if not isinstance(
                node,
                (ast.Assign, ast.AnnAssign),
            ):
                continue

            targets = []

            value_node = None

            if isinstance(node, ast.Assign):

                targets = node.targets
                value_node = node.value

            else:

                targets = [node.target]
                value_node = node.value

            if value_node is None:
                continue

            try:
                literal_value = ast.literal_eval(
                    value_node
                )
            except Exception:
                continue

            for target in targets:

                if not isinstance(
                    target,
                    ast.Name,
                ):
                    continue

                name = target.id

                if not name.isupper():
                    continue

                if SECRET_NAME_PATTERN.search(name):

                    constants.append({
                        "name": name,
                        "line": node.lineno,
                        "value": "[REDACTED]",
                        "possible_secret": True,
                    })

                else:

                    constants.append({
                        "name": name,
                        "line": node.lineno,
                        "value":
                            safe_constant_value(
                                literal_value
                            ),
                        "possible_secret": False,
                    })

        if constants:

            results.append({
                "file": relative_string(path),
                "constants": constants,
            })

    return results


# =============================================================================
# DUPLICATED CONSTANT NAMES
# =============================================================================

def find_duplicate_constant_names(
    python_constants: list[dict],
) -> list[dict]:

    locations = defaultdict(set)

    for file_record in python_constants:

        filename = file_record["file"]

        for constant in file_record["constants"]:

            locations[
                constant["name"]
            ].add(filename)

    duplicates = []

    for name, files in locations.items():

        if len(files) < 2:
            continue

        duplicates.append({
            "name": name,
            "file_count": len(files),
            "files": sorted(files),
            "classification":
                "POSSIBLE_DUPLICATED_CONFIGURATION",
        })

    duplicates.sort(
        key=lambda item: (
            -item["file_count"],
            item["name"],
        )
    )

    return duplicates


# =============================================================================
# COMPLETE ANALYSIS
# =============================================================================

def analyze_configuration() -> dict:

    active_project_files, historical_files = (
        classify_project_files()
    )

    config_files = discover_config_files()

    env_files = analyze_env_files()

    env_references = (
        scan_environment_references()
    )

    possible_secrets = (
        detect_possible_secrets()
    )

    runtime_configuration = (
        scan_runtime_configuration()
    )

    python_constants = (
        scan_python_constants()
    )

    duplicate_constants = (
        find_duplicate_constant_names(
            python_constants
        )
    )

    env_defined = set()

    for env_file in env_files:

        for variable in env_file["variables"]:

            env_defined.add(
                variable["name"]
            )

    env_referenced = set(
        env_references.keys()
    )

    referenced_not_detected = sorted(
        env_referenced - env_defined
    )

    defined_not_referenced = sorted(
        env_defined - env_referenced
    )

    config_types = Counter(
        item["type"]
        for item in config_files
    )

    return {
        "metadata": {
            "analyzer": ANALYZER_NAME,
            "version": ANALYZER_VERSION,

            "generated_utc":
                datetime.now(
                    timezone.utc
                ).isoformat(),

            "project_name":
                PROJECT_NAME,

            "project_root":
                str(PROJECT_ROOT),

            "intelligence_root":
                str(INTELLIGENCE_ROOT),

            "mode":
                "READ_ONLY",

            "secret_policy":
                (
                    "Secret values are intentionally "
                    "never written to this report."
                ),
        },

        "summary": {
            "active_project_files_scanned":
                len(active_project_files),

            "historical_files_excluded":
                len(historical_files),

            "configuration_files":
                len(config_files),

            "environment_files":
                len(env_files),

            "environment_variables_defined":
                len(env_defined),

            "environment_variables_referenced":
                len(env_referenced),

            "environment_referenced_not_detected":
                len(referenced_not_detected),

            "environment_defined_not_referenced":
                len(defined_not_referenced),

            "possible_secret_locations":
                len(possible_secrets),

            "static_urls":
                len(
                    runtime_configuration["urls"]
                ),

            "static_local_ports":
                len(
                    runtime_configuration["ports"]
                ),

            "absolute_paths":
                len(
                    runtime_configuration[
                        "absolute_paths"
                    ]
                ),

            "python_files_with_constants":
                len(python_constants),

            "duplicated_constant_names":
                len(duplicate_constants),
        },

        "historical_files_excluded":
            historical_files,

        "configuration_types":
            dict(config_types),

        "configuration_files":
            config_files,

        "environment_files":
            env_files,

        "environment_references":
            env_references,

        "environment_referenced_not_detected":
            referenced_not_detected,

        "environment_defined_not_referenced":
            defined_not_referenced,

        "possible_secret_locations":
            possible_secrets,

        "runtime_configuration":
            runtime_configuration,

        "python_constants":
            python_constants,

        "duplicated_constant_names":
            duplicate_constants,
    }


# =============================================================================
# OUTPUT
# =============================================================================

def write_report(result: dict) -> Path:

    ensure_output_directories()

    output_dir = (
        PROJECT_OUTPUT_ROOT
        / "LATEST"
        / "05_CONFIGURATION"
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        output_dir
        / "CONFIGURATION_MAP.json"
    )

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            result,
            handle,
            indent=2,
            ensure_ascii=False,
        )

    return output_file


# =============================================================================
# MAIN
# =============================================================================

def main() -> int:

    print("=" * 100)
    print("PYTHON PROJECT INTELLIGENCE")
    print(
        "ANALYZER 05 - "
        "CONFIGURATION & ENVIRONMENT"
    )
    print("=" * 100)

    print(
        f"Project name       : "
        f"{PROJECT_NAME}"
    )

    print(
        f"Project root       : "
        f"{PROJECT_ROOT}"
    )

    print(
        "Mode               : "
        "READ ONLY / SECRET SAFE"
    )

    print()
    print(
        "Analisi configurazioni, "
        "environment e costanti..."
    )
    print()

    result = analyze_configuration()

    summary = result["summary"]

    print(
        f"File attivi scan   : "
        f"{summary['active_project_files_scanned']}"
    )

    print(
        f"Storici esclusi    : "
        f"{summary['historical_files_excluded']}"
    )

    print(
        f"File configurazione: "
        f"{summary['configuration_files']}"
    )

    print(
        f"File .env          : "
        f"{summary['environment_files']}"
    )

    print(
        f"Variabili ENV def. : "
        f"{summary['environment_variables_defined']}"
    )

    print(
        f"Variabili ENV usate: "
        f"{summary['environment_variables_referenced']}"
    )

    print(
        f"ENV usate non viste: "
        f"{summary['environment_referenced_not_detected']}"
    )

    print(
        f"Possibili secret   : "
        f"{summary['possible_secret_locations']}"
    )

    print(
        f"URL statici        : "
        f"{summary['static_urls']}"
    )

    print(
        f"Porte locali       : "
        f"{summary['static_local_ports']}"
    )

    print(
        f"Path assoluti      : "
        f"{summary['absolute_paths']}"
    )

    print(
        f"File con costanti  : "
        f"{summary['python_files_with_constants']}"
    )

    print(
        f"Costanti duplicate : "
        f"{summary['duplicated_constant_names']}"
    )

    if result[
        "environment_referenced_not_detected"
    ]:

        print()
        print(
            "ENV REFERENZIATE MA NON "
            "TROVATE NEI FILE .env:"
        )

        for name in result[
            "environment_referenced_not_detected"
        ][:30]:

            print(f"  {name}")

    if result[
        "duplicated_constant_names"
    ]:

        print()
        print(
            "COSTANTI PIU' DUPLICATE:"
        )

        for item in result[
            "duplicated_constant_names"
        ][:15]:

            print(
                f"  {item['file_count']:>3} file <- "
                f"{item['name']}"
            )

    output_file = write_report(result)

    print()
    print(
        f"Report JSON         : "
        f"{output_file}"
    )

    print()
    print(
        "NOTA SICUREZZA      : "
        "i valori dei possibili secret "
        "NON vengono salvati nel report."
    )

    print()
    print(
        "ANALYZER STATUS: OK"
    )

    print("=" * 100)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


