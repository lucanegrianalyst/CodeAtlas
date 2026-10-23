from __future__ import annotations

import ast
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

HERE_DIR = Path(__file__).resolve().parent
INTELLIGENCE_ROOT = HERE_DIR.parent
CORE_DIR = INTELLIGENCE_ROOT / 'core'
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from project_context import (
    PROJECT_ROOT,
    PROJECT_NAME,
    PROJECT_OUTPUT_ROOT,
    iter_project_files,
    iter_python_files,
    is_inside_intelligence,
 )

VERSION = '2.0.0-test'
RUN_ID = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
LATEST_DIR = PROJECT_OUTPUT_ROOT / 'LATEST'
OUTPUT_DIR = LATEST_DIR / '12_PROJECT_ORGANIZATION'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REPORT_01 = LATEST_DIR / '01_PROJECT_STRUCTURE' / 'PROJECT_STRUCTURE.json'
REPORT_10 = LATEST_DIR / '10_CROSS_ANALYSIS' / 'CROSS_ANALYSIS_MAP.json'
REPORT_11 = LATEST_DIR / '11_FINAL_PROJECT_INTELLIGENCE' / 'FINAL_PROJECT_INTELLIGENCE.json'

def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except (ValueError, OSError):
        return str(path)

def norm(value) -> str:
    return str(value).replace(chr(47), chr(92)).lower()

def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}

report_01 = load_json(REPORT_01)
report_10 = load_json(REPORT_10)
report_11 = load_json(REPORT_11)

component_registry = report_10.get('component_registry', [])
registry_by_file = {}
for component in component_registry:
    file_name = norm(component.get('file', ''))
    if file_name:
        registry_by_file[file_name] = component

active_confirmed = {norm(x.get('file', '')) for x in component_registry if x.get('state') == 'ACTIVE_CONFIRMED'}
connected_confirmed = {norm(x.get('file', '')) for x in component_registry if x.get('state') == 'CONNECTED_CONFIRMED'}
protected_operational = active_confirmed | connected_confirmed

print('=' * 110)
print('PYTHON PROJECT INTELLIGENCE - ANALYZER 12 V2 TEST')
print('=' * 110)
print(f'Project : {PROJECT_NAME}')
print(f'Root    : {PROJECT_ROOT}')
print('Mode    : READ ONLY / EVIDENCE DRIVEN')
print()
print('[1/6] Source evidence')
print(f'Analyzer 01 : {"OK" if report_01 else "MISSING"}')
print(f'Analyzer 10 : {"OK" if report_10 else "MISSING"}')
print(f'Analyzer 11 : {"OK" if report_11 else "MISSING"}')
print(f'Registry    : {len(component_registry)} components')
print(f'Active      : {len(active_confirmed)}')
print(f'Connected   : {len(connected_confirmed)}')
print(f'Protected   : {len(protected_operational)}')

print('[2/6] Python organization and quality scan...')
python_inventory = []
parse_errors = []
legacy_files = []

for path in iter_python_files():
    relative = rel(path)
    relative_norm = norm(relative)
    if relative_norm.startswith('site_intelligence' + chr(92)):
        legacy_files.append(relative)
        continue
    try:
        text = path.read_text(encoding='utf-8-sig', errors='replace')
        tree = ast.parse(text, filename=relative)
    except (OSError, SyntaxError, ValueError) as exc:
        parse_errors.append({'file': relative, 'error': str(exc)})
        continue
    lines = text.count(chr(10)) + 1 if text else 0
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    max_function_lines = 0
    for fn in functions:
        end_line = getattr(fn, 'end_lineno', fn.lineno)
        max_function_lines = max(max_function_lines, end_line - fn.lineno + 1)
    state = registry_by_file.get(relative_norm, {}).get('state', 'UNCLASSIFIED')
    python_inventory.append({
        'file': relative,
        'state': state,
        'protected': relative_norm in protected_operational,
        'lines': lines,
        'functions': len(functions),
        'classes': len(classes),
        'max_function_lines': max_function_lines,
        'todo_fixme': len(re.findall(r'\b(?:TODO|FIXME)\b', text, flags=re.I)),
        'print_calls': len(re.findall(r'\bprint\s*\(', text)),
        'global_statements': sum(isinstance(n, ast.Global) for n in ast.walk(tree)),
    })

