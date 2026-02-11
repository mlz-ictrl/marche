# -*- mode: python -*-

from pathlib import Path

rootdir = str(Path('..').resolve())
guidir = f'{rootdir}/marche/gui'

a = Analysis(
    [f'{rootdir}/bin/marche-gui'],
    pathex=[rootdir],
    binaries=[],
    datas=[(f'{guidir}/ui/*.ui', 'marche/gui/ui')],
    hiddenimports=['xmlrpc', 'marche.gui.res'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
)
pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None,
)
exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name='marche-gui',
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='marche-gui',
)
app = BUNDLE(
    coll,
    name='marche-gui.app',
    icon=f'{guidir}/res/logo-new.icns',
    bundle_identifier=None,
    version='.'.join(version.decode('utf-8').split('.')[:3]),
)
