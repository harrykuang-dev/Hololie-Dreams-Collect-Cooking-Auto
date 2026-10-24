"""Export the five trained checkpoints for framework-free inference."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'outputs/kitchen-bot'))


def export(destination):
    import torch
    import onnx
    from torch import nn
    from torchvision import models
    from segmenter import Segmenter, LABELS

    class Probabilities(nn.Module):
        def __init__(self, model, surface):
            super().__init__(); self.model = model; self.surface = surface
        def forward(self, pixels):
            probabilities=self.model(pixels).softmax(1)
            if self.surface:return probabilities,probabilities.argmax(1),probabilities.amax(1)
            return probabilities

    destination.mkdir(parents=True, exist_ok=True)
    checkpoints = {
        'segmenter-adapted': 'outputs/kitchen-bot/segmenter-adapted.pt',
        'segmenter-positive-surfaces': 'outputs/kitchen-bot/segmenter-positive-surfaces.pt',
        'icon-classifier': 'outputs/kitchen-bot/icon-classifier.pt',
        'point-classifier-resnet18': 'outputs/kitchen-labeler/point-classifier-resnet18.pt',
        'point-classifier-resnet101': 'outputs/kitchen-labeler/point-classifier-resnet101.pt',
    }
    for name, relative in checkpoints.items():
        source = ROOT/relative
        checkpoint = torch.load(source, map_location='cpu', weights_only=True)
        segmenter = name.startswith('segmenter-')
        architecture = 'segmenter' if segmenter else checkpoint.get('architecture', 'resnet18')
        labels = LABELS if segmenter else checkpoint['labels']
        model = Segmenter() if segmenter else getattr(models, architecture)(weights=None)
        if not segmenter:model.fc = nn.Linear(model.fc.in_features, len(labels))
        model.load_state_dict(checkpoint['model']); model.eval()
        shape = (1,3,280,448) if segmenter else (1,3,96,96)
        dynamic = {'pixels':{2:'height',3:'width'}, 'probabilities':{2:'height',3:'width'}} if segmenter else {
            'pixels':{0:'batch'}, 'probabilities':{0:'batch'}}
        outputs=['probabilities','labels','confidence'] if segmenter else ['probabilities']
        if segmenter:dynamic.update(labels={1:'height',2:'width'},confidence={1:'height',2:'width'})
        output = destination/(name+'.onnx')
        torch.onnx.export(Probabilities(model,segmenter), torch.zeros(shape), str(output),
                          input_names=['pixels'], output_names=outputs,
                          opset_version=17, dynamic_axes=dynamic, dynamo=False)
        onnx.checker.check_model(str(output))
        metadata = {'format':2,'kind':'segmenter' if segmenter else 'classifier',
                    'architecture':architecture,'labels':labels,'input':checkpoint.get('input',{}),
                    'dataset_sha256':checkpoint.get('dataset_sha256'),
                    'parameters':sum(p.numel() for p in model.parameters()),
                    'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                    'onnx_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
                    'opset':17,'input_name':'pixels','output_name':'probabilities',
                    'outputs':outputs,
                    'preprocessing':'BGR NCHW float32 /255; OpenCV resize',
                    'output':'softmax probabilities'}
        output.with_suffix('.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
        print('Exported '+name, flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'models/inference')
    export(parser.parse_args().output)
