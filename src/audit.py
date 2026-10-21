import json
import os
import struct
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


def elf_identities(path):
    """SONAME and exported module names of a guest ELF module (the names other modules import it by)."""
    d = Path(path).read_bytes()
    if d[:4] != b"\x7fELF" or len(d) < 64:
        return set()
    phoff, phentsize, phnum = struct.unpack_from("<Q", d, 0x20)[0], *struct.unpack_from("<HH", d, 0x36)
    loads, dyn, dynlib = [], None, None
    for i in range(phnum):
        o = phoff + i * phentsize
        if o + 56 > len(d):
            break
        typ, _, off, vaddr, _, filesz, _, _ = struct.unpack_from("<IIQQQQQQ", d, o)
        if typ == 1:
            loads.append((vaddr, off, filesz))
        elif typ == 2:
            dyn = (off, filesz)
        elif typ == 0x61000000:
            dynlib = (off, filesz)
    if not dyn:
        return set()
    tags, names = {}, []
    for o in range(dyn[0], min(dyn[0] + dyn[1], len(d) - 15), 16):
        tag, val = struct.unpack_from("<QQ", d, o)
        if tag == 0:
            break
        if tag in (0x6100000D, 0x61000043):
            names.append(val & 0xFFFFFFFF)
        elif tag == 14:
            names.append(("so", val))
        else:
            tags.setdefault(tag, val)
    if 5 in tags:
        base = next((off + tags[5] - va for va, off, sz in loads if va <= tags[5] < va + sz), None)
    elif 0x61000035 in tags and dynlib:
        base = dynlib[0] + tags[0x61000035]
    else:
        base = None
    if base is None:
        return set()
    out = set()
    for n in names:
        n = n[1] if isinstance(n, tuple) else n
        start = base + n
        end = d.find(b"\0", start)
        if 0 <= start < len(d) and end > start:
            out.add(d[start:end].decode("utf-8", "replace"))
    return out


def _stem(name):
    name = name.lower()
    for suffix in (".debug_prx", ".suprx", ".sprx", ".prx"):
        if name.endswith(suffix) and len(name) > len(suffix):
            return name[:-len(suffix)]
    return name


def title_identities(module_dirs):
    ids = set()
    for d in module_dirs:
        d = Path(d)
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if f.is_file() and f.suffix.lower() in (".prx", ".sprx", ".suprx") and not f.name.endswith(".guest.prx"):
                try:
                    ids |= {_stem(n) for n in elf_identities(f)}
                except (OSError, struct.error):
                    pass
    return ids


def resolve_identities(result, ids):
    """The relinker also links an import to a title module by the module's own name (SONAME / exported module name,
    e.g. dra01.prx is "libdra01"); import_audit only matches file names. Count those imports as provided by the game."""
    if not ids:
        return
    try:
        data = json.loads(Path(result).read_text("utf-8"))
    except (OSError, ValueError):
        return
    by = data.setdefault("unique_by_class", {})
    changed = False
    for r in data.get("imports", []):
        if r.get("class") == "absent" and r.get("library") and _stem(r["library"]) in ids:
            r["class"] = "module"
            by["absent"] = max(0, by.get("absent", 0) - 1)
            by["module"] = by.get("module", 0) + 1
            changed = True
    for key in ("missing_libraries", "missing"):
        libs = data.get(key)
        if isinstance(libs, dict):
            for lib in [k for k in libs if _stem(k) in ids]:
                del libs[lib]
                changed = True
    if changed:
        Path(result).write_text(json.dumps(data, indent=2), "utf-8")


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
    resolve_identities(result, title_identities(module_dirs))
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
