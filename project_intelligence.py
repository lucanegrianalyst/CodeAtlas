from pathlib import Path
from datetime import datetime
import subprocess
import sys
import json
import time
import threading

# ============================================================
# PORTABLE PROJECT CONTEXT
# ============================================================

INTELLIGENCE_ROOT = Path(__file__).resolve().parent
CORE_DIR = INTELLIGENCE_ROOT / "core"

if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from project_context import (
    PROJECT_ROOT,
    PROJECT_OUTPUT_ROOT,
    PROJECT_NAME,
)

ROOT = PROJECT_ROOT
ANALYZERS = INTELLIGENCE_ROOT / "analyzers"
OUTPUT = PROJECT_OUTPUT_ROOT
LOG_DIR = PROJECT_OUTPUT_ROOT / "MASTER_LOGS"

LOG_DIR.mkdir(parents=True, exist_ok=True)

MASTER_RUN = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = LOG_DIR / f"MASTER_RUN_{MASTER_RUN}.log"
META_FILE = LOG_DIR / f"MASTER_RUN_{MASTER_RUN}.json"

EXPECTED = {
    1: "PROJECT_STRUCTURE.json",
    2: "RUNTIME_MAP.json",
    3: "DATABASE_MAP.json",
    4: "CODE_CONNECTIONS.json",
    5: "CONFIGURATION_MAP.json",
    6: "API_ENDPOINTS_MAP.json",
    7: "DATA_FLOW_MAP.json",
    8: "HEALTH_ERROR_MAP.json",
    9: "PERFORMANCE_MAP.json",
    10: "CROSS_ANALYSIS_MAP.json",
    11: "FINAL_PROJECT_INTELLIGENCE.json",
    12: "ORGANIZATION_REFACTORING_MAP.json",
    13: "HARDWARE_RESOURCE_MAP.json",
    14: "FINAL_ARCHITECTURE_MAP.json",
    15: "MASTER_SITE_INTELLIGENCE.json",
}


def log(message=""):
    print(message, flush=True)

    with LOG_FILE.open(
        "a",
        encoding="utf-8"
    ) as f:
        f.write(message + "\n")



def progress_heartbeat(
    number,
    total,
    script_name,
    start_time,
    stop_event
):
    """
    Heartbeat del master orchestrator.

    Non modifica il comportamento dell'Analyzer.
    Mostra soltanto che il processo e' ancora in esecuzione.
    """

    while not stop_event.wait(10):

        elapsed = time.time() - start_time

        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        completed = number - 1

        bar_width = 30

        filled = int(
            bar_width * completed / total
        )

        bar = (
            "#" * filled
            + "-" * (bar_width - filled)
        )

        log()
        log(
            f"[PROGRESS] [{number:02d}/{total:02d}] "
            f"{script_name}"
        )

        log(
            f"  AVANZAMENTO : "
            f"[{bar}] "
            f"{completed}/{total}"
        )

        log(
            f"  STATO       : IN ESECUZIONE"
        )

        log(
            f"  TEMPO       : "
            f"{minutes:02d}:{seconds:02d}"
        )

        log(
            f"  HEARTBEAT   : processo ancora attivo"
        )

def discover_analyzer(number):

    pattern = f"{number:02d}_*.py"

    matches = sorted(
        ANALYZERS.glob(pattern)
    )

    if len(matches) == 0:
        raise RuntimeError(
            f"Analyzer {number:02d}: "
            f"nessun file trovato con {pattern}"
        )

    if len(matches) > 1:
        names = "\n".join(
            f"  - {x.name}"
            for x in matches
        )

        raise RuntimeError(
            f"Analyzer {number:02d}: "
            f"piu file trovati:\n{names}"
        )

    return matches[0]


def snapshot_expected(filename):

    result = {}

    if not OUTPUT.exists():
        return result

    for path in OUTPUT.rglob(filename):

        if not path.is_file():
            continue

        try:
            result[str(path)] = (
                path.stat().st_mtime_ns,
                path.stat().st_size
            )
        except Exception:
            pass

    return result


def find_new_report(filename, before):

    candidates = []

    if not OUTPUT.exists():
        return None

    for path in OUTPUT.rglob(filename):

        if not path.is_file():
            continue

        try:
            state = (
                path.stat().st_mtime_ns,
                path.stat().st_size
            )
        except Exception:
            continue

        old_state = before.get(
            str(path)
        )

        if old_state is None or state != old_state:
            candidates.append(path)

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda p: p.stat().st_mtime_ns
    )


