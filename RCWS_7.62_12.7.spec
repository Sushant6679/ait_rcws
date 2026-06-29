# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['Main.py'],
    pathex=[],
    binaries=[],
    datas=[('rangetable.csv', '.'), ('rangetableNSVT.csv', '.'), ('config.ini', '.'), ('default.ini', '.'), ('pre_registered_targets.json', '.'), ('assets', 'assets'), ('api', 'api'), ('utils', 'utils'), ('qt_utils', 'qt_utils'), ('TinyFrame.dll', '.'), ('TinyFrame.so', '.'), ('tinyframe_python.dll', '.')],
    hiddenimports=['win32gui', 'win32api', 'win32ui', 'win32con', 'requests', 'numba', 'pygame', 'PyQt5.QtWidgets', 'numpy', 'cv2', 'vlc', 'pandas', 'configparser_crypt', 'pydash', 'ctypes', 'threading', 'json', 'hashlib', 'math', 'serial', 'serial.tools.list_ports', 'tinyframe', 'utils.tinyframe'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='RCWS_7.62_12.7',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\logo.png'],
)
