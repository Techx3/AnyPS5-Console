import os
import sys
from pathlib import Path

VERSION = "1.1.0"
APP_REPO = "Techx3/AnyPS5-Console"
FROZEN = getattr(sys, "frozen", False)
CODE = Path(__file__).resolve().parent
RES = Path(getattr(sys, "_MEIPASS", CODE))
ASSETS = RES / "assets"

EXE_DIR = Path(sys.executable).resolve().parent if FROZEN else CODE
PORTABLE = FROZEN and (EXE_DIR / "portable.txt").exists()
if FROZEN:
    if PORTABLE:
        DATA = EXE_DIR / "data"
    else:
        DATA = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "AnyPS5Console"
elif CODE.parent.name == "tools":
    DATA = CODE
else:
    DATA = CODE.parent / "data"
DATA.mkdir(parents=True, exist_ok=True)

LEGACY_ROOT = CODE.parent.parent if (CODE.parent.parent / "core" / "relinker").is_dir() else None
TOOLS = DATA / "tools"
MINGW_BIN = TOOLS / "mingw64" / "bin"
GIT_DIR = TOOLS / "git"


def tool_paths():
    dirs = [MINGW_BIN, GIT_DIR / "cmd", GIT_DIR / "mingw64" / "bin"]
    if LEGACY_ROOT:
        dirs.append(LEGACY_ROOT / "tools" / "mingw64" / "bin")
    return [d for d in dirs if d.is_dir()]


def ca_bundle():
    for p in (GIT_DIR / "mingw64" / "etc" / "ssl" / "certs" / "ca-bundle.crt",
              Path(r"C:\Program Files\Git\mingw64\etc\ssl\certs\ca-bundle.crt"),
              Path(r"C:\Program Files\Git\ucrt64\etc\ssl\certs\ca-bundle.crt")):
        if p.is_file():
            return p
    return None


def setup_environment():
    extra = [str(d) for d in tool_paths()]
    if extra:
        os.environ["PATH"] = os.pathsep.join(extra) + os.pathsep + os.environ.get("PATH", "")
    ca = ca_bundle()
    if ca and not os.environ.get("SSL_CERT_FILE"):
        os.environ["SSL_CERT_FILE"] = str(ca)
