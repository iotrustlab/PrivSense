"""Offline publication check. Findings identify locations, never matched secrets."""
import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = {
    'credential': re.compile(
        r'(?:sk-(?:or-v1-)?[A-Za-z0-9_-]{16,}'
        r'|gh[pousr]_[A-Za-z0-9]{20,}'
        r'|github_pat_[A-Za-z0-9_]{20,}'
        r'|AKIA[0-9A-Z]{16}'
        r'|-----BEGIN [A-Z ]*PRIVATE KEY-----)'
    ),
    'machine_path': re.compile(
        r'/(?:home|Users|root|mnt|media|private|tmp|var/folders|opt)/[^\s\"\'<>`,;)]+'
        r'|\b[A-Z]:[\\/][A-Za-z0-9_]'
    ),
}


def findings(text):
    for kind, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            yield kind, text.count('\n', 0, match.start()) + 1


def sensitive_filename(name):
    path = Path(name)
    return (
        (path.name == '.env' or path.name.startswith('.env.'))
        and path.name != '.env.example'
    ) or path.suffix.lower() in {'.pem', '.key', '.p12', '.pfx'} or bool(
        {'secrets', 'credentials'} & set(path.parts)
    )


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def scan_blob(name, data, revision='worktree'):
    found = 0
    if sensitive_filename(name):
        print(f'{revision}:{name}: sensitive filename')
        found += 1
    # Binary artifacts are not decoded as text; inspect them separately before publication.
    if b'\0' in data:
        return found
    for kind, line in findings(data.decode('utf-8', errors='replace')):
        print(f'{revision}:{name}:{line}: {kind}')
        found += 1
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', action='store_true', help='Also inspect all reachable Git blobs')
    args = parser.parse_args()
    count = 0
    names = git('ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0')
    for name in sorted(set(filter(None, names))):
        path = ROOT / name
        if path.is_file():
            count += scan_blob(name, path.read_bytes())
    if args.history:
        for row in git('rev-list', '--objects', '--all').decode().splitlines():
            oid, _, name = row.partition(' ')
            if name and git('cat-file', '-t', oid).strip() == b'blob':
                count += scan_blob(name, git('cat-file', 'blob', oid), oid[:12])
    print(f'Privacy check: {count} finding(s). Matched values are never printed.')
    return bool(count)


if __name__ == '__main__':
    raise SystemExit(main())
