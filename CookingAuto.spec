# Build with the CUDA-capable environment used for gameplay development.
from pathlib import Path
root = Path(SPECPATH)
data = []
for directory in ('outputs/kitchen-bot', 'outputs/kitchen-labeler', 'outputs/kitchen-assets/textures', 'assets'):
    for file in (root / directory).rglob('*'):
        if file.is_file() and file.suffix in ('.py', '.pt', '.png'):
            if file.suffix=='.pt' and file.name not in {'point-classifier-resnet18.pt','point-classifier-resnet101.pt','icon-classifier.pt','segmenter-adapted.pt','segmenter-positive-surfaces.pt'}:continue
            data.append((str(file), str(file.parent.relative_to(root))))
a = Analysis(['gui.py'], pathex=[str(root/'outputs/kitchen-bot')],
             binaries=[], datas=data, hiddenimports=[],
             excludes=['matplotlib', 'IPython', 'pytest', 'tensorflow', 'tensorboard',
                       'pandas', 'sympy.testing'],
             hookspath=[], runtime_hooks=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='Collect-Cooking-Auto-v1.0.1', debug=False, strip=False,
          upx=False, console=False, icon=str(root/'assets/cooking-icon.ico'))
collect = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
                  name='Collect-Cooking-Auto-v1.0.1')
