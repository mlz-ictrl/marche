# -*- mode: python -*-

import sys
import subprocess
from os import path

rootdir = path.abspath('..')
binscript = path.join(rootdir, 'bin', 'marche-gui')
versionfile = path.join(rootdir, 'marche', 'RELEASE-VERSION')
uidir = path.join(rootdir, 'marche', 'gui', 'ui')

# Make sure to generate the version file.
subprocess.check_call([sys.executable,
                       path.join(rootdir, 'marche', 'version.py')])

with open(versionfile, 'r', encoding='utf-8') as f:
    v = ''.join(f.readlines()).strip()

a = Analysis([binscript],
             pathex=[rootdir],
             binaries=[],
             datas=[(path.join(uidir, '*.ui'), 'marche/gui/ui'),
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
             icon='../marche/gui/res/logo-new.icns',
             bundle_identifier=None,
             version=v)
