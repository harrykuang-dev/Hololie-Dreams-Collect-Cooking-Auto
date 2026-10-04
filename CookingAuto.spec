# Build with the CUDA-capable environment used for gameplay development.
from pathlib import Path
root = Path(SPECPATH)
data = []
for directory in ('outputs/kitchen-bot', 'outputs/kitchen-labeler', 'outputs/kitchen-assets/textures'):
    for file in (root / directory).rglob('*'):
        if file.is_file() and file.suffix in ('.py', '.pt', '.png'):
            data.append((str(file), str(file.parent.relative_to(root))))
a = Analysis(['gui.py'], pathex=[str(root/'outputs/kitchen-bot')],
             binaries=[], datas=data, hiddenimports=[],
             excludes=['matplotlib', 'IPython', 'pytest', 'tensorflow', 'tensorboard',
                       'pandas', 'sympy.testing'],
             hookspath=[], runtime_hooks=[], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True,
          name='Collect-Cooking-Auto-v0.2.0', debug=False, strip=False,
          upx=False, console=False)
collect = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False,
                  name='Collect-Cooking-Auto-v0.2.0')
