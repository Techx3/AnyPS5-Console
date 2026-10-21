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
