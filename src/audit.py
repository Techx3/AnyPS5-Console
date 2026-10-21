import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_support = {}


def python_exe():
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe" and (exe.parent / "python.exe").is_file():
        return str(exe.parent / "python.exe")
    return str(exe)


def supports_registry(relinker):
    key = str(relinker)
    if key not in _support:
        try:
            p = subprocess.run([key, "--help"], capture_output=True, text=True, errors="replace", timeout=30,
                               creationflags=NO_WINDOW)
            _support[key] = "--registry" in (p.stdout + p.stderr)
        except (OSError, subprocess.SubprocessError):
            _support[key] = False
    return _support[key]


def names_db(tools_dir, cache):
    cache = Path(cache)
    if cache.is_file() and cache.stat().st_size > 0:
        return cache
    try:
        sys.path.insert(0, str(tools_dir))
        import nid_names
        url = nid_names.DB_URL
    except Exception:
        return None
    finally:
        if sys.path and sys.path[0] == str(tools_dir):
            sys.path.pop(0)
    try:
        tmp = cache.with_suffix(".tmp")
        urllib.request.urlretrieve(url, str(tmp))
        tmp.replace(cache)
        return cache
    except Exception:
        return None


def registries(out):
    return sorted(p for p in Path(out).glob("*.registry.json") if not p.name.endswith(".needed.json"))


def _run_inprocess(tools, argv):
    import contextlib
    import importlib.util
    import io
    buf = io.StringIO()
    saved = {k: sys.modules.pop(k) for k in ("nid_names", "progress") if k in sys.modules}
    sys.path.insert(0, str(tools))
    try:
        spec = importlib.util.spec_from_file_location("anyps5_import_audit", tools / "import_audit.py")
        module = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            spec.loader.exec_module(module)
            try:
                code = module.main(argv)
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 2
            except Exception as e:
                print(f"FAIL: {e}")
                code = 2
    finally:
        sys.path.remove(str(tools))
        for k in ("nid_names", "progress"):
            sys.modules.pop(k, None)
        sys.modules.update(saved)
    return code, buf.getvalue()


def run(out, libs_dir, source_root, module_dirs, names, log):
    out = Path(out).resolve()
    libs_dir = Path(libs_dir).resolve()
    regs = registries(out)
    if not regs:
        return None
    tools = Path(source_root) / "tools"
    script = tools / "import_audit.py"
    if not script.is_file():
        return None
    result = out / "audit.json"
    cmd = [python_exe(), str(script), *map(str, regs), "--libs", str(libs_dir), "--json", str(result)]
    prx = Path(source_root) / "core" / "libs" / "prx"
    if prx.is_dir():
        cmd += ["--source", str(prx)]
    for d in module_dirs:
        if Path(d).is_dir():
            cmd += ["--modules", str(Path(d).resolve())]
    if names:
        cmd += ["--names", str(Path(names).resolve())]
    code, text = _run_inprocess(tools, cmd[2:])
    (out / "audit.txt").write_text(text, "utf-8")
    if code == 2 or not result.is_file():
        log("Auditoría de funciones falló: " + text.strip()[-300:])
        return None
    return load(out)


def load(out):
    try:
        data = json.loads((Path(out) / "audit.json").read_text("utf-8"))
    except (OSError, ValueError):
        return None
    by = data.get("unique_by_class", {})
    records = [r for r in data.get("imports", []) if r.get("class") in ("absent", "stub")]
    records.sort(key=lambda r: (r["class"] != "absent", r.get("library") or "", r.get("name") or r.get("nid") or ""))
    stop = next((s for s in data.get("stops", []) if s.get("nid")), None)
    return {"absent": by.get("absent", 0), "stub": by.get("stub", 0), "implemented": by.get("implemented", 0),
            "missing_libs": len(data.get("missing_libraries", data.get("missing", {})) or {}),
            "records": records, "stop": stop, "commit": data.get("source_commit", "")}


def label(r):
    name = r.get("name")
    return f"{name} ({r['nid']})" if name else r["nid"]
