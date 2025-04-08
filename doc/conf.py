# marche documentation build configuration file

import sys
from pathlib import Path

sys.path.insert(0, str(Path('..').absolute()))

import marche

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.coverage',
    'sphinx.ext.viewcode',
]
exclude_patterns = ['_build']
master_doc = 'index'

project = 'Marche'
copyright = '2015-2025, Georg Brandl, Alexander Lenz'
author = 'Georg Brandl, Alexander Lenz'
version = marche.__version__
release = version
pygments_style = 'sphinx'

todo_include_todos = False

html_theme = 'alabaster'
html_theme_options = {
    'logo': 'logo.svg',
    'logo_name': True,
    'font_family': 'Open Sans, DejaVu Sans, sans-serif',
    'head_font_family': 'Georgia, serif',
}
html_static_path = ['_static']

htmlhelp_basename = 'marchedoc'

latex_elements = {}
latex_documents = [
  (master_doc, 'marche.tex', 'marche Documentation',
   'Georg Brandl, Alexander Lenz', 'manual'),
]

man_pages = [
    (master_doc, 'marche', 'marche Documentation',
     [author], 1)
]
