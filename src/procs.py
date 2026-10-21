import os
import subprocess
import threading
import weakref

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
cancel_event = threading.Event()
_live = weakref.WeakSet()
_lock = threading.Lock()
_original = subprocess.Popen


class TrackedPopen(_original):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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


def kill_all():
    for p in running():
        try:
            kill(p)
        except OSError:
            pass


class Cancelled(Exception):
    pass


def check_cancel():
    if cancel_event.is_set():
        raise Cancelled("Cancelado")
