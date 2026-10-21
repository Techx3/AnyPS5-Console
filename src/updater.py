import re
import json
import shutil
import subprocess
import urllib.request
import zipfile

import procs
from pathlib import Path

REPO = "boykopovar/AnyPS5"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
NO_WINDOW = 0x08000000 if shutil.os.name == "nt" else 0


def _git(root, *args, check=True, timeout=120):
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                       errors="replace", timeout=timeout, creationflags=NO_WINDOW)
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {(p.stderr or p.stdout).strip()}")
    return p


def repo_check(root, upstream="https://github.com/boykopovar/AnyPS5.git"):
    if not (Path(root) / ".git").exists():
        sha = _remote_head(upstream, "main")
        return {"remote": sha[:9], "local": "-", "update": True}
    remote = _git(root, "ls-remote", upstream, "refs/heads/main").stdout.split()
    if not remote:
        raise RuntimeError("No se pudo leer main de " + upstream)
    sha = remote[0]
    head = _git(root, "rev-parse", "HEAD").stdout.strip()
    has = _git(root, "cat-file", "-e", sha + "^{commit}", check=False).returncode == 0
    merged = has and _git(root, "merge-base", "--is-ancestor", sha, "HEAD", check=False).returncode == 0
    return {"remote": sha[:9], "local": head[:9], "update": not merged}


def repo_update(root, upstream, log):
    root = Path(root)
    if not (root / ".git").exists():
        root.parent.mkdir(parents=True, exist_ok=True)
        log(f"Clonando {upstream}...")
        p = subprocess.run(["git", "clone", upstream, str(root)], capture_output=True, text=True, errors="replace",
                           timeout=3600, creationflags=NO_WINDOW)
        if p.returncode != 0:
            raise RuntimeError("git clone: " + (p.stderr or p.stdout).strip()[-500:])
        return
    merge_from(root, upstream, "main", log)


def merge_from(root, url, branch, log):
    """Fetch url/branch and merge it into the current branch, keeping local commits; aborts on conflict."""
    root = Path(root)
    log(f"Descargando cambios de {url} ({branch or 'HEAD'})...")
    _git(root, "fetch", url, branch or "HEAD", timeout=1800)
    behind = _git(root, "rev-list", "--count", "HEAD..FETCH_HEAD").stdout.strip()
    if behind == "0":
        log("Ya estaba al día.")
        return
    log(f"{behind} commits nuevos. Fusionando...")
    p = _git(root, "-c", "user.name=AnyPS5 Console", "-c", "user.email=anyps5-console@local",
             "merge", "--no-edit", "FETCH_HEAD", check=False, timeout=600)
    if p.returncode != 0:
        _git(root, "merge", "--abort", check=False)
        raise RuntimeError("Conflicto al fusionar; se deshizo. Hay que resolverlo a mano.\n"
                           + (p.stdout + p.stderr).strip()[-600:])
    log("Fusión lista.")


def release_check(base):
    req = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "AnyPS5-Console"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    tag = data["tag_name"]
    assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
    cur = release_current(base)
    return {"remote": tag, "local": cur["tag"] if cur else "-", "update": not cur or cur["tag"] != tag,
            "assets": assets}


