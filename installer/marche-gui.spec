# -*- mode: python -*-

from pathlib import Path

rootdir = str(Path('..').resolve())
guidir = f'{rootdir}/marche/gui'
binscript = f'{rootdir}/bin/marche-gui'

a = Analysis([binscript],
             pathex=[rootdir],
             binaries=[],
             datas=[(f'{guidir}/ui/*.ui', 'marche/gui/ui')],
             hiddenimports=['xmlrpc', 'sip', 'marche.gui.res'],
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
