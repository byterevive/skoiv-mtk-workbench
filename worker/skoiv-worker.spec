# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Skoiv worker sidecar.

Build:  uv run pyinstaller skoiv-worker.spec
Output: worker/dist/skoiv-worker(.exe)

The bundle is a headless, one-file console-less process driven by the desktop
shell over stdio. It contains CPython, the Workbench worker package, and
mtkclient (GPLv3 upstream) with its read-only adapter. Qt/PySide6 (mtkclient's
optional GUI), tkinter, and FUSE helpers are excluded.

PyInstaller (bootloader) is GPL-compatible with this project's GPL-3.0-only
license. mtkclient remains GPLv3 upstream; corresponding source for the
distributed bundle is this repository plus the pinned upstream tag.
"""

from PyInstaller.utils.hooks import collect_all, collect_submodules

mtk_datas, mtk_binaries, mtk_hidden = collect_all("mtkclient")
libusb_datas, libusb_binaries, libusb_hidden = collect_all("libusb_package")
usb_hidden = collect_submodules("usb")
skoiv_hidden = collect_submodules("skoiv_worker")
serial_hidden = collect_submodules("serial")
crypto_hidden = collect_submodules("Crypto") + collect_submodules("Cryptodome")

# Drop mtkclient's bundled Windows driver installer and GUI resources; the
# Workbench ships its own documentation and never mounts DA partitions over
# FUSE or launches the upstream GUI.
mtk_datas = [
    (src, dest)
    for (src, dest) in mtk_datas
    if "/gui/" not in src.replace("\\", "/") and "/Windows/" not in src.replace("\\", "/")
]

a = Analysis(
    ["skoiv_worker_entry.py"],
    pathex=["src"],
    binaries=mtk_binaries + libusb_binaries,
    datas=mtk_datas + libusb_datas,
    hiddenimports=sorted(
        set(
            mtk_hidden
            + libusb_hidden
            + usb_hidden
            + serial_hidden
            + crypto_hidden
            + skoiv_hidden
        )
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6",
        "PySide6.QtCore",
        "shiboken6",
        "PyQt5",
        "PyQt6",
        "tkinter",
        "unittest",
        "pydoc",
        "IPython",
        "matplotlib",
        "numpy",
        "pandas",
        "PIL",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="skoiv-worker",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    # Windowed: the desktop shell owns the lifecycle and stdio pipes. Avoid
    # flashing a console window for the sidecar on Windows.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
