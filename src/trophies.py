"""Trophies of a game: definitions from sce_sys/trophy2/trophyNN.ucp, unlocks recorded by AnyPS5 (libSceNpTrophy2)
in `_trophy/<user>_<label>.txt` ("<trophy id> <unlock tick>", ticks are microseconds since 0001-01-01)."""
import datetime
import json
from pathlib import Path

UCP_MAGIC = 0xB228C60A
GRADES = {"P": "platinum", "G": "gold", "S": "silver", "B": "bronze"}
# AnyPS5 LanguageTag(): console language index -> locale tag
LANG_TAGS = ["ja-JP", "en-US", "fr-FR", "es-ES", "de-DE", "it-IT", "nl-NL", "pt-PT", "ru-RU", "ko-KR", "zh-Hant",
             "zh-Hans", "fi-FI", "sv-SE", "da-DK", "no-NO", "pl-PL", "pt-BR", "en-GB", "tr-TR", "es-419", "ar-AE",
             "fr-CA", "cs-CZ", "hu-HU", "el-GR", "ro-RO", "th-TH", "vi-VN", "id-ID", "uk-UA"]


def read_ucp(path):
    d = Path(path).read_bytes()
    if len(d) < 0x40 or int.from_bytes(d[0:4], "big") != UCP_MAGIC:
        raise ValueError("not a trophy package")
    size = min(int.from_bytes(d[8:16], "big"), len(d))
    count, toc = int.from_bytes(d[0x10:0x14], "big"), int.from_bytes(d[0x14:0x18], "big")
    files = {}
    for i in range(min(count, 4096)):
        e = toc + 0x20 + i * 0x40
        if e + 0x40 > size:
            break
        name = d[e:e + 0x20].split(b"\0")[0].decode("utf-8", "replace")
        off, ln = int.from_bytes(d[e + 0x20:e + 0x28], "big"), int.from_bytes(d[e + 0x28:e + 0x30], "big")
        if off + ln <= size:
            files[name] = d[off:off + ln]
    return files


def _json(files, name):
    return json.loads(files[name].decode("utf-8-sig"))


def package_path(game_dir, label=0):
    p = Path(game_dir) / "sce_sys" / "trophy2" / f"trophy{label:02d}.ucp"
    return p if p.is_file() else None


def load(game_dir, language_index=1, label=0):
    """{"title", "trophies": [{"id", "grade", "hidden", "name", "detail", "icon": bytes|None}]} or None."""
    p = package_path(game_dir, label)
    if not p:
        return None
    files = read_ucp(p)
    conf = _json(files, "tropconf.json")
    lang = None
    for cand in (LANG_TAGS[language_index] if 0 <= language_index < len(LANG_TAGS) else "", "en-US",
                 conf.get("defaultLanguage", "")):
        if cand and f"tropmeta_{cand}.json" in files:
            lang = cand
            break
    meta = _json(files, f"tropmeta_{lang}.json") if lang else {}
    md = meta.get("metadata", {})
    texts = {str(t.get("id")): t for t in md.get("trophyMetadata", [])}
    out = []
    for t in conf.get("trophies", []):
        tid = str(t.get("id", ""))
        tx = texts.get(tid, {})
        out.append({"id": int(tid) if tid.isdigit() else tid, "grade": GRADES.get(t.get("grade"), "bronze"),
                    "hidden": bool(t.get("hidden")), "name": tx.get("name", f"#{tid}"), "detail": tx.get("detail", ""),
                    "icon": files.get(f"trop{tid}.png")})
    return {"title": md.get("titleMetadata", {}).get("name", ""), "trophies": out}


def unlocks(folder, label=0):
    """{trophy id: datetime} from every user record of that label in the folder."""
    res = {}
    folder = Path(folder)
    if not folder.is_dir():
        return res
    for f in folder.glob(f"*_{label}.txt"):
        try:
            for line in f.read_text("utf-8", "replace").splitlines():
                parts = line.split()
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    when = datetime.datetime(1, 1, 1) + datetime.timedelta(microseconds=int(parts[1]))
                    try:  # ticks are UTC
                        when = when.replace(tzinfo=datetime.timezone.utc).astimezone().replace(tzinfo=None)
                    except (OverflowError, ValueError, OSError):
                        pass
                    res[int(parts[0])] = when
        except OSError:
            pass
    return res


def summary(game_dir, folder):
    try:
        pkg = load(game_dir)
    except (OSError, ValueError, KeyError):
        return None
    if not pkg or not pkg["trophies"]:
        return None
    got = unlocks(folder)
    return sum(1 for t in pkg["trophies"] if t["id"] in got), len(pkg["trophies"])