def validate_json(path):

    if not path or not path.exists():
        return False, "file non trovato"

    if path.stat().st_size <= 0:
        return False, "file vuoto"

    try:
        with path.open(
            "r",
            encoding="utf-8-sig",
            errors="replace"
        ) as f:
            json.load(f)

        return True, "OK"

    except Exception as exc:
        return False, f"JSON non valido: {exc}"


def find_latest_handoff():

    candidates = list(
        OUTPUT.rglob(
            "START_HERE_NEW_CHAT.md"
        )
    )

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda p: p.stat().st_mtime_ns
    )


def find_latest_architecture():

    candidates = list(
        OUTPUT.rglob(
            "14_FINAL_ARCHITECTURE_ADVISOR.md"
        )
    )

    if not candidates:
        return None

    return max(
        candidates,
        key=lambda p: p.stat().st_mtime_ns
    )


# ============================================================
# DISCOVERY
# ============================================================

log("=" * 110)
log("PYTHON PROJECT INTELLIGENCE - MASTER ORCHESTRATOR")
log("=" * 110)
log(f"PROJECT    : {PROJECT_NAME}")
log(f"ROOT       : {ROOT}")
log(f"ANALYZERS  : {ANALYZERS}")
log(f"OUTPUT     : {OUTPUT}")
log(f"MASTER RUN : {MASTER_RUN}")
log("MODE       : READ ONLY - PROJECT")
log()

log("[PRECHECK] Ricerca Analyzer 01-15...")

analyzers = {}

try:

    for number in range(1, 16):

        script = discover_analyzer(
            number
        )

        analyzers[number] = script

        log(
            f"  {number:02d} OK -> "
            f"{script.name}"
        )

except Exception as exc:

    log()
    log("PRECHECK FALLITO")
    log(str(exc))
    log()
    log(
        "Nessun Analyzer e stato eseguito."
    )

    raise SystemExit(1)


log()
log("Analyzer trovati: 15/15")
log()


# ============================================================
# EXECUTION
# ============================================================

results = []

master_start = time.time()

for number in range(1, 16):

    script = analyzers[number]
    expected = EXPECTED[number]

    log("=" * 110)
    completed_before = number - 1

    bar_width = 30

    filled = int(
        bar_width * completed_before / 15
    )

    bar = (
        "#" * filled
        + "-" * (bar_width - filled)
    )

    log(
        f"[{number:02d}/15] AVVIO "
        f"{script.name}"
    )

    log(
        f"AVANZAMENTO : "
        f"[{bar}] "
        f"{completed_before}/15"
    )

    log(
        "STATO       : IN ESECUZIONE"
    )
    log(
        f"Output atteso: {expected}"
    )
    log("=" * 110)

    before = snapshot_expected(
        expected
    )

    start = time.time()

    try:

        stop_heartbeat = threading.Event()

        heartbeat = threading.Thread(
            target=progress_heartbeat,
            args=(
                number,
                15,
                script.name,
                start,
                stop_heartbeat
            ),
            daemon=True
        )

        heartbeat.start()

        process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                str(script)
            ],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1
        )

        try:

            if process.stdout:

                for line in process.stdout:

                    log(
                        "    " +
                        line.rstrip()
                    )

            return_code = process.wait()

        finally:

            stop_heartbeat.set()

            heartbeat.join(
                timeout=2
            )

    except Exception as exc:

        return_code = -1

        log(
            f"ERRORE AVVIO ANALYZER: {exc}"
        )

    elapsed = round(
        time.time() - start,
        2
    )

    new_report = find_new_report(
        expected,
        before
    )

    json_ok = False
    validation = (
        "nessun nuovo report"
    )

    if new_report:

        json_ok, validation = (
            validate_json(
                new_report
            )
        )

    success = (
        return_code == 0
        and new_report is not None
        and json_ok
    )

    result = {
        "number": number,
        "script": str(script),
        "expected_report": expected,
        "return_code": return_code,
        "elapsed_seconds": elapsed,
        "new_report":
            str(new_report)
            if new_report else None,
        "json_valid": json_ok,
        "validation": validation,
        "success": success
    }

    results.append(result)

    log()
    log(
        f"Analyzer {number:02d} "
        f"return code : {return_code}"
    )

    log(
        f"Durata                  : "
        f"{elapsed} sec"
    )

    log(
        f"Nuovo report            : "
        f"{new_report if new_report else 'NON TROVATO'}"
    )

    log(
        f"Validazione JSON         : "
        f"{validation}"
    )

    if success:

        completed_now = number

        filled = int(
            30 * completed_now / 15
        )

        bar = (
            "#" * filled
            + "-" * (30 - filled)
        )

        log(
            f"RISULTATO                : OK"
        )

        log(
            f"AVANZAMENTO              : "
            f"[{bar}] "
            f"{completed_now}/15"
        )

        log(
            f"STATO                    : COMPLETATO"
        )

    else:

        log(
            f"RISULTATO                : FAILED"
        )

        log()
        log("=" * 110)
        log(
            "MASTER ORCHESTRATOR INTERROTTO"
        )
        log("=" * 110)

        log(
            f"Analyzer fallito: "
            f"{number:02d} - {script.name}"
        )

        log()
        log(
            "Gli Analyzer successivi NON "
            "verranno eseguiti."
        )

        log(
            "Questo impedisce di costruire "
            "un pacchetto usando report vecchi."
        )

        break

    log()


