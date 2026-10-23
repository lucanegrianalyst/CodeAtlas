from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, UTC
from pathlib import Path

HERE_DIR = Path(__file__).resolve().parent
INTELLIGENCE_ROOT = HERE_DIR.parent
CORE_DIR = INTELLIGENCE_ROOT / 'core'
if str(CORE_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_DIR))

from project_context import PROJECT_ROOT, PROJECT_NAME, PROJECT_OUTPUT_ROOT

VERSION = '2.0.0-test'
RUN_ID = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
LATEST_DIR = PROJECT_OUTPUT_ROOT / 'LATEST'
OUTPUT_DIR = LATEST_DIR / '13_HARDWARE_RESOURCE'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

REPORT_02 = LATEST_DIR / '02_RUNTIME' / 'RUNTIME_MAP.json'
REPORT_03 = LATEST_DIR / '03_DATABASE' / 'DATABASE_MAP.json'
REPORT_09 = LATEST_DIR / '09_PERFORMANCE_BOTTLENECK' / 'PERFORMANCE_MAP.json'
REPORT_10 = LATEST_DIR / '10_CROSS_ANALYSIS' / 'CROSS_ANALYSIS_MAP.json'

def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}

def ensure_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]

def gb(value) -> float:
    try:
        return round(float(value) / (1024 ** 3), 2)
    except (TypeError, ValueError):
        return 0.0

def mb(value) -> float:
    try:
        return round(float(value) / (1024 ** 2), 2)
    except (TypeError, ValueError):
        return 0.0

report_02 = load_json(REPORT_02)
report_03 = load_json(REPORT_03)
report_09 = load_json(REPORT_09)
report_10 = load_json(REPORT_10)

print('=' * 110)
print('PYTHON PROJECT INTELLIGENCE - ANALYZER 13 V2 TEST')
print('=' * 110)
print(f'Project : {PROJECT_NAME}')
print(f'Root    : {PROJECT_ROOT}')
print('Mode    : READ ONLY / HARDWARE & RESOURCE INTELLIGENCE')
print()
print('[1/6] Source evidence')
print(f'Analyzer 02 Runtime     : {"OK" if report_02 else "MISSING"}')
print(f'Analyzer 03 Database    : {"OK" if report_03 else "MISSING"}')
print(f'Analyzer 09 Performance : {"OK" if report_09 else "MISSING"}')
print(f'Analyzer 10 Cross       : {"OK" if report_10 else "MISSING"}')

def powershell_json(command: str):
    try:
        r = subprocess.run(['powershell','-NoProfile','-Command',command], capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        text = r.stdout.strip()
        return json.loads(text) if text else None
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError):
        return None

print('[2/6] Hardware snapshot...')
cpu_list = ensure_list(powershell_json("Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed | ConvertTo-Json -Compress"))
memory_info = powershell_json("Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize,FreePhysicalMemory | ConvertTo-Json -Compress") or {}
physical_disks = ensure_list(powershell_json("Get-PhysicalDisk | Select-Object FriendlyName,MediaType,BusType,Size,HealthStatus | ConvertTo-Json -Compress"))
logical_disks = ensure_list(powershell_json("Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,Size,FreeSpace | ConvertTo-Json -Compress"))
gpu_list = ensure_list(powershell_json("Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json -Compress"))

physical_cores = sum(int(x.get('NumberOfCores') or 0) for x in cpu_list)
logical_cores = sum(int(x.get('NumberOfLogicalProcessors') or 0) for x in cpu_list)
total_ram_bytes = int(memory_info.get('TotalVisibleMemorySize') or 0) * 1024
free_ram_bytes = int(memory_info.get('FreePhysicalMemory') or 0) * 1024
used_ram_bytes = max(0, total_ram_bytes - free_ram_bytes)
ram_used_pct = round((used_ram_bytes / total_ram_bytes * 100), 2) if total_ram_bytes else 0.0

print(f'CPU              : {cpu_list[0].get("Name") if cpu_list else "UNKNOWN"}')
print(f'Cores            : {physical_cores} physical / {logical_cores} logical')
print(f'RAM              : {gb(total_ram_bytes)} GB total / {gb(free_ram_bytes)} GB free / {ram_used_pct}% used')
print(f'Physical disks   : {len(physical_disks)}')
print(f'Logical disks    : {len(logical_disks)}')
print(f'GPU controllers  : {len(gpu_list)}')

print('[3/6] Project resource attribution...')
runtime_summary = report_02.get('summary', {})
project_processes = report_02.get('project_processes', [])
external_processes = report_02.get('external_python_processes', [])
project_process_count = int(runtime_summary.get('project_python_processes') or len(project_processes))
project_ws_mb = float(runtime_summary.get('project_working_set_mb') or 0)
project_private_mb = float(runtime_summary.get('project_private_memory_mb') or 0)
project_threads = int(runtime_summary.get('project_threads') or 0)
project_ports = report_02.get('project_listening_ports', [])
project_ram_pct = round((project_ws_mb * 1024 * 1024 / total_ram_bytes * 100), 2) if total_ram_bytes else 0.0

heaviest_processes = sorted(project_processes, key=lambda x: float((x.get('resources') or {}).get('working_set_mb') or 0), reverse=True)

print(f'Project processes : {project_process_count}')
print(f'External Python   : {len(external_processes)}')
print(f'Project WS        : {project_ws_mb:.2f} MB')
print(f'Project private   : {project_private_mb:.2f} MB')
print(f'Project threads   : {project_threads}')
print(f'Project RAM share : {project_ram_pct:.2f}%')
print(f'Project ports     : {len(project_ports)}')
if heaviest_processes:
    hp = heaviest_processes[0]
    hr = hp.get('resources') or {}
    print(f'Heaviest process  : PID {hp.get("pid")} | {hr.get("working_set_mb",0)} MB WS | {hp.get("command_line","")}')

