#!/usr/bin/env python3
"""AnyPS5 Launcher: lista juegos PS5 de una carpeta, los convierte con el relinker
la primera vez (cache) y los ejecuta. Solo biblioteca estandar de Python 3.8+."""
import hashlib
import json
import os
import queue
import shlex
import shutil
import struct
import subprocess
import sys
import threading
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:  # permite importar el nucleo sin Tk (tests)
    tk = None

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / "config.json"
IS_WIN = os.name == "nt"
EXE_EXT = ".exe" if IS_WIN else ".elf"
NO_WINDOW = 0x08000000 if IS_WIN else 0
MODULE_DIRS = ("sce_module", "sce_modules", "prx")
MINGW_DLLS = ("libgcc_s_seh-1.dll", "libstdc++-6.dll", "libwinpthread-1.dll")
SELF_MAGICS = (b"\x4f\x15\x3d\x1d", b"\x54\x14\xf5\xee")

DEFAULT_CONFIG = {
    "games_dir": "",
    "anyps5_dir": str(APP_DIR.parent.parent),
    "relinker": "",
    "libs_dir": "",
    "cache_dir": str(APP_DIR / "cache"),
    "extra_args": "",
    "emulators": [],  # [{"name": "...", "command": "\"C:\\x.exe\" \"{elf}\""}]
}


# ----------------------------------------------------------------- config
def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        cfg.update(json.loads(CONFIG_PATH.read_text("utf-8")))
    except (OSError, ValueError):
        pass
    return cfg


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), "utf-8")


def find_relinker(cfg):
    p = cfg.get("relinker")
    if p and Path(p).is_file():
        return Path(p)
    build = Path(cfg["anyps5_dir"]) / "build"
    if build.is_dir():
        for name in ("relinker.exe", "relinker"):
            for hit in build.rglob(name):
                if hit.is_file():
                    return hit
    return None


def libs_dir(cfg):
    if cfg.get("libs_dir"):
        return Path(cfg["libs_dir"])
    return Path(cfg["anyps5_dir"]) / "build" / "core" / "libs" / "libs"


# ------------------------------------------------------------------ juegos
class Game:
    def __init__(self, path, name, title_id, icon, elf, kind, module_dir):
        self.path, self.name, self.title_id = path, name, title_id
        self.icon, self.elf, self.kind, self.module_dir = icon, elf, kind, module_dir
        raw = title_id or path.name
        self.key = "".join(c if c.isalnum() or c in "-_." else "_" for c in raw)


def read_param(game_dir):
    try:
        data = json.loads((game_dir / "sce_sys" / "param.json").read_text("utf-8", errors="replace"))
    except (OSError, ValueError):
        return "", ""
    tid = str(data.get("titleId") or data.get("title_id") or "")
    lp = data.get("localizedParameters")
    name = ""
    if isinstance(lp, dict):
        for k in (lp.get("defaultLanguage"), "en-US", "en-GB"):
            v = lp.get(k) if k else None
            if isinstance(v, dict) and v.get("titleName"):
                name = v["titleName"]
                break
        if not name:
            for v in lp.values():
                if isinstance(v, dict) and v.get("titleName"):
                    name = v["titleName"]
                    break
    return tid, name


def find_executable(d):
    names = ["eboot.elf", "eboot.bin"]
    names += sorted(p.name for p in d.glob("*.elf") if p.name not in names)
    names += sorted(p.name for p in d.glob("*.bin") if p.name not in names)
    self_hit = None
    for n in names:
        p = d / n
        if not p.is_file():
            continue
        try:
            with open(p, "rb") as f:
                magic = f.read(4)
        except OSError:
            continue
        if magic == b"\x7fELF":
            return p, "elf"
        if magic in SELF_MAGICS and self_hit is None:
            self_hit = p
    return (self_hit, "self") if self_hit else (None, "none")


def scan_games(root, max_depth=4):
    root = Path(root)
    if not root.is_dir():
        return []
    games = []

    def walk(d, depth):
        elf, kind = find_executable(d)
        if kind != "none":
            tid, name = read_param(d)
            icon = d / "sce_sys" / "icon0.png"
            mod = next((d / m for m in MODULE_DIRS if (d / m).is_dir()), None)
            games.append(Game(d, name or d.name, tid, icon if icon.is_file() else None, elf, kind, mod))
            return
        if depth >= max_depth:
            return
        try:
            subs = sorted(p for p in d.iterdir() if p.is_dir())
        except OSError:
            return
        for p in subs:
            walk(p, depth + 1)

    walk(root, 0)
    return games