large_python = [x for x in python_inventory if x['lines'] >= 500]
very_large_python = [x for x in python_inventory if x['lines'] >= 1000]
large_functions = [x for x in python_inventory if x['max_function_lines'] >= 100]

print(f'Python analyzed : {len(python_inventory)}')
print(f'Legacy excluded : {len(legacy_files)}')
print(f'Parse errors    : {len(parse_errors)}')
print(f'>=500 lines     : {len(large_python)}')
print(f'>=1000 lines    : {len(very_large_python)}')
print(f'Functions >=100 : {len(large_functions)}')

HISTORICAL_DIRS = {'backup','backups','archive','archives','old','legacy','_deep_audit','_runtime_report','_forensic_report','site_intelligence'}

def is_historical(relative: str) -> bool:
    parts = {part.lower() for part in Path(relative).parts[:-1]}
    return bool(parts & HISTORICAL_DIRS) and norm(relative) not in protected_operational

active_python_inventory = [x for x in python_inventory if not is_historical(x['file'])]
historical_python_inventory = [x for x in python_inventory if is_historical(x['file'])]
active_large_python = [x for x in active_python_inventory if x['lines'] >= 500]
active_very_large_python = [x for x in active_python_inventory if x['lines'] >= 1000]
active_large_functions = [x for x in active_python_inventory if x['max_function_lines'] >= 100]
protected_found = sum(1 for x in active_python_inventory if x['protected'])

print('[3/6] Active versus historical organization...')
print(f'Active Python       : {len(active_python_inventory)}')
print(f'Historical Python   : {len(historical_python_inventory) + len(legacy_files)}')
print(f'Active >=500 lines  : {len(active_large_python)}')
print(f'Active >=1000 lines : {len(active_very_large_python)}')
print(f'Active funcs >=100  : {len(active_large_functions)}')
print(f'Protected preserved : {protected_found} / {len(protected_operational)}')

print('[4/6] Evidence-driven refactoring recommendations...')
recommendations = []

for item in python_inventory:
    relative = item['file']
    key = norm(relative)
    component = registry_by_file.get(key, {})
    state = component.get('state', item.get('state', 'UNCLASSIFIED'))
    if key in protected_operational:
        action = 'DO_NOT_TOUCH'
        confidence = 'CONFIRMED'
        reason = 'Operational evidence from Analyzer 10/11.'
    elif is_historical(relative):
        action = 'REVIEW_FOR_ARCHIVE'
        confidence = 'PROBABLE'
        reason = 'Historical directory classification; no automatic deletion.'
    elif state == 'MULTI_SOURCE_COMPONENT':
        action = 'KEEP_OR_REVIEW'
        confidence = 'PROBABLE'
        reason = 'Multiple analyzer evidence sources; role requires review.'
    else:
        action = 'KEEP_OR_REVIEW'
        confidence = 'POSSIBLE'
        reason = 'No sufficient evidence for move, archive, or deletion.'
    recommendations.append({'file': relative, 'state': state, 'action': action, 'confidence': confidence, 'reason': reason})

action_counts = Counter(x['action'] for x in recommendations)
protected_bad = [x for x in recommendations if norm(x['file']) in protected_operational and x['action'] != 'DO_NOT_TOUCH']

print(f'DO_NOT_TOUCH      : {action_counts.get("DO_NOT_TOUCH", 0)}')
print(f'REVIEW_FOR_ARCHIVE: {action_counts.get("REVIEW_FOR_ARCHIVE", 0)}')
print(f'KEEP_OR_REVIEW    : {action_counts.get("KEEP_OR_REVIEW", 0)}')
print(f'Protection errors : {len(protected_bad)}')

