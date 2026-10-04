"""Verify the published runtime and model hashes; never sends game input."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BOT = ROOT / 'outputs/kitchen-bot'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    tested = json.loads((ROOT / 'docs/packaged-runtime.json').read_text(encoding='utf-8'))
    actual = {}
    for name, expected in tested['files'].items():
        path = BOT / name
        if not path.is_file():
            raise SystemExit('Missing runtime/model file: ' + name + '. Install models.zip first.')
        actual[name] = digest(path)
        if actual[name] != expected:
            raise SystemExit('Runtime/model fingerprint differs: ' + name)
    version = hashlib.sha256(json.dumps(actual, sort_keys=True).encode()).hexdigest()[:16]
    if version != tested['version']:
        raise SystemExit('Runtime version mismatch')
    models = json.loads((ROOT / 'models-manifest.json').read_text(encoding='utf-8'))
    for name, expected in models['files'].items():
        path = ROOT / name
        if not path.is_file() or path.stat().st_size != expected['bytes'] or digest(path) != expected['sha256']:
            raise SystemExit('Checkpoint fingerprint differs: ' + name)
    print(f"PASS: runtime {version}; all {len(actual)} published fingerprints and {len(models['files'])} model files match.")


if __name__ == '__main__':
    main()