# ------------------------------------------------------------- conversion
def extra_module_dirs(game, max_depth=3):
    """Carpetas con .prx ELF/SELF fuera de sce_module (p. ej. Unity: Media/Modules, Media/Plugins)."""
    found = []

    def walk(d, depth):
        try:
            entries = sorted(d.iterdir())
        except OSError:
            return
        if depth > 0 and any(e.is_file() and e.suffix.lower() == ".prx" and read_magic(e) in (b"\x7fELF",) + SELF_MAGICS
                             for e in entries):
            found.append(d.relative_to(game.path))
        if depth >= max_depth:
            return
        for e in entries:
            if e.is_dir() and not (depth == 0 and e.name in MODULE_DIRS + ("sce_sys",)):
                walk(e, depth + 1)

    walk(game.path, 0)
    return found


def read_magic(p):
    try:
        with open(p, "rb") as f:
            return f.read(4)
    except OSError:
        return b""


def fingerprint(game, cfg, relinker):
    h = hashlib.sha256()

    def add(p):
        st = p.stat()
        h.update(f"{p}|{st.st_size}|{int(st.st_mtime)}\n".encode())

    add(game.elf)
    for m in list(MODULE_DIRS) + [str(x) for x in extra_module_dirs(game)]:
        d = game.path / m
        if d.is_dir():
            for f in sorted(d.rglob("*")):
                if f.is_file():
                    add(f)
    if relinker:
        add(relinker)
    h.update(f"{cfg.get('extra_args','')}|{sys.platform}".encode())
    return h.hexdigest()


def cache_dir(cfg, game):
    return Path(cfg["cache_dir"]) / game.key


def read_state(out):
    try:
        return json.loads((out / "state.json").read_text("utf-8"))
    except (OSError, ValueError):
        return {}


def game_status(game, cfg):
    rel = find_relinker(cfg)
    if not rel:
        return "Sin relinker"
    out = cache_dir(cfg, game)
    exe = out / ("app" + EXE_EXT)
    if not exe.exists():
        return "Sin convertir"
    return "Listo" if read_state(out).get("fingerprint") == fingerprint(game, cfg, rel) else "Desactualizado"


def unself(src, dst):
    """Extrae el ELF de un SELF PS4/PS5 NO cifrado (dump descifrado)."""
    d = Path(src).read_bytes()
    if d[:4] not in SELF_MAGICS:
        raise RuntimeError(f"{Path(src).name}: no es un SELF")
    num = struct.unpack_from("<H", d, 0x18)[0]
    elf = 0x20 + num * 0x20
    if d[elf:elf + 4] != b"\x7fELF":
        raise RuntimeError(f"{Path(src).name}: cabecera ELF no encontrada dentro del SELF")
    phoff, = struct.unpack_from("<Q", d, elf + 0x20)
    phentsize, phnum = struct.unpack_from("<HH", d, elf + 0x36)
    phdrs = []
    for i in range(phnum):
        _t, _f, off, _va, _pa, fsz, _msz, _al = struct.unpack_from("<IIQQQQQQ", d, elf + phoff + i * phentsize)
        phdrs.append((off, fsz))
    out = bytearray(max([phoff + phnum * phentsize] + [o + f for o, f in phdrs]))
    head = phoff + phnum * phentsize
    out[:head] = d[elf:elf + head]
    for i in range(num):
        props, off, fsz, _msz = struct.unpack_from("<QQQQ", d, 0x20 + i * 32)
        if not props & 0x800:  # solo segmentos de datos (los demas son firmas/metadatos)
            continue
        if props & 0x8:
            raise RuntimeError(f"{Path(src).name}: segmento comprimido (SELF no soportado)")
        if props & 0x2:
            raise RuntimeError(f"{Path(src).name}: segmento cifrado; se necesita un dump descifrado")
        idx = props >> 20
        if idx >= phnum:
            raise RuntimeError(f"{Path(src).name}: segmento {idx} fuera de la tabla de programa")
        po, pf = phdrs[idx]
        n = min(fsz, pf)
        out[po:po + n] = d[off:off + n]
    Path(dst).write_bytes(out)


