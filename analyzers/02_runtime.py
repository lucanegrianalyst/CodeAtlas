from __future__ import annotations

import csv
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# =============================================================================
# PYTHON PROJECT INTELLIGENCE
# ANALYZER 02 - UNIVERSAL RUNTIME ANALYZER
# =============================================================================

import re
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
    ensure_output_directories,
)


ANALYZER_NAME = "02_runtime"
ANALYZER_VERSION = "2.0"


# =============================================================================
# HELPERS
# =============================================================================

def run_command(command: list[str], timeout: int = 30) -> tuple[int, str, str]:

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=timeout,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if os.name == "nt"
                else 0
            ),
        )

        return (
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )

    except Exception as exc:
        return 1, "", str(exc)


def normalize(value: str | None) -> str:

    if value is None:
        return ""

    return str(value).strip()


def path_mentions_project(value: str) -> bool:

    if not value:
        return False

    project = str(PROJECT_ROOT).lower()
    intelligence = str(INTELLIGENCE_ROOT).lower()
    candidate = value.lower()

    if intelligence in candidate:
        return False

    return project in candidate


def project_module_exists(module_name: str) -> bool:
    """
    Verifica se un modulo usato con `python -m package.module`
    esiste realmente dentro il progetto.

    Esempio:
        modular.orchestrator
        ->
        PROJECT_ROOT/modular/orchestrator.py
        oppure
        PROJECT_ROOT/modular/orchestrator/__main__.py

    Non considera mai Python Project Intelligence come parte
    del progetto analizzato.
    """

    if not module_name:
        return False

    module_name = module_name.strip().strip("\"'")

    if not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*",
        module_name,
    ):
        return False

    parts = module_name.split(".")

    candidates = [
        PROJECT_ROOT.joinpath(*parts).with_suffix(".py"),
        PROJECT_ROOT.joinpath(*parts, "__main__.py"),
        PROJECT_ROOT.joinpath(*parts, "__init__.py"),
    ]

    for candidate in candidates:

        try:
            resolved = candidate.resolve()
        except Exception:
            resolved = candidate

        try:
            resolved.relative_to(
                INTELLIGENCE_ROOT.resolve()
            )
            continue
        except ValueError:
            pass

        if resolved.is_file():
            return True

    return False


def project_script_exists(script_value: str) -> bool:
    """
    Verifica se uno script Python indicato nella command line
    appartiene al progetto anche quando viene lanciato con un
    percorso relativo, per esempio:

        python start.py
        python tools/worker.py
        python .\\tools\\worker.py

    I path assoluti continuano a essere gestiti anche dal
    controllo PROJECT_ROOT gi? esistente.
    """

    if not script_value:
        return False

    value = script_value.strip().strip("\"'")

    if not value.lower().endswith((".py", ".pyw")):
        return False

    candidate = Path(value)

    if candidate.is_absolute():

        try:
            resolved = candidate.resolve()
            resolved.relative_to(PROJECT_ROOT.resolve())
        except (ValueError, OSError):
            return False

    else:

        try:
            resolved = (
                PROJECT_ROOT / candidate
            ).resolve()

            resolved.relative_to(
                PROJECT_ROOT.resolve()
            )

        except (ValueError, OSError):
            return False

    try:
        resolved.relative_to(
            INTELLIGENCE_ROOT.resolve()
        )
        return False
    except ValueError:
        pass

    return resolved.is_file()


def command_line_mentions_project_entrypoint(
    command_line: str,
) -> bool:
    """
    Riconosce entrypoint Python del progetto anche quando
    PROJECT_ROOT non compare testualmente nella command line.

    Supporta:
        python script.py
        python path/script.py
        python -m package.module

    ? volutamente conservativa: un processo viene attribuito
    al progetto soltanto se il relativo file/modulo esiste
    realmente sotto PROJECT_ROOT.
    """

    if not command_line:
        return False

    try:
        import shlex

        tokens = shlex.split(
            command_line,
            posix=False,
        )

    except Exception:

        tokens = re.findall(
            r'"[^"]*"|\S+',
            command_line,
        )

    tokens = [
        token.strip().strip("\"'")
        for token in tokens
        if token.strip()
    ]

    # ----------------------------------------------------------
    # python -m package.module
    # ----------------------------------------------------------

    for index, token in enumerate(tokens):

        if token == "-m" and index + 1 < len(tokens):

            if project_module_exists(
                tokens[index + 1]
            ):
                return True

    # ----------------------------------------------------------
    # python script.py / python relative/path/script.py
    # ----------------------------------------------------------

    for token in tokens[1:]:

        if project_script_exists(token):
            return True

    return False


