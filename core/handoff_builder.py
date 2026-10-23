from pathlib import Path
import json
import re
import shutil
import tempfile
import zipfile


def get_handoff_paths(project_output_root):
    latest = Path(project_output_root) / "LATEST"
    return {
        "latest": latest,
        "folder": latest / "CHATGPT_HANDOFF",
        "zip": latest / "CHATGPT_HANDOFF.zip",
    }

REPORT_DIRECTORIES = {
    1: "01_PROJECT_STRUCTURE",
    2: "02_RUNTIME",
    3: "03_DATABASE",
    4: "04_CODE_CONNECTIONS",
    5: "05_CONFIGURATION",
    6: "06_API_ENDPOINTS",
    7: "07_DATA_FLOW",
    8: "08_HEALTH_ERRORS",
    9: "09_PERFORMANCE_BOTTLENECK",
    10: "10_CROSS_ANALYSIS",
    11: "11_FINAL_PROJECT_INTELLIGENCE",
    12: "12_PROJECT_ORGANIZATION",
    13: "13_HARDWARE_RESOURCE",
    14: "14_FINAL_ARCHITECTURE_ADVISOR",
    15: "15_ULTIMATE_HANDOFF",
}

REPORT_NAMES = [
    "PROJECT_STRUCTURE.json",
    "RUNTIME_MAP.json",
    "DATABASE_MAP.json",
    "CODE_CONNECTIONS.json",
    "CONFIGURATION_MAP.json",
    "API_ENDPOINTS_MAP.json",
    "DATA_FLOW_MAP.json",
    "HEALTH_ERROR_MAP.json",
    "PERFORMANCE_MAP.json",
    "CROSS_ANALYSIS_MAP.json",
    "FINAL_PROJECT_INTELLIGENCE.json",
    "ORGANIZATION_REFACTORING_MAP.json",
    "HARDWARE_RESOURCE_MAP.json",
    "FINAL_ARCHITECTURE_MAP.json",
    "FUNCTIONAL_KNOWLEDGE.json",
]

EXTRA_REPORTS = {
    "PROJECT_FUNCTIONAL_MANUAL.md":
        "15_ULTIMATE_HANDOFF/PROJECT_FUNCTIONAL_MANUAL.md",

    "FINAL_ARCHITECTURE.md":
        "14_FINAL_ARCHITECTURE_ADVISOR/14_FINAL_ARCHITECTURE_ADVISOR.md",

    "ORGANIZATION_REPORT.md":
        "12_PROJECT_ORGANIZATION/ORGANIZATION_REFACTORING_REPORT.md",

    "HARDWARE_REPORT.md":
        "13_HARDWARE_RESOURCE/HARDWARE_RESOURCE_REPORT.md",

    "SAFE_MIGRATION_PLAN.txt":
        "14_FINAL_ARCHITECTURE_ADVISOR/SAFE_MIGRATION_PLAN.txt",
}

def get_report_map():
    result = {}

    for number, filename in enumerate(REPORT_NAMES, 1):
        result[f"{number:02d}_{filename}"] = (
            Path(REPORT_DIRECTORIES[number]) / filename
        )

    result.update({
        name: Path(relative)
        for name, relative in EXTRA_REPORTS.items()
    })

    return result