# ============================================================
# MASTER METADATA
# ============================================================

master_elapsed = round(
    time.time() - master_start,
    2
)

complete = (
    len(results) == 15
    and all(
        x["success"]
        for x in results
    )
)

latest_handoff = (
    find_latest_handoff()
    if complete
    else None
)

latest_architecture = (
    find_latest_architecture()
    if complete
    else None
)

metadata = {
    "master_run": MASTER_RUN,
    "started":
        datetime.fromtimestamp(
            master_start
        ).isoformat(),
    "finished":
        datetime.now().isoformat(),
    "elapsed_seconds":
        master_elapsed,
    "complete":
        complete,
    "analyzers_expected":
        15,
    "analyzers_executed":
        len(results),
    "analyzers_successful":
        sum(
            1 for x in results
            if x["success"]
        ),
    "results":
        results,
    "ultimate_handoff":
        str(latest_handoff)
        if latest_handoff else None,
    "architecture_report":
        str(latest_architecture)
        if latest_architecture else None
}

META_FILE.write_text(
    json.dumps(
        metadata,
        indent=2,
        ensure_ascii=False
    ),
    encoding="utf-8"
)


# ============================================================
# FINAL SUMMARY
# ============================================================

log()
log("=" * 110)
log("SITE INTELLIGENCE MASTER - RISULTATO FINALE")
log("=" * 110)
log()

for result in results:

    status = (
        "OK"
        if result["success"]
        else "FAILED"
    )

    log(
        f"{result['number']:02d} "
        f"{Path(result['script']).name:<40} "
        f"{status:<8} "
        f"{result['elapsed_seconds']:>8.2f} sec"
    )


log()
log(
    f"Analyzer eseguiti        : "
    f"{len(results)}/15"
)

log(
    f"Analyzer riusciti        : "
    f"{sum(1 for x in results if x['success'])}/15"
)

log(
    f"Durata totale            : "
    f"{master_elapsed} sec"
)

log(
    f"Master metadata          : "
    f"{META_FILE}"
)

log(
    f"Master log               : "
    f"{LOG_FILE}"
)

log()

if complete:

    log(
        "MASTER STATUS: COMPLETE"
    )

    log()

    log(
        "ULTIMATE CHATGPT HANDOFF:"
    )

    log(
        str(latest_handoff)
    )

    log()

    log(
        "FINAL ARCHITECTURE REPORT:"
    )

    log(
        str(latest_architecture)
    )

else:

    log(
        "MASTER STATUS: INCOMPLETE"
    )

    log()

    failed = [
        x for x in results
        if not x["success"]
    ]

    if failed:

        item = failed[0]

        log(
            f"Prima fase fallita: "
            f"{item['number']:02d}"
        )

        log(
            f"Script: "
            f"{item['script']}"
        )

        log(
            f"Motivo: "
            f"{item['validation']}"
        )


log()
log("SICUREZZA:")
log("  Nessun file operativo eliminato.")
log("  Nessun file operativo spostato.")
log("  Nessun database modificato dal master.")
log("  Nessun processo operativo arrestato dal master.")
log(
    "  Il master esegue esclusivamente "
    "gli Analyzer Site Intelligence."
)
log("=" * 110)

if not complete:
    raise SystemExit(1)

