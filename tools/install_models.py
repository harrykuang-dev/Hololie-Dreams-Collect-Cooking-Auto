"""Install only the release's verified checkpoint allowlist. No game access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {'models/inference/'+name+extension
           for name in ('icon-classifier','segmenter-adapted','segmenter-positive-surfaces',
                        'point-classifier-resnet18','point-classifier-resnet101')
           for extension in ('.onnx','.json')}


def sha256(stream):
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(chunk)
    return h.hexdigest()


def install(archive, verify_only=False):
    manifest = json.loads((ROOT / 'models-manifest.json').read_text(encoding='utf-8'))
    assert set(manifest['files']) == ALLOWED, 'Unexpected manifest paths'
    with archive.open('rb') as stream:
        if manifest.get('archive_sha256') and sha256(stream) != manifest['archive_sha256']:
            raise ValueError('Archive SHA-256 mismatch')
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        if len(entries) != len(ALLOWED) or {e.filename for e in entries} != ALLOWED:
            raise ValueError('Unexpected or duplicate archive entries')
        # Verify every checkpoint and existing destination before any mutation.
        for name, expected in manifest['files'].items():
            destination = (ROOT / name).resolve()
            if not destination.is_relative_to(ROOT):
                raise ValueError('Destination left repository')
            if z.getinfo(name).file_size != expected['bytes']:
                raise ValueError('Checkpoint size mismatch: ' + name)
            with z.open(name) as stream:
                if sha256(stream) != expected['sha256']:
                    raise ValueError('Checkpoint SHA-256 mismatch: ' + name)
            if destination.exists() and not verify_only:
                with destination.open('rb') as stream:
                    if sha256(stream) != expected['sha256']:
                        raise ValueError('Existing checkpoint differs; move it aside first: ' + name)
        if not verify_only:
            for name in manifest['files']:
                destination = (ROOT / name).resolve()
                if destination.exists():
                    continue
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_suffix(destination.suffix+'.download')
                with z.open(name) as source, temporary.open('wb') as target:
                    shutil.copyfileobj(source, target)
                    target.flush()
                    os.fsync(target.fileno())
                os.replace(temporary, destination)
    print(('Verified' if verify_only else 'Installed') + f" {len(ALLOWED)} inference files for {manifest['runtime_version']}.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    install(args.archive, args.verify_only)