print('[4/6] Database and storage intelligence...')
db_summary = report_03.get('summary', {})
database_inventory = report_03.get('databases', [])
database_count = int(db_summary.get('database_files') or 0)
database_size_mb = float(db_summary.get('total_database_size_mb') or 0)
database_rows = int(db_summary.get('confirmed_rows') or 0)
database_integrity_issues = int(db_summary.get('integrity_problems') or 0)
largest_database = max(database_inventory, key=lambda x: float(x.get('size_bytes') or 0), default={})

disk_capacity = []
for disk in logical_disks:
    size = int(disk.get('Size') or 0)
    free = int(disk.get('FreeSpace') or 0)
    free_pct = round(free / size * 100, 2) if size else None
    disk_capacity.append({'drive': disk.get('DeviceID'), 'size_gb': gb(size), 'free_gb': gb(free), 'free_percent': free_pct})

print(f'Databases          : {database_count}')
print(f'Database size      : {database_size_mb:.2f} MB')
print(f'Confirmed rows     : {database_rows:,}')
print(f'Integrity problems : {database_integrity_issues}')
print(f'Largest database   : {largest_database.get("relative_path", "UNKNOWN")} | {largest_database.get("size_mb", 0)} MB')
print('Disk capacity:')
for disk in disk_capacity:
    print('  {} | {} GB total | {} GB free | {}% free'.format(disk['drive'], disk['size_gb'], disk['free_gb'], disk['free_percent']))

print('[5/6] Resource risk assessment...')
resource_findings = []
def add_finding(code, severity, confidence, evidence):
    resource_findings.append(dict(code=code, severity=severity, confidence=confidence, evidence=evidence))
if ram_used_pct >= 75:
    add_finding('HOST_RAM', 'HIGH' if ram_used_pct >= 90 else 'MEDIUM', 'CONFIRMED', str(ram_used_pct)+'% used')
for d in disk_capacity:
    pct = d.get('free_percent')
    if pct is not None and pct < 20:
        add_finding('DISK_SPACE', 'HIGH' if pct < 10 else 'MEDIUM', 'CONFIRMED', str(d.get('drive'))+' '+str(pct)+'% free')
if database_integrity_issues:
    add_finding('DB_INTEGRITY', 'HIGH', 'CONFIRMED', str(database_integrity_issues)+' issues')
if database_size_mb >= 2048:
    add_finding('DB_GROWTH', 'LOW', 'POSSIBLE', str(database_size_mb)+' MB; growth rate unknown')
if heaviest_processes and project_ws_mb:
    top = heaviest_processes[0]
    share = float(top.get('resources',{}).get('working_set_mb',0))/project_ws_mb*100
    if share >= 70:
        add_finding('MEMORY_CONCENTRATION', 'INFO', 'CONFIRMED', str(round(share,1))+'% of project working set')
print('Findings:',len(resource_findings))
for f in resource_findings: print(f['severity'], '|', f['confidence'], '|', f['code'], '|', f['evidence'])
print('Confirmed hardware bottlenecks: NOT ESTABLISHED')
print('[6/6] Generating reports...')
report = {'metadata': {'analyzer': 13, 'version': VERSION, 'project': PROJECT_NAME, 'generated_utc': datetime.now(UTC).isoformat()}, 'hardware': {'cpu': cpu_list, 'physical_cores': physical_cores, 'logical_cores': logical_cores, 'ram_total_gb': gb(total_ram_bytes), 'ram_free_gb': gb(free_ram_bytes), 'ram_used_percent': ram_used_pct, 'physical_disks': physical_disks, 'logical_disks': disk_capacity, 'gpus': gpu_list}, 'project_resources': {'processes': project_process_count, 'external_python_processes': len(external_processes), 'working_set_mb': project_ws_mb, 'private_memory_mb': project_private_mb, 'threads': project_threads, 'ports': len(project_ports), 'ram_share_percent': project_ram_pct}, 'databases': {'count': database_count, 'size_mb': database_size_mb, 'confirmed_rows': database_rows, 'integrity_problems': database_integrity_issues, 'largest': largest_database.get('relative_path')}, 'findings': resource_findings, 'confirmed_hardware_bottlenecks': 0}
json_path = OUTPUT_DIR / 'HARDWARE_RESOURCE_MAP.json'
md_path = OUTPUT_DIR / 'HARDWARE_RESOURCE_REPORT.md'
txt_path = OUTPUT_DIR / 'HARDWARE_RESOURCE_SUMMARY.txt'
json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding='utf-8')
lines = ['# Hardware and Resource Intelligence', '', 'Project: '+PROJECT_NAME, '', '## Hardware', 'CPU: '+str(cpu_list[0].get('Name') if cpu_list else 'UNKNOWN'), 'RAM used: '+str(ram_used_pct)+'%', '', '## Project', 'Processes: '+str(project_process_count), 'Working set: '+str(project_ws_mb)+' MB', 'Private memory: '+str(project_private_mb)+' MB', '', '## Databases', 'Size: '+str(database_size_mb)+' MB', 'Confirmed rows: '+str(database_rows), '', '## Findings']
lines += [f['severity']+' | '+f['confidence']+' | '+f['code']+' | '+f['evidence'] for f in resource_findings]
lines += ['', 'Confirmed hardware bottlenecks: NOT ESTABLISHED']
md_path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
txt_path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
for path in [json_path, md_path, txt_path]: print(('OK' if path.is_file() and path.stat().st_size else 'ERROR'), path.name, path.stat().st_size if path.exists() else 0)
print('ANALYZER 13 V2 TEST COMPLETE')



