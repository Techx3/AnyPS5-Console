import os
import subprocess
import threading
import weakref

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
BG_THREAD = "bg-update"
cancel_event = threading.Event()  # foreground task (busy screen)
bg_cancel = threading.Event()  # background updates
_live = weakref.WeakSet()
_lock = threading.Lock()
_original = subprocess.Popen


class TrackedPopen(_original):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = threading.current_thread().name
        with _lock:
            _live.add(self)


def install():
    subprocess.Popen = TrackedPopen


def running():
    with _lock:
        return [p for p in list(_live) if p.poll() is None]


def kill(proc):
    if proc.poll() is not None:
        return
    if os.name == "nt":
        _original(["taskkill", "/T", "/F", "/PID", str(proc.pid)], stdout=subprocess.DEVNULL,
                  stderr=subprocess.DEVNULL, creationflags=NO_WINDOW).wait()
    else:
        proc.kill()


def kill_all(bg=False):
    """bg=False: processes of foreground tasks and games; bg=True: only background updates."""
    for p in running():
        if (getattr(p, "owner", "") == BG_THREAD) != bg:
            continue
        try:
            kill(p)
        except OSError:
            pass


class Cancelled(Exception):
    pass


def in_background():
    return threading.current_thread().name == BG_THREAD


def check_cancel():
    if (bg_cancel if in_background() else cancel_event).is_set():
        raise Cancelled("Cancelado")
