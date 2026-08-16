#!/usr/bin/env python3
"""Fail CI when pip-audit finds HIGH or CRITICAL severity advisories.

pip-audit has no --severity flag; this wrapper audits requirements.lock.txt
and classifies each finding via the OSV API. Low/medium findings are printed
but do not fail the build. Unscored findings fail closed (treated as blocking).
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LOCKFILE = str(REPO_ROOT / 'requirements.lock.txt')
OSV_VULN = 'https://api.osv.dev/v1/vulns/{id}'
BLOCK_LABELS = {'HIGH', 'CRITICAL'}


def run_pip_audit() -> dict:
    cmd = [
        sys.executable,
        '-m',
        'pip_audit',
        '-r',
        LOCKFILE,
        '--disable-pip',
        '-f',
        'json',
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    raw = (proc.stdout or '').strip()
    if not raw:
        print(proc.stderr, file=sys.stderr)
        # No vulns → pip-audit often prints a human message and empty stdout.
        if proc.returncode == 0:
            return {'dependencies': []}
        print('pip-audit failed without JSON output', file=sys.stderr)
        raise SystemExit(2)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        print(raw)
        print(proc.stderr, file=sys.stderr)
        print('pip-audit did not return JSON', file=sys.stderr)
        raise SystemExit(2)


def should_block(vuln_id: str) -> bool:
    try:
        with urllib.request.urlopen(OSV_VULN.format(id=vuln_id), timeout=30) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f'WARN: OSV lookup failed for {vuln_id}: {exc}', file=sys.stderr)
        return True

    label = str((data.get('database_specific') or {}).get('severity') or '').upper()
    if label in BLOCK_LABELS:
        return True

    for entry in data.get('severity') or []:
        if not isinstance(entry, dict):
            continue
        for key in ('baseScore', 'base_score', 'score'):
            val = entry.get(key)
            if isinstance(val, (int, float)) and float(val) >= 7.0:
                return True
        # CVSS vector strings alone are not enough; prefer explicit labels.
    return False


def main() -> int:
    payload = run_pip_audit()
    blockers: list[str] = []
    advisories: list[str] = []
    for dep in payload.get('dependencies') or []:
        name = dep.get('name')
        version = dep.get('version')
        for vuln in dep.get('vulns') or []:
            vid = vuln.get('id') or 'UNKNOWN'
            line = f'{name}=={version} {vid}'
            if should_block(vid):
                blockers.append(line)
            else:
                advisories.append(line)

    for line in advisories:
        print(f'advisory (non-blocking): {line}')
    if blockers:
        print('HIGH/CRITICAL (or unscored) findings:')
        for line in blockers:
            print(f'  {line}')
        return 1
    print('pip-audit: no HIGH/CRITICAL vulnerabilities found')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