def stage_source(game, out, log):
    """Crea out/src/ con ELF + modulos listos para el relinker (extrae SELF si hace falta)."""
    src = out / "src"
    src.mkdir(parents=True, exist_ok=True)
    elf = src / "eboot.elf"
    if game.kind == "self":
        log("Extrayendo ELF del SELF de eboot...")
        unself(game.elf, elf)
    else:
        link_or_copy(game.elf, elf)
    for m in list(MODULE_DIRS) + [str(x) for x in extra_module_dirs(game)]:
        md = game.path / m
        if not md.is_dir():
            continue
        (src / m).mkdir(parents=True, exist_ok=True)
        for f in sorted(md.iterdir()):
            if not f.is_file() or f.name.endswith(".esbak"):
                continue
            if m not in MODULE_DIRS and f.suffix.lower() != ".prx":
                continue
            with open(f, "rb") as fh:
                magic = fh.read(4)
            if magic in SELF_MAGICS:
                log(f"Extrayendo ELF de {m}/{f.name}...")
                unself(f, src / m / f.name)
            else:
                link_or_copy(f, src / m / f.name)
    return elf


def link_or_copy(s, d):
    try:
        os.link(s, d)
    except OSError:
        shutil.copy2(s, d)


def run_cmd(cmd, cwd, log):
    log("$ " + " ".join(str(c) for c in cmd))
    p = subprocess.Popen([str(c) for c in cmd], cwd=str(cwd), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, errors="replace",
                         creationflags=NO_WINDOW)
    for line in p.stdout:
        log(line.rstrip())
    return p.wait()


def link_tree(src, dst, skip_top, log):
    """Hardlinks (o copia si es otro volumen) de los recursos del juego a app0/.
    Nunca toca los originales: borrar la cache solo quita enlaces."""
    copied = 0
    for root, dirs, files in os.walk(src):
        rel = Path(root).relative_to(src)
        if rel == Path("."):
            dirs[:] = [d for d in dirs if d not in skip_top]
        target = dst / rel
        target.mkdir(parents=True, exist_ok=True)
        for f in files:
            s, d = Path(root) / f, target / f
            if d.exists():
                continue
            try:
                os.link(s, d)
            except OSError:
                shutil.copy2(s, d)
                copied += 1
    if copied:
        log(f"Aviso: {copied} archivos copiados (la cache esta en otro volumen que el juego).")


def sync_libs(out, cfg, log):
    src = libs_dir(cfg)
    prx = sorted(src.glob("*.prx")) if src.is_dir() else []
    if not prx:
        raise RuntimeError(f"No hay .prx en {src}. Compila AnyPS5 (boton 'Compilar AnyPS5').")
    dst = out / "libs"
    dst.mkdir(exist_ok=True)
    for f in prx:
        d = dst / f.name
        if not d.exists() or d.stat().st_size != f.stat().st_size or d.stat().st_mtime < f.stat().st_mtime:
            shutil.copy2(f, d)
    if IS_WIN:
        gcc = shutil.which("g++") or shutil.which("gcc")
        dirs = [Path(gcc).parent] if gcc else []
        dirs += [Path(cfg["anyps5_dir"]) / "tools" / "mingw64" / "bin", src]
        for name in MINGW_DLLS:
            hit = next((d / name for d in dirs if (d / name).is_file()), None)
            if hit is None:
                log(f"Aviso: no encuentro {name} (MinGW). Las .prx pueden no cargar.")
                continue
            for target in (dst, out):
                if not (target / name).exists():
                    shutil.copy2(hit, target / name)


