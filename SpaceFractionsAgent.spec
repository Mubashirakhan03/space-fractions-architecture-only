# PyInstaller spec — build with:  python -m PyInstaller --noconfirm --clean SpaceFractionsAgent.spec
# One-file, windowed exe. Bundles: our app, customtkinter assets, openai SDK, pytest (to run the generated
# tests), the stdlib modules the generated game may use (app/bundled.py), samples and the JSON schema.
import sys
from pathlib import Path

import pytest
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

sys.path.insert(0, str(Path(SPECPATH)))
from sfagent.bundled import BUNDLED_STDLIB  # noqa: E402

hiddenimports = (
    BUNDLED_STDLIB
    + pytest.freeze_includes()
    + collect_submodules("sfagent")
    + ["pytest", "pluggy", "iniconfig", "packaging", "jsonschema", "yaml", "dotenv"]
)
datas = (
    collect_data_files("customtkinter")
    + collect_data_files("jsonschema_specifications")
    + [("samples", "samples"), ("schemas/spec.schema.json", "schemas"), ("assets/icon.png", "assets"), ("assets/icon.ico", "assets")]
)

a = Analysis(
    ["run_agent.py"],
    pathex=[SPECPATH],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["matplotlib", "numpy", "pandas", "PIL", "IPython"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="SpaceFractionsArchOnly",
    icon="assets/icon.ico",
    console=False,
    upx=False,
    runtime_tmpdir=None,
)
