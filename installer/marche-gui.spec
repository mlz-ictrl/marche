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


a = Analysis([binscript],
             pathex=[rootdir],
             binaries=[],
             datas=[(path.join(uidir, '*.ui'), 'marche/gui/ui'),
                    (versionfile, 'marche')],
             hiddenimports=['xmlrpclib', 'sip'],
             hookspath=[],
             runtime_hooks=['rthook_pyqt4.py'],
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