def validate_sources(latest):
    latest = Path(latest)
    problems = []

    report_map = get_report_map()

    for name, relative in report_map.items():

        path = latest / relative

        # ---------------------------------------------------------
        # FILE ESISTENTE
        # ---------------------------------------------------------
        if not path.is_file():
            problems.append((name, "MISSING"))
            continue

        # ---------------------------------------------------------
        # FILE NON VUOTO
        # ---------------------------------------------------------
        if path.stat().st_size <= 0:
            problems.append((name, "EMPTY"))
            continue

        try:
            # -----------------------------------------------------
            # LETTURA UTF-8 / UTF-8-SIG
            # -----------------------------------------------------
            content = path.read_text(
                encoding="utf-8-sig"
            )

            # -----------------------------------------------------
            # VALIDAZIONE JSON
            # -----------------------------------------------------
            if name.endswith(".json"):
                json.loads(content)

            # -----------------------------------------------------
            # CONTROLLO PRIVATE KEY
            # -----------------------------------------------------
            if re.search(
                r"-----BEGIN .*PRIVATE KEY-----",
                content,
                re.IGNORECASE
            ):
                problems.append(
                    (name, "PRIVATE_KEY")
                )

            # -----------------------------------------------------
            # CONTROLLO BEARER TOKEN
            # -----------------------------------------------------
            if re.search(
                r"\bBearer\s+[A-Za-z0-9._~+/-]{16,}",
                content,
                re.IGNORECASE
            ):
                problems.append(
                    (name, "BEARER_TOKEN")
                )

        except json.JSONDecodeError:
            problems.append(
                (name, "INVALID_JSON")
            )

        except UnicodeError:
            problems.append(
                (name, "INVALID_ENCODING")
            )

        except Exception as exc:
            problems.append(
                (
                    name,
                    f"UNREADABLE:{type(exc).__name__}"
                )
            )

    return problems

