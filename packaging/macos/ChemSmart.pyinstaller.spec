# -*- mode: python ; coding: utf-8 -*-
"""P1 PyInstaller onedir candidate for the real ChemSmart GUI entry point."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


PROJECT_ROOT = Path(SPECPATH).parents[1]
ENTRY_POINT = PROJECT_ROOT / "chemsmart" / "gui" / "__main__.py"

hiddenimports = collect_submodules(
    "chemsmart",
    filter=lambda name: not name.startswith("chemsmart.agent.tui"),
)
hiddenimports += [
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "anthropic",
    "openai",
    "pymatgen",
    "rdkit",
]

a = Analysis(
    [str(ENTRY_POINT)],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=collect_data_files("chemsmart", include_py_files=False),
    hiddenimports=sorted(set(hiddenimports)),
    hookspath=[],
    hooksconfig={"matplotlib": {"backends": ["Agg"]}},
    runtime_hooks=[],
    excludes=[
        "PyQt5",
        "PyQt6",
        "PySide2",
        "mlx",
        "mlx_lm",
        "torch",
        "transformers",
        "textual",
        "watchdog",
        "pyperclip",
    ],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ChemSmart",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,
    entitlements_file=None,
)
collection = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ChemSmart",
)
app = BUNDLE(
    collection,
    name="ChemSmart.app",
    icon=None,
    bundle_identifier="org.zhanglab.chemsmart",
    info_plist={
        "CFBundleDisplayName": "ChemSmart",
        "CFBundleName": "ChemSmart",
        "LSMinimumSystemVersion": "14.0",
        "NSHighResolutionCapable": True,
    },
)
