from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


# =============================================================================
# PYTHON PROJECT INTELLIGENCE
# ANALYZER 01 - UNIVERSAL PROJECT STRUCTURE
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
    is_excluded,
    ensure_output_directories,
)


ANALYZER_NAME = "01_project_structure"
ANALYZER_VERSION = "2.0"


# =============================================================================
# CLASSIFICAZIONE UNIVERSALE
# =============================================================================

CATEGORY_EXTENSIONS = {
    "python": {".py", ".pyw", ".pyi"},

    "web_html": {".html", ".htm"},
    "web_css": {".css", ".scss", ".sass", ".less"},
    "web_javascript": {
        ".js", ".mjs", ".cjs", ".jsx",
        ".ts", ".tsx", ".vue", ".svelte"
    },

    "database": {
        ".db", ".sqlite", ".sqlite3",
        ".duckdb", ".mdb", ".accdb"
    },

    "data": {
        ".csv", ".tsv", ".parquet",
        ".feather", ".arrow",
        ".pkl", ".pickle"
    },

    "configuration": {
        ".json", ".yaml", ".yml",
        ".toml", ".ini", ".cfg",
        ".conf", ".properties"
    },

    "documentation": {
        ".md", ".rst", ".txt",
        ".pdf", ".doc", ".docx",
        ".rtf"
    },

    "spreadsheet": {
        ".xls", ".xlsx", ".xlsm",
        ".ods"
    },

    "audio": {
        ".wav", ".mp3", ".flac",
        ".ogg", ".aac", ".m4a",
        ".aiff", ".aif"
    },

    "midi": {
        ".mid", ".midi"
    },

    "video": {
        ".mp4", ".mov", ".avi",
        ".mkv", ".webm", ".mpeg",
        ".mpg"
    },

    "image": {
        ".png", ".jpg", ".jpeg",
        ".gif", ".webp", ".bmp",
        ".svg", ".ico", ".tiff",
        ".tif"
    },

    "model_ai": {
        ".pt", ".pth", ".onnx",
        ".safetensors", ".ckpt",
        ".h5", ".keras",
        ".pb", ".tflite"
    },

    "archive": {
        ".zip", ".7z", ".rar",
        ".tar", ".gz", ".bz2",
        ".xz"
    },

    "binary": {
        ".exe", ".dll", ".so",
        ".dylib", ".bin"
    },

    "log": {
        ".log"
    },
}


SPECIAL_CONFIG_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "pipfile",
    "pipfile.lock",
    "poetry.lock",
    "setup.py",
    "setup.cfg",
    "tox.ini",
    "environment.yml",
    "environment.yaml",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    ".env",
    ".env.example",
    ".gitignore",
}


ENTRYPOINT_NAMES = {
    "main.py",
    "app.py",
    "server.py",
    "run.py",
    "start.py",
    "launcher.py",
    "manage.py",
    "__main__.py",
}


BACKUP_MARKERS = (
    "backup",
    "_bak",
    ".bak",
    "_old",
    "-old",
    "_copy",
    "copia",
    "archive",
    "archivio",
)


TEST_MARKERS = (
    "test",
    "tests",
    "pytest",
)


# =============================================================================
# HELPERS
# =============================================================================

