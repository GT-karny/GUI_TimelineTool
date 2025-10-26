# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build specification for the TimelineTool GUI application."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


def _project_root() -> Path:
    """Return the repository root independent of how the spec is executed."""

    if "__file__" in globals():
        return Path(__file__).resolve().parent.parent

    # PyInstaller>=6 executes the spec via ``exec`` without defining ``__file__``.
    # ``SPEC`` holds the path to the spec file in this context.
    spec_path = globals().get("SPEC") or globals().get("spec")
    if spec_path:
        return Path(spec_path).resolve().parent.parent

    return Path.cwd()


PROJECT_ROOT = _project_root()

block_cipher = None

hiddenimports = sorted(set(
    collect_submodules("pyqtgraph")
    + [
        "PySide6.QtPrintSupport",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "PySide6.QtOpenGLWidgets",
    ]
))

analysis = Analysis(
    [str(PROJECT_ROOT / 'app' / 'app.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(analysis.pure, analysis.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name='TimelineTool',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    analysis.binaries,
    analysis.zipfiles,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='TimelineTool',
)
