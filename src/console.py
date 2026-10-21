import json
import math
import os
import queue
import re
import sys
import threading
import time
from pathlib import Path

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import core  # noqa: E402
import updater  # noqa: E402
import users as userlib  # noqa: E402
import synth  # noqa: E402
import pcgames  # noqa: E402
import audit  # noqa: E402
import winfs  # noqa: E402
import i18n  # noqa: E402
import procs  # noqa: E402
import compat  # noqa: E402

procs.install()
import ambient as amb  # noqa: E402
from ambient import Ambient, BlueBloom  # noqa: E402

HERE = paths.DATA
ASSETS = paths.ASSETS
CONF_PATH = HERE / "config.json"
REL_DIR = HERE / "releases"
UPSTREAM = "https://github.com/boykopovar/AnyPS5.git"
W, H = 1920, 1080
MIN_W, MAX_W = 1440, 3840


def canvas_width(ww, wh):
    if ww <= 0 or wh <= 0:
        return 1920
    return max(MIN_W, min(MAX_W, round(H * ww / wh)))
ACCENT = (79, 195, 217)
TEXT = (236, 240, 245)
DIM = (150, 160, 175)
BAD = (235, 110, 110)
GOOD = (120, 220, 150)
FONT_NAMES = "microsoftyaheiui,yugothicui,segoeui,arial"
KEYBOARD = ["ABCDEFGHIJ", "KLMNOPQRST", "UVWXYZÑ.-_", "0123456789"]
KEY_ACTIONS = ["Espacio", "Borrar", "Listo"]
KEYBOARD_URL = ["1234567890", "qwertyuiop", "asdfghjkl:", "zxcvbnm./-", ["_", "#", "@", "~", "?", "=", "&", "%", "+", "Aa"]]
URL_ACTIONS = ["Pegar", "Borrar", "Listo"]
PLATFORM_COLOR = {"PS5": (79, 195, 217), "PC": (240, 150, 70)}

paths.setup_environment()


def load_conf():
    conf = {"channel": "repo", "games_dir": "", "fullscreen": True, "check_updates": True, "game_fullscreen": True,
            "lang": "en", "game_lang": "auto", "music": True, "sort": "recent", "compat": True}
    try:
        conf.update(json.loads(CONF_PATH.read_text("utf-8")))
    except (OSError, ValueError):
        pass
    if conf.get("compat_default", 0) < 1:
        conf["compat"] = True
        conf["compat_default"] = 1
    if not conf["games_dir"]:
        legacy = paths.CODE.parent / "launcher" / "config.json"
        try:
            conf["games_dir"] = json.loads(legacy.read_text("utf-8")).get("games_dir", "") if legacy.is_file() else ""
        except (OSError, ValueError):
            conf["games_dir"] = ""
    return conf


def save_conf(conf):
    CONF_PATH.write_text(json.dumps(conf, indent=2, ensure_ascii=False), "utf-8")