def process_belongs_to_project(
    executable: str,
    command_line: str,
) -> bool:

    # Metodo 1:
    # PROJECT_ROOT compare esplicitamente nella command line.
    if path_mentions_project(command_line):
        return True

    # Metodo 2:
    # entrypoint relativo o modulo `python -m` realmente
    # presente nel progetto.
    if command_line_mentions_project_entrypoint(
        command_line
    ):
        return True

    # Non classifichiamo un processo come appartenente al
    # progetto soltanto perch? usa lo stesso python.exe.
    #
    # executable normalmente punta all'interprete Python,
    # non al progetto. Manteniamo il controllo precedente
    # soltanto per eventuali interpreti collocati realmente
    # dentro PROJECT_ROOT.
    if path_mentions_project(executable):
        return True

    return False


# =============================================================================
# WINDOWS PROCESS DISCOVERY
# =============================================================================

def get_windows_processes() -> tuple[list[dict], list[str]]:

    findings = []
    errors = []

    ps_script = r'''
$ErrorActionPreference = "SilentlyContinue"

Get-CimInstance Win32_Process |
    Select-Object ProcessId,
                  ParentProcessId,
                  Name,
                  ExecutablePath,
                  CommandLine,
                  CreationDate |
    ConvertTo-Csv -NoTypeInformation
'''

    code, stdout, stderr = run_command(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            ps_script,
        ],
        timeout=60,
    )

    if code != 0:
        errors.append(
            f"Process discovery failed: {stderr.strip()}"
        )
        return findings, errors

    try:
        reader = csv.DictReader(stdout.splitlines())

        for row in reader:

            name = normalize(row.get("Name"))
            executable = normalize(row.get("ExecutablePath"))
            command_line = normalize(row.get("CommandLine"))

            is_python = (
                "python" in name.lower()
                or "python" in executable.lower()
                or "python" in command_line.lower()
            )

            if not is_python:
                continue

            try:
                pid = int(row.get("ProcessId") or 0)
            except ValueError:
                pid = 0

            try:
                parent_pid = int(row.get("ParentProcessId") or 0)
            except ValueError:
                parent_pid = 0

            findings.append({
                "pid": pid,
                "parent_pid": parent_pid,
                "name": name,
                "executable": executable,
                "command_line": command_line,
                "creation_date": normalize(
                    row.get("CreationDate")
                ),
                "belongs_to_project":
                    process_belongs_to_project(
                        executable,
                        command_line,
                    ),
            })

    except Exception as exc:
        errors.append(
            f"Unable to parse process list: {exc}"
        )

    return findings, errors


# =============================================================================
# WINDOWS RESOURCE DISCOVERY
# =============================================================================

def get_process_resources(pids: list[int]) -> dict[int, dict]:

    if not pids:
        return {}

    pid_text = ",".join(str(pid) for pid in pids)

    ps_script = f'''
$ErrorActionPreference = "SilentlyContinue"

$pids = @({pid_text})

Get-Process |
    Where-Object {{ $pids -contains $_.Id }} |
    Select-Object Id,
                  CPU,
                  WorkingSet64,
                  PrivateMemorySize64,
                  Threads |
    ForEach-Object {{
        [PSCustomObject]@{{
            Id = $_.Id
            CPU = $_.CPU
            WorkingSet64 = $_.WorkingSet64
            PrivateMemorySize64 = $_.PrivateMemorySize64
            ThreadCount = $_.Threads.Count
        }}
    }} |
    ConvertTo-Csv -NoTypeInformation
'''

    code, stdout, _ = run_command(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            ps_script,
        ],
        timeout=30,
    )

    if code != 0:
        return {}

    resources = {}

    try:
        reader = csv.DictReader(stdout.splitlines())

        for row in reader:

            try:
                pid = int(row.get("Id") or 0)
            except ValueError:
                continue

            try:
                cpu = float(row.get("CPU") or 0)
            except ValueError:
                cpu = 0.0

            try:
                working_set = int(row.get("WorkingSet64") or 0)
            except ValueError:
                working_set = 0

            try:
                private_memory = int(
                    row.get("PrivateMemorySize64") or 0
                )
            except ValueError:
                private_memory = 0

            try:
                thread_count = int(
                    row.get("ThreadCount") or 0
                )
            except ValueError:
                thread_count = 0

            resources[pid] = {
                "cpu_seconds": round(cpu, 3),
                "working_set_bytes": working_set,
                "working_set_mb": round(
                    working_set / 1024 / 1024,
                    2,
                ),
                "private_memory_bytes": private_memory,
                "private_memory_mb": round(
                    private_memory / 1024 / 1024,
                    2,
                ),
                "thread_count": thread_count,
            }

    except Exception:
        return {}

    return resources