def build_handoff(project_output_root, dry_run=True, replace_existing=False):
    from datetime import datetime
    import shutil
    import tempfile
    import zipfile

    root = Path(project_output_root)
    latest = root / "LATEST"
    destination = latest / "CHATGPT_HANDOFF"
    archive = latest / "CHATGPT_HANDOFF.zip"

    if not latest.is_dir():
        raise RuntimeError(f"LATEST non esiste: {latest}")

    problems = validate_sources(latest)

    if problems:
        raise RuntimeError("HANDOFF BLOCKED: " + repr(problems))

    report_map = get_report_map()

    if dry_run:
        return {
            "status": "DRY_RUN_OK",
            "documents": len(report_map),
            "destination": str(destination),
            "archive": str(archive),
            "writes_performed": False,
            "replace_existing": replace_existing,
        }

    if (destination.exists() or archive.exists()) and not replace_existing:
        raise RuntimeError(
            "EXISTING HANDOFF BLOCKED: replace_existing=False"
        )

    temp_root = Path(tempfile.mkdtemp(
        prefix="CHATGPT_HANDOFF_BUILD_",
        dir=str(latest)
    ))

    temp_package = temp_root / "CHATGPT_HANDOFF"
    temp_archive = temp_root / "CHATGPT_HANDOFF.zip"
    backup_root = None
    destination_moved = False
    archive_moved = False

    try:
        temp_package.mkdir()

        for name, relative in report_map.items():
            source = latest / relative
            target = temp_package / name

            if not source.is_file():
                raise RuntimeError(f"SOURCE DISAPPEARED: {source}")

            shutil.copy2(source, target)

        readme = temp_package / "00_READ_ME_FIRST.md"

        readme.write_text(
            """# PYTHON PROJECT INTELLIGENCE - TECHNICAL HANDOFF

Pacchetto tecnico generato automaticamente da
Python Project Intelligence.

Contiene informazioni tecniche osservabili durante
la scansione del progetto.

La presenza di codice statico non dimostra
necessariamente che quel codice sia attivo.

I dati runtime rappresentano una fotografia
del momento della scansione.

Il pacchetto non ricostruisce la cronologia della
conversazione ChatGPT e non determina gli obiettivi
futuri dell'utente.
""",
            encoding="utf-8"
        )

        expected = {"00_READ_ME_FIRST.md"} | set(report_map.keys())

        files = [
            x for x in temp_package.iterdir()
            if x.is_file()
        ]

        actual = {x.name for x in files}

        if len(files) != 21:
            raise RuntimeError(
                f"PACKAGE FILE COUNT INVALID: {len(files)}"
            )

        if actual != expected:
            raise RuntimeError("PACKAGE CONTENT INVALID")

        for item in files:
            if item.stat().st_size <= 0:
                raise RuntimeError(
                    f"EMPTY PACKAGE FILE: {item.name}"
                )

        with zipfile.ZipFile(
            temp_archive,
            "w",
            compression=zipfile.ZIP_DEFLATED
        ) as zf:
            for item in sorted(files):
                zf.write(item, arcname=item.name)

        with zipfile.ZipFile(temp_archive, "r") as zf:
            bad = zf.testzip()
            entries = set(zf.namelist())

        if bad is not None:
            raise RuntimeError(f"ZIP CORRUPTED: {bad}")

        if entries != expected:
            raise RuntimeError("ZIP CONTENT INVALID")

        if replace_existing and (
            destination.exists() or archive.exists()
        ):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            backup_root = (
                latest /
                "CHATGPT_HANDOFF_BACKUPS" /
                f"HANDOFF_{timestamp}"
            )

            backup_root.mkdir(
                parents=True,
                exist_ok=False
            )

            if destination.exists():
                shutil.copytree(
                    destination,
                    backup_root / "CHATGPT_HANDOFF"
                )

            if archive.exists():
                shutil.copy2(
                    archive,
                    backup_root / "CHATGPT_HANDOFF.zip"
                )

        # =====================================================
        # COMMIT PROTETTO
        # =====================================================

        if destination.exists():
            shutil.rmtree(destination)

        if archive.exists():
            archive.unlink()

        shutil.move(
            str(temp_package),
            str(destination)
        )

        destination_moved = True

        shutil.move(
            str(temp_archive),
            str(archive)
        )

        archive_moved = True

        # =====================================================
        # VERIFICA FINALE
        # =====================================================

        final_files = [
            x for x in destination.iterdir()
            if x.is_file()
        ]

        final_names = {x.name for x in final_files}

        if len(final_files) != 21:
            raise RuntimeError(
                "FINAL PACKAGE FILE COUNT INVALID"
            )

        if final_names != expected:
            raise RuntimeError(
                "FINAL PACKAGE CONTENT INVALID"
            )

        with zipfile.ZipFile(archive, "r") as zf:
            bad = zf.testzip()
            final_entries = set(zf.namelist())

        if bad is not None:
            raise RuntimeError(
                f"FINAL ZIP CORRUPTED: {bad}"
            )

        if final_entries != expected:
            raise RuntimeError(
                "FINAL ZIP CONTENT INVALID"
            )

        return {
            "status": "UPDATED" if replace_existing else "CREATED",
            "documents": len(report_map),
            "package_files": 21,
            "destination": str(destination),
            "archive": str(archive),
            "backup": str(backup_root) if backup_root else None,
            "writes_performed": True,
            "rollback": "NOT_REQUIRED",
        }

    except Exception as exc:

        # =====================================================
        # ROLLBACK
        # =====================================================

        rollback_error = None

        try:

            if archive_moved and archive.exists():
                archive.unlink()

            if destination_moved and destination.exists():
                shutil.rmtree(destination)

            if backup_root and backup_root.exists():

                backup_folder = (
                    backup_root / "CHATGPT_HANDOFF"
                )

                backup_archive = (
                    backup_root / "CHATGPT_HANDOFF.zip"
                )

                if backup_folder.exists():
                    shutil.copytree(
                        backup_folder,
                        destination
                    )

                if backup_archive.exists():
                    shutil.copy2(
                        backup_archive,
                        archive
                    )

        except Exception as rollback_exc:
            rollback_error = str(rollback_exc)

        message = (
            f"HANDOFF BUILD FAILED: {exc}"
        )

        if rollback_error:
            message += (
                f" | ROLLBACK FAILED: "
                f"{rollback_error}"
            )
        else:
            message += (
                " | ROLLBACK: OK"
            )

        raise RuntimeError(message) from exc

    finally:

        if temp_root.exists():
            shutil.rmtree(
                temp_root,
                ignore_errors=True
            )
