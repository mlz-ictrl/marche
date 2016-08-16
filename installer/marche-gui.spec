# -*- mode: python -*-

import sys
import os.path

rootdir = os.path.abspath('..')
binscript = os.path.join(rootdir, 'bin', 'marche-gui')
versionfile = os.path.join(rootdir, 'marche', 'RELEASE-VERSION')
uidir = os.path.join(rootdir, 'marche', 'gui', 'ui')

sys.path.insert(0, rootdir)
from marche.version import get_version
get_version()


block_cipher = None


a = Analysis([binscript],
             pathex=[rootdir],
             binaries=[],
             datas=[(os.path.join(uidir, '*.ui'), 'marche/gui/ui'),
	     (versionfile, 'marche')],
             hiddenimports=['xmlrpclib', 'sip'],
             hookspath=[],
             runtime_hooks=['rthook_pyqt4.py'],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='marche-gui',
          debug=False,
          strip=False,
          upx=True,
          console=False )
