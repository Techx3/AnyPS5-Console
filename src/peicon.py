import struct
from pathlib import Path


def _rva_to_off(sections, rva):
    for va, vsize, raw, rsize in sections:
        if va <= rva < va + max(vsize, rsize):
            return rva - va + raw
    return None


def exe_icon(path):
    data = Path(path).read_bytes()
    if data[:2] != b"MZ":
        return None
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        return None
    nsec, = struct.unpack_from("<H", data, pe + 6)
    optsize, = struct.unpack_from("<H", data, pe + 20)
    opt = pe + 24
    magic, = struct.unpack_from("<H", data, opt)
    dd = opt + (96 if magic == 0x10B else 112)
    rsrc_rva, rsrc_size = struct.unpack_from("<II", data, dd + 2 * 8)
    if not rsrc_rva:
        return None
    sec = opt + optsize
    sections = []
    for i in range(nsec):
        o = sec + i * 40
        vsize, va, rsize, raw = struct.unpack_from("<IIII", data, o + 8)
        sections.append((va, vsize, raw, rsize))
    base = _rva_to_off(sections, rsrc_rva)
    if base is None:
        return None

    def entries(off):
        named, ids = struct.unpack_from("<HH", data, off + 12)
        out = []
        for i in range(named + ids):
            name, target = struct.unpack_from("<II", data, off + 16 + i * 8)
            out.append((name, target))
        return out

    def leaf(target):
        while target & 0x80000000:
            sub = entries(base + (target & 0x7FFFFFFF))
            if not sub:
                return None
            target = sub[0][1]
        rva, size = struct.unpack_from("<II", data, base + target)
        off = _rva_to_off(sections, rva)
        return data[off:off + size] if off is not None else None

    types = {name: target for name, target in entries(base) if not name & 0x80000000}
    if 14 not in types or 3 not in types:
        return None
    groups = entries(base + (types[14] & 0x7FFFFFFF))
    if not groups:
        return None
    grp = leaf(groups[0][1])
    icons = {}
    for name, target in entries(base + (types[3] & 0x7FFFFFFF)):
        icons[name] = target
    if not grp or len(grp) < 6:
        return None
    count, = struct.unpack_from("<H", grp, 4)
    best = None
    for i in range(count):
        w, h, colors, _, planes, bits, size, rid = struct.unpack_from("<BBBBHHIH", grp, 6 + i * 14)
        w = w or 256
        score = (w, bits)
        if rid in icons and (best is None or score > best[0]):
            best = (score, rid, grp[6 + i * 14:6 + i * 14 + 12])
    if not best:
        return None
    img = leaf(icons[best[1]])
    if not img:
        return None
    if img[:8] == b"\x89PNG\r\n\x1a\n":
        return "png", img
    entry = best[2]
    ico = struct.pack("<HHH", 0, 1, 1) + entry[:8] + struct.pack("<II", len(img), 22) + img
    return "ico", ico
