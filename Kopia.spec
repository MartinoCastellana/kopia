from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

root = Path(SPECPATH)
hidden = collect_submodules('kopia.gui.tkinter')
analysis = Analysis([str(root / 'main.py')], pathex=[str(root)], binaries=[], datas=[], hiddenimports=['kopia.gui.tkinter', *hidden], hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[])
pyz = PYZ(analysis.pure)
exe = EXE(pyz, analysis.scripts, analysis.binaries, analysis.datas, [], name='Kopia', debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=False)
app = BUNDLE(exe, name='Kopia.app', icon=None, bundle_identifier='com.kopia.app', info_plist={'CFBundleShortVersionString': '0.0.1', 'CFBundleVersion': '0.0.1'})
