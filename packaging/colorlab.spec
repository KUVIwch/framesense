# -*- mode: python ; coding: utf-8 -*-
"""Portable Windows preview. Never bundle foreign ICU over the Windows ICU ABI."""
from pathlib import Path
ROOT = Path(SPECPATH).parent
excluded = [
    'PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtWebEngineQuick',
    'PySide6.QtQuick','PySide6.QtQml','PySide6.QtTest','PySide6.QtPdf','PySide6.QtPdfWidgets',
    'tkinter','pytest','IPython','notebook','cv2','pandas','pyarrow','streamlit','openai',
]
a = Analysis([str(ROOT/'framesense'/'app.py')], pathex=[str(ROOT)],
    binaries=[], datas=[(str(ROOT/'framesense'/'assets'),'framesense/assets')],
    hiddenimports=['rawpy'], hookspath=[], runtime_hooks=[], excludes=excluded,
    noarchive=False, optimize=0)
# PyInstaller's dependency resolver can select a foreign Poppler ICU from the
# host PATH. Qt's Windows build needs the OS ICU forwarding ABI. Do not copy
# system files and do not shadow that ABI with ICU's version-suffixed symbols.
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() not in {'icuuc.dll','icudt78.dll'}]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='FrameSenseColorLab',
    debug=False, strip=False, upx=False, console=False,
    icon=str(ROOT/'framesense'/'assets'/'framesense.ico'))
coll = COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='FrameSenseColorLab')
