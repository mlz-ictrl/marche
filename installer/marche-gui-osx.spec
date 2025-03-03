# -*- mode: python -*-

import subprocess
import sys
from pathlib import Path

rootdir = str(Path('..').resolve())
guidir = f'{rootdir}/marche/gui'
versionfile = f'{rootdir}/marche/RELEASE-VERSION'

# Make sure to generate the version file.
subprocess.check_call([sys.executable, f'{rootdir}/marche/version.py'])

version = (rootdir / 'marche' / 'RELEASE-VERSION').read_text().strip()

a = Analysis([f'{rootdir}/bin/marche-gui'],
             pathex=[rootdir],
             binaries=[],
             datas=[(f'{guidir}/ui/*.ui', 'marche/gui/ui'),
                    (versionfile, 'marche')],
             hiddenimports=['xmlrpc', 'marche.gui.res'],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=None)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='marche-gui',
          debug=False,
          strip=False,
          upx=False,
          console=False)
app = BUNDLE(exe,
             name='marche.app',
             icon=f'{guidir}/res/logo-new.icns',
             bundle_identifier=None,
             version=v)