class Console:
    def __init__(self):
        os.environ.setdefault("SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS", "0")
        os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
        # Smooth (bilinear) scaling of the 1080p canvas to the screen instead of nearest pixel.
        os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "linear")
        # Real pixels on Windows display scaling (125%, 150%...): no blurry bitmap stretch by Windows.
        os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
        if os.name == "nt":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("LarimarStudios.AnyPS5Console")
            except Exception:
                pass
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass
        pygame.init()
        try:
            self.logo = pygame.image.load(str(ASSETS / "anyps5_icon_512.png"))
            pygame.display.set_icon(pygame.transform.smoothscale(self.logo, (64, 64)))
        except Exception:
            self.logo = None
        try:
            from pygame._sdl2 import controller
            controller.init()
            self.controllers = [controller.Controller(i) for i in range(controller.get_count())
                                if controller.is_controller(i)]
        except Exception:
            self.controllers = []
        self.conf = load_conf()
        self.window = None
        self.apply_display()
        pygame.display.set_caption("AnyPS5 Console")
        pygame.mouse.set_visible(False)
        self.fonts = {}
        self.images = {}
        self.q = queue.Queue()
        self.games = []
        self.sel = 0
        self.scroll = 0.0
        self.state = "boot"
        self.boot_t = time.time()
        self.state_t = time.time()
        self.rebuild_canvas()
        self.users = userlib.Users(HERE / "users")
        self.user = None
        self.usel = 0
        self.kb = {"name": "", "r": 0, "c": 0}
        self.fade = 0.0
        self.sounds = {}
        self.swell_played = False
        try:
            pygame.mixer.init()
            for k, path in synth.ensure(HERE / "sounds").items():
                self.sounds[k] = pygame.mixer.Sound(str(path))
        except Exception:
            self.sounds = {}
        self.menu = None
        self.log_lines = []
        self.busy_title = ""
        self.error = None
        self.toast = None
        self.updates = {"repo": None, "release": None}
        self.update_err = {"repo": "", "release": ""}
        self.status = {}
        self.axis_dir = None
        self.axis_next = 0
        self.running = True
        self.pc_games = []
        self.audits = {}
        self.audit_view = None
        self.pc_sel = 0
        self.pc_scroll = 0.0
        self.row_i = 0
        self.vscroll = 0.0
        self.stats = {}
        self.filter_text = ""
        self.progress = None
        self.cancelling = False
        self.game_exe = None
        self.music_on = False
        self.app_update = None
        self.bg = None
        self.compat_store = compat.Store(paths.DATA)
        self.device_code = None
        if self.conf.get("compat"):
            threading.Thread(target=self.flush_reports, daemon=True).start()
        self.worker(self.task_scan)
        self.worker(self.task_scan_pc)
        self.worker(self.task_prepare_music)
        if self.conf["check_updates"]:
            self.worker(self.task_check_updates)

    def sfx(self, name):
        snd = self.sounds.get(name)
        if snd:
            snd.play()

    def go(self, state):
        self.state = state
        self.state_t = time.time()
        self.fade = 1.0
        if state == "home":
            self.maybe_first_setup()

    # ------------------------------------------------------------ first run
    def maybe_first_setup(self):
        if getattr(self, "_setup_asked", False):
            return
        self._setup_asked = True
        if any(self.channel_ready(c, True) for c in self.channels()):
            if not self.conf.get("setup_done"):
                self.conf["setup_done"] = True
                save_conf(self.conf)
            return
        if self.bg:
            return
        self.setup_menu()

    def setup_menu(self):
        self.open_menu(self.tr("¿Tienes AnyPS5 instalado en tu PC?"), [
            ("Sí, elegir su carpeta", self.setup_existing),
            ("No, instalarlo ahora", self.setup_install_menu),
            ("Más tarde", None)])

    def setup_existing(self):
        self.conf["setup_done"] = True
        save_conf(self.conf)
        self.use_existing_menu()

    def setup_install_menu(self):
        self.open_menu(self.tr("¿Qué versión quieres usar?"), [
            ("Estable (release): recomendada, no hay que compilar", lambda: self.setup_install("release")),
            ("Main oficial: lo último, se compila en tu PC", lambda: self.setup_install("repo")),
            ("Un fork (enlace de GitHub)", lambda: self.setup_install("fork")),
            ("Volver", self.setup_menu)])

    def need_tools(self):
        st = updater.tools_status(paths.TOOLS)
        return not (st["git"] and st["mingw"])

    def setup_install(self, kind):
        self.conf["setup_done"] = True
        self.conf["anyps5_dir_asked"] = True
        save_conf(self.conf)
        if kind == "fork":
            self.start_fork_entry()
            self.kb["setup"] = True
            return
        tools = ["tools"] if kind == "repo" and self.need_tools() else []
        self.use_channel(kind)
        self.bg_update(tools + [kind])

    def apply_display(self):
        global W
        if self.conf["fullscreen"]:
            try:
                dw, dh = pygame.display.get_desktop_sizes()[0]
            except Exception:
                info = pygame.display.Info()
                dw, dh = info.current_w, info.current_h
            W = canvas_width(dw, dh)
            try:
                self.window = pygame.display.set_mode((W, H), pygame.FULLSCREEN | pygame.SCALED)
            except pygame.error:
                self.window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        else:
            size = tuple(self.conf.get("window_size") or (1280, 720))
            self.window = pygame.display.set_mode(size, pygame.RESIZABLE)
            W = canvas_width(*self.window.get_size())
        self.hwnd = self.window_handle()
        if hasattr(self, "ambient"):
            self.rebuild_canvas()

    def rebuild_canvas(self):
        amb.W = W
        self.screen = pygame.Surface((W, H))
        old = getattr(self, "ambient", None)
        self.ambient = Ambient()
        if old is not None:
            self.ambient.t, self.ambient.boost = old.t, old.boost
        self.bloom = BlueBloom()
        self.__dict__.pop("_shade", None)
        self.__dict__.pop("_boot_mark", None)
        self.images = {k: v for k, v in getattr(self, "images", {}).items() if not k[2]}

    def on_resize(self, ww, wh):
        global W
        if self.conf["fullscreen"]:
            return
        self.conf["window_size"] = [ww, wh]
        save_conf(self.conf)
        nw = canvas_width(ww, wh)
        if nw != W:
            W = nw
            self.rebuild_canvas()

    def font(self, size, bold=False, script=None):
        key = (size, bold, script)
        if key not in self.fonts:
            f = pygame.font.SysFont(i18n.FONTS.get(script, i18n.DEFAULT_FONTS), size, bold=bold)
            try:
                if script == "arab":
                    f.set_script("Arab")
                    f.set_direction(pygame.DIRECTION_RTL)
                elif script == "deva":
                    f.set_script("Deva")
            except Exception:
                pass
            self.fonts[key] = f
        return self.fonts[key]

    def render_str(self, s, size, color, bold=False):
        parts = i18n.runs(s)
        if len(parts) <= 1 and (not parts or parts[0][0] in ("latin", "cjk")):
            script = parts[0][0] if parts else None
            return self.font(size, bold, "cjk" if script == "cjk" else None).render(s, True, color)
        surfs = [self.font(size, bold, sc if sc != "latin" else None).render(txt, True, color) for sc, txt in parts]
        if any(sc == "arab" for sc, _ in parts):
            surfs.reverse()
        w = sum(x.get_width() for x in surfs)
        h = max(x.get_height() for x in surfs)
        out = pygame.Surface((max(1, w), h), pygame.SRCALPHA)
        x = 0
        for srf in surfs:
            out.blit(srf, (x, (h - srf.get_height()) // 2))
            x += srf.get_width()
        return out

    def render(self, s, size, color, bold=False):
        return self.render_str(self.tr(str(s)), size, color, bold)

    def tr(self, s):
        return i18n.tr(s, self.conf.get("lang", "en"))

    def text(self, s, size, color=TEXT, pos=(0, 0), bold=False, anchor="topleft", maxw=None):
        s = self.tr(str(s))
        surf = self.render_str(s, size, color, bold)
        if maxw and surf.get_width() > maxw:
            while len(s) > 1 and surf.get_width() > maxw:
                s = s[:-2] + "…"
                surf = self.render_str(s, size, color, bold)
        r = surf.get_rect(**{anchor: pos})
        self.screen.blit(surf, r)
        return r

    def image(self, path, size, cover=False):
        key = (str(path), size, cover)
        if key in self.images:
            return self.images[key]
        img = None
        try:
            src = pygame.image.load(str(path)).convert_alpha()
            if cover:
                sw, sh = src.get_size()
                k = max(size[0] / sw, size[1] / sh)
                src = pygame.transform.smoothscale(src, (int(sw * k) + 1, int(sh * k) + 1))
                img = src.subsurface(pygame.Rect(0, 0, *size).clamp(src.get_rect()).move(
                    (src.get_width() - size[0]) // 2, (src.get_height() - size[1]) // 2)).copy()
            else:
                img = pygame.transform.smoothscale(src, size)
        except Exception:
            img = None
        self.images[key] = img
        return img

    def forks(self):
        return self.conf.setdefault("forks", [])

    def fork_dir(self, name):
        f = next((x for x in self.forks() if x["name"] == name), None)
        if f and f.get("dir"):
            return Path(f["dir"])
        return HERE / "forks" / name

    def fork_of(self, ch):
        name = ch[5:] if ch.startswith("fork:") else ""
        return next((f for f in self.forks() if f["name"] == name), None)

    def channels(self):
        return ["repo", "release"] + ["fork:" + f["name"] for f in self.forks()]

    def channel_name(self, ch=None):
        ch = ch or self.conf["channel"]
        if ch == "tools":
            return "Herramientas de compilación"
        if ch == "repo":
            return "Repositorio"
        if ch == "release":
            return "Estable"
        return "Fork " + ch[5:]

    def version_menu(self):
        items = []
        for ch in self.channels():
            u = self.updates.get(ch) or {}
            if not self.channel_ready(ch):
                state = "no instalada"
            elif self.bg_busy(ch):
                state = "actualizando"
            elif u.get("update"):
                state = "actualización disponible"
            else:
                state = "al día" if u else ""
            label = self.tr(self.channel_name(ch)) + (" (en uso)" if ch == self.conf["channel"] else "")
            items.append((label + (f"  ·  {state}" if state else ""), lambda ch=ch: self.choose_version(ch)))
        items.append(("Cerrar", None))
        self.open_menu(self.tr("Versión de AnyPS5"), items)

    def choose_version(self, ch):
        if not self.channel_ready(ch, True):
            self.toast = (f"{self.channel_name(ch)} no está instalada. Instálala en Actualizaciones.", time.time() + 6)
            return
        self.set_channel(ch)

    def channel_ready(self, ch, fresh=False):
        cache = getattr(self, "_ready", {})
        hit = cache.get(ch)
        if hit and not fresh and time.time() - hit[1] < 5:
            return hit[0]
        if ch == "release":
            ok = updater.release_current(REL_DIR) is not None
        elif ch.startswith("fork:"):
            ok = self.fork_of(ch) is not None and core.find_relinker(
                {"relinker": "", "anyps5_dir": str(self.fork_dir(ch[5:]))}) is not None
        else:
            ok = core.find_relinker(self.base_cfg()) is not None
        cache[ch] = (ok, time.time())
        self._ready = cache
        return ok

    def use_channel(self, ch):
        """Select a channel the user set up on purpose, even before it is built."""
        self.conf["channel"] = ch
        save_conf(self.conf)

    def set_channel(self, ch):
        if ch == self.conf["channel"]:
            return
        if not self.channel_ready(ch, True):
            self.toast = (f"{self.channel_name(ch)} no está instalada. Instálala en Actualizaciones.", time.time() + 6)
            return
        self.conf["channel"] = ch
        save_conf(self.conf)
        self.toast = (f"Usando {self.channel_name(ch)}", time.time() + 4)
        self.worker(self.task_scan)

    def ready_channels(self):
        return [c for c in self.channels() if self.channel_ready(c)]

    def next_channel(self):
        ready = self.ready_channels()
        if not ready:
            return self.conf["channel"]
        cur = self.conf["channel"]
        return ready[(ready.index(cur) + 1) % len(ready)] if cur in ready else ready[0]

    def other_channel(self):
        return self.next_channel()

    def channel_root(self, channel=None):
        channel = channel or self.conf["channel"]
        if channel.startswith("fork:") and self.fork_of(channel):
            return self.fork_dir(channel[5:])
        root = self.anyps5_root()
        if channel == "release" and not (root / "tools" / "import_audit.py").is_file():
            info = updater.release_current(REL_DIR)
            if info and info.get("tools"):
                return Path(info["tools"]).parent
        return root

    def anyps5_root(self):
        if self.conf.get("anyps5_dir"):
            return Path(self.conf["anyps5_dir"])
        return paths.LEGACY_ROOT or (HERE / "AnyPS5")

    def base_cfg(self):
        return {"games_dir": self.conf.get("games_dir", ""), "anyps5_dir": str(self.anyps5_root()), "relinker": "",
                "libs_dir": "", "cache_dir": str(HERE / "cache"), "extra_args": "", "emulators": []}

    def core_cfg(self, channel=None):
        channel = channel or self.conf["channel"]
        if channel not in self.channels():
            channel = "repo"
        cfg = self.base_cfg()
        cfg["cache_dir"] = str(HERE / "cache" / channel.replace(":", "-"))
        cfg["relinker"], cfg["libs_dir"] = "", ""
        if channel == "release":
            info = updater.release_current(REL_DIR)
            if not info:
                raise RuntimeError("No hay versión estable instalada. Ve a Actualizaciones.")
            cfg["relinker"], cfg["libs_dir"] = info["relinker"], info["libs"]
        elif channel.startswith("fork:"):
            cfg["anyps5_dir"] = str(self.fork_dir(channel[5:]))
        return cfg

    def worker(self, fn, *args):
        def run():
            try:
                fn(*args)
            except Exception as e:
                self.q.put(("error", str(e)))
        threading.Thread(target=run, daemon=True).start()

    def log(self, line):
        self.q.put(("log", line))

    def task_scan(self):
        games = core.scan_games(self.conf["games_dir"]) if self.conf["games_dir"] else []
        games.sort(key=lambda g: g.name.lower())
        for g in games:
            g.platform = "PS5"
        self.q.put(("games", games))
        try:
            cfg = self.core_cfg()
        except Exception:
            cfg = None
        for g in games:
            st = core.game_status(g, cfg) if cfg else "Sin versión estable"
            self.q.put(("status", g.key, st))
            if cfg:
                self.q.put(("audit", g.key, audit.load(Path(cfg["cache_dir"]) / g.key)))

    def task_prepare_music(self):
        try:
            path = synth.ensure_music(HERE / "sounds")
            self.q.put(("music_ready", str(path)))
        except Exception:
            pass

    def set_music(self, on):
        want = bool(on and self.conf.get("music", True) and getattr(self, "music_path", None))
        if want == self.music_on:
            return
        try:
            if want:
                pygame.mixer.music.load(self.music_path)
                pygame.mixer.music.set_volume(0.22)
                pygame.mixer.music.play(-1, fade_ms=2500)
            else:
                pygame.mixer.music.fadeout(800)
            self.music_on = want
        except Exception:
            self.music_on = False

    def load_user_stats(self):
        self.stats = userlib.load_stats(self.users.base, self.user["id"]) if self.user else {}

    def record_play(self, game, seconds):
        if not self.user:
            return
        st = self.stats.setdefault(game.key, {})
        st["time"] = st.get("time", 0) + max(0, int(seconds))
        st["last"] = int(time.time())
        st["count"] = st.get("count", 0) + 1
        userlib.save_stats(self.users.base, self.user["id"], self.stats)

    def toggle_fav(self, game):
        st = self.stats.setdefault(game.key, {})
        st["fav"] = not st.get("fav", False)
        if self.user:
            userlib.save_stats(self.users.base, self.user["id"], self.stats)

    def view(self, games):
        if self.filter_text:
            f = self.filter_text.lower()
            games = [g for g in games if f in g.name.lower() or f in (g.title_id or "").lower()]
        mode = self.conf.get("sort", "recent")
        st = self.stats
        if mode == "az":
            key = lambda g: g.name.lower()
        elif mode == "played":
            key = lambda g: (-st.get(g.key, {}).get("time", 0), g.name.lower())
        else:
            key = lambda g: (-st.get(g.key, {}).get("last", 0), g.name.lower())
        return sorted(games, key=lambda g: (not st.get(g.key, {}).get("fav", False), key(g)))

    def view_ps5(self):
        return self.view(self.games)

    def view_pc(self):
        return self.view(self.pc_games)

    def task_check_app(self):
        try:
            self.q.put(("app_update", updater.app_check(paths.APP_REPO, paths.VERSION), ""))
        except Exception as e:
            self.q.put(("app_update", None, str(e)))

    def task_update_app(self):
        if not paths.FROZEN:
            raise RuntimeError("Ejecutando desde el código fuente: actualiza con git pull.")
        check = updater.app_check(paths.APP_REPO, paths.VERSION)
        updater.app_update(check, HERE, paths.EXE_DIR, paths.PORTABLE, self.log)
        self.q.put(("quit",))

    def task_scan_pc(self):
        hidden = set(self.conf.get("pc_hidden", []))
        games = [g for g in pcgames.scan_all(self.conf, HERE / "pc_icons256") if g.key not in hidden]
        self.q.put(("pc_games", games))

    def task_check_updates(self):
        self.task_check_app()
        checks = [("repo", lambda: updater.repo_check(self.anyps5_root())), ("release", lambda: updater.release_check(REL_DIR))]
        for f in list(self.forks()):
            checks.append(("fork:" + f["name"], lambda f=f: updater.fork_check(self.fork_dir(f["name"]), f)))
        for ch, fn in checks:
            try:
                self.q.put(("update", ch, fn(), ""))
            except Exception as e:
                self.q.put(("update", ch, None, str(e)))
        self.q.put(("updates_done",))

    def require_tools(self):
        st = updater.tools_status(paths.TOOLS)
        if not (st["git"] and st["mingw"]):
            raise RuntimeError("Faltan herramientas de compilación (Git y MinGW). Instálalas en Actualizaciones.")

    def task_install_tools(self):
        updater.install_tools(paths.TOOLS, self.log)
        paths.setup_environment()
        self._ready = {}
        self.q.put(("done", "Herramientas de compilación instaladas."))

    def task_remove_fork(self, name, delete):
        if delete:
            import shutil
            shutil.rmtree(self.fork_dir(name), ignore_errors=True)
            shutil.rmtree(HERE / "cache" / ("fork-" + name), ignore_errors=True)
        self.q.put(("done", f"Fork {name} quitado."))

    def task_play_pc(self, game):
        import subprocess
        self.q.put(("launch",))
        try:
            proc = subprocess.Popen([game.target], cwd=game.cwd or None)
        except OSError as e:
            self.q.put(("error", f"No se pudo abrir {game.name}: {e}"))
            return
        t0 = time.time()
        proc.wait()
        self.record_play(game, time.time() - t0)
        self.q.put(("ended", 0, ""))

    def run_audit(self, game, cfg, out, channel=None):
        self.log("Revisando funciones del sistema que usa el juego...")
        root = self.channel_root(channel)
        names = audit.names_db(root / "tools", HERE / "aerolib.csv")
        mods = [out / "src" / m for m in ("sce_module", "sce_modules", "prx")]
        mods += [out / "src" / d for d in core.extra_module_dirs(game)]
        result = audit.run(out, core.libs_dir(cfg), root, mods, names, self.log)
        self.q.put(("audit", game.key, result))
        return result

    def task_audit(self, game):
        cfg = self.core_cfg()
        rel = core.find_relinker(cfg)
        if rel and audit.supports_registry(rel):
            cfg["extra_args"] = (cfg.get("extra_args", "") + " --registry").strip()
        exe = core.ensure_converted(game, cfg, self.log)
        result = self.run_audit(game, cfg, exe.parent)
        self.q.put(("show_audit", game.key, result, False))

    def task_play(self, game, force=False, channel=None, skip_audit=False):
        cfg = self.core_cfg(channel)
        rel = core.find_relinker(cfg)
        if rel and audit.supports_registry(rel):
            cfg["extra_args"] = (cfg.get("extra_args", "") + " --registry").strip()
        try:
            exe = core.ensure_converted(game, cfg, self.log, force=force)
        except procs.Cancelled:
            raise
        except Exception as e:
            # Only a failure of AnyPS5 itself is a compatibility result, not a missing build or tools.
            if not procs.cancel_event.is_set() and core.find_relinker(cfg):
                self.report(game, channel, converted=False, error=str(e))
            raise
        result = None
        if not skip_audit:
            result = self.run_audit(game, cfg, exe.parent, channel)
            if result and (result["absent"] or result["missing_libs"]):
                self.q.put(("show_audit", game.key, result, True))
                return
        else:
            result = audit.load(exe.parent)
        if self.user:
            legacy = []
            if not any(userlib.has_files(self.users.save_dir(u["id"], game.key)) for u in self.users.items):
                old = paths.CODE.parent / "launcher" / "cache"
                legacy = [old / game.key / "_sd"] + sorted(old.glob(game.key + "-*/_sd"))
            userlib.bind_saves(exe.parent, self.users.save_dir(self.user["id"], game.key), legacy, self.log)
            os.environ["APS5_USER_NAME"] = self.user["name"]
        os.environ["ANYPS5_LANGUAGE"] = str(self.game_language())
        if self.conf.get("game_fullscreen", True):
            os.environ["APS5_FULLSCREEN"] = "1"
        else:
            os.environ.pop("APS5_FULLSCREEN", None)
        self.q.put(("launch",))
        if self.conf.get("game_fullscreen", True):
            threading.Thread(target=winfs.fullscreen_when_ready, args=(str(exe.resolve()), getattr(self, "hwnd", None)),
                             daemon=True).start()
        self.game_exe = str(exe.resolve())
        self.closed_by_user = False
        t0 = time.time()
        seen = {}
        done = threading.Event()

        def watch():
            while not done.is_set():
                if winfs.has_window(self.game_exe or ""):
                    seen["t"] = time.time() - t0
                    return
                done.wait(1.0)
        shots = []

        def shooter():
            for minute in compat.SHOT_MINUTES:
                if done.wait(max(0.0, minute * 60 - (time.time() - t0))):
                    return
                self.take_shot(game, minute, shots)
        if os.name == "nt":
            threading.Thread(target=watch, daemon=True).start()
        else:
            seen["t"] = 0.0
        shot_thread = threading.Thread(target=shooter, daemon=True)
        shot_thread.start()
        rc = core.launch(exe, self.log)
        done.set()
        shot_thread.join(timeout=15)
        played = time.time() - t0
        self.record_play(game, played)
        self.game_exe = None
        self.report(game, channel, converted=True, window_after=seen.get("t"), seconds=played, exit_code=rc,
                    audit_result=result, log_path=exe.parent / "last_run.log", shots=shots)
        self.q.put(("ended", rc, str(exe.parent / "last_run.log")))

    def anyps5_version(self, channel=None):
        channel = channel or self.conf["channel"]
        try:
            if channel == "release":
                info = updater.release_current(REL_DIR)
                return info["tag"] if info else "-"
            root = self.channel_root(channel)
            head = updater._git(root, "rev-parse", "--short=9", "HEAD", timeout=20).stdout.strip()
            base = updater._git(root, "merge-base", "HEAD", "origin/main", check=False, timeout=20).stdout.strip()
            ahead = updater._git(root, "rev-list", "--count", "origin/main..HEAD", check=False, timeout=20).stdout.strip()
            if ahead and ahead != "0" and base:
                return f"{base[:9]} + {ahead} local ({head})"
            return head
        except Exception:
            return "-"

    def report(self, game, channel, *, converted, window_after=None, seconds=0, exit_code=None, audit_result=None,
               log_path=None, error="", shots=()):
        if not self.conf.get("compat"):
            return
        try:
            ch = channel or self.conf["channel"]
            words = [self.user["name"]] if self.user else []
            words += [self.conf.get("games_dir", ""), str(paths.DATA)]
            r = compat.build(game, converted=converted, window_after=window_after, seconds=seconds,
                             exit_code=exit_code, closed_by_user=getattr(self, "closed_by_user", False),
                             anyps5={"channel": ch if not ch.startswith("fork:") else "fork " + ch[5:],
                                     "version": self.anyps5_version(ch)},
                             console_version=paths.VERSION, audit_result=audit_result, log_path=log_path,
                             error=error, private_words=words, shots=shots)
            self.compat_store.queue(r)
            threading.Thread(target=self.flush_reports, daemon=True).start()
        except Exception as e:
            self.log(f"Reporte de compatibilidad: {e}")

    def take_shot(self, game, minute, shots):
        if not self.conf.get("compat") or not compat.relay_url(self.conf) or not self.game_exe:
            return
        try:
            cap = winfs.capture(self.game_exe)
            if not cap:
                return
            folder = self.compat_store.dir / "shots"
            folder.mkdir(exist_ok=True)
            out = folder / f"{game.key}-{int(time.time())}-{minute}m.jpg"
            compat.shot_jpeg(*cap, out)
            shots.append({"minute": minute, "file": str(out)})
        except Exception as e:
            self.log(f"Captura: {e}")

    def flush_reports(self):
        try:
            n = compat.flush(self.compat_store, self.log, self.conf)
            if n:
                self.q.put(("toast", f"Reporte de compatibilidad enviado ({n})"))
        except Exception as e:
            self.log(f"Reporte de compatibilidad: {e}")

    def task_github_login(self):
        start = compat.device_start()
        self.q.put(("device_code", start["user_code"], start.get("verification_uri", "https://github.com/login/device")))
        try:
            import webbrowser
            webbrowser.open(start.get("verification_uri", "https://github.com/login/device"))
        except Exception:
            pass
        token = compat.device_poll(start, procs.cancel_event.is_set)
        login = compat.whoami(token)
        self.compat_store.set_auth(token, login)
        self.conf["compat"] = True
        save_conf(self.conf)
        self.q.put(("device_code", None, None))
        self.q.put(("done", f"Sesión iniciada como {login}"))
        self.flush_reports()

    def compat_menu(self):
        st = self.compat_store
        on = self.conf.get("compat")
        items = []
        if on:
            items.append(("Desactivar reportes", lambda: self.set_compat(False)))
        else:
            items.append(("Activar reportes", lambda: self.set_compat(True)))
        if st.token():
            items.append((f"Cerrar sesión de GitHub ({st.login_name()})", self.compat_logout))
        elif compat.relay_url(self.conf):
            items.append(("Firmar con mi cuenta de GitHub (opcional)", lambda: self.start_busy(
                "Iniciar sesión con GitHub", self.task_github_login)))
        else:
            items.append(("Iniciar sesión con GitHub", lambda: self.start_busy("Iniciar sesión con GitHub",
                                                                               self.task_github_login)))
        items += [("Ver lista de compatibilidad", lambda: self.open_url(compat.PAGE)), ("Cerrar", None)]
        self.open_menu(self.tr("Reportes de compatibilidad"), items)

    def set_compat(self, on):
        self.conf["compat"] = on
        save_conf(self.conf)
        if on and not compat.can_send(self.compat_store, self.conf):
            self.start_busy("Iniciar sesión con GitHub", self.task_github_login)
        elif on:
            threading.Thread(target=self.flush_reports, daemon=True).start()

    def compat_logout(self):
        self.compat_store.logout()
        self.toast = ("Sesión de GitHub cerrada", time.time() + 4)

    def open_url(self, url):
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass

    def update_repo(self):
        root = self.anyps5_root()
        if not (root / ".git").exists() and not self.conf.get("anyps5_dir_asked"):
            self.open_menu(self.tr("¿Ya tienes AnyPS5 en tu PC?"), [
                ("Sí, elegir su carpeta", self.use_existing_menu),
                ("No, descargar una copia nueva", lambda: self.confirm_new_copy()),
                ("Cancelar", None)])
            return
        self.bg_update(["repo"])

    def confirm_new_copy(self):
        self.conf["anyps5_dir_asked"] = True
        save_conf(self.conf)
        self.bg_update(["repo"])

    def use_existing_menu(self):
        d = self.ask_path("Carpeta de AnyPS5", True)
        if not d:
            return
        root = Path(d)
        self.conf["anyps5_dir_asked"] = True
        save_conf(self.conf)
        if (root / ".git").exists() and (root / "CMakeLists.txt").is_file() and (root / "core").is_dir():
            origin, branch = updater.repo_info(root)
            if origin and updater.is_upstream(origin):
                label = "Main oficial (boykopovar/AnyPS5)"
                yes = lambda: self.adopt_main(root)
            elif origin:
                try:
                    fork = updater.parse_fork(origin + (f"#{branch}" if branch else ""))
                except Exception:
                    fork = None
                label = f"Fork {fork['name'] if fork else origin}"
                yes = (lambda: self.adopt_fork(root, origin, branch)) if fork else (lambda: self.edit_fork(root, origin, branch))
            else:
                label = "Repositorio sin origin"
                yes = lambda: self.edit_fork(root, "", branch)
            self.open_menu(self.tr("Detectado"), [
                (f"Usar {label}" + (f"  ·  {branch}" if branch else ""), yes),
                ("No, es un fork: escribir su enlace", lambda: self.edit_fork(root, origin, branch)),
                ("Cancelar", None)])
            return
        try:
            info = updater.release_info(root)
        except Exception:
            self.toast = ("No se reconoce AnyPS5 en esa carpeta: no es un repositorio ni una release.", time.time() + 7)
            return
        self.open_menu(self.tr("Detectado"), [
            (f"Usar Estable {info['tag']}", lambda: self.adopt_release(root)),
            ("Cancelar", None)])

    def adopt_main(self, root):
        self.pick_anyps5_dir(root=root)
        self.use_channel("repo")
        if not core.find_relinker({"relinker": "", "anyps5_dir": str(root)}):
            self.bg_update(["repo"])

    def adopt_release(self, root):
        try:
            info = updater.adopt_release(REL_DIR, root)
        except Exception as e:
            self.toast = (str(e), time.time() + 7)
            return
        self._ready = {}
        self.use_channel("release")
        self.toast = (f"Versión estable {info['tag']} lista", time.time() + 6)
        self.worker(self.task_check_updates)

    def adopt_fork(self, root, origin, branch):
        self.kb = {"name": origin + (f"#{branch}" if branch else ""), "own_dir": str(root), "mode": "url"}
        self.finish_fork()

    def edit_fork(self, root, origin, branch):
        url = origin if origin.startswith(("http", "git@")) else "https://github.com/"
        if branch and origin:
            url += "#" + branch
        self.kb = {"name": url, "r": 1, "c": 0, "mode": "url", "own_dir": str(root)}
        self.go("newuser")

    def anyps5_dir_menu(self):
        items = [("Elegir mi copia de AnyPS5…", self.use_existing_menu)]
        if self.conf.get("anyps5_dir"):
            items.append(("Usar la copia de la consola", self.reset_anyps5_dir))
        items.append(("Cerrar", None))
        self.open_menu(self.tr("Carpeta de AnyPS5 (repositorio)"), items)

    def pick_anyps5_dir(self, then_update=False, root=None):
        if root is None:
            d = self.ask_path("Carpeta de AnyPS5", True, self.conf.get("anyps5_dir") or None)
            if not d:
                return
            root = Path(d)
        if not ((root / ".git").exists() and (root / "CMakeLists.txt").is_file() and (root / "core").is_dir()):
            self.toast = ("Esa carpeta no es un repositorio de AnyPS5 (falta .git, CMakeLists.txt o core).",
                          time.time() + 7)
            return
        self.conf["anyps5_dir"] = str(root)
        self.conf["anyps5_dir_asked"] = True
        save_conf(self.conf)
        self._ready = {}
        found = core.find_relinker({"relinker": "", "anyps5_dir": str(root)})
        self.toast = (("Compilación encontrada: " + found.name) if found else "Carpeta guardada (sin compilar todavía)",
                      time.time() + 6)
        self.worker(self.task_check_updates)
        self.worker(self.task_scan)
        if then_update:
            self.bg_update(["repo"])

    def reset_anyps5_dir(self):
        self.conf.pop("anyps5_dir", None)
        save_conf(self.conf)
        self._ready = {}
        self.worker(self.task_check_updates)

    # ------------------------------------------------------------ background updates
    def installed_channels_cached(self):
        c = getattr(self, "_installed", None)
        if not c or time.time() - c[0] > 5:
            c = (time.time(), self.installed_channels())
            self._installed = c
        return c[1]

    def installed_channels(self):
        out = []
        if (self.anyps5_root() / ".git").exists():
            out.append("repo")
        if updater.release_current(REL_DIR):
            out.append("release")
        out += ["fork:" + f["name"] for f in self.forks() if (self.fork_dir(f["name"]) / ".git").exists()]
        return out

    def bg_busy(self, ch=None):
        b = self.bg
        if not b:
            return False
        return ch is None or ch == b.get("current") or ch in b["queue"]

    def bg_update(self, channels):
        channels = [c for c in channels if c in self.channels() or c == "tools"]
        if not channels:
            return
        if self.bg:
            new = [c for c in channels if not self.bg_busy(c)]
            self.bg["queue"] += new
            self.bg["n"] += len(new)
        else:
            procs.bg_cancel.clear()
            self.bg = {"queue": list(channels), "current": None, "done": 0, "n": len(channels), "log": [],
                       "progress": None}
            threading.Thread(target=self.task_bg, name=procs.BG_THREAD, daemon=True).start()
        names = ", ".join(self.tr(self.channel_name(c)) for c in channels)
        self.toast = (f"Actualizando en segundo plano: {names}", time.time() + 5)

    def update_all(self):
        pend = [c for c in self.installed_channels() if (self.updates.get(c) or {}).get("update")]
        if not pend:
            self.toast = ("Todo está al día", time.time() + 4)
            return
        self.bg_update(pend)

    def cancel_bg(self):
        if not self.bg:
            return
        procs.bg_cancel.set()
        self.bg["queue"] = []
        threading.Thread(target=procs.kill_all, kwargs={"bg": True}, daemon=True).start()

    def bglog(self, line):
        self.q.put(("bglog", line))

    def task_bg(self):
        results = []
        b = self.bg
        while b["queue"] and not procs.bg_cancel.is_set():
            ch = b["queue"].pop(0)
            b["current"], b["progress"] = ch, None
            self.bglog(f"== {self.channel_name(ch)} ==")
            try:
                self.update_channel(ch, self.bglog)
                results.append((ch, True, ""))
            except Exception as e:
                cancelled = procs.bg_cancel.is_set()
                results.append((ch, False, "Cancelado" if cancelled else str(e)))
                self.bglog(("Cancelado" if cancelled else "Error: " + str(e))[:400])
            b["done"] += 1
            b["current"] = None
            self._ready = {}
        self.q.put(("bg_done", results))
        try:
            self.task_check_updates()
            self.task_scan()
        except Exception:
            pass

    def update_channel(self, ch, log):
        if ch == "tools":
            updater.install_tools(paths.TOOLS, log)
            paths.setup_environment()
            return
        if ch == "release":
            check = updater.release_check(REL_DIR)
            updater.release_update(REL_DIR, check, log)
            return
        if ch == "repo":
            path, fork = self.anyps5_root(), None
        else:
            fork = self.fork_of(ch)
            if not fork:
                raise RuntimeError("Fork no encontrado")
            path = self.fork_dir(fork["name"])
        own_build = (path / "build" / "CMakeCache.txt").is_file()
        if not (own_build and updater.tools_status(paths.TOOLS)["git"]):
            self.require_tools()
        if fork:
            updater.fork_sync(path, fork, log)
        else:
            updater.repo_update(path, UPSTREAM, log)
        procs.check_cancel()
        cfg = self.base_cfg()
        cfg["anyps5_dir"] = str(path)
        core.build_anyps5(cfg, log)

    def start_busy(self, title, fn, *args):
        self.busy_title = title
        self.log_lines = []
        self.progress = None
        self.cancelling = False
        procs.cancel_event.clear()
        self.state = "busy"
        self.worker(fn, *args)

    def cancel_busy(self):
        if self.cancelling:
            return
        self.cancelling = True
        procs.cancel_event.set()
        threading.Thread(target=procs.kill_all, daemon=True).start()

    def close_game(self):
        self.closed_by_user = True
        threading.Thread(target=procs.kill_all, daemon=True).start()

    def quick_menu(self):
        self.restore()
        self.open_menu(self.tr("Juego en curso"), [
            ("Volver al juego", lambda: winfs.focus(self.game_exe) if self.game_exe else None),
            ("Cerrar el juego", self.close_game),
        ])

    def window_handle(self):
        try:
            return pygame.display.get_wm_info()["window"]
        except Exception:
            return None

    def minimize(self):
        pygame.display.iconify()

    def restore(self):
        hwnd = self.window_handle()
        if os.name == "nt" and hwnd:
            import ctypes
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)

    def poll_queue(self):
        while True:
            try:
                msg = self.q.get_nowait()
            except queue.Empty:
                return
            kind = msg[0]
            if kind == "games":
                self.games = msg[1]
                self.sel = min(self.sel, max(0, len(self.games) - 1))
            elif kind == "pc_games":
                self.pc_games = msg[1]
                self.pc_sel = min(self.pc_sel, max(0, len(self.pc_games) - 1))
            elif kind == "audit":
                if msg[2] is not None:
                    self.audits[msg[1]] = msg[2]
            elif kind == "show_audit":
                g = next((x for x in self.games if x.key == msg[1]), None)
                self.audit_view = {"game": g, "data": msg[2], "scroll": 0, "blocked": msg[3]}
                self.state = "audit"
            elif kind == "status":
                self.status[msg[1]] = msg[2]
            elif kind == "log":
                self.log_lines.append(msg[1])
                self.log_lines = self.log_lines[-200:]
                m = re.search(r"\[(\d+)/(\d+)\]", msg[1]) or re.search(r"(\d{1,3})%", msg[1])
                if m:
                    self.progress = int(m[1]) / int(m[2]) if m.lastindex == 2 else int(m[1]) / 100
            elif kind == "device_code":
                self.device_code = (msg[1], msg[2]) if msg[1] else None
            elif kind == "toast":
                self.toast = (msg[1], time.time() + 5)
            elif kind == "music_ready":
                self.music_path = msg[1]
            elif kind == "app_update":
                self.app_update = msg[1]
                self.app_err = msg[2]
                if msg[1] and msg[1]["update"]:
                    self.toast = (f"AnyPS5 Console {msg[1]['remote']} disponible  ·  Menú > Actualizaciones", time.time() + 12)
            elif kind == "bglog":
                if self.bg:
                    self.bg["log"] = (self.bg["log"] + [msg[1]])[-300:]
                    m = re.search(r"\[(\d+)/(\d+)\]", msg[1]) or re.search(r"(\d{1,3})%", msg[1])
                    if m:
                        self.bg["progress"] = int(m[1]) / int(m[2]) if m.lastindex == 2 else int(m[1]) / 100
            elif kind == "bg_done":
                ok = [self.tr(self.channel_name(c)) for c, good, _ in msg[1] if good]
                bad = [(self.tr(self.channel_name(c)), err) for c, good, err in msg[1] if not good]
                parts = []
                if ok:
                    parts.append("Actualizado: " + ", ".join(ok))
                if bad:
                    parts.append("Falló: " + ", ".join(n for n, _ in bad))
                self.toast = ("  ·  ".join(parts) or "Sin cambios", time.time() + 10)
                self.bg_last = {"log": self.bg["log"] if self.bg else [], "results": msg[1]}
                self.bg = None
            elif kind == "quit":
                self.running = False
            elif kind == "update":
                self.updates[msg[1]] = msg[2]
                self.update_err[msg[1]] = msg[3]
            elif kind == "updates_done":
                pend = [self.channel_name(c).lower() for c in self.channels()
                        if self.updates.get(c) and self.updates[c]["update"]]
                if pend:
                    self.toast = ("Actualización disponible: " + " y ".join(pend) + "  ·  Menú > Actualizaciones",
                                  time.time() + 12)
            elif kind == "launch":
                self.state = "playing"
                self.play_t = time.time()
                if not self.conf.get("game_fullscreen", True):
                    self.minimize()
            elif kind == "ended":
                self.restore()
                self.menu = None
                if getattr(self, "closed_by_user", False):
                    self.closed_by_user = False
                    self.state = "home"
                elif msg[1] != 0 and msg[2]:
                    self.error = (f"El juego terminó con codigo {msg[1]}", self.log_lines[-14:], msg[2])
                    self.state = "error"
                else:
                    self.state = "home"
                if msg[2]:
                    self.worker(self.task_scan)
            elif kind == "done":
                self.device_code = None
                self.toast = (msg[1], time.time() + 8)
                self.state = "home"
            elif kind == "error":
                self.device_code = None
                self.restore()
                if self.cancelling:
                    self.cancelling = False
                    self.toast = ("Cancelado", time.time() + 4)
                    self.state = "home"
                else:
                    self.error = ("Error", [msg[1]] + self.log_lines[-10:], "")
                    self.state = "error"

    def open_menu(self, title, items):
        self.menu = {"title": title, "items": items, "i": 0}

    def cur_list(self):
        return self.view_pc() if self.row_i == 1 else self.view_ps5()

    def cur_game(self):
        lst = self.cur_list()
        idx = self.pc_sel if self.row_i == 1 else self.sel
        return lst[idx] if lst and idx < len(lst) else None

    def game_menu(self):
        g = self.cur_game()
        if g is None:
            return
        fav = ("Quitar de favoritos" if self.stats.get(g.key, {}).get("fav") else "Añadir a favoritos",
               lambda: self.toggle_fav(g))
        if getattr(g, "platform", "PS5") == "PC":
            items = [("Jugar", lambda: self.play(g)), fav, ("Abrir carpeta del juego", lambda: self.open_folder(g.path))]
            items.append(("Ocultar de la lista", lambda: self.hide_pc(g)))
            items.append(("Cerrar", None))
            self.open_menu(g.name, items)
            return
        items = [("Jugar", lambda: self.play(g)), fav, ("Reconvertir y jugar", lambda: self.play(g, True))]
        for ch in self.ready_channels():
            if ch != self.conf["channel"]:
                items.append((f"Jugar con {self.channel_name(ch)}", lambda ch=ch: self.play(g, channel=ch)))
        items.append(("Funciones del sistema (qué le falta)", lambda: self.show_audit(g)))
        items += [("Abrir carpeta convertida", lambda: self.open_folder(Path(self.core_cfg()["cache_dir"]) / g.key)),
                  ("Abrir carpeta del juego", lambda: self.open_folder(g.path)),
                  ("Cerrar", None)]
        self.open_menu(g.name, items)

    def show_audit(self, g):
        data = self.audits.get(g.key)
        if data:
            self.audit_view = {"game": g, "data": data, "scroll": 0, "blocked": False}
            self.state = "audit"
        else:
            self.start_busy(f"Revisando funciones de {g.name}", self.task_audit, g)

    def hide_pc(self, g):
        self.conf.setdefault("pc_hidden", []).append(g.key)
        if g.source == "exe" and g.target in self.conf.get("pc_exes", []):
            self.conf["pc_exes"].remove(g.target)
        save_conf(self.conf)
        self.pc_games = [x for x in self.pc_games if x.key != g.key]
        self.pc_sel = min(self.pc_sel, max(0, len(self.pc_games) - 1))

    def main_menu(self):
        nxt = self.next_channel()
        items = []
        if nxt != self.conf["channel"]:
            items.append((f"Usar {self.channel_name(nxt)}", lambda: self.set_channel(nxt)))
        sort_names = {"recent": "Recientes", "az": "A–Z", "played": "Más jugados"}
        items.append(("Buscar juego", self.start_search))
        if self.filter_text:
            items.append(("Quitar búsqueda", self.clear_search))
        items.append((f"Ordenar: {sort_names.get(self.conf.get('sort', 'recent'), 'Recientes')}", self.cycle_sort))
        items += [
            ("Cambiar de usuario", lambda: self.go("users")),
            ("Lista de compatibilidad", lambda: self.open_url(compat.PAGE)),
            ("Actualizaciones", lambda: setattr(self, "state", "updates")),
            ("Ajustes", lambda: setattr(self, "state", "settings")),
            ("Recargar juegos", self.rescan),
            ("Salir", self.quit),
            ("Cerrar", None),
        ]
        self.open_menu("Menú", items)

    def cycle_sort(self):
        order = ["recent", "az", "played"]
        cur = self.conf.get("sort", "recent")
        self.conf["sort"] = order[(order.index(cur) + 1) % len(order)] if cur in order else "recent"
        save_conf(self.conf)
        self.sel = self.pc_sel = 0

    def start_search(self):
        self.kb = {"name": self.filter_text, "r": 0, "c": 0, "mode": "search"}
        self.go("newuser")

    def clear_search(self):
        self.filter_text = ""
        self.sel = self.pc_sel = 0

    def rescan(self):
        self.worker(self.task_scan)
        self.worker(self.task_scan_pc)

    def open_folder(self, path):
        if os.name == "nt" and Path(path).exists():
            os.startfile(str(path))

    def play(self, game, force=False, channel=None, skip_audit=False):
        if getattr(game, "platform", "PS5") == "PC":
            if game.source in ("steam", "epic"):
                if os.name == "nt":
                    os.startfile(game.target)
                self.toast = (f"Abriendo {game.name} en {game.title_id}...", time.time() + 5)
                return
            self.log_lines = []
            self.worker(self.task_play_pc, game)
            return
        if channel and not self.channel_ready(channel, True):
            self.toast = (f"La versión {self.channel_name(channel)} no está instalada.", time.time() + 5)
            return
        if not channel and not self.channel_ready(self.conf["channel"], True) and not self.bg_busy(self.conf["channel"]):
            if not any(self.channel_ready(c) for c in self.channels()):
                self.setup_menu()
            else:
                self.toast = (f"{self.tr(self.channel_name())} no está instalada. Elige otra en Ajustes > Versión de AnyPS5.",
                              time.time() + 7)
            return
        if self.bg_busy(channel or self.conf["channel"]):
            self.toast = (f"{self.tr(self.channel_name(channel))} se está actualizando; espera a que termine o elige otra versión.",
                          time.time() + 6)
            return
        label = f" ({self.channel_name(channel)})" if channel else ""
        self.start_busy(f"Preparando {game.name}{label}", self.task_play, game, force, channel, skip_audit)

    def quit(self):
        self.running = False

    def ask_path(self, title, folder=True, initial=None):
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            if folder:
                d = filedialog.askdirectory(initialdir=initial or None, title=title)
            else:
                d = filedialog.askopenfilename(title=title, filetypes=[("Ejecutables", "*.exe"), ("Todos", "*.*")])
            root.destroy()
        except Exception:
            d = ""
        return d

    def pick_folder(self):
        d = self.ask_path("Carpeta de juegos PS5", True, self.conf["games_dir"])
        if d:
            self.conf["games_dir"] = d
            save_conf(self.conf)
            self.worker(self.task_scan)

    def pc_menu(self):
        items = [("Añadir carpeta de juegos PC", self.add_pc_dir), ("Añadir un ejecutable (.exe)", self.add_pc_exe)]
        for d in self.conf.get("pc_dirs", []):
            items.append((f"Quitar carpeta: {d}", lambda d=d: self.remove_pc_dir(d)))
        if self.conf.get("pc_hidden"):
            items.append(("Mostrar juegos ocultos", self.unhide_pc))
        items.append(("Cerrar", None))
        self.open_menu("Juegos PC", items)

    def add_pc_dir(self):
        d = self.ask_path("Carpeta de juegos PC", True)
        if d and d not in self.conf.setdefault("pc_dirs", []):
            self.conf["pc_dirs"].append(d)
            save_conf(self.conf)
            self.worker(self.task_scan_pc)

    def add_pc_exe(self):
        f = self.ask_path("Ejecutable del juego", False)
        if f and f not in self.conf.setdefault("pc_exes", []):
            self.conf["pc_exes"].append(f)
            save_conf(self.conf)
            self.worker(self.task_scan_pc)

    def remove_pc_dir(self, d):
        self.conf["pc_dirs"].remove(d)
        save_conf(self.conf)
        self.worker(self.task_scan_pc)

    def unhide_pc(self):
        self.conf["pc_hidden"] = []
        save_conf(self.conf)
        self.worker(self.task_scan_pc)

    def settings_rows(self):
        c = self.conf
        return [
            ("Idioma", dict(i18n.UI_LANGUAGES).get(c.get("lang", "en"), "English"), "lang"),
            ("Idioma de los juegos", self.game_lang_label(), "game_lang"),
            ("Versión de AnyPS5", self.channel_name(), "channel"),
            ("Carpeta de juegos PS5", c["games_dir"] or "(sin elegir)", "games_dir"),
            ("Carpeta de AnyPS5 (repositorio)", c.get("anyps5_dir") or "(copia de la consola)", "anyps5_dir"),
            ("Juegos PC (carpetas y ejecutables)", f"{len(c.get('pc_dirs', []))} carpetas, {len(c.get('pc_exes', []))} exe", "pc"),
            ("Detectar juegos de Steam", "Sí" if c.get("pc_steam", True) else "No", "pc_steam"),
            ("Detectar juegos de Epic Games", "Sí" if c.get("pc_epic", True) else "No", "pc_epic"),
            ("Pantalla completa (consola)", "Sí" if c["fullscreen"] else "No", "fullscreen"),
            ("Juegos en pantalla completa", "Sí" if c.get("game_fullscreen", True) else "No", "game_fullscreen"),
            ("Buscar actualizaciones al iniciar", "Sí" if c["check_updates"] else "No", "check_updates"),
            ("Música de fondo", "Sí" if c.get("music", True) else "No", "music"),
            ("Reportes de compatibilidad", self.compat_label(), "compat"),
            ("Volver", "", "back"),
        ]

    def compat_label(self):
        if not self.conf.get("compat"):
            return "No"
        login = self.compat_store.login_name()
        if login:
            return f"{self.tr('Sí')} · {login}"
        return self.tr("Sí") if compat.relay_url(self.conf) else self.tr("Sí (sin sesión)")

    def set_lang(self, code):
        self.conf["lang"] = code
        save_conf(self.conf)
        self.__dict__.pop("_boot_mark", None)

    def game_language(self):
        v = self.conf.get("game_lang", "auto")
        return i18n.DEFAULT_GAME_LANGUAGE.get(self.conf.get("lang", "en"), 1) if v == "auto" else int(v)

    def game_lang_label(self):
        names = dict(i18n.GAME_LANGUAGES)
        name = names.get(self.game_language(), "English (US)")
        if self.conf.get("game_lang", "auto") == "auto":
            return f"{self.tr('Igual que la consola')} ({name})"
        return name

    def set_game_lang(self, value):
        self.conf["game_lang"] = value
        save_conf(self.conf)

    def game_lang_menu(self):
        items = [(self.tr("Igual que la consola"), lambda: self.set_game_lang("auto"))]
        items += [(name, lambda n=n: self.set_game_lang(n)) for n, name in i18n.GAME_LANGUAGES]
        self.open_menu(self.tr("Idioma de los juegos"), items)

    def settings_action(self, key, step=0):
        c = self.conf
        if key == "lang":
            codes = [k for k, _ in i18n.UI_LANGUAGES]
            cur = c.get("lang", "en")
            cur = cur if cur in codes else "en"
            if step == 0:
                self.open_menu(self.tr("Idioma"), [(name, lambda code=code: self.set_lang(code)) for code, name in i18n.UI_LANGUAGES])
            else:
                self.set_lang(codes[(codes.index(cur) + step) % len(codes)])
        elif key == "game_lang":
            if step == 0:
                self.game_lang_menu()
            else:
                opts = ["auto"] + [n for n, _ in i18n.GAME_LANGUAGES]
                cur = c.get("game_lang", "auto")
                c["game_lang"] = opts[(opts.index(cur if cur in opts else "auto") + step) % len(opts)]
        elif key == "channel":
            if step == 0:
                self.version_menu()
            else:
                self.set_channel(self.next_channel())
        elif key == "pc" and step == 0:
            self.pc_menu()
        elif key in ("pc_steam", "pc_epic"):
            c[key] = not c.get(key, True)
            self.worker(self.task_scan_pc)
        elif key == "games_dir" and step == 0:
            self.pick_folder()
        elif key == "anyps5_dir" and step == 0:
            self.anyps5_dir_menu()
        elif key == "fullscreen":
            c["fullscreen"] = not c["fullscreen"]
            self.apply_display()
        elif key == "check_updates":
            c["check_updates"] = not c["check_updates"]
        elif key == "game_fullscreen":
            c["game_fullscreen"] = not c.get("game_fullscreen", True)
        elif key == "compat":
            if step == 0:
                self.compat_menu()
            else:
                self.set_compat(not c.get("compat"))
        elif key == "music":
            c["music"] = not c.get("music", True)
            self.set_music(True)
        elif key == "back" and step == 0:
            self.state = "home"
        save_conf(c)

    def updates_rows(self):
        rows = [
            ("Usar versión: " + self.channel_name(), self.version_menu),
            ("Actualizar desde el repositorio y compilar", self.update_repo),
            (("Actualizar la versión estable" if updater.release_current(REL_DIR) else "Instalar la versión estable"),
             lambda: self.bg_update(["release"])),
        ]
        for f in self.forks():
            rows.append((f"Fork {f['name']}…", lambda f=f: self.fork_menu(f)))
        st = updater.tools_status(paths.TOOLS)
        if not (st["git"] and st["mingw"]):
            rows.append(("Instalar herramientas de compilación (Git + MinGW)", lambda: self.start_busy(
                "Instalando herramientas de compilación", self.task_install_tools)))
        if self.bg:
            b = self.bg
            cur = self.tr(self.channel_name(b["current"])) if b.get("current") else "…"
            rows.insert(0, (f"Ver progreso: {cur} ({min(b['done'] + 1, b['n'])}/{b['n']})",
                            lambda: setattr(self, "state", "bglog")))
            rows.insert(1, ("Cancelar actualizaciones en segundo plano", self.cancel_bg))
        else:
            pend = [c for c in self.installed_channels() if (self.updates.get(c) or {}).get("update")]
            if pend:
                rows.insert(0, (f"Actualizar todo ({len(pend)})", self.update_all))
            if getattr(self, "bg_last", None):
                rows.append(("Ver registro de la última actualización", lambda: setattr(self, "state", "bglog")))
        a = self.app_update
        if a and a.get("update"):
            rows.insert(0, (f"Actualizar AnyPS5 Console a {a['remote']}", lambda: self.start_busy(
                "Actualizando AnyPS5 Console", self.task_update_app)))
        rows += [
            ("Usar mi AnyPS5 existente…", self.use_existing_menu),
            ("Añadir fork (enlace de GitHub)", self.start_fork_entry),
            ("Buscar de nuevo", lambda: self.worker(self.task_check_updates)),
            ("Volver", lambda: setattr(self, "state", "home")),
        ]
        return rows

    def fork_menu(self, f):
        ch = "fork:" + f["name"]
        installed = (self.fork_dir(f["name"]) / ".git").exists()
        items = [(("Actualizar y compilar" if installed else "Clonar y compilar"),
                  lambda: self.bg_update(["fork:" + f["name"]]))]
        if ch != self.conf["channel"]:
            items.append(("Usar esta versión", lambda: self.set_channel(ch)))
        items.append(("Quitar de la lista", lambda: self.remove_fork(f, False)))
        if not f.get("own"):
            items.append(("Quitar y borrar sus archivos", lambda: self.remove_fork(f, True)))
        items.append(("Cerrar", None))
        self.open_menu(f"Fork {f['name']}", items)

    def remove_fork(self, f, delete):
        self.conf["forks"] = [x for x in self.forks() if x["name"] != f["name"]]
        if self.conf["channel"] == "fork:" + f["name"]:
            self.conf["channel"] = "repo"
        save_conf(self.conf)
        self.updates.pop("fork:" + f["name"], None)
        self.worker(self.task_remove_fork, f["name"], delete)

    def start_fork_entry(self):
        self.kb = {"name": "https://github.com/", "r": 1, "c": 0, "mode": "url"}
        self.go("newuser")

    def finish_fork(self):
        try:
            fork = updater.parse_fork(self.kb["name"])
        except Exception as e:
            self.toast = (str(e), time.time() + 5)
            return
        own = self.kb.get("own_dir")
        if own:
            fork["dir"], fork["own"] = own, True
            self.conf["forks"] = [f for f in self.forks() if f["name"] != fork["name"]]
        elif any(f["name"] == fork["name"] for f in self.forks()):
            self.toast = (f"El fork {fork['name']} ya está en la lista", time.time() + 4)
            self.state = "updates"
            return
        self.forks().append(fork)
        save_conf(self.conf)
        if own:
            self._ready = {}
            self.use_channel("fork:" + fork["name"])
            self.state = "updates"
            if core.find_relinker({"relinker": "", "anyps5_dir": own}):
                self.toast = (f"Fork {fork['name']} listo.", time.time() + 6)
                self.worker(self.task_check_updates)
            else:
                self.bg_update(["fork:" + fork["name"]])
            return
        if self.kb.get("setup"):
            self.use_channel("fork:" + fork["name"])
            self.state = "home"
        else:
            self.state = "updates"
        self.bg_update((["tools"] if self.need_tools() else []) + ["fork:" + fork["name"]])

    def handle(self, action):
        if self.menu:
            m = self.menu
            if action == "up":
                m["i"] = (m["i"] - 1) % len(m["items"])
            elif action == "down":
                m["i"] = (m["i"] + 1) % len(m["items"])
            elif action == "back":
                self.menu = None
            elif action == "ok":
                fn = m["items"][m["i"]][1]
                self.menu = None
                if fn:
                    fn()
            return
        st = self.state
        if st == "boot":
            if time.time() - self.boot_t > 1.0:
                self.enter_users()
        elif st == "users":
            n = len(self.users.items) + 1
            if action == "left":
                self.usel = max(0, self.usel - 1)
                self.sfx("tick")
            elif action == "right":
                self.usel = min(n - 1, self.usel + 1)
                self.sfx("tick")
            elif action == "ok":
                self.sfx("chime")
                if self.usel == n - 1:
                    self.kb = {"name": "", "r": 0, "c": 0, "mode": "user"}
                    self.go("newuser")
                else:
                    self.user = self.users.items[self.usel]
                    self.load_user_stats()
                    self.users.touch(self.user["id"])
                    self.ambient.boost = 0.6
                    self.go("home")
            elif action == "options" and self.usel < n - 1:
                u = self.users.items[self.usel]
                items = [("Elegir imagen…", lambda: self.pick_avatar(u))]
                if u.get("avatar"):
                    items.append(("Quitar imagen", lambda: self.set_avatar(u, None)))
                items += [("Eliminar usuario (los saves se conservan)", lambda: self.delete_user(u["id"])), ("Cerrar", None)]
                self.open_menu(u["name"], items)
            elif action == "back" and self.user:
                self.go("home")
        elif st == "newuser":
            self.keyboard_action(action)
        elif st == "home":
            lst = self.cur_list()
            if action in ("left", "right") and lst:
                step = 1 if action == "right" else -1
                if self.row_i == 1:
                    self.pc_sel = max(0, min(len(lst) - 1, self.pc_sel + step))
                else:
                    self.sel = max(0, min(len(lst) - 1, self.sel + step))
                self.sfx("tick")
            elif action == "down" and self.row_i == 0:
                self.row_i = 1
                self.sfx("tick")
            elif action == "up" and self.row_i == 1:
                self.row_i = 0
                self.sfx("tick")
            elif action == "ok" and self.cur_game():
                self.play(self.cur_game())
            elif action == "options":
                self.game_menu()
            elif action in ("menu", "back"):
                self.main_menu()
            elif action == "refresh":
                self.rescan()
        elif st == "settings":
            rows = self.settings_rows()
            self.row = getattr(self, "row", 0) % len(rows)
            if action == "up":
                self.row = (self.row - 1) % len(rows)
            elif action == "down":
                self.row = (self.row + 1) % len(rows)
            elif action == "ok":
                self.settings_action(rows[self.row][2])
            elif action in ("left", "right"):
                self.settings_action(rows[self.row][2], 1 if action == "right" else -1)
            elif action == "back":
                self.state = "home"
        elif st == "updates":
            rows = self.updates_rows()
            self.urow = getattr(self, "urow", 0) % len(rows)
            if action == "up":
                self.urow = (self.urow - 1) % len(rows)
            elif action == "down":
                self.urow = (self.urow + 1) % len(rows)
            elif action == "ok":
                rows[self.urow][1]()
            elif action in ("left", "right") and self.urow == 0:
                rows[0][1]()
            elif action == "back":
                self.state = "home"
        elif st == "audit":
            v = self.audit_view
            if action == "up":
                v["scroll"] = max(0, v["scroll"] - 1)
            elif action == "down":
                v["scroll"] += 1
            elif action == "back":
                self.state = "home"
            elif action == "ok" and v["game"] is not None:
                self.state = "home"
                self.play(v["game"], skip_audit=True)
            elif action == "options" and v["game"] is not None:
                self.open_folder(Path(self.core_cfg()["cache_dir"]) / v["game"].key)
        elif st == "bglog":
            if action in ("back", "ok"):
                self.state = "updates"
            elif action == "options" and self.bg:
                self.cancel_bg()
        elif st == "error":
            if action in ("ok", "back"):
                self.state = "home"
            elif action == "options" and self.error and self.error[2]:
                self.open_folder(Path(self.error[2]).parent)

    def pick_avatar(self, u):
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            f = filedialog.askopenfilename(title="Avatar", filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.webp"), ("*", "*.*")])
            root.destroy()
        except Exception:
            f = ""
        if f:
            try:
                img = pygame.image.load(f)
                side = min(img.get_size())
                img = img.subsurface(pygame.Rect((img.get_width() - side) // 2, (img.get_height() - side) // 2, side, side))
                out = self.users.base / u["id"] / "avatar.png"
                out.parent.mkdir(parents=True, exist_ok=True)
                pygame.image.save(pygame.transform.smoothscale(img, (256, 256)), str(out))
                self.set_avatar(u, str(out))
            except Exception as e:
                self.toast = (str(e), time.time() + 5)

    def set_avatar(self, u, path):
        u["avatar"] = path
        if path is None:
            u.pop("avatar", None)
        self.users.save()
        self.images = {k: v for k, v in self.images.items() if k[0] != "avatar"}

    def delete_user(self, uid):
        self.users.remove(uid)
        if self.user and self.user["id"] == uid:
            self.user = None
        self.usel = 0

    def kb_layout(self):
        if self.kb.get("mode") == "url":
            rows = [list(r) if isinstance(r, str) else r for r in KEYBOARD_URL]
            if self.kb.get("upper"):
                rows = [[k.upper() if len(k) == 1 else k for k in r] for r in rows]
            return rows, URL_ACTIONS, 200
        return [list(r) for r in KEYBOARD], KEY_ACTIONS, 30 if self.kb.get("mode") == "search" else 16

    def kb_finish(self):
        if self.kb.get("mode") == "search":
            self.filter_text = self.kb["name"].strip()
            self.sel = self.pc_sel = 0
            self.go("home")
        elif self.kb.get("mode") == "url":
            self.finish_fork()
        else:
            self.finish_user()

    def paste(self):
        text = ""
        try:
            text = pygame.scrap.get_text() or ""
        except Exception:
            try:
                import tkinter as tk
                root = tk.Tk()
                root.withdraw()
                text = root.clipboard_get()
                root.destroy()
            except Exception:
                text = ""
        text = text.strip().replace("\n", "").replace("\r", "")
        if text:
            self.kb["name"] = (text if self.kb["name"] in ("", "https://github.com/") else self.kb["name"] + text)[:200]

    def keyboard_action(self, action, char=None):
        kb = self.kb
        layout, actions, limit = self.kb_layout()
        rows = len(layout) + 1
        if char is not None:
            if len(kb["name"]) < limit:
                kb["name"] += char
            return
        if action == "up":
            kb["r"] = (kb["r"] - 1) % rows
        elif action == "down":
            kb["r"] = (kb["r"] + 1) % rows
        elif action in ("left", "right"):
            width = len(actions) if kb["r"] == len(layout) else 10
            kb["c"] = (kb["c"] + (1 if action == "right" else -1)) % width
        elif action == "erase":
            kb["name"] = kb["name"][:-1]
        elif action == "done":
            self.kb_finish()
        elif action == "paste":
            self.paste()
        elif action == "back":
            self.go({"url": "updates", "search": "home"}.get(kb.get("mode"), "users"))
        elif action == "ok":
            if kb["r"] < len(layout):
                key = layout[kb["r"]][min(kb["c"], 9)]
                if key == "Aa":
                    kb["upper"] = not kb.get("upper")
                elif len(kb["name"]) < limit:
                    if kb.get("mode") == "url":
                        kb["name"] += key
                    else:
                        kb["name"] += key if not kb["name"] or kb["name"][-1] == " " else key.lower()
            else:
                act = actions[min(kb["c"], len(actions) - 1)]
                if act == "Espacio" and kb["name"] and len(kb["name"]) < limit:
                    kb["name"] += " "
                elif act == "Pegar":
                    self.paste()
                elif act == "Borrar":
                    kb["name"] = kb["name"][:-1]
                elif act == "Listo":
                    self.kb_finish()
        if kb["r"] == len(layout):
            kb["c"] = min(kb["c"], len(actions) - 1)

    def finish_user(self):
        if not self.kb["name"].strip():
            self.toast = ("Escribe un nombre", time.time() + 3)
            return
        user = self.users.create(self.kb["name"])
        self.usel = len(self.users.items) - 1
        self.sfx("chime")
        self.toast = (f"Usuario {user['name']} creado", time.time() + 3)
        self.go("users")

    def read_events(self):
        keys = {pygame.K_LEFT: "left", pygame.K_RIGHT: "right", pygame.K_UP: "up", pygame.K_DOWN: "down",
                pygame.K_RETURN: "ok", pygame.K_SPACE: "ok", pygame.K_ESCAPE: "back", pygame.K_BACKSPACE: "back",
                pygame.K_TAB: "options", pygame.K_m: "menu", pygame.K_F5: "refresh"}
        buttons = {pygame.CONTROLLER_BUTTON_A: "ok", pygame.CONTROLLER_BUTTON_B: "back",
                   pygame.CONTROLLER_BUTTON_Y: "options", pygame.CONTROLLER_BUTTON_X: "refresh",
                   pygame.CONTROLLER_BUTTON_START: "menu", pygame.CONTROLLER_BUTTON_BACK: "menu",
                   pygame.CONTROLLER_BUTTON_DPAD_LEFT: "left", pygame.CONTROLLER_BUTTON_DPAD_RIGHT: "right",
                   pygame.CONTROLLER_BUTTON_DPAD_UP: "up", pygame.CONTROLLER_BUTTON_DPAD_DOWN: "down"}
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                self.running = False
            elif e.type == pygame.VIDEORESIZE:
                self.on_resize(e.w, e.h)
            elif e.type == pygame.TEXTINPUT and self.state == "newuser" and not self.menu:
                for ch in e.text:
                    if ch.isprintable():
                        self.keyboard_action(None, ch)
            elif e.type == pygame.KEYDOWN and self.state == "newuser" and not self.menu:
                special = {pygame.K_BACKSPACE: "erase", pygame.K_RETURN: "done", pygame.K_ESCAPE: "back",
                           pygame.K_UP: "up", pygame.K_DOWN: "down", pygame.K_LEFT: "left", pygame.K_RIGHT: "right"}
                if e.key == pygame.K_v and (e.mod & pygame.KMOD_CTRL):
                    self.keyboard_action("paste")
                elif e.key in special:
                    self.keyboard_action(special[e.key])
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_F11:
                    self.settings_action("fullscreen", 1)
                elif e.key in keys and self.state == "busy":
                    if keys[e.key] == "back":
                        self.cancel_busy()
                elif e.key in keys and (self.state != "playing" or self.menu):
                    self.handle(keys[e.key])
            elif e.type == pygame.CONTROLLERDEVICEADDED:
                from pygame._sdl2 import controller
                try:
                    self.controllers.append(controller.Controller(e.device_index))
                except Exception:
                    pass
            elif e.type == pygame.CONTROLLERBUTTONDOWN and self.state == "newuser" and not self.menu:
                if e.button == pygame.CONTROLLER_BUTTON_X:
                    self.keyboard_action("erase")
                elif e.button == pygame.CONTROLLER_BUTTON_START:
                    self.keyboard_action("done")
                elif e.button == pygame.CONTROLLER_BUTTON_Y:
                    if self.kb.get("mode") == "url":
                        self.keyboard_action("paste")
                    else:
                        self.keyboard_action(None, " ")
                elif e.button in buttons:
                    self.keyboard_action(buttons[e.button])
            elif e.type == pygame.CONTROLLERBUTTONDOWN:
                if self.state == "playing" and e.button == pygame.CONTROLLER_BUTTON_GUIDE:
                    self.quick_menu()
                elif self.state == "busy":
                    if e.button == pygame.CONTROLLER_BUTTON_B:
                        self.cancel_busy()
                elif e.button in buttons and (self.state != "playing" or self.menu):
                    self.handle(buttons[e.button])
        self.read_stick()

    def read_stick(self):
        if (self.state in ("busy", "playing") and not self.menu) or not self.controllers:
            return
        x = y = 0
        for c in self.controllers:
            try:
                x = x or c.get_axis(pygame.CONTROLLER_AXIS_LEFTX)
                y = y or c.get_axis(pygame.CONTROLLER_AXIS_LEFTY)
            except Exception:
                pass
        d = None
        if abs(x) > 20000 and abs(x) >= abs(y):
            d = "right" if x > 0 else "left"
        elif abs(y) > 20000:
            d = "down" if y > 0 else "up"
        now = time.time()
        if d is None:
            self.axis_dir = None
        elif d != self.axis_dir:
            self.axis_dir, self.axis_next = d, now + 0.35
            self.handle(d)
        elif now >= self.axis_next:
            self.axis_next = now + 0.09
            self.handle(d)

    def shade(self):
        if not hasattr(self, "_shade"):
            shade = pygame.Surface((W, H), pygame.SRCALPHA)
            for yy in range(0, H, 6):
                a = int(110 + 120 * (yy / H) ** 1.4)
                pygame.draw.rect(shade, (5, 8, 14, min(235, a)), (0, yy, W, 6))
            self._shade = shade
        return self._shade

    def draw_background(self, game=None):
        bg = None
        if game is not None:
            if getattr(game, "platform", "PS5") == "PC":
                if game.background and game.background.is_file():
                    bg = self.image(game.background, (W, H), cover=True)
            else:
                for name in ("pic0.png", "pic1.png"):
                    p = game.path / "sce_sys" / name
                    if p.is_file():
                        bg = self.image(p, (W, H), cover=True)
                        if bg:
                            break
        if bg:
            self.screen.blit(bg, (0, 0))
            self.screen.blit(self.shade(), (0, 0))
        else:
            self.ambient.draw(self.screen)
            dim = pygame.Surface((W, H), pygame.SRCALPHA)
            dim.fill((0, 0, 0, 70))
            self.screen.blit(dim, (0, 0))

    def avatar_image(self, user, radius):
        path = user.get("avatar") if user else None
        if not path or not Path(path).is_file():
            return None
        key = ("avatar", path, radius, Path(path).stat().st_mtime)
        if key not in self.images:
            try:
                src = pygame.image.load(path).convert_alpha()
                side = min(src.get_size())
                src = src.subsurface(pygame.Rect((src.get_width() - side) // 2, (src.get_height() - side) // 2, side, side))
                img = pygame.transform.smoothscale(src, (radius * 2, radius * 2))
                mask = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
                pygame.draw.circle(mask, (255, 255, 255, 255), (radius, radius), radius)
                img.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
                self.images[key] = img
            except Exception:
                self.images[key] = None
        return self.images[key]

    def avatar(self, user, center, radius, ring=False):
        img = self.avatar_image(user, radius)
        if img is not None:
            self.screen.blit(img, (center[0] - radius, center[1] - radius))
            if ring:
                pygame.draw.circle(self.screen, (255, 255, 255), center, radius + 10, 4)
            return
        color = tuple(user["color"]) if user else (90, 100, 115)
        pygame.draw.circle(self.screen, color, center, radius)
        hi = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(hi, (255, 255, 255, 50), (radius, int(radius * 0.7)), int(radius * 0.8))
        self.screen.blit(hi, (center[0] - radius, center[1] - radius))
        letter = user["name"][:1].upper() if user else "+"
        self.text(letter, int(radius * 1.05), (255, 255, 255), center, bold=True, anchor="center")
        if ring:
            pygame.draw.circle(self.screen, (255, 255, 255), center, radius + 10, 4)

    def draw_topbar(self):
        if self.user:
            self.avatar(self.user, (98, 62), 26)
            self.text(self.user["name"], 30, TEXT, (140, 62), anchor="midleft")
        else:
            self.text("AnyPS5", 34, ACCENT, (70, 40), bold=True)
        r = self.text(self.channel_name(), 22, DIM, (W - 215, 62), anchor="midright", maxw=420)
        self.text(time.strftime("%H:%M"), 34, TEXT, (W - 70, 40), anchor="topright")
        pend = any((self.updates.get(c) or {}).get("update") for c in self.installed_channels_cached())
        if pend:
            pygame.draw.circle(self.screen, ACCENT, (W - 190, 62), 9)
        if self.bg:
            b = self.bg
            cur = self.tr(self.channel_name(b["current"])) if b.get("current") else "…"
            label = f"{self.tr('Actualizando')} {cur} ({min(b['done'] + 1, b['n'])}/{b['n']})"
            if b.get("progress") is not None:
                label += f"  {int(b['progress'] * 100)}%"
            t = time.time()
            x = r.left - 40
            for i in range(6):
                a = t * 4 + i * math.pi / 3
                c = int(90 + 165 * ((i + int(t * 6)) % 6) / 5)
                pygame.draw.circle(self.screen, (c, c, c), (x + int(10 * math.cos(a)), 62 + int(10 * math.sin(a))), 3)
            self.text(label, 22, ACCENT, (x - 22, 62), anchor="midright", maxw=520)

    def draw_hints(self, hints):
        x = 70
        for btn, label in hints:
            pygame.draw.circle(self.screen, TEXT, (x + 20, H - 55), 20)
            self.text(btn, 24, (10, 14, 20), (x + 20, H - 55), bold=True, anchor="center")
            r = self.text(label, 26, TEXT, (x + 50, H - 55), anchor="midleft")
            x = r.right + 50

    def badge(self, label, pos, size=20):
        f = self.font(size, True)
        w, h = f.size(label)
        r = pygame.Rect(pos[0], pos[1], w + 18, h + 6)
        pygame.draw.rect(self.screen, PLATFORM_COLOR.get(label, ACCENT), r, border_radius=r.height // 2)
        self.text(label, size, (10, 14, 20), r.center, bold=True, anchor="center")
        return r

    def tile_art(self, g, size):
        key = ("tile", g.key, size)
        if key in self.images:
            return self.images[key]
        art = None
        if g.icon and Path(g.icon).is_file():
            art = self.image(g.icon, (size, size), cover=getattr(g, "platform", "PS5") == "PC")
        if art is None:
            h = sum(ord(c) for c in g.key)
            base = ((h * 37) % 60 + 30, (h * 53) % 60 + 34, (h * 71) % 70 + 44)
            art = pygame.Surface((size, size))
            for yy in range(size):
                k = yy / size
                art.fill(tuple(int(c * (1.15 - 0.55 * k)) for c in base), (0, yy, size, 1))
            small = getattr(g, "icon_small", None)
            ic = None
            if small and Path(small).is_file():
                try:
                    ic = pygame.transform.smoothscale(pygame.image.load(str(small)).convert_alpha(),
                                                      (int(size * 0.78), int(size * 0.78)))
                except Exception:
                    ic = None
            if ic is not None:
                art.blit(ic, ic.get_rect(center=(size // 2, size // 2)))
            else:
                letter = self.font(int(size * 0.5), True).render(g.name[:1].upper(), True, (255, 255, 255))
                art.blit(letter, letter.get_rect(center=(size // 2, size // 2)))
        self.images[key] = art
        return art

    def draw_row(self, games, sel, scroll, y, big, small, label, active, alpha=255):
        self.text(label, 26 if active else 22, TEXT if active else DIM, (90, y - 40), bold=active)
        if not games:
            msg = ("Elige la carpeta de juegos PS5 en Menú > Ajustes" if label.startswith("Juegos PS5")
                   else "Sin juegos de PC: Menú > Ajustes > Juegos PC")
            self.text(msg, 28 if active else 22, DIM, (90, y + 20))
            return
        step = small + 30
        for i, g in enumerate(games):
            selected = active and i == sel
            x = 90 + i * step + ((big - small) if active and i > sel else 0) - int(scroll)
            if x < -big or x > W + 20:
                continue
            size = big if selected else small
            yy = y if selected or not active else y + (big - small) // 2
            art = self.tile_art(g, size)
            if not active:
                art = art.copy()
                art.set_alpha(150)
            self.screen.blit(art, (x, yy))
            self.badge(getattr(g, "platform", "PS5"), (x + 8, yy + 8), 16 if size < 200 else 20)
            if selected:
                pygame.draw.rect(self.screen, TEXT, pygame.Rect(x, yy, size, size).inflate(12, 12), 4, border_radius=16)

    def draw_home(self):
        game = self.cur_game()
        self.draw_background(game)
        self.draw_topbar()
        ps5, pc = self.view_ps5(), self.view_pc()
        self.sel = min(self.sel, max(0, len(ps5) - 1))
        self.pc_sel = min(self.pc_sel, max(0, len(pc) - 1))
        self.scroll += (self.sel * 230 - self.scroll) * 0.25
        self.pc_scroll += (self.pc_sel * 230 - self.pc_scroll) * 0.25
        rows = [(ps5, self.sel, self.scroll, f"Juegos PS5  ·  {len(ps5)}"),
                (pc, self.pc_sel, self.pc_scroll, f"Juegos PC  ·  {len(pc)}")]
        act = rows[self.row_i]
        other = rows[1 - self.row_i]
        self.draw_row(act[0], act[1], act[2], 180, 280, 200, act[3], True)
        arrow = "▲ " if self.row_i == 1 else "▼ "
        peek = (other[0], other[1], other[1] * 150, arrow + other[3])
        self.draw_row(peek[0], peek[1], peek[2], 840, 120, 120, peek[3], False)
        if game is not None:
            info_y = 490
            self.text(game.name, 60, TEXT, (80, info_y), bold=True, maxw=W - 160)
            if getattr(game, "platform", "PS5") == "PC":
                where = Path(game.target).name if game.source == "exe" else str(game.path or "")
                meta, color = f"{game.title_id}   ·   {where}", DIM
            else:
                st = self.status.get(game.key, "...")
                color = GOOD if st in ("Listo", "Ready") else DIM
                meta = f"{game.title_id or game.path.name}   ·   {st}   ·   {game.kind.upper()}"
                a = self.audits.get(game.key)
                if a and (a["absent"] or a["missing_libs"]):
                    meta += f"   ·   le faltan {a['absent'] + a['missing_libs']} funciones"
                    color = BAD
                elif a and a["stub"]:
                    meta += f"   ·   {a['stub']} funciones incompletas"
                elif a:
                    meta += "   ·   funciones completas"
            r = self.badge(getattr(game, "platform", "PS5"), (82, info_y + 84), 22)
            self.text(meta, 28, color, (r.right + 16, r.centery), anchor="midleft", maxw=W - r.right - 120)
            play = pygame.Rect(80, info_y + 140, 300, 80)
            pygame.draw.rect(self.screen, TEXT, play, border_radius=40)
            self.text("Jugar", 36, (10, 14, 20), play.center, bold=True, anchor="center")
            st = self.stats.get(game.key, {})
            extra = []
            if st.get("fav"):
                extra.append("★")
            if st.get("time"):
                extra.append(f"Jugado {userlib.format_duration(st['time'])}")
            if st.get("last"):
                extra.append(f"Última vez: {time.strftime('%d/%m/%Y', time.localtime(st['last']))}")
            if extra:
                self.text("   ·   ".join(extra), 26, DIM, (play.right + 30, play.centery), anchor="midleft", maxw=W - play.right - 120)
            idx = self.pc_sel if self.row_i == 1 else self.sel
            self.text(f"{idx + 1} / {len(self.cur_list())}", 26, DIM, (W - 80, info_y + 20), anchor="topright")
        if self.filter_text:
            self.text(f"Búsqueda: {self.filter_text}", 24, ACCENT, (W - 80, 140), anchor="topright")
        self.draw_hints([("A", "Jugar"), ("Y", "Opciones"), ("X", "Recargar"), ("≡", "Menú")])

    def content_width(self):
        return min(W - 220, 1700)

    def draw_list_screen(self, title, rows, index, extra=None, extra_h=0):
        self.draw_background(None)
        sel_bottom = 260 + extra_h + index * 92 + 78
        target = max(0, sel_bottom - (H - 120))
        self.list_off = getattr(self, "list_off", 0) + (target - getattr(self, "list_off", 0)) * 0.3
        off = int(self.list_off)
        self.draw_topbar()
        self.text(title, 56, TEXT, (120, 150 - off), bold=True)
        y = 260 - off
        if extra:
            y = extra(y)
        for i, (label, value) in enumerate(rows):
            r = pygame.Rect(110, y, self.content_width(), 78)
            if i == index:
                hl = pygame.Surface(r.size, pygame.SRCALPHA)
                pygame.draw.rect(hl, (255, 255, 255, 28), hl.get_rect(), border_radius=12)
                self.screen.blit(hl, r)
                pygame.draw.rect(self.screen, ACCENT, r, 3, border_radius=12)
            self.text(label, 32, TEXT, (140, r.centery), anchor="midleft")
            if value:
                self.text(value, 30, ACCENT if i == index else DIM, (r.right - 30, r.centery), anchor="midright",
                          maxw=W // 2)
            y += 92
        band = pygame.Surface((W, 120), pygame.SRCALPHA)
        for i in range(120):
            band.fill((8, 10, 14, min(250, i * 7)), (0, i, W, 1))
        self.screen.blit(band, (0, H - 120))
        self.draw_hints([("A", "Elegir"), ("B", "Volver")])

    def draw_updates_info(self, y):
        a = self.app_update
        r = self.text("AnyPS5 Console", 30, TEXT, (140, y), bold=True)
        if a:
            state = ("Actualización disponible", ACCENT) if a["update"] else ("Al día", GOOD)
            detail = f"local {paths.VERSION}  ·  disponible {a['remote']}"
        elif getattr(self, "app_err", ""):
            state, detail = ("Sin conexión", BAD), f"local {paths.VERSION}"
        else:
            state, detail = ("Comprobando...", DIM), f"local {paths.VERSION}"
        self.text(detail, 22, DIM, (r.right + 16, y + 8))
        self.text(state[0], 26, state[1], (110 + self.content_width() - 30, y + 4), anchor="topright")
        y += 60
        for ch in self.channels():
            u = self.updates.get(ch)
            err = self.update_err.get(ch, "")
            if u:
                state = ("Actualización disponible", ACCENT) if u["update"] else ("Al día", GOOD)
                detail = f"local {u['local']}  ·  disponible {u['remote']}"
            elif err:
                state, detail = ("Sin conexión", BAD), err[:70]
            else:
                state, detail = ("Comprobando...", DIM), ""
            label = {"repo": "Repositorio (main)", "release": "Estable (release)"}.get(ch, self.channel_name(ch))
            r = self.text(label, 30, TEXT, (140, y), bold=True)
            x = r.right + 16
            if ch == self.conf["channel"]:
                badge = pygame.Rect(x, y + 4, 110, 32)
                pygame.draw.rect(self.screen, ACCENT, badge, border_radius=16)
                self.text("EN USO", 20, (10, 14, 20), badge.center, bold=True, anchor="center")
                x = badge.right + 16
            elif not self.channel_ready(ch):
                r2 = self.text("no instalada", 22, DIM, (x, y + 8))
                x = r2.right + 16
            self.text(detail, 22, DIM, (x, y + 8), maxw=max(100, 110 + self.content_width() - 360 - x))
            self.text(state[0], 26, state[1], (110 + self.content_width() - 30, y + 4), anchor="topright")
            y += 60
        return y + 20

    def draw_busy(self):
        self.draw_background(self.cur_game())
        self.draw_topbar()
        self.text(self.busy_title, 52, TEXT, (120, 170), bold=True, maxw=W - 240)
        t = time.time()
        for i in range(8):
            a = t * 4 + i * math.pi / 4
            c = int(80 + 175 * ((i + int(t * 8)) % 8) / 7)
            pygame.draw.circle(self.screen, (c, c, c), (W - 180 + int(36 * math.cos(a)), 200 + int(36 * math.sin(a))), 7)
        bar = pygame.Rect(120, 250, W - 240, 10)
        pygame.draw.rect(self.screen, (50, 56, 68), bar, border_radius=5)
        if self.progress is not None:
            fill = bar.copy()
            fill.width = max(10, int(bar.width * max(0.0, min(1.0, self.progress))))
            pygame.draw.rect(self.screen, ACCENT, fill, border_radius=5)
            self.text(f"{int(self.progress * 100)}%", 22, DIM, (bar.right, bar.bottom + 8), anchor="topright")
        else:
            seg = bar.width // 5
            x = bar.x + int((t * 0.6 % 1.0) * (bar.width + seg)) - seg
            part = pygame.Rect(max(bar.x, x), bar.y, min(seg, bar.right - max(bar.x, x)), bar.height)
            if part.width > 0:
                pygame.draw.rect(self.screen, ACCENT, part, border_radius=5)
        if self.device_code:
            code, url = self.device_code
            self.text("Abre esta dirección e introduce el código:", 28, DIM, (W // 2, 360), anchor="center")
            self.text(url, 30, ACCENT, (W // 2, 410), anchor="center")
            self.text(code, 96, TEXT, (W // 2, 520), bold=True, anchor="center")
            self.draw_hints([("B", "Cancelando…" if self.cancelling else "Cancelar")])
            return
        y = 300
        for line in self.log_lines[-19:]:
            self.text(line, 24, DIM, (124, y), maxw=W - 250)
            y += 34
        self.draw_hints([("B", "Cancelando…" if self.cancelling else "Cancelar")])

    def draw_bglog(self):
        self.draw_background(None)
        self.draw_topbar()
        b = self.bg
        if b:
            cur = self.tr(self.channel_name(b["current"])) if b.get("current") else "…"
            title = f"Actualizando {cur} ({min(b['done'] + 1, b['n'])}/{b['n']})"
            log, progress = b["log"], b.get("progress")
        else:
            last = getattr(self, "bg_last", None) or {"log": [], "results": []}
            title, log, progress = "Última actualización", last["log"], 1.0
        self.text(title, 48, TEXT, (120, 170), bold=True, maxw=W - 240)
        bar = pygame.Rect(120, 250, W - 240, 10)
        pygame.draw.rect(self.screen, (50, 56, 68), bar, border_radius=5)
        if progress is not None:
            fill = bar.copy()
            fill.width = max(10, int(bar.width * max(0.0, min(1.0, progress))))
            pygame.draw.rect(self.screen, ACCENT, fill, border_radius=5)
        y = 300
        for line in log[-19:]:
            self.text(line, 24, TEXT if line.startswith("==") else DIM, (124, y), maxw=W - 250)
            y += 34
        hints = [("B", "Volver")]
        if b:
            hints.append(("Y", "Cancelar"))
        self.draw_hints(hints)

    def draw_audit(self):
        v = self.audit_view
        d = v["data"]
        self.draw_background(None)
        self.draw_topbar()
        g = v["game"]
        self.text(f"Funciones del sistema · {g.name if g else ''}", 46, TEXT, (110, 120), bold=True, maxw=W - 220)
        if not d:
            self.text("No se pudo revisar: la versión de AnyPS5 en uso no genera el registro (--registry).", 28, DIM, (110, 200))
            self.draw_hints([("B", "Volver")])
            return
        y = 190
        chips = [(f"{d['implemented']} implementadas", GOOD), (f"{d['stub']} incompletas (stub)", ACCENT),
                 (f"{d['absent']} ausentes", BAD if d["absent"] else DIM)]
        if d["missing_libs"]:
            chips.append((f"{d['missing_libs']} librerías faltantes", BAD))
        x = 110
        for label, color in chips:
            r = self.text(label, 28, color, (x, y), bold=True)
            x = r.right + 40
        y += 50
        if v["blocked"]:
            self.text("El juego no puede cargar: le faltan funciones que AnyPS5 aún no tiene.", 26, BAD, (110, y))
            y += 40
        if d.get("stop"):
            s = d["stop"]
            self.text(f"Primer bloqueo: {s.get('name') or s.get('nid')}  [{s.get('library')}]", 26, TEXT, (110, y))
            y += 40
        lines = []
        current = None
        for r in d["records"]:
            head = ("AUSENTE" if r["class"] == "absent" else "STUB") + "  ·  " + (r.get("library") or "librería sin nombre")
            if head != current:
                current = head
                lines.append((head, True, r["class"]))
            lines.append((f"{audit.label(r)}   ×{r.get('references', 1)}", False, r["class"]))
        visible = max(1, (H - 140 - y) // 34)
        v["scroll"] = min(v["scroll"], max(0, len(lines) - visible))
        for text, header, cls in lines[v["scroll"]:v["scroll"] + visible]:
            color = (BAD if cls == "absent" else ACCENT) if header else TEXT
            self.text(text, 24 if not header else 24, color, (140 if not header else 110, y), bold=header, maxw=W - 260)
            y += 34
        if not lines:
            self.text("No falta nada: todas las funciones que usa el juego existen en esta versión.", 26, GOOD, (110, y))
        hints = [("A", "Jugar igual" if v["blocked"] else "Jugar"), ("Y", "Abrir carpeta (audit.txt)"), ("B", "Volver")]
        if len(lines) > visible:
            hints.insert(1, ("↕", "Desplazar"))
        self.draw_hints(hints)

    def draw_playing(self):
        self.screen.fill((0, 0, 0))
        g = self.cur_game()
        t = time.time() - getattr(self, "play_t", time.time())
        a = int(255 * min(1.0, t / 0.8))
        if g is not None:
            name = self.render_str(g.name, 40, TEXT, True)
            name.set_alpha(a)
            self.screen.blit(name, name.get_rect(center=(W // 2, H // 2 - 30)))
        sub = self.render("Cargando juego…" if t < 20 else "En juego · cierra el juego para volver", 24, DIM)
        sub.set_alpha(a)
        self.screen.blit(sub, sub.get_rect(center=(W // 2, H // 2 + 30)))
        if t > 3:
            self.draw_hints([("G", "Menú rápido (botón Guide)")])

    def draw_error(self):
        self.draw_background(None)
        title, lines, path = self.error
        self.text(title, 52, BAD, (120, 150), bold=True)
        y = 250
        for line in lines:
            self.text(line, 24, TEXT, (124, y), maxw=W - 250)
            y += 34
        if path:
            self.text(path, 24, DIM, (124, y + 20), maxw=W - 250)
        self.draw_hints([("A", "Aceptar")] + ([("Y", "Abrir carpeta del log")] if path else []))

    def draw_boot(self):
        t = time.time() - self.boot_t
        self.screen.fill((0, 0, 0))
        if t < 2.2:
            a = max(0, min(255, int(255 * min(t / 0.5, (2.2 - t) / 0.5))))
            if not hasattr(self, "_boot_mark"):
                try:
                    mark = pygame.image.load(str(ASSETS / "anyps5_wordmark_dark.png")).convert_alpha()
                    mw = min(1100, W - 200)
                    self._boot_mark = pygame.transform.smoothscale(mark, (mw, int(mark.get_height() * mw / mark.get_width())))
                except Exception:
                    self._boot_mark = self.font(110, True).render("AnyPS5", True, (255, 255, 255))
            self._boot_mark.set_alpha(a)
            self.screen.blit(self._boot_mark, self._boot_mark.get_rect(center=(W // 2, H // 2)))
        elif t < 4.6:
            a = max(0, min(255, int(255 * min((t - 2.2) / 0.5, (4.6 - t) / 0.5))))
            surf = self.render("AnyPS5 Console es un proyecto personal. Haz pausas cuando juegues por mucho tiempo.", 22,
                               (190, 190, 190))
            surf.set_alpha(a)
            self.screen.blit(surf, surf.get_rect(center=(W // 2, H // 2)))
        elif t < 7.6:
            if not self.swell_played:
                self.swell_played = True
                self.sfx("swell")
            self.bloom.draw(self.screen, t - 4.6)
        else:
            self.enter_users()

    def enter_users(self):
        self.ambient.boost = 1.0
        self.usel = max(0, next((i for i, u in enumerate(self.users.items) if u["id"] == self.users.last), 0))
        self.go("users")
        self.fade = 1.0

    def draw_press(self):
        t = time.time() - self.state_t
        self.ambient.draw(self.screen)
        a = int(255 * min(1.0, t / 1.2))
        msg = self.render("Pulsa cualquier botón del control", 28, (225, 225, 225))
        msg.set_alpha(a)
        self.screen.blit(msg, msg.get_rect(center=(W // 2, 300)))
        pulse = 0.5 + 0.5 * math.sin(t * 2.4)
        c = (W // 2, H // 2 - 60)
        ring = pygame.Surface((240, 240), pygame.SRCALPHA)
        pygame.draw.circle(ring, (255, 255, 255, int(a * (0.25 + 0.35 * pulse))), (120, 120), int(70 + 18 * pulse), 3)
        pygame.draw.circle(ring, (255, 255, 255, int(a * 0.9)), (120, 120), 46, 4)
        pygame.draw.circle(ring, (255, 255, 255, a), (120, 120), 12)
        self.screen.blit(ring, (c[0] - 120, c[1] - 120))

    def draw_users(self):
        t = time.time() - self.state_t
        self.ambient.draw(self.screen)
        a = int(255 * min(1.0, t / 0.6))
        msg = self.render("¿Quién está usando el control?", 30, (230, 230, 230))
        msg.set_alpha(a)
        self.screen.blit(msg, msg.get_rect(center=(W // 2, 330)))
        items = self.users.items + [None]
        gap = 230
        x0 = W // 2 - (len(items) - 1) * gap // 2
        for i, u in enumerate(items):
            selected = i == self.usel
            r = 92 if selected else 74
            c = (x0 + i * gap, H // 2 - 20)
            if u is None:
                pygame.draw.circle(self.screen, (255, 255, 255), c, r, 3)
                pygame.draw.line(self.screen, (255, 255, 255), (c[0] - 26, c[1]), (c[0] + 26, c[1]), 4)
                pygame.draw.line(self.screen, (255, 255, 255), (c[0], c[1] - 26), (c[0], c[1] + 26), 4)
                if selected:
                    pygame.draw.circle(self.screen, (255, 255, 255), c, r + 10, 4)
                name = "Nuevo usuario"
            else:
                self.avatar(u, c, r, selected)
                name = u["name"]
            self.text(name, 30 if selected else 26, TEXT if selected else DIM, (c[0], c[1] + r + 30), anchor="midtop")
        hints = [("A", "Elegir")]
        if self.usel < len(self.users.items):
            hints.append(("Y", "Opciones"))
        self.draw_hints(hints)

    def draw_newuser(self):
        self.ambient.draw(self.screen)
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 120))
        self.screen.blit(dim, (0, 0))
        url = self.kb.get("mode") == "url"
        layout, actions, limit = self.kb_layout()
        title = {"url": "Añadir fork de AnyPS5", "search": "Buscar juego"}.get(self.kb.get("mode"), "Crear usuario")
        self.text(title, 52, TEXT, (W // 2, 140), bold=True, anchor="center")
        if url:
            self.text("Enlace del repositorio. Para una rama: …/tree/rama o enlace#rama", 24, DIM, (W // 2, 200), anchor="center")
        fw = 1200 if url else 840
        field = pygame.Rect(W // 2 - fw // 2, 230, fw, 90)
        pygame.draw.rect(self.screen, (30, 34, 42), field, border_radius=14)
        pygame.draw.rect(self.screen, ACCENT, field, 2, border_radius=14)
        caret = "|" if int(time.time() * 2) % 2 else " "
        f = self.font(40 if url else 44)
        shown = self.kb["name"] + caret
        while len(shown) > 1 and f.size(shown)[0] > fw - 140:
            shown = shown[1:]
        self.text(shown, 40 if url else 44, TEXT, (field.x + 30, field.centery), anchor="midleft")
        self.text(f"{len(self.kb['name'])}/{limit}", 22, DIM, (field.right - 24, field.centery), anchor="midright")
        kw, kh, gap = 120, (76 if url else 90), 14
        x0 = W // 2 - (10 * kw + 9 * gap) // 2
        y = 360
        for r, row in enumerate(layout):
            for c, ch in enumerate(row):
                rect = pygame.Rect(x0 + c * (kw + gap), y, kw, kh)
                sel = self.kb["r"] == r and self.kb["c"] == c
                on = ch == "Aa" and self.kb.get("upper")
                pygame.draw.rect(self.screen, (235, 238, 242) if sel else ACCENT if on else (44, 50, 62), rect, border_radius=12)
                self.text(ch, 36, (12, 14, 18) if sel or on else TEXT, rect.center, anchor="center")
            y += kh + gap
        aw = (10 * kw + 9 * gap - 2 * gap) // 3
        for c, label in enumerate(actions):
            rect = pygame.Rect(x0 + c * (aw + gap), y, aw, kh)
            sel = self.kb["r"] == len(layout) and self.kb["c"] == c
            pygame.draw.rect(self.screen, (235, 238, 242) if sel else (44, 50, 62), rect, border_radius=12)
            self.text(label, 32, (12, 14, 18) if sel else TEXT, rect.center, anchor="center")
        if url:
            self.draw_hints([("A", "Escribir"), ("X", "Borrar"), ("Y", "Pegar"), ("≡", "Listo"), ("B", "Cancelar")])
        else:
            self.draw_hints([("A", "Escribir"), ("X", "Borrar"), ("Y", "Espacio"), ("≡", "Listo"), ("B", "Cancelar")])

    def draw_menu(self):
        m = self.menu
        shade = pygame.Surface((W, H), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 160))
        self.screen.blit(shade, (0, 0))
        need = max([self.render_str(self.tr(lbl), 32, TEXT).get_width() for lbl, _ in m["items"]] +
                   [self.render_str(self.tr(m["title"]), 40, TEXT, True).get_width()])
        bw = max(640, min(1000, need + 110))
        box = pygame.Rect(W - bw, 0, bw, H)
        pygame.draw.rect(self.screen, (18, 24, 34), box)
        self.text(m["title"], 40, TEXT, (box.x + 50, 120), bold=True, maxw=bw - 100)
        visible = max(1, (H - 260) // 84)
        first = min(max(0, m["i"] - visible + 1), max(0, len(m["items"]) - visible))
        first = min(first, m["i"])
        y = 220
        for i, (label, _) in enumerate(m["items"][first:first + visible], start=first):
            r = pygame.Rect(box.x + 30, y, bw - 60, 70)
            if i == m["i"]:
                pygame.draw.rect(self.screen, ACCENT, r, 3, border_radius=12)
            self.text(label, 32, TEXT, (r.x + 24, r.centery), anchor="midleft", maxw=bw - 100)
            y += 84
        if len(m["items"]) > visible:
            self.text(f"{m['i'] + 1} / {len(m['items'])}", 22, DIM, (box.right - 40, H - 40), anchor="bottomright")

    def draw_toast(self):
        if not self.toast or time.time() > self.toast[1]:
            self.toast = None
            return
        w = self.render_str(self.tr(self.toast[0]), 28, TEXT).get_width() + 60
        r = pygame.Rect((W - w) // 2, 110, w, 64)
        pygame.draw.rect(self.screen, (24, 32, 46), r, border_radius=32)
        pygame.draw.rect(self.screen, ACCENT, r, 2, border_radius=32)
        self.text(self.toast[0], 28, TEXT, r.center, anchor="center")

    def draw(self):
        st = self.state
        if st == "boot":
            self.draw_boot()
        elif st == "press":
            self.draw_press()
        elif st == "users":
            self.draw_users()
        elif st == "newuser":
            self.draw_newuser()
        elif st == "home":
            self.draw_home()
        elif st == "settings":
            rows = self.settings_rows()
            self.draw_list_screen("Ajustes", [(a, b) for a, b, _ in rows], getattr(self, "row", 0) % len(rows))
        elif st == "updates":
            rows = self.updates_rows()
            self.draw_list_screen("Actualizaciones", [(a, "") for a, _ in rows], getattr(self, "urow", 0) % len(rows),
                                  self.draw_updates_info, 60 * len(self.channels()) + 80)
        elif st == "busy":
            self.draw_busy()
        elif st == "bglog":
            self.draw_bglog()
        elif st == "playing":
            self.draw_playing()
        elif st == "audit":
            self.draw_audit()
        elif st == "error":
            self.draw_error()
        if self.menu:
            self.draw_menu()
        self.draw_toast()
        if self.fade > 0:
            veil = pygame.Surface((W, H))
            veil.set_alpha(int(255 * self.fade))
            self.screen.blit(veil, (0, 0))
        win = pygame.display.get_surface()
        ww, wh = win.get_size()
        win.fill((0, 0, 0))
        if (ww, wh) == (W, H):
            win.blit(self.screen, (0, 0))
        else:
            k = min(ww / W, wh / H)
            size = (max(1, int(W * k)), max(1, int(H * k)))
            frame = pygame.transform.smoothscale(self.screen, size)
            win.blit(frame, ((ww - frame.get_width()) // 2, (wh - frame.get_height()) // 2))
        pygame.display.flip()

    def run(self):
        clock = pygame.time.Clock()
        while self.running:
            dt = min(0.05, clock.get_time() / 1000)
            self.read_events()
            self.poll_queue()
            self.set_music(self.state not in ("boot", "playing"))
            if self.state == "playing":
                self.draw()
                clock.tick(30 if self.menu else 5)
                continue
            self.ambient.update(dt)
            self.fade = max(0.0, self.fade - dt * 2.2)
            self.draw()
            clock.tick(60)
        pygame.quit()


if __name__ == "__main__":
    Console().run()
