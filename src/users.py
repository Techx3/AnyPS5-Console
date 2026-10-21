import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

PALETTE = [(79, 195, 217), (232, 120, 96), (126, 200, 120), (190, 130, 230), (240, 196, 90), (90, 140, 240),
           (230, 110, 170), (110, 210, 200)]
NO_WINDOW = 0x08000000 if os.name == "nt" else 0


class Users:
    def __init__(self, base):
        self.base = Path(base)
        self.path = self.base / "users.json"
        self.items = []
        self.last = ""
        try:
            data = json.loads(self.path.read_text("utf-8"))
            self.items = data.get("users", [])
            self.last = data.get("last", "")
        except (OSError, ValueError):
            pass

    def save(self):
        self.base.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"users": self.items, "last": self.last}, indent=2, ensure_ascii=False), "utf-8")

    def create(self, name):
        name = name.strip()[:16] or "Jugador"
        user = {"id": uuid.uuid4().hex[:8], "name": name, "color": PALETTE[len(self.items) % len(PALETTE)],
                "created": int(time.time())}
        self.items.append(user)
        self.save()
        return user

    def remove(self, uid):
        self.items = [u for u in self.items if u["id"] != uid]
        if self.last == uid:
            self.last = ""
        self.save()

    def get(self, uid):
        return next((u for u in self.items if u["id"] == uid), None)

    def touch(self, uid):
        self.last = uid
        self.save()

    def save_dir(self, uid, game_key):
        return self.base / uid / "saves" / game_key

    def trophy_dir(self, uid, game_key):
        return self.base / uid / "trophies" / game_key


def is_link(p):
    p = Path(p)
    if p.is_symlink():
        return True
    is_junction = getattr(p, "is_junction", None)
    if is_junction and is_junction():
        return True
    try:
        return p.exists() and os.path.realpath(p) != os.path.abspath(p)
    except OSError:
        return False


def unlink_dir(p):
    p = Path(p)
    if p.is_symlink() or os.name != "nt":
        p.unlink()
    else:
        os.rmdir(p)


def make_link(link, target):
    if os.name == "nt":
        r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True,
                           creationflags=NO_WINDOW)
        if r.returncode != 0:
            raise RuntimeError("No se pudo enlazar los saves: " + (r.stderr or r.stdout).strip())
    else:
        os.symlink(target, link, target_is_directory=True)


def has_files(d):
    return Path(d).is_dir() and any(Path(d).rglob("*"))


def bind_saves(out, target, legacy, log):
    out, target = Path(out), Path(target)
    target.mkdir(parents=True, exist_ok=True)
    sd = out / "_sd"
    if is_link(sd):
        unlink_dir(sd)
    elif sd.exists():
        if has_files(sd) and not has_files(target):
            shutil.copytree(sd, target, dirs_exist_ok=True)
            shutil.rmtree(sd)
            log("Saves existentes movidos al usuario.")
        else:
            sd.rename(out / f"_sd.bak-{int(time.time())}")
    if not has_files(target):
        for old in legacy:
            if has_files(old) and not is_link(old):
                shutil.copytree(old, target, dirs_exist_ok=True)
                log(f"Saves importados de {old}")
                break
    make_link(sd, target)


def bind_dir(out, name, target, log):
    """Point out/<name> at target (per-user folder), moving what the game already wrote there the first time."""
    out, target = Path(out), Path(target)
    target.mkdir(parents=True, exist_ok=True)
    link = out / name
    if is_link(link):
        unlink_dir(link)
    elif link.exists():
        if has_files(link) and not has_files(target):
            shutil.copytree(link, target, dirs_exist_ok=True)
            shutil.rmtree(link)
            log(f"{name} existente movido al usuario.")
        else:
            link.rename(out / f"{name}.bak-{int(time.time())}")
    make_link(link, target)


# ---------------------------------------------------------------- backup of a user's saves
def export_user(base, uid, zip_path):
    import zipfile
    root = Path(base) / uid
    n = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for part in ("saves", "trophies", "stats.json"):
            p = root / part
            items = [p] if p.is_file() else (sorted(x for x in p.rglob("*") if x.is_file()) if p.is_dir() else [])
            for f in items:
                z.write(f, f.relative_to(root).as_posix())
                n += 1
    return n


def _backup_existing(root, rel_dirs):
    stamp = time.strftime("%Y%m%d-%H%M%S")
    for rel in rel_dirs:
        cur = root / rel
        if cur.exists() and has_files(cur):
            dst = root / "backups" / stamp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(cur, dst, dirs_exist_ok=True)


def import_user(base, uid, source):
    """Restore saves/trophies of a user from a zip or a folder made by export_user/sync. Existing data is backed up
    in users/<uid>/backups/<date> first. Returns the number of files restored."""
    import zipfile
    root = Path(base) / uid
    source = Path(source)
    if source.is_file():
        with zipfile.ZipFile(source) as z:
            names = [n for n in z.namelist() if (n.startswith("saves/") or n.startswith("trophies/")) and not n.endswith("/")]
            games = sorted({"/".join(n.split("/")[:2]) for n in names})
            _backup_existing(root, games)
            for g in games:
                shutil.rmtree(root / g, ignore_errors=True)
            for n in names:
                if ".." in Path(n).parts:
                    continue
                dst = root / n
                dst.parent.mkdir(parents=True, exist_ok=True)
                with z.open(n) as src, open(dst, "wb") as out:
                    shutil.copyfileobj(src, out)
            return len(names)
    count = 0
    games = [f"{part}/{d.name}" for part in ("saves", "trophies") if (source / part).is_dir()
             for d in (source / part).iterdir() if d.is_dir()]
    _backup_existing(root, games)
    for g in games:
        shutil.rmtree(root / g, ignore_errors=True)
        shutil.copytree(source / g, root / g)
        count += sum(1 for x in (root / g).rglob("*") if x.is_file())
    return count


def sync_game(base, uid, game_key, sync_root):
    """Mirror one game's saves and trophies of a user to <sync_root>/<uid>/."""
    root, dest = Path(base) / uid, Path(sync_root) / uid
    for part in ("saves", "trophies"):
        src = root / part / game_key
        if src.is_dir() and has_files(src):
            dst = dest / part / game_key
            tmp = dst.with_name(dst.name + ".tmp")
            shutil.rmtree(tmp, ignore_errors=True)
            shutil.copytree(src, tmp)
            shutil.rmtree(dst, ignore_errors=True)
            tmp.rename(dst)


def _stats_path(base, uid):
    return Path(base) / uid / "stats.json"


def load_stats(base, uid):
    try:
        return json.loads(_stats_path(base, uid).read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def save_stats(base, uid, stats):
    p = _stats_path(base, uid)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(stats, indent=1), "utf-8")
    tmp.replace(p)


def format_duration(seconds):
    minutes = int(seconds // 60)
    if minutes < 1:
        return "<1 min"
    h, m = divmod(minutes, 60)
    return f"{h} h {m} min" if h else f"{m} min"