# =============================================================================
# WINDOWS LISTENING PORTS
# =============================================================================

def get_windows_listening_ports() -> tuple[list[dict], list[str]]:

    findings = []
    errors = []

    ps_script = r'''
$ErrorActionPreference = "SilentlyContinue"

Get-NetTCPConnection -State Listen |
    Select-Object LocalAddress,
                  LocalPort,
                  OwningProcess |
    Sort-Object LocalPort |
    ConvertTo-Csv -NoTypeInformation
'''

    code, stdout, stderr = run_command(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            ps_script,
        ],
        timeout=60,
    )

    if code != 0:
        errors.append(
            f"Port discovery failed: {stderr.strip()}"
        )
        return findings, errors

    try:
        reader = csv.DictReader(stdout.splitlines())

        for row in reader:

            try:
                port = int(row.get("LocalPort") or 0)
            except ValueError:
                port = 0

            try:
                pid = int(row.get("OwningProcess") or 0)
            except ValueError:
                pid = 0

            findings.append({
                "address": normalize(
                    row.get("LocalAddress")
                ),
                "port": port,
                "pid": pid,
            })

    except Exception as exc:
        errors.append(
            f"Unable to parse listening ports: {exc}"
        )

    return findings, errors


# =============================================================================
# RUNTIME ANALYSIS
# =============================================================================

def analyze_runtime() -> dict:

    errors = []

    if os.name == "nt":

        processes, process_errors = get_windows_processes()
        ports, port_errors = get_windows_listening_ports()

        errors.extend(process_errors)
        errors.extend(port_errors)

    else:

        processes = []
        ports = []

        errors.append(
            "Runtime process/port discovery currently has "
            "full support on Windows. "
            "Other operating systems will be added later."
        )

    python_pids = [
        process["pid"]
        for process in processes
        if process["pid"]
    ]

    resources = get_process_resources(python_pids)

    for process in processes:

        process["resources"] = resources.get(
            process["pid"],
            {},
        )

        process["listening_ports"] = sorted(
            port["port"]
            for port in ports
            if port["pid"] == process["pid"]
        )

    project_processes = [
        process
        for process in processes
        if process["belongs_to_project"]
    ]

    external_python_processes = [
        process
        for process in processes
        if not process["belongs_to_project"]
    ]

    project_pids = {
        process["pid"]
        for process in project_processes
    }

    project_ports = [
        port
        for port in ports
        if port["pid"] in project_pids
    ]

    python_ports = [
        port
        for port in ports
        if port["pid"] in {
            process["pid"]
            for process in processes
        }
    ]

    total_working_set = sum(
        process.get("resources", {}).get(
            "working_set_bytes",
            0,
        )
        for process in project_processes
    )

    total_private_memory = sum(
        process.get("resources", {}).get(
            "private_memory_bytes",
            0,
        )
        for process in project_processes
    )

    total_threads = sum(
        process.get("resources", {}).get(
            "thread_count",
            0,
        )
        for process in project_processes
    )

    result = {
        "metadata": {
            "analyzer": ANALYZER_NAME,
            "version": ANALYZER_VERSION,
            "generated_utc":
                datetime.now(timezone.utc).isoformat(),
            "project_name": PROJECT_NAME,
            "project_root": str(PROJECT_ROOT),
            "intelligence_root": str(
                INTELLIGENCE_ROOT
            ),
            "operating_system": platform.platform(),
            "python_executable": sys.executable,
            "python_version": platform.python_version(),
        },

        "summary": {
            "python_processes_total":
                len(processes),

            "project_python_processes":
                len(project_processes),

            "external_python_processes":
                len(external_python_processes),

            "listening_ports_total":
                len(ports),

            "python_listening_ports":
                len(python_ports),

            "project_listening_ports":
                len(project_ports),

            "project_working_set_mb":
                round(
                    total_working_set
                    / 1024
                    / 1024,
                    2,
                ),

            "project_private_memory_mb":
                round(
                    total_private_memory
                    / 1024
                    / 1024,
                    2,
                ),

            "project_threads":
                total_threads,

            "runtime_errors":
                len(errors),
        },

        "project_processes":
            project_processes,

        "external_python_processes":
            external_python_processes,

        "all_python_processes":
            processes,

        "project_listening_ports":
            project_ports,

        "all_listening_ports":
            ports,

        "errors":
            errors,
    }

    return result