def ensure_converted(game, cfg, log, force=False):
    rel = find_relinker(cfg)
    if not rel:
        raise RuntimeError("No se encontro el relinker. Usa 'Compilar AnyPS5' o indicalo en Ajustes.")
    out = cache_dir(cfg, game)
    exe = out / ("app" + EXE_EXT)
    fp = fingerprint(game, cfg, rel)
    if not force and exe.exists() and read_state(out).get("fingerprint") == fp:
        log("Ya convertido: se omite la conversion.")
        sync_libs(out, cfg, log)
        return exe
    log(f"Convirtiendo {game.name} (solo la primera vez)...")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    elf = stage_source(game, out, log)
    extra = []
    for d in extra_module_dirs(game):
        extra += ["--module-dir", d.as_posix()]
        log(f"Modulos adicionales: {d.as_posix()}")
    cmd = [rel] + (["--windows"] if IS_WIN else []) + extra + shlex.split(cfg.get("extra_args", "")) + [elf, exe]
    rc = run_cmd(cmd, out, log)
    if rc != 0 or not exe.exists():
        raise RuntimeError(f"El relinker fallo (codigo {rc}). Revisa el registro.")
    app0 = out / "app0"
    app0.mkdir(exist_ok=True)
    link_tree(game.path, app0, MODULE_DIRS, log)
    sync_libs(out, cfg, log)
    (out / "state.json").write_text(json.dumps({"fingerprint": fp, "elf": str(game.elf)}), "utf-8")
    log("Conversion terminada.")
    return exe


def launch(exe, log):
    out = exe.parent
    if not IS_WIN:
        exe.chmod(exe.stat().st_mode | 0o111)
    log(f"Ejecutando {exe.name}...")
    env = dict(os.environ)
    envfile = Path(__file__).with_name("env.txt")
    if envfile.exists():
        for ln in envfile.read_text("utf-8").splitlines():
            ln = ln.strip()
            if ln and not ln.startswith("#") and "=" in ln:
                k, v = ln.split("=", 1)
                env[k.strip()] = v.strip()
    p = subprocess.Popen([str(exe)], cwd=str(out), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, errors="replace",
                         creationflags=NO_WINDOW, env=env)
    with open(out / "last_run.log", "w", encoding="utf-8") as lf:
        for line in p.stdout:
            lf.write(line)
            log(line.rstrip())
    rc = p.wait()
    log(f"Proceso terminado con codigo {rc}.")
    return rc


def emulator_command(template, game):
    s = template.format(elf=str(game.elf), dir=str(game.path), id=game.title_id or game.key)
    parts = shlex.split(s, posix=not IS_WIN)
    return [x[1:-1] if len(x) > 1 and x[0] == x[-1] == '"' else x for x in parts]


def build_anyps5(cfg, log):
    root = Path(cfg["anyps5_dir"])
    missing = [t for t in ("git", "cmake", "ninja", "gcc", "g++") if not shutil.which(t)]
    if missing:
        raise RuntimeError("Faltan herramientas en PATH: " + ", ".join(missing)
                           + (" (Windows: MinGW-w64 GCC 15.2.0 winlibs ucrt-posix-seh)" if IS_WIN else ""))
    steps = [
        ["git", "submodule", "update", "--init", "--recursive"],
        ["cmake", "-S", ".", "-B", "build", "-G", "Ninja", "-DCMAKE_BUILD_TYPE=Release",
         "-DCMAKE_C_COMPILER=gcc", "-DCMAKE_CXX_COMPILER=g++"],
        ["cmake", "--build", "build", "--parallel"],
        ["cmake", "--build", "build", "--target", "libs", "--parallel"],
    ]
    for s in steps:
        if run_cmd(s, root, log) != 0:
            raise RuntimeError("Fallo: " + " ".join(s))
    log("AnyPS5 compilado.")


