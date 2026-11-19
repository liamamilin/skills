"""Small, explicit local media helpers; no downloads, scheduling or account access."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


def binary(name, explicit=None):
    candidate = explicit or os.environ.get(name.upper() + '_BIN') or shutil.which(name)
    if not candidate or not Path(candidate).is_file() or not os.access(candidate, os.X_OK):
        raise ValueError(f'Provide --{name} or {name.upper()}_BIN pointing to an executable.')
    return str(Path(candidate).resolve())


def run(args):
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError(f'{Path(args[0]).name} failed: {result.stderr[-1500:]}')
    return result.stdout


def probe(path, ffprobe):
    return json.loads(run([ffprobe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)]))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