def release_current(base):
    try:
        info = json.loads((base / "current.json").read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if Path(info.get("relinker", "")).is_file() and Path(info.get("libs", "")).is_dir():
        return info
    return None


def _download(url, dst, log):
    req = urllib.request.Request(url, headers={"User-Agent": "AnyPS5-Console"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done, last = 0, -10
        while True:
            procs.check_cancel()
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            pct = done * 100 // total if total else 0
            if pct >= last + 10:
                last = pct
                log(f"{dst.name}: {pct}% ({done >> 20} MiB)")


def release_update(base, check, log):
    tag = check["remote"]
    assets = check["assets"]
    rel_name = next((n for n in assets if n.startswith("relinker-") and n.endswith(".exe")), None)
    zip_name = next((n for n in assets if n.startswith("prx-windows-") and n.endswith(".zip")), None)
    if not rel_name or not zip_name:
        raise RuntimeError(f"La release {tag} no trae relinker .exe o prx-windows .zip")
    out = base / tag
    tmp = base / (tag + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    _download(assets[rel_name], tmp / "relinker.exe", log)
    _download(assets[zip_name], tmp / zip_name, log)
    log("Extrayendo librerias...")
    with zipfile.ZipFile(tmp / zip_name) as z:
        z.extractall(tmp / "prx")
    (tmp / zip_name).unlink()
    prx = next((p.parent for p in sorted((tmp / "prx").rglob("*.prx"))), None)
    if prx is None:
        raise RuntimeError("El zip no contiene .prx")
    if out.exists():
        shutil.rmtree(out)
    tmp.rename(out)
    libs = out / prx.relative_to(tmp)
    tools = out / "tools"
    tools.mkdir(exist_ok=True)
    for name in ("import_audit.py", "nid_names.py", "progress.py"):
        try:
            _download(f"https://raw.githubusercontent.com/{REPO}/{tag}/tools/{name}", tools / name, lambda _m: None)
        except Exception:
            pass
    info = {"tag": tag, "relinker": str(out / "relinker.exe"), "libs": str(libs), "tools": str(tools)}
    (base / "current.json").write_text(json.dumps(info, indent=2), "utf-8")
    log(f"Versión estable {tag} instalada.")
    return info


def parse_fork(text):
    text = text.strip()
    branch = ""
    if "#" in text:
        text, branch = text.split("#", 1)
    if "/tree/" in text:
        text, branch = text.split("/tree/", 1)
    text = text.rstrip("/")
    if text.endswith(".git"):
        text = text[:-4]
    if not (text.startswith("https://") or text.startswith("http://") or text.startswith("git@")):
        if text.count("/") == 1:
            text = "https://github.com/" + text
        else:
            raise RuntimeError("Enlace no valido. Ejemplo: https://github.com/usuario/AnyPS5")
    parts = text.replace(":", "/").split("/")
    owner, repo = parts[-2], parts[-1]
    if not owner or not repo:
        raise RuntimeError("Enlace no valido")
    name = f"{owner}-{repo}" + (f"-{branch.replace('/', '_')}" if branch else "")
    return {"name": name, "url": text + ".git" if text.startswith("http") else text, "branch": branch.strip()}


def repo_info(root):
    """origin URL and current branch of a local clone."""
    origin = _git(root, "remote", "get-url", "origin", check=False, timeout=20).stdout.strip()
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD", check=False, timeout=20).stdout.strip()
    return origin, ("" if branch == "HEAD" else branch)


def is_upstream(url):
    u = url.lower().rstrip("/")
    u = u[:-4] if u.endswith(".git") else u
    return u.endswith("github.com/boykopovar/anyps5") or u.endswith("github.com:boykopovar/anyps5")


def adopt_release(base, folder):
    """Use a release the user already unpacked (relinker*.exe + prx libraries) as the installed stable version."""
    folder = Path(folder).resolve()
    relinker = next(iter(sorted(folder.rglob("relinker*.exe"))), None) or next(iter(sorted(folder.rglob("relinker"))), None)
    prx = next(iter(sorted(folder.rglob("*.prx"))), None)
    if not relinker or not prx:
        raise RuntimeError("En esa carpeta no hay relinker .exe y librerías .prx de una release de AnyPS5.")
    m = re.search(r"v\d+\.\d+\.\d+", " ".join([relinker.name, folder.name, str(prx.parent)]))
    info = {"tag": m.group(0) if m else "local", "relinker": str(relinker), "libs": str(prx.parent), "own": True}
    tools = folder / "tools"
    if (tools / "import_audit.py").is_file():
        info["tools"] = str(tools)
    Path(base).mkdir(parents=True, exist_ok=True)
    (Path(base) / "current.json").write_text(json.dumps(info, indent=2), "utf-8")
    return info


def _remote_head(url, branch):
    ref = f"refs/heads/{branch}" if branch else "HEAD"
    p = subprocess.run(["git", "ls-remote", url, ref], capture_output=True, text=True, errors="replace",
                       timeout=60, creationflags=NO_WINDOW)
    if p.returncode != 0 or not p.stdout.split():
        raise RuntimeError(f"No se pudo leer {url} {branch}".strip())
    return p.stdout.split()[0]


def fork_check(path, fork):
    remote = _remote_head(fork["url"], fork["branch"])
    if fork.get("own") and (Path(path) / ".git").exists():
        head = _git(path, "rev-parse", "HEAD").stdout.strip()
        has = _git(path, "cat-file", "-e", remote + "^{commit}", check=False).returncode == 0
        merged = has and _git(path, "merge-base", "--is-ancestor", remote, "HEAD", check=False).returncode == 0
        return {"remote": remote[:9], "local": head[:9], "update": not merged}
    if not (Path(path) / ".git").exists():
        return {"remote": remote[:9], "local": "-", "update": True}
    head = _git(path, "rev-parse", "HEAD").stdout.strip()
    return {"remote": remote[:9], "local": head[:9], "update": head != remote}


def fork_sync(path, fork, log):
    path = Path(path)
    if fork.get("own"):
        if not (path / ".git").exists():
            raise RuntimeError(f"No se encontró el repositorio en {path}")
        merge_from(path, fork["url"], fork["branch"], log)
        return
    if not (path / ".git").exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        log(f"Clonando {fork['url']}...")
        args = ["git", "clone", "--depth", "1"] + (["--branch", fork["branch"]] if fork["branch"] else []) + [fork["url"], str(path)]
        p = subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=1800, creationflags=NO_WINDOW)
        if p.returncode != 0:
            raise RuntimeError("git clone: " + (p.stderr or p.stdout).strip()[-500:])
    else:
        log("Descargando cambios del fork...")
        ref = fork["branch"] or "HEAD"
        _git(path, "fetch", "--depth", "1", "origin", ref, timeout=1800)
        _git(path, "reset", "--hard", "FETCH_HEAD", timeout=600)
    log("Fork al dia: " + _git(path, "log", "--oneline", "-1").stdout.strip())


WINLIBS_URL = ("https://github.com/brechtsanders/winlibs_mingw/releases/download/15.2.0posix-14.0.0-ucrt-r7/"
               "winlibs-x86_64-posix-seh-gcc-15.2.0-mingw-w64ucrt-14.0.0-r7.zip")
MINGIT_API = "https://api.github.com/repos/git-for-windows/git/releases/latest"


def tools_status(tools_dir):
    tools_dir = Path(tools_dir)
    have_git = shutil.which("git") is not None
    mingw = tools_dir / "mingw64" / "bin"
    have_mingw = all((mingw / n).is_file() for n in ("gcc.exe", "g++.exe", "cmake.exe", "ninja.exe")) or all(
        shutil.which(n) for n in ("gcc", "g++", "cmake", "ninja"))
    return {"git": have_git, "mingw": have_mingw}


def install_tools(tools_dir, log):
    tools_dir = Path(tools_dir)
    tools_dir.mkdir(parents=True, exist_ok=True)
    status = tools_status(tools_dir)
    if not status["git"]:
        req = urllib.request.Request(MINGIT_API, headers={"User-Agent": "AnyPS5-Console"})
        with urllib.request.urlopen(req, timeout=30) as r:
            assets = json.load(r).get("assets", [])
        asset = next((a for a in assets if a["name"].startswith("MinGit-") and a["name"].endswith("-64-bit.zip")
                      and "busybox" not in a["name"]), None)
        if asset is None:
            raise RuntimeError("MinGit not found in the latest Git for Windows release")
        zpath = tools_dir / asset["name"]
        _download(asset["browser_download_url"], zpath, log)
        log("Git...")
        with zipfile.ZipFile(zpath) as z:
            z.extractall(tools_dir / "git")
        zpath.unlink()
    if not status["mingw"]:
        zpath = tools_dir / "winlibs.zip"
        _download(WINLIBS_URL, zpath, log)
        log("MinGW-w64 GCC 15.2.0...")
        with zipfile.ZipFile(zpath) as z:
            z.extractall(tools_dir)
        zpath.unlink()
    return tools_status(tools_dir)


def _version_tuple(v):
    parts = []
    for x in v.lstrip("v").split("-")[0].split("."):
        try:
            parts.append(int(x))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def app_check(repo, current):
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/latest",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "AnyPS5-Console"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    tag = data["tag_name"]
    assets = {a["name"]: a["browser_download_url"] for a in data.get("assets", [])}
    return {"remote": tag, "local": "v" + current.lstrip("v"),
            "update": _version_tuple(tag) > _version_tuple(current), "assets": assets}


def app_update(check, data_dir, exe_dir, portable, log):
    import os
    import tempfile
    tag = check["remote"]
    work = Path(tempfile.mkdtemp(prefix="anyps5console-"))
    if portable:
        name = next((n for n in check["assets"] if n.endswith("-portable.zip")), None)
        if not name:
            raise RuntimeError(f"{tag}: portable zip not found")
        zpath = work / name
        _download(check["assets"][name], zpath, log)
        with zipfile.ZipFile(zpath) as z:
            z.extractall(work / "new")
        src = next((p.parent for p in (work / "new").rglob("AnyPS5Console.exe")), None)
        if src is None:
            raise RuntimeError("AnyPS5Console.exe not found in the zip")
        script = work / "update.cmd"
        script.write_text(
            "@echo off\r\n"
            f"set PID={os.getpid()}\r\n"
            ":wait\r\n"
            "tasklist /FI \"PID eq %PID%\" | find \"%PID%\" >nul && (timeout /t 1 >nul & goto wait)\r\n"
            f"robocopy \"{src}\" \"{exe_dir}\" /E /XD data /NFL /NDL /NJH /NJS >nul\r\n"
            f"start \"\" \"{Path(exe_dir) / 'AnyPS5Console.exe'}\"\r\n", "utf-8")
        subprocess.Popen(["cmd", "/c", str(script)], creationflags=NO_WINDOW | 0x00000008)
    else:
        name = next((n for n in check["assets"] if n.lower().startswith("anyps5console-setup") and n.endswith(".exe")), None)
        if not name:
            raise RuntimeError(f"{tag}: installer not found")
        exe = work / name
        _download(check["assets"][name], exe, log)
        script = work / "update.cmd"
        script.write_text(
            "@echo off\r\n"
            f"set PID={os.getpid()}\r\n"
            ":wait\r\n"
            "tasklist /FI \"PID eq %PID%\" | find \"%PID%\" >nul && (timeout /t 1 >nul & goto wait)\r\n"
            f"\"{exe}\" /SILENT /SUPPRESSMSGBOXES /NORESTART /CLOSEAPPLICATIONS\r\n", "utf-8")
        subprocess.Popen(["cmd", "/c", str(script)], creationflags=NO_WINDOW | 0x00000008)
    return True
