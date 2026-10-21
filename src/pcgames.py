import hashlib
import json
import os
import re
from pathlib import Path

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
SKIP_EXE = re.compile(r"unins|setup|crash|redist|vcredist|vc_redist|dxsetup|dxweb|prereq|helper|reporter|update|"
                      r"easyanticheat|eac_|eacore|battleye|cefprocess|notification|uploader|launcherpatcher|"
                      r"dotnet|directx|install|benchmark|config|settings|quicksfv|rapidcrc|md5|sfv|"
                      r"activation|touchup|cleanup|patchprogress|proxy|repair|verify|unitycrash", re.I)
SKIP_DIRS = {"redist", "_redist", "_commonredist", "commonredist", "directx", "support", "installers", "__installer",
             "md5", "core", "engine", "prerequisites", "_installer"}
REPACK = re.compile(r"repack|\[dodi|\[fitgirl|elamigos|kaos|setup", re.I)
SKIP_STEAM = re.compile(r"redistributable|steamworks|steamvr|proton|sdk|dedicated server|soundtrack", re.I)
ART_NAMES = ("cover.png", "cover.jpg", "folder.jpg", "folder.png", "poster.jpg", "poster.png", "icon.png")


class PcGame:
    def __init__(self, name, source, target, path=None, icon=None, background=None, cwd=None):
        self.name, self.source, self.target = name, source, target
        self.path = Path(path) if path else None
        self.icon = Path(icon) if icon else None
        self.background = Path(background) if background else None
        self.cwd = cwd
        self.key = "pc-" + hashlib.sha1(f"{source}|{target}".encode()).hexdigest()[:12]
        self.title_id = {"steam": "Steam", "epic": "Epic Games", "exe": "PC"}[source]
        self.platform = "PC"


def _steam_root():
    if os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
                return Path(winreg.QueryValueEx(k, "SteamPath")[0])
        except OSError:
            pass
        for p in (Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam",
                  Path(r"C:\Program Files\Steam")):
            if p.is_dir():
                return p
        return None
    p = Path.home() / ".steam" / "steam"
    return p if p.is_dir() else None


def _vdf_pairs(text):
    return re.findall(r'"([^"]+)"\s+"([^"]*)"', text)


def _steam_art(root, appid, names):
    cache = root / "appcache" / "librarycache"
    for name in names:
        flat = cache / f"{appid}_{name}"
        if flat.is_file():
            return flat
        folder = cache / str(appid)
        if folder.is_dir():
            hit = next(iter(sorted(folder.rglob(name))), None)
            if hit:
                return hit
    return None


def scan_steam():
    root = _steam_root()
    if not root:
        return []
    libs = {root}
    try:
        text = (root / "steamapps" / "libraryfolders.vdf").read_text("utf-8", errors="replace")
        libs |= {Path(v.replace("\\\\", "\\")) for k, v in _vdf_pairs(text) if k == "path"}
    except OSError:
        pass
    games, seen = [], set()
    for lib in libs:
        for acf in sorted((lib / "steamapps").glob("appmanifest_*.acf")):
            try:
                data = dict(_vdf_pairs(acf.read_text("utf-8", errors="replace")))
            except OSError:
                continue
            appid, name = data.get("appid"), data.get("name", "")
            if not appid or appid in seen or SKIP_STEAM.search(name):
                continue
            seen.add(appid)
            games.append(PcGame(name, "steam", f"steam://rungameid/{appid}",
                                path=lib / "steamapps" / "common" / data.get("installdir", ""),
                                icon=_steam_art(root, appid, ("library_600x900.jpg", "library_capsule.jpg", "header.jpg")),
                                background=_steam_art(root, appid, ("library_hero.jpg",))))
    return games


def scan_epic():
    base = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    games = []
    for item in sorted(base.glob("*.item")) if base.is_dir() else []:
        try:
            data = json.loads(item.read_text("utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        if data.get("bIsIncompleteInstall") or not data.get("DisplayName"):
            continue
        if "UE_" in data.get("AppName", "") or data.get("bIsApplication") is False:
            continue
        uri = ("com.epicgames.launcher://apps/" + "%3A".join(
            [data.get("CatalogNamespace", ""), data.get("CatalogItemId", ""), data.get("AppName", "")]) +
            "?action=launch&silent=true")
        loc = Path(data.get("InstallLocation", ""))
        games.append(PcGame(data["DisplayName"], "epic", uri, path=loc, icon=_folder_art(loc)))
    return games


def _folder_art(folder):
    for name in ART_NAMES:
        p = Path(folder) / name
        if p.is_file():
            return p
    return None


def _best_exe(folder, max_depth=3):
    best = None
    for dirpath, dirnames, filenames in os.walk(folder):
        depth = len(Path(dirpath).relative_to(folder).parts)
        if depth >= max_depth:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if not d.startswith((".", "_")) and d.lower() not in SKIP_DIRS
                       and not REPACK.search(d) and "update" not in d.lower()]
        for f in filenames:
            if not f.lower().endswith(".exe") or SKIP_EXE.search(f):
                continue
            p = Path(dirpath) / f
            try:
                unity = (Path(dirpath) / (p.stem + "_Data")).is_dir()
                score = (0 if unity else 1, depth, -p.stat().st_size)
            except OSError:
                continue
            if best is None or score < best[0]:
                best = (score, p)
    return best[1] if best else None


def scan_folders(folders):
    games = []
    for root in folders:
        root = Path(root)
        if not root.is_dir():
            continue
        try:
            entries = sorted(root.iterdir())
        except OSError:
            continue
        for e in entries:
            if e.is_file() and e.suffix.lower() == ".exe" and not SKIP_EXE.search(e.name):
                games.append(PcGame(e.stem, "exe", str(e), path=e.parent, cwd=str(e.parent)))
            elif e.is_dir():
                exe = _best_exe(e)
                if exe:
                    games.append(PcGame(e.name, "exe", str(exe), path=e, icon=_folder_art(e), cwd=str(exe.parent)))
    return games


def extract_icons(games, cache):
    from peicon import exe_icon
    cache = Path(cache)
    cache.mkdir(parents=True, exist_ok=True)
    for g in games:
        if g.source != "exe":
            continue
        hits = sorted(cache.glob(g.key + ".*"))
        if hits:
            g.icon_small = hits[0]
            continue
        try:
            found = exe_icon(g.target)
        except Exception:
            found = None
        if found:
            out = cache / f"{g.key}.{found[0]}"
            out.write_bytes(found[1])
            g.icon_small = out


def scan_all(conf, icon_cache):
    games = []
    if conf.get("pc_steam", True):
        games += scan_steam()
    if conf.get("pc_epic", True):
        games += scan_epic()
    games += scan_folders(conf.get("pc_dirs", []))
    for exe in conf.get("pc_exes", []):
        p = Path(exe)
        if p.is_file():
            games.append(PcGame(p.stem, "exe", str(p), path=p.parent, icon=_folder_art(p.parent), cwd=str(p.parent)))
    seen, unique = set(), []
    for g in games:
        if g.key not in seen:
            seen.add(g.key)
            unique.append(g)
    unique.sort(key=lambda g: g.name.lower())
    extract_icons(unique, icon_cache)
    return unique
