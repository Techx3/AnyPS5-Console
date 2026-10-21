"""Compatibility reports: GitHub device-flow login and reports sent as issues to the compatibility repo."""
import getpass
import hashlib
import json
import os
import platform
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CLIENT_ID = "Ov23liTC0DFDVRDqDBsN"
REPO = "Techx3/AnyPS5-Compat"
PAGE = "https://techx3.github.io/AnyPS5-Compat/"
# Relay (Cloudflare Worker) that files reports without a GitHub sign-in. Empty: sign-in required.
RELAY = "https://anyps5-compat.techx3.workers.dev"
SCOPE = "public_repo"
PLAYABLE_SECONDS = 600
BOOT_SECONDS = 120
NO_WINDOW = 0x08000000 if os.name == "nt" else 0
UA = {"User-Agent": "AnyPS5-Console", "Accept": "application/vnd.github+json"}


class Store:
    def __init__(self, data_dir):
        self.dir = Path(data_dir) / "compat"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.pending = self.dir / "pending"
        self.pending.mkdir(exist_ok=True)

    def _json(self, name, default):
        try:
            return json.loads((self.dir / name).read_text("utf-8"))
        except (OSError, ValueError):
            return default

    def _save(self, name, value):
        (self.dir / name).write_text(json.dumps(value, indent=1), "utf-8")

    def reporter(self):
        f = self.dir / "id.txt"
        try:
            return f.read_text("utf-8").strip()
        except OSError:
            import uuid
            v = uuid.uuid4().hex[:16]
            f.write_text(v, "utf-8")
            return v

    def token(self):
        return self._json("auth.json", {}).get("token")

    def login_name(self):
        return self._json("auth.json", {}).get("login", "")

    def set_auth(self, token, login):
        self._save("auth.json", {"token": token, "login": login})

    def logout(self):
        try:
            (self.dir / "auth.json").unlink()
        except OSError:
            pass

    def sent(self):
        return self._json("sent.json", {})

    def mark_sent(self, title, digest):
        s = self.sent()
        s[title] = digest
        self._save("sent.json", s)

    def queue(self, report):
        (self.pending / f"{int(time.time() * 1000)}.json").write_text(json.dumps(report), "utf-8")

    def queued(self):
        return sorted(self.pending.glob("*.json"))


def _post(url, data, token=None, form=False):
    headers = dict(UA)
    if token:
        headers["Authorization"] = "Bearer " + token
    if form:
        headers["Accept"] = "application/json"
    body = json.dumps(data).encode()
    headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, body, headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _get(url, token=None):
    headers = dict(UA)
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return json.load(r)


# --- device flow -----------------------------------------------------------

def device_start():
    return _post("https://github.com/login/device/code", {"client_id": CLIENT_ID, "scope": SCOPE}, form=True)


