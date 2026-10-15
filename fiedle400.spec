# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_dynamic_libs

block_cipher = None

# `import hid` lives inside a function (hid_driver._get_hid_module), and the
# package ships a compiled extension plus its hidapi DLL. Name it explicitly and
# collect its binaries, or the frozen build imports the module but cannot call
# into it -- which surfaces as "no device found" on a machine where the device
# is plainly attached.
hid_binaries = collect_dynamic_libs('hid')

a = Analysis(
    ['fiedle400/cli.py'],
    pathex=[],
    binaries=hid_binaries,
    datas=[],
    hiddenimports=['fiedle400', 'fiedle400.protocol', 'fiedle400.engine', 'fiedle400.serial_engine', 'fiedle400.hid_driver', 'fiedle400.export', 'hid'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],  # matplotlib bundled (psytrap, 2026-10-15): +~35MB measured, accepted -- see RELEASE_PLAN.md B1b
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='fiedle400',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