# =============================================================================
# OUTPUT
# =============================================================================

def write_report(result: dict) -> Path:

    ensure_output_directories()

    analyzer_output = (
        PROJECT_OUTPUT_ROOT
        / "LATEST"
        / "02_RUNTIME"
    )

    analyzer_output.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        analyzer_output
        / "RUNTIME_MAP.json"
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
    print("ANALYZER 02 - UNIVERSAL RUNTIME")
    print("=" * 100)

    print(f"Project name       : {PROJECT_NAME}")
    print(f"Project root       : {PROJECT_ROOT}")
    print(f"Intelligence root  : {INTELLIGENCE_ROOT}")

    print()
    print("Analisi runtime in corso...")
    print()

    result = analyze_runtime()
    summary = result["summary"]

    print(
        f"Processi Python    : "
        f"{summary['python_processes_total']}"
    )

    print(
        f"Processi progetto  : "
        f"{summary['project_python_processes']}"
    )

    print(
        f"Python esterni     : "
        f"{summary['external_python_processes']}"
    )

    print(
        f"Porte LISTEN       : "
        f"{summary['listening_ports_total']}"
    )

    print(
        f"Porte Python       : "
        f"{summary['python_listening_ports']}"
    )

    print(
        f"Porte progetto     : "
        f"{summary['project_listening_ports']}"
    )

    print(
        f"RAM progetto WS    : "
        f"{summary['project_working_set_mb']} MB"
    )

    print(
        f"RAM progetto priv. : "
        f"{summary['project_private_memory_mb']} MB"
    )

    print(
        f"Thread progetto    : "
        f"{summary['project_threads']}"
    )

    print()

    if result["project_processes"]:

        print("PROCESSI DEL PROGETTO:")

        for process in result["project_processes"]:

            print("-" * 100)

            print(
                f"PID {process['pid']} "
                f"| Parent {process['parent_pid']}"
            )

            print(
                f"Command: "
                f"{process['command_line']}"
            )

            ports = process.get(
                "listening_ports",
                [],
            )

            if ports:
                print(
                    "Ports: "
                    + ", ".join(
                        str(port)
                        for port in ports
                    )
                )

            resource = process.get(
                "resources",
                {},
            )

            if resource:

                print(
                    f"RAM WS: "
                    f"{resource.get('working_set_mb', 0)} MB "
                    f"| Private: "
                    f"{resource.get('private_memory_mb', 0)} MB "
                    f"| Threads: "
                    f"{resource.get('thread_count', 0)}"
                )

    else:

        print(
            "Nessun processo Python del progetto "
            "identificato in questo momento."
        )

    print()

    if result["errors"]:

        print("NOTE / LIMITAZIONI:")

        for error in result["errors"]:
            print(f"  - {error}")

        print()

    output_file = write_report(result)

    print(
        f"Report JSON         : {output_file}"
    )

    print()

    # Un errore di discovery non deve essere interpretato
    # automaticamente come errore del progetto.
    if result["errors"]:

        print("ANALYZER STATUS: ATTENTION")

    else:

        print("ANALYZER STATUS: OK")

    print("=" * 100)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
