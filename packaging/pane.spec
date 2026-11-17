# PyInstaller recipe for Pane.exe. Build with packaging\build.ps1.
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent
SHIMS = ROOT / "handset" / "_shims"

# collect_all imports packages in a subprocess; pyimg4 needs the lzss shim.
sys.path.insert(0, str(SHIMS))
os.environ["PYTHONPATH"] = os.pathsep.join(filter(None, [str(SHIMS), os.environ.get("PYTHONPATH")]))

datas = [(str(ROOT / "handset" / "web"), "handset/web")]
_bin_dir = ROOT / "handset" / "bin"
if _bin_dir.is_dir():
    datas.append((str(_bin_dir), "handset/bin"))
binaries = []
hiddenimports = [
    "lzfse",
    "lzss",
    "handset.server",
    "handset.screen",
    "handset.wifi",
    "handset.window",
    "handset.airplay",
    "psutil",
]

# pymobiledevice3 imports most services lazily and ships viewer assets,
# certificates and native helpers, so these are bundled whole.
for package in (
    "pymobiledevice3",
    "pmd_pytcp",
    "pytun_pmd3",
    "qh3",
    "pyimg4",
    "ipsw_parser",
    "developer_disk_image",
    "opack2",
    "bpylist2",
    "construct",
    "srptools",
    "ifaddr",
):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

a = Analysis(
    [str(ROOT / "packaging" / "pane_main.py")],
    pathex=[str(ROOT), str(SHIMS)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Pane",
    icon=str(ROOT / "packaging" / "pane.ico"),
    console=False,
    upx=False,
    version=str(ROOT / "packaging" / "version.txt"),
)
