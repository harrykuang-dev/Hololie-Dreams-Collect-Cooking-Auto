"""Read the published point-classification dataset without SQLite or the game."""
import json
from pathlib import Path


def read_rows(root=None, split=None, include_uncertain=False):
    root = Path(root or Path(__file__).resolve().parent)
    with (root / 'classification/samples.jsonl').open(encoding='utf8') as stream:
        for line in stream:
            row = json.loads(line)
            if not include_uncertain and row['status'] != 'confirmed':
                continue
            if split is None or row['split'] == split:
                yield row


def load_bgr(root, row, augment=None):
    import cv2
    import numpy as np
    image = cv2.imread(str(Path(root) / row['crop']), cv2.IMREAD_COLOR)
    if image is None or image.shape != (64, 64, 3):
        raise ValueError('Invalid crop: ' + row['id'])
    image = cv2.resize(image, (96, 96), interpolation=cv2.INTER_LINEAR)
    if augment is not None:
        if augment.random() < .5:
            image = image[:, ::-1]
        image = np.clip(image.astype('float32') * augment.uniform(.92, 1.08), 0, 255).astype('uint8')
    # Existing cooking weights use BGR /255, without ImageNet RGB normalization.
    return image.transpose(2, 0, 1).copy().astype('float32') / 255