# --------------------------------------------------------------------- UI
class App:
    def __init__(self, root):
        self.root, self.cfg = root, load_config()
        self.q, self.games, self.icons, self.busy = queue.Queue(), {}, {}, False
        root.title("AnyPS5 Launcher")
        root.geometry("920x660")
        self.build_ui()
        self.poll()
        if self.cfg["games_dir"]:
            self.refresh()

    def build_ui(self):
        r = self.root
        top = ttk.Frame(r, padding=8)
        top.pack(fill="x")
        self.dir_var = tk.StringVar(value=self.cfg["games_dir"])
        ttk.Label(top, text="Carpeta de juegos:").pack(side="left")
        ttk.Entry(top, textvariable=self.dir_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(top, text="Examinar...", command=self.pick_dir).pack(side="left")
        ttk.Button(top, text="Actualizar", command=self.refresh).pack(side="left", padx=4)
        ttk.Button(top, text="Ajustes", command=self.settings).pack(side="left")

        style = ttk.Style()
        style.configure("Games.Treeview", rowheight=56)
        mid = ttk.Frame(r, padding=(8, 0))
        mid.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(mid, style="Games.Treeview", columns=("id", "state"), selectmode="browse")
        self.tree.heading("#0", text="Juego")
        self.tree.heading("id", text="ID")
        self.tree.heading("state", text="Estado")
        self.tree.column("#0", width=420)
        self.tree.column("id", width=120)
        self.tree.column("state", width=160)
        sb = ttk.Scrollbar(mid, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")
        self.tree.bind("<Double-1>", lambda e: self.play())

        bar = ttk.Frame(r, padding=8)
        bar.pack(fill="x")
        self.buttons = [
            ttk.Button(bar, text="Jugar", command=self.play),
            ttk.Button(bar, text="Reconvertir", command=lambda: self.play(force=True, run=False)),
            ttk.Button(bar, text="Abrir carpeta convertida", command=self.open_out),
        ]
        for b in self.buttons:
            b.pack(side="left", padx=(0, 6))
        self.emu_btn = ttk.Menubutton(bar, text="Ejecutar con emulador")
        self.emu_btn.pack(side="left", padx=(0, 6))
        self.emu_menu = tk.Menu(self.emu_btn, tearoff=0)
        self.emu_btn["menu"] = self.emu_menu
        self.build_btn = ttk.Button(bar, text="Compilar AnyPS5", command=self.build)
        self.build_btn.pack(side="right")
        self.reload_emulators()

        self.logbox = tk.Text(r, height=11, state="disabled", wrap="none")
        self.logbox.pack(fill="both", padx=8, pady=(0, 8))

    # -- utilidades
    def log(self, text):
        self.q.put(("log", text))

    def poll(self):
        try:
            while True:
                m = self.q.get_nowait()
                if m[0] == "log":
                    self.logbox.configure(state="normal")
                    self.logbox.insert("end", m[1] + "\n")
                    self.logbox.see("end")
                    self.logbox.configure(state="disabled")
                elif m[0] == "games":
                    self.fill(m[1])
                elif m[0] == "state":
                    if self.tree.exists(m[1]):
                        self.tree.set(m[1], "state", m[2])
                elif m[0] == "busy":
                    self.busy = m[1]
                elif m[0] == "error":
                    messagebox.showerror("AnyPS5 Launcher", m[1])
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def worker(self, fn):
        if self.busy:
            return
        self.busy = True

        def run():
            try:
                fn()
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR: {e}")
                self.q.put(("error", str(e)))
            finally:
                self.q.put(("busy", False))
        threading.Thread(target=run, daemon=True).start()

    def selected(self):
        sel = self.tree.selection()
        return self.games.get(sel[0]) if sel else None

    def pick_dir(self):
        d = filedialog.askdirectory(title="Carpeta con los juegos de PS5")
        if d:
            self.dir_var.set(d)
            self.cfg["games_dir"] = d
            save_config(self.cfg)
            self.refresh()

    # -- lista
    def refresh(self):
        self.cfg["games_dir"] = self.dir_var.get().strip()
        save_config(self.cfg)
        cfg = dict(self.cfg)

        def job():
            try:
                games = scan_games(cfg["games_dir"])
                self.q.put(("games", games))
                for g in games:
                    try:
                        self.q.put(("state", g.key, game_status(g, cfg)))
                    except Exception as e:  # noqa: BLE001
                        self.q.put(("state", g.key, "Error"))
                        self.log(f"{g.name}: {e}")
            except Exception as e:  # noqa: BLE001
                self.log(f"ERROR al escanear: {e}")
        threading.Thread(target=job, daemon=True).start()

    def fill(self, games):
        self.tree.delete(*self.tree.get_children())
        self.games = {g.key: g for g in games}
        self.icons = {}
        for g in games:
            img = ""
            if g.icon:
                try:
                    p = tk.PhotoImage(file=str(g.icon))
                    p = p.subsample(max(1, p.width() // 48))
                    self.icons[g.key] = p
                    img = p
                except tk.TclError:
                    pass
            self.tree.insert("", "end", iid=g.key, text="  " + g.name, image=img,
                             values=(g.title_id, "..."))
        self.log(f"{len(games)} juego(s) encontrados.")

    # -- acciones
    def play(self, force=False, run=True):
        g = self.selected()
        if not g:
            return
        cfg = dict(self.cfg)

        def job():
            flag = APP_DIR / "rebuild.flag"
            if flag.exists():
                self.log("Recompilando AnyPS5 (rebuild.flag)...")
                subprocess.run(["cmd", "/c", str(APP_DIR / "build_anyps5.bat")], cwd=str(APP_DIR),
                               creationflags=NO_WINDOW)
                text = (APP_DIR / "build.log").read_text("utf-8", errors="replace")
                if "[DONE]" not in text:
                    raise RuntimeError("La compilacion fallo; revisa tools\\launcher\\build.log")
                flag.unlink()
                self.log("Compilacion terminada.")
            exe = ensure_converted(g, cfg, self.log, force=force)
            self.q.put(("state", g.key, "Listo"))
            if run:
                launch(exe, self.log)
        self.worker(job)

    def open_out(self):
        g = self.selected()
        if not g:
            return
        d = cache_dir(self.cfg, g)
        if not d.exists():
            self.log("Aun no convertido.")
            return
        if IS_WIN:
            os.startfile(str(d))  # noqa: S606
        else:
            subprocess.Popen(["xdg-open", str(d)])

    def reload_emulators(self):
        self.emu_menu.delete(0, "end")
        for e in self.cfg.get("emulators", []):
            self.emu_menu.add_command(label=e["name"], command=lambda e=e: self.run_emulator(e))
        if not self.cfg.get("emulators"):
            self.emu_menu.add_command(label="(configura emuladores en Ajustes)", state="disabled")

    def run_emulator(self, emu):
        g = self.selected()
        if not g:
            return
        try:
            cmd = emulator_command(emu["command"], g)
            self.log("$ " + " ".join(cmd))
            subprocess.Popen(cmd)
        except Exception as e:  # noqa: BLE001
            self.log(f"ERROR: {e}")

    def build(self):
        cfg = dict(self.cfg)

        def job():
            build_anyps5(cfg, self.log)
            self.refresh()
        self.worker(job)

    # -- ajustes
    def settings(self):
        win = tk.Toplevel(self.root)
        win.title("Ajustes")
        win.geometry("760x420")
        fields = [("Repositorio AnyPS5", "anyps5_dir", True), ("relinker (vacio = auto)", "relinker", False),
                  ("Carpeta de .prx (vacio = auto)", "libs_dir", True), ("Carpeta cache", "cache_dir", True),
                  ("Argumentos extra del relinker", "extra_args", None)]
        vars_ = {}
        for i, (label, key, is_dir) in enumerate(fields):
            ttk.Label(win, text=label).grid(row=i, column=0, sticky="w", padx=8, pady=4)
            v = tk.StringVar(value=self.cfg.get(key, ""))
            vars_[key] = v
            ttk.Entry(win, textvariable=v, width=60).grid(row=i, column=1, sticky="we", pady=4)
            if is_dir is not None:
                def browse(v=v, is_dir=is_dir):
                    p = filedialog.askdirectory() if is_dir else filedialog.askopenfilename()
                    if p:
                        v.set(p)
                ttk.Button(win, text="...", width=3, command=browse).grid(row=i, column=2, padx=4)
        ttk.Label(win, text="Emuladores (uno por linea: Nombre = comando con {elf} {dir} {id})").grid(
            row=len(fields), column=0, columnspan=3, sticky="w", padx=8, pady=(10, 2))
        emu = tk.Text(win, height=7)
        emu.grid(row=len(fields) + 1, column=0, columnspan=3, sticky="nsew", padx=8)
        emu.insert("1.0", "\n".join(f'{e["name"]} = {e["command"]}' for e in self.cfg.get("emulators", [])))
        win.columnconfigure(1, weight=1)

        def save():
            for k, v in vars_.items():
                self.cfg[k] = v.get().strip()
            emus = []
            for line in emu.get("1.0", "end").splitlines():
                if "=" in line:
                    n, c = line.split("=", 1)
                    if n.strip() and c.strip():
                        emus.append({"name": n.strip(), "command": c.strip()})
            self.cfg["emulators"] = emus
            save_config(self.cfg)
            self.reload_emulators()
            win.destroy()
            self.refresh()
        ttk.Button(win, text="Guardar", command=save).grid(row=len(fields) + 2, column=1, sticky="e", pady=8)


def main():
    if tk is None:
        sys.exit("Tkinter no esta disponible en este Python.")
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
