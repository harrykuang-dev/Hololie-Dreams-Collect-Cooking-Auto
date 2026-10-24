"""Verify hashes, human labels, image references and frozen split integrity."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def jsonl(path):
    with path.open(encoding='utf8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def validate(root, check_manifest=True):
    from PIL import Image
    root = root.resolve()
    if check_manifest:
        manifest = json.loads((root / 'manifest.json').read_text(encoding='utf8'))
        for entry in manifest['files']:
            path = (root / entry['path']).resolve()
            assert path.is_relative_to(root), entry['path']
            assert path.is_file() and path.stat().st_size == entry['bytes'], entry['path']
            assert sha256(path) == entry['sha256'], entry['path']
    images = jsonl(root / 'image-index.jsonl')
    image_map = {r['path']: r for r in images}
    assert len(images) == len(image_map)
    for row in images:
        path = (root / row['path']).resolve()
        assert path.is_relative_to(root) and path.is_file(), row['path']
        assert sha256(path) == row['sha256'], row['path']
        with Image.open(path) as image:
            assert list(image.size) == [row['width'], row['height']], row['path']
            image.verify()
    rows = jsonl(root / 'classification/samples.jsonl')
    assert len({r['id'] for r in rows}) == len(rows)
    labels = [r['id'] for r in json.loads((root / 'labels.json').read_text(encoding='utf8'))['labels']]
    source_splits = {}; hash_splits = {}; counts = Counter()
    for row in rows:
        assert row['human_annotated'] is True
        for key in ('crop', 'context', 'board'):
            assert row[key] in image_map, (row['id'], key)
        crop = image_map[row['crop']]
        assert crop['width'] == crop['height'] == 64
        assert crop['sha256'] == row['crop_sha256']
        if row['status'] == 'uncertain':
            assert row['label'] == 'uncertain' and row['split'] == 'excluded'
            continue
        assert row['label'] in labels and row['split'] in ('train', 'validation', 'development_test')
        for value, mapping in ((row['source_group'], source_splits), (row['crop_sha256'], hash_splits)):
            assert value not in mapping or mapping[value] == row['split'], ('split leakage', row['id'])
            mapping[value] = row['split']
        counts[row['split']] += 1
    for split in counts:
        expected = json.loads((root / f'classification/splits/{split}.json').read_text(encoding='utf8'))
        actual = [r['id'] for r in rows if r['status'] == 'confirmed' and r['split'] == split]
        assert expected == actual, split
    # Verify every reference in legacy/review records, not only primary crops.
    references = 0
    def walk(value):
        nonlocal references
        if isinstance(value, dict):
            for item in value.values():walk(item)
        elif isinstance(value, list):
            for item in value:walk(item)
        elif isinstance(value, str) and value.startswith('images/'):
            assert value in image_map, value
            references += 1
    for folder in ('legacy', 'segmentation'):
        for path in (root / folder).rglob('*.jsonl'):
            for row in jsonl(path):walk(row)
    stats = json.loads((root / 'statistics.json').read_text(encoding='utf8'))
    assert len(rows) == stats['classification']['total_human_reviewed']
    assert sum(counts.values()) == stats['classification']['confirmed']
    return {'passed': True, 'confirmed': sum(counts.values()), 'uncertain': len(rows)-sum(counts.values()),
            'split_counts': dict(counts), 'unique_images': len(images), 'legacy_image_references': references,
            'image_bytes': sum(r['bytes'] for r in images), 'split_leakage': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--skip-manifest', action='store_true')
    args = parser.parse_args()
    print(json.dumps(validate(args.data, not args.skip_manifest), indent=2))