def relative_string(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def classify_file(path: Path) -> str:

    name_lower = path.name.lower()
    suffix = path.suffix.lower()

    if name_lower in SPECIAL_CONFIG_FILES:
        return "configuration"

    for category, extensions in CATEGORY_EXTENSIONS.items():
        if suffix in extensions:
            return category

    return "other"


def looks_like_backup(path: Path) -> bool:

    value = relative_string(path).lower()

    return any(marker in value for marker in BACKUP_MARKERS)


def looks_like_test(path: Path) -> bool:

    parts = [part.lower() for part in path.parts]
    name = path.name.lower()

    if name.startswith("test_") or name.endswith("_test.py"):
        return True

    return any(marker in parts for marker in TEST_MARKERS)


def looks_like_entrypoint(path: Path) -> bool:

    name = path.name.lower()

    if name in ENTRYPOINT_NAMES:
        return True

    if path.suffix.lower() != ".py":
        return False

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except Exception:
        return False

    return 'if __name__ == "__main__"' in text


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str | None:

    try:
        digest = hashlib.sha256()

        with path.open("rb") as handle:

            while True:
                chunk = handle.read(chunk_size)

                if not chunk:
                    break

                digest.update(chunk)

        return digest.hexdigest()

    except Exception:
        return None


def safe_size(path: Path) -> int:

    try:
        return path.stat().st_size
    except OSError:
        return 0


# =============================================================================
# ANALISI
# =============================================================================

def analyze_project() -> dict:

    files = sorted(
        iter_project_files(),
        key=lambda p: str(p).lower()
    )

    categories = Counter()
    extensions = Counter()
    directory_counts = Counter()

    entrypoints = []
    backup_candidates = []
    test_files = []
    large_files = []
    zero_byte_files = []

    file_records = []

    total_bytes = 0

    hash_groups = defaultdict(list)

    for path in files:

        relative = relative_string(path)
        suffix = path.suffix.lower() or "[no_extension]"
        category = classify_file(path)
        size = safe_size(path)

        total_bytes += size

        categories[category] += 1
        extensions[suffix] += 1

        parent = str(Path(relative).parent)

        directory_counts[parent] += 1

        if looks_like_entrypoint(path):
            entrypoints.append(relative)

        if looks_like_backup(path):
            backup_candidates.append(relative)

        if looks_like_test(path):
            test_files.append(relative)

        if size == 0:
            zero_byte_files.append(relative)

        if size >= 50 * 1024 * 1024:
            large_files.append({
                "path": relative,
                "size_bytes": size,
                "size_mb": round(size / 1024 / 1024, 2),
            })

        # Hash soltanto per file <= 25 MB.
        # Serve a trovare duplicati senza caricare file enormi in memoria.
        file_hash = None

        if 0 < size <= 25 * 1024 * 1024:
            file_hash = sha256_file(path)

            if file_hash:
                hash_groups[file_hash].append(relative)

        file_records.append({
            "path": relative,
            "extension": suffix,
            "category": category,
            "size_bytes": size,
        })

    duplicate_groups = []

    for digest, paths in hash_groups.items():

        if len(paths) > 1:
            duplicate_groups.append({
                "sha256": digest,
                "count": len(paths),
                "files": paths,
            })

    duplicate_groups.sort(
        key=lambda item: item["count"],
        reverse=True,
    )

    # Directory reali del progetto, rispettando le esclusioni.
    directories = set()

    for path in files:

        parent = path.parent

        while True:

            if parent == PROJECT_ROOT:
                break

            if is_excluded(parent):
                break

            directories.add(relative_string(parent))

            if parent.parent == parent:
                break

            parent = parent.parent

    result = {
        "metadata": {
            "analyzer": ANALYZER_NAME,
            "version": ANALYZER_VERSION,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "project_name": PROJECT_NAME,
            "project_root": str(PROJECT_ROOT),
            "intelligence_root": str(INTELLIGENCE_ROOT),
        },

        "summary": {
            "total_files": len(files),
            "total_directories": len(directories),
            "total_size_bytes": total_bytes,
            "total_size_mb": round(total_bytes / 1024 / 1024, 2),

            "python_files": categories.get("python", 0),

            "entrypoint_candidates": len(entrypoints),
            "backup_candidates": len(backup_candidates),
            "test_files": len(test_files),
            "large_files_50mb_plus": len(large_files),
            "zero_byte_files": len(zero_byte_files),
            "exact_duplicate_groups": len(duplicate_groups),
        },

        "categories": dict(
            sorted(
                categories.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),

        "extensions": dict(
            sorted(
                extensions.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),

        "entrypoint_candidates": entrypoints,

        "backup_candidates": backup_candidates,

        "test_files": test_files,

        "large_files": sorted(
            large_files,
            key=lambda item: item["size_bytes"],
            reverse=True,
        ),

        "zero_byte_files": zero_byte_files,

        "exact_duplicate_groups": duplicate_groups,

        "directory_file_counts": dict(
            sorted(
                directory_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),

        "files": file_records,
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
        / "01_PROJECT_STRUCTURE"
    )

    analyzer_output.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = analyzer_output / "PROJECT_STRUCTURE.json"

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
    print("ANALYZER 01 - UNIVERSAL PROJECT STRUCTURE")
    print("=" * 100)

    print(f"Project name       : {PROJECT_NAME}")
    print(f"Project root       : {PROJECT_ROOT}")
    print(f"Intelligence root  : {INTELLIGENCE_ROOT}")

    print()
    print("Analisi struttura progetto in corso...")
    print()

    result = analyze_project()

    summary = result["summary"]

    print(f"File progetto      : {summary['total_files']}")
    print(f"Directory          : {summary['total_directories']}")
    print(f"Dimensione         : {summary['total_size_mb']} MB")
    print(f"File Python        : {summary['python_files']}")
    print(f"Entrypoint         : {summary['entrypoint_candidates']}")
    print(f"Backup candidati   : {summary['backup_candidates']}")
    print(f"File test          : {summary['test_files']}")
    print(f"File >= 50 MB      : {summary['large_files_50mb_plus']}")
    print(f"File zero byte     : {summary['zero_byte_files']}")
    print(f"Duplicati esatti   : {summary['exact_duplicate_groups']}")

    print()
    print("CATEGORIE:")

    for category, count in result["categories"].items():
        print(f"  {category:<20} {count}")

    output_file = write_report(result)

    # Verifica anti-contaminazione.
    contamination = [
        item["path"]
        for item in result["files"]
        if "python_project_intelligence" in Path(item["path"]).parts
    ]

    print()
    print(f"Self contamination : {len(contamination)}")
    print(f"Report JSON         : {output_file}")

    print()

    if contamination:
        print("ANALYZER STATUS: FAILED")
        print("Python Project Intelligence e' entrato nell'inventario.")
        return 1

    print("ANALYZER STATUS: OK")
    print("=" * 100)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
