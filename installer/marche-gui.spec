# -*- mode: python -*-

import subprocess
import sys
from pathlib import Path

rootdir = str(Path('..').resolve())
guidir = f'{rootdir}/marche/gui'
versionfile = f'{rootdir}/marche/RELEASE-VERSION'
binscript = f'{rootdir}/bin/marche-gui'

# Make sure to generate the version file.
subprocess.check_call([sys.executable, f'{rootdir}/marche/version.py'])


a = Analysis([binscript],
             pathex=[rootdir],
             binaries=[],
             datas=[(f'{guidir}/ui/*.ui', 'marche/gui/ui'),
                    (versionfile, 'marche')],
             hiddenimports=['xmlrpclib', 'sip', 'marche.gui.res'],
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
          upx=True,
          console=False)
