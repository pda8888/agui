# -*- mode: python ; coding: utf-8 -*-

import os

# 设置 AGUI_SLIM=1 时不打包 aria2c.exe（运行时按需下载）
SLIM = os.environ.get("AGUI_SLIM", "") == "1"
binaries = [] if SLIM else [('aria2c.exe', '.')]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=[
        ('assets', 'assets')
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'PySide6', 'PySide6_Essentials', 'PySide6_Addons', 'shiboken6',
        'pyqtdarktheme', 'QDarkStyle', 'QtPy', 'pyaria2'
    ],
    noarchive=False,
    optimize=2,          # 优化字节码，减小体积
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='agui',
    debug=False,
    bootloader_ignore_signals=False,
    #strip=True,          # 去除符号表，进一步减小体积
    upx=True,           # 若系统中安装了 UPX，可设为 True 并指定 upx_dir
    upx_exclude=[],
    # runtime_tmpdir=None,
    console=False,
    # console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets\\boat.ico'],
)