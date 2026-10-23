from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Iterator


# =============================================================================
# PYTHON PROJECT INTELLIGENCE
# UNIVERSAL PROJECT CONTEXT
# =============================================================================

# Questo file si trova in:
#
#   <PROJECT_ROOT>\python_project_intelligence\core\project_context.py
#
# Quindi:
#
#   CORE_DIR                = ...\python_project_intelligence\core
#   INTELLIGENCE_ROOT       = ...\python_project_intelligence
#   PROJECT_ROOT            = cartella progetto analizzato
#   PROJECT_NAME            = nome della cartella progetto
# =============================================================================

CORE_DIR = Path(__file__).resolve().parent
INTELLIGENCE_ROOT = CORE_DIR.parent
PROJECT_ROOT = INTELLIGENCE_ROOT.parent
PROJECT_NAME = PROJECT_ROOT.name

ANALYZERS_DIR = INTELLIGENCE_ROOT / "analyzers"

OUTPUT_BASE = INTELLIGENCE_ROOT / "output"
PROJECT_OUTPUT_ROOT = OUTPUT_BASE / PROJECT_NAME
MASTER_LOG_DIR = PROJECT_OUTPUT_ROOT / "MASTER_LOGS"


# =============================================================================
# DIRECTORY DA ESCLUDERE DALL'ANALISI DEL PROGETTO
# =============================================================================

EXCLUDED_DIR_NAMES = {
    "_OLD_python_project_intelligence",
    "_OLD_python_project_intelligence_PORTABLE",
    "python_project_intelligence",
    "python_project_intelligence_PORTABLE",
    ".git",
    ".github",
    ".idea",
    ".vscode",

    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",

    ".venv",
    "venv",
    "env",

    "node_modules",

    "dist",
    "build",

    ".tox",
    ".nox",

    # Python Project Intelligence:
    # esclude sia la versione attualmente in uso
    # sia eventuali versioni precedenti/portable
    # presenti contemporaneamente nel progetto analizzato.
    "python_project_intelligence",
    "python_project_intelligence_PORTABLE",
    "python_project_intelligence_V2",
}


def is_inside_intelligence(path: Path) -> bool:
    """
    True se path appartiene a Python Project Intelligence.

    Il tool deve analizzare il progetto che lo contiene,
    NON se stesso.
    """

    try:
        path.resolve().relative_to(INTELLIGENCE_ROOT.resolve())
        return True
    except ValueError:
        return False


def is_excluded(path: Path) -> bool:
    """
    Determina se un file/cartella deve essere escluso
    dall'analisi del progetto.
    """

    path = path.resolve()

    if is_inside_intelligence(path):
        return True

    try:
        relative = path.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return True

    for part in relative.parts:
        if part in EXCLUDED_DIR_NAMES:
            return True

    return False


def iter_project_files() -> Iterator[Path]:
    """
    Itera esclusivamente sui file appartenenti al progetto reale.

    Python Project Intelligence e le directory tecniche escluse
    non vengono considerate parte del progetto analizzato.
    """

    for root, dirs, files in os.walk(PROJECT_ROOT):

        root_path = Path(root)

        dirs[:] = [
            directory
            for directory in dirs
            if not is_excluded(root_path / directory)
        ]

        for filename in files:

            file_path = root_path / filename

            if not is_excluded(file_path):
                yield file_path


def iter_python_files() -> Iterator[Path]:

    for file_path in iter_project_files():

        if file_path.suffix.lower() == ".py":
            yield file_path


def ensure_output_directories() -> None:

    PROJECT_OUTPUT_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    MASTER_LOG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def get_context_summary() -> dict:

    project_files = list(iter_project_files())

    python_files = [
        file_path
        for file_path in project_files
        if file_path.suffix.lower() == ".py"
    ]

    return {
        "project_name": PROJECT_NAME,
        "project_root": str(PROJECT_ROOT),
        "intelligence_root": str(INTELLIGENCE_ROOT),
        "analyzers_dir": str(ANALYZERS_DIR),
        "output_root": str(PROJECT_OUTPUT_ROOT),
        "master_log_dir": str(MASTER_LOG_DIR),

        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "operating_system": platform.platform(),

        "project_files": len(project_files),
        "python_files": len(python_files),
    }


if __name__ == "__main__":

    ensure_output_directories()

    context = get_context_summary()

    print("=" * 100)
    print("PYTHON PROJECT INTELLIGENCE - UNIVERSAL PROJECT CONTEXT")
    print("=" * 100)

    print(f"Project name       : {context['project_name']}")
    print(f"Project root       : {context['project_root']}")
    print(f"Intelligence root  : {context['intelligence_root']}")
    print(f"Analyzers          : {context['analyzers_dir']}")
    print(f"Output root        : {context['output_root']}")
    print(f"Master logs        : {context['master_log_dir']}")

    print()

    print(f"Python executable  : {context['python_executable']}")
    print(f"Python version     : {context['python_version']}")
    print(f"Operating system   : {context['operating_system']}")

    print()

    print(f"Project files      : {context['project_files']}")
    print(f"Python files       : {context['python_files']}")

    print()

    contamination = []

    for file_path in iter_project_files():

        if is_inside_intelligence(file_path):
            contamination.append(str(file_path))

    print(f"Self contamination : {len(contamination)}")

    if contamination:

        print()
        print("ERRORE - file Python Project Intelligence trovati nel target:")

        for item in contamination[:20]:
            print(f"  {item}")

        print()
        print("CONTEXT STATUS: FAILED")

    else:

        print()
        print("CONTEXT STATUS: OK")

    print("=" * 100)

