"""The two selectable, fully trained point classifiers."""
from pathlib import Path

DEFAULT_MODEL = 'resnet18'
MODEL_FILES = {
    'resnet18': 'outputs/kitchen-labeler/point-classifier-resnet18.pt',
    'resnet101': 'outputs/kitchen-labeler/point-classifier-resnet101.pt',
}


def point_model(root, name):
    if name not in MODEL_FILES:
        raise ValueError('Unsupported point model: '+str(name))
    file = Path(root)/MODEL_FILES[name]
    if not file.is_file():
        raise FileNotFoundError('Missing point model: '+str(file))
    return file.resolve()