def device_poll(start, should_stop=lambda: False):
    interval = int(start.get("interval", 5))
    end = time.time() + int(start.get("expires_in", 900))
    while time.time() < end:
        for _ in range(interval * 4):
            if should_stop():
                raise RuntimeError("Cancelado")
            time.sleep(0.25)
        r = _post("https://github.com/login/oauth/access_token",
                  {"client_id": CLIENT_ID, "device_code": start["device_code"],
                   "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}, form=True)
        if r.get("access_token"):
            return r["access_token"]
        err = r.get("error")
        if err == "slow_down":
            interval = int(r.get("interval", interval + 5))
        elif err != "authorization_pending":
            raise RuntimeError(r.get("error_description") or err or "login failed")
    raise RuntimeError("El código expiró")


def whoami(token):
    return _get("https://api.github.com/user", token).get("login", "")


# --- report ----------------------------------------------------------------

_gpu = None


def gpu_name():
    global _gpu
    if _gpu is None:
        _gpu = ""
        if os.name == "nt":
            try:
                p = subprocess.run(["powershell", "-NoProfile", "-Command",
                                    "(Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join ' / '"],
                                   capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW)
                _gpu = p.stdout.strip()[:200]
            except (OSError, subprocess.SubprocessError):
                pass
    return _gpu


def os_name():
    if os.name == "nt":
        v = platform.version()
        build = int(v.split(".")[-1]) if v.split(".")[-1].isdigit() else 0
        return f"Windows {'11' if build >= 22000 else '10'} ({v})"
    return f"{platform.system()} {platform.release()}"


def sanitizer(extra=()):
    words = []
    home = str(Path.home())
    for w in [home, home.replace("\\", "/"), getpass.getuser(), *extra]:
        if w and len(w) > 2:
            words.append(w)
    words.sort(key=len, reverse=True)
    pats = [re.compile(re.escape(w), re.I) for w in words]
    drive = re.compile(r"\b[A-Za-z]:[\\/](?:[^\\/\r\n\"'<>|:*?]+[\\/])*")

    def clean(s):
        s = drive.sub("<path>/", s)
        for p in pats:
            s = p.sub("<user>", s)
        return s
    return clean


ERROR_LINE = re.compile(r"error|exception|fatal|assert|unresolved|unimplemented|not implemented|crash|abort|"
                        r"access violation|segfault|panic|failed|missing", re.I)
LOG_SEPARATOR = "··· end of log ···"


def log_excerpt(lines, errors=20, tail=38):
    """Error lines from the whole log (deduplicated, last ones first kept) plus the end of the log."""
    body = lines[:-tail] if len(lines) > tail else []
    seen, found = set(), []
    for ln in reversed(body):
        key = re.sub(r"0x[0-9a-fA-F]+|\d+", "#", ln.strip())
        if ln.strip() and ERROR_LINE.search(ln) and key not in seen:
            seen.add(key)
            found.append(ln)
            if len(found) >= errors:
                break
    found.reverse()
    out = found + ([LOG_SEPARATOR] if found else []) + lines[-tail:]
    return out[-60:]


def crashed(exit_code, closed_by_user):
    return exit_code not in (0, None) and not closed_by_user


def status_of(converted, window_after, seconds, exit_code, closed_by_user=False):
    if not converted:
        return "convert"
    if window_after is None:
        return "nothing"
    if seconds >= PLAYABLE_SECONDS and not crashed(exit_code, closed_by_user):
        return "playable"
    if seconds >= BOOT_SECONDS:
        return "ingame"
    return "boots"


def build(game, *, converted, window_after, seconds, exit_code, closed_by_user, anyps5, console_version,
          audit_result, log_path, error="", private_words=()):
    clean = sanitizer(private_words)
    lines = []
    if log_path and Path(log_path).is_file():
        try:
            lines = Path(log_path).read_text("utf-8", errors="replace").splitlines()
        except OSError:
            pass
    if error:
        lines += error.splitlines()[-20:]
    tail = log_excerpt(lines)
    missing = []
    stop = None
    if audit_result:
        for r in audit_result.get("records", [])[:80]:
            missing.append({"class": r.get("class"), "lib": r.get("library") or "", "name": r.get("name") or "",
                            "nid": r.get("nid") or ""})
        s = audit_result.get("stop")
        if s:
            stop = {"lib": s.get("library") or "", "name": s.get("name") or "", "nid": s.get("nid") or ""}
    version = ""
    try:
        param = json.loads((Path(game.path) / "sce_sys" / "param.json").read_text("utf-8", errors="replace"))
        version = str(param.get("contentVersion") or param.get("masterVersion") or "")
    except (OSError, ValueError):
        pass
    return {
        "v": 1,
        "title_id": game.title_id or game.key,
        "name": game.name,
        "game_version": version,
        "status": status_of(converted, window_after, seconds, exit_code, closed_by_user),
        "crashed": converted and crashed(exit_code, closed_by_user),
        "exit_code": exit_code,
        "seconds": int(seconds),
        "window_after": None if window_after is None else round(window_after, 1),
        "closed_by_user": bool(closed_by_user),
        "anyps5": anyps5,
        "console": console_version,
        "os": os_name(),
        "gpu": gpu_name(),
        "absent": (audit_result or {}).get("absent", 0),
        "stub": (audit_result or {}).get("stub", 0),
        "missing_libs": (audit_result or {}).get("missing_libs", 0),
        "missing": missing,
        "stop": stop,
        "log_tail": [clean(x)[:300] for x in tail],
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def digest(report):
    key = {k: report.get(k) for k in ("status", "anyps5", "game_version", "absent", "stub", "missing_libs", "stop")}
    key["exit"] = report.get("exit_code") if report.get("status") != "playable" else 0
    return hashlib.sha1(json.dumps(key, sort_keys=True).encode()).hexdigest()[:16]


STATUS_TEXT = {"convert": "Does not convert", "nothing": "Does not boot", "boots": "Boots",
               "ingame": "In game", "playable": "Playable"}


def body_of(report):
    a = report["anyps5"]
    lines = [
        f"**Status:** {STATUS_TEXT.get(report['status'], report['status'])}",
        f"**AnyPS5:** {a.get('channel', '')} {a.get('version', '')}  ·  **Console:** {report['console']}",
        f"**Played:** {report['seconds'] // 60} min  ·  **Exit code:** {report['exit_code']}"
        + ("  ·  closed by the user" if report["closed_by_user"] else ""),
        f"**System:** {report['os']}  ·  {report['gpu'] or 'unknown GPU'}",
        f"**Functions:** {report['absent']} missing, {report['stub']} stub, {report['missing_libs']} missing libraries",
    ]
    if report.get("stop"):
        s = report["stop"]
        lines.append(f"**Stops at:** `{s['lib']}` {s['name'] or s['nid']}")
    if report["log_tail"]:
        lines += ["", "<details><summary>Log (last lines)</summary>", "", "```", *report["log_tail"][-40:], "```",
                  "</details>"]
    lines += ["", "<!-- anyps5-report", json.dumps(report, ensure_ascii=False).replace("--", "\\u002d\\u002d"),
              "-->"]
    return "\n".join(lines)


def find_issue(token, title_id):
    q = urllib.parse.quote(f'repo:{REPO} is:issue in:title "[{title_id}]"')
    for it in _get(f"https://api.github.com/search/issues?q={q}&per_page=5", token).get("items", []):
        if it["title"].startswith(f"[{title_id}]"):
            return it["number"]
    return None


def send(token, report):
    num = find_issue(token, report["title_id"])
    body = body_of(report)
    if num:
        _post(f"https://api.github.com/repos/{REPO}/issues/{num}/comments", {"body": body}, token)
    else:
        num = _post(f"https://api.github.com/repos/{REPO}/issues",
                    {"title": f"[{report['title_id']}] {report['name']}", "body": body}, token)["number"]
    return num


def relay_url(conf=None):
    return ((conf or {}).get("compat_relay") or RELAY).rstrip("/")


def can_send(store, conf=None):
    return bool(store.token() or relay_url(conf))


def send_relay(url, report):
    return _post(url + "/report", report).get("issue")


def flush(store, log=lambda s: None, conf=None):
    token = store.token()
    relay = relay_url(conf)
    if not token and not relay:
        return 0
    sent = 0
    for f in store.queued():
        try:
            report = json.loads(f.read_text("utf-8"))
        except (OSError, ValueError):
            f.unlink(missing_ok=True)
            continue
        d = digest(report)
        if store.sent().get(report["title_id"]) == d:
            f.unlink(missing_ok=True)
            continue
        report.setdefault("reporter", store.reporter())
        try:
            if token:
                send(token, report)
            else:
                send_relay(relay, report)
        except urllib.error.HTTPError as e:
            if e.code == 401 and token:
                store.logout()
            log(f"Reporte no enviado: HTTP {e.code}")
            break
        except OSError as e:
            log(f"Reporte no enviado: {e}")
            break
        store.mark_sent(report["title_id"], d)
        f.unlink(missing_ok=True)
        sent += 1
    return sent