print('[5/6] Building organization intelligence report...')
root_python = [x for x in active_python_inventory if len(Path(x['file']).parts) == 1]
large_ratio = (len(active_large_python) / len(active_python_inventory)) if active_python_inventory else 0
very_large_ratio = (len(active_very_large_python) / len(active_python_inventory)) if active_python_inventory else 0
root_ratio = (len(root_python) / len(active_python_inventory)) if active_python_inventory else 0
refactoring_pressure_score = min(100, round((large_ratio * 35) + (very_large_ratio * 35) + (root_ratio * 30)))

result = {
    'metadata': {
        'analyzer': '12_PROJECT_ORGANIZATION_AND_REFACTORING_ADVISOR',
        'version': VERSION,
        'run_id': RUN_ID,
        'project_name': PROJECT_NAME,
        'project_root': str(PROJECT_ROOT),
        'mode': 'READ_ONLY',
    },
    'evidence': {
        'analyzer_01_loaded': bool(report_01),
        'analyzer_10_loaded': bool(report_10),
        'analyzer_11_loaded': bool(report_11),
        'component_registry': len(component_registry),
        'active_confirmed': len(active_confirmed),
        'connected_confirmed': len(connected_confirmed),
        'protected_operational': len(protected_operational),
    },
    'organization': {
        'active_python_files': len(active_python_inventory),
        'historical_python_files': len(historical_python_inventory) + len(legacy_files),
        'root_python_files': len(root_python),
        'active_large_python_files': len(active_large_python),
        'active_very_large_python_files': len(active_very_large_python),
        'active_files_with_large_functions': len(active_large_functions),
        'parse_errors': len(parse_errors),
    },
    'refactoring_pressure': {
        'score_0_100': refactoring_pressure_score,
        'meaning': 'Structural refactoring pressure only. This is NOT a runtime health score and NOT a percentage of project failure.',
        'confidence': 'PROBABLE',
    },
    'recommendation_counts': dict(action_counts),
    'recommendations': recommendations,
    'active_python_inventory': active_python_inventory,
    'parse_errors': parse_errors,
    'safety': {
        'protected_components_expected': len(protected_operational),
        'protected_components_found': protected_found,
        'protection_errors': protected_bad,
        'automatic_moves': False,
        'automatic_deletions': False,
    },
}

json_path = OUTPUT_DIR / 'ORGANIZATION_REFACTORING_MAP.json'
md_path = OUTPUT_DIR / 'ORGANIZATION_REFACTORING_REPORT.md'
txt_path = OUTPUT_DIR / 'ORGANIZATION_REFACTORING_SUMMARY.txt'
json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
md_lines = ['# Project Organization & Refactoring Advisor V2','',f'Project: {PROJECT_NAME}',f'Active Python files: {len(active_python_inventory)}',f'Historical/legacy Python files: {len(historical_python_inventory) + len(legacy_files)}',f'Protected operational components: {protected_found}/{len(protected_operational)}',f'Refactoring pressure score: {refactoring_pressure_score}/100','', '**Important:** this score measures structural refactoring pressure only. It is not a runtime-health score and not a percentage of project failure.','',f'DO_NOT_TOUCH: {action_counts.get("DO_NOT_TOUCH",0)}',f'REVIEW_FOR_ARCHIVE: {action_counts.get("REVIEW_FOR_ARCHIVE",0)}',f'KEEP_OR_REVIEW: {action_counts.get("KEEP_OR_REVIEW",0)}']
md_path.write_text(chr(10).join(md_lines) + chr(10), encoding='utf-8')
txt_path.write_text(chr(10).join(x.replace('# ','') for x in md_lines if not x.startswith('**')) + chr(10), encoding='utf-8')

print('[6/6] Output validation...')
print(f'Refactoring pressure : {refactoring_pressure_score}/100')
print(f'JSON                 : {json_path}')
print(f'Markdown             : {md_path}')
print(f'Summary              : {txt_path}')
print(f'Protection errors    : {len(protected_bad)}')
print('ANALYZER 12 STATUS   : ' + ('ORGANIZATION_INTELLIGENCE_READY' if not protected_bad else 'PROTECTION_ERROR'))

