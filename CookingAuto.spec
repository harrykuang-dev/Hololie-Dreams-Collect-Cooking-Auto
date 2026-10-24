# One complete runtime: TensorRT, DirectML and CPU; shared FP32 ONNX models.
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_dynamic_libs
root = Path(SPECPATH)
data = []
for directory in ('outputs/kitchen-bot', 'outputs/kitchen-assets/textures', 'assets', 'models/inference'):
    for file in (root / directory).rglob('*'):
        if file.is_file() and file.suffix in ('.py', '.onnx', '.json', '.png'):
            if file.name=='segmenter.py':continue
            data.append((str(file), str(file.parent.relative_to(root))))

binaries = collect_dynamic_libs('tensorrt_libs')+collect_dynamic_libs('onnxruntime')
for path in sys.path:
    cuda = Path(path)/'nvidia/cuda_runtime/bin'
    if cuda.is_dir():
        binaries += [(str(file),'nvidia/cuda_runtime/bin') for file in cuda.glob('*.dll')]
a = Analysis(['gui.py'], pathex=[str(root/'outputs/kitchen-bot')],
             binaries=binaries, datas=data, hiddenimports=['tensorrt_libs','tensorrt_bindings'],
             excludes=['matplotlib', 'IPython', 'pytest', 'tensorflow', 'tensorboard',
                       'pandas', 'sympy.testing', 'torch', 'torchvision', 'onnx', 'onnxscript', 'segmenter'],
             hookspath=[], runtime_hooks=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='Collect-Cooking-Auto-v1.1.0', debug=False, strip=False,
          upx=False, console=False, icon=str(root/'assets/cooking-icon.ico'))
collect = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
                  name='Collect-Cooking-Auto-v1.1.0')
