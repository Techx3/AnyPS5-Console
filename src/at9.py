"""ATRAC9 (.at9) to WAV, for the sce_sys/snd0.at9 theme of each game. Uses LibAtrac9 (native/libatrac9)."""
import ctypes
import os
import struct
import sys
import wave
from pathlib import Path

import paths

_lib = None


class CodecInfo(ctypes.Structure):
    _fields_ = [("channels", ctypes.c_int), ("channelConfigIndex", ctypes.c_int), ("samplingRate", ctypes.c_int),
                ("superframeSize", ctypes.c_int), ("framesInSuperframe", ctypes.c_int), ("frameSamples", ctypes.c_int),
                ("wlength", ctypes.c_int), ("configData", ctypes.c_ubyte * 4)]


def library():
    global _lib
    if _lib is not None:
        return _lib or None
    name = "atrac9.dll" if os.name == "nt" else "libatrac9.so"
    for folder in (paths.RES / "native", paths.CODE / "native", paths.CODE.parent / "native", Path(sys.executable).parent):
        p = folder / name
        if p.is_file():
            try:
                lib = ctypes.CDLL(str(p))
                lib.Atrac9GetHandle.restype = ctypes.c_void_p
                lib.Atrac9ReleaseHandle.argtypes = [ctypes.c_void_p]
                lib.Atrac9InitDecoder.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
                lib.Atrac9Decode.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_short),
                                             ctypes.POINTER(ctypes.c_int), ctypes.c_int]
                lib.Atrac9GetCodecInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(CodecInfo)]
                _lib = lib
                return lib
            except OSError:
                pass
    _lib = False
    return None


def available():
    return library() is not None


def _chunks(data):
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    pos, out = 12, {}
    while pos + 8 <= len(data):
        cid, size = data[pos:pos + 4], struct.unpack_from("<I", data, pos + 4)[0]
        out.setdefault(cid, data[pos + 8:pos + 8 + size])
        pos += 8 + size + (size & 1)
    return out


def decode(at9_path, wav_path, max_seconds=60):
    lib = library()
    if lib is None:
        raise RuntimeError("LibAtrac9 not found")
    ch = _chunks(Path(at9_path).read_bytes())
    fmt, data = ch.get(b"fmt "), ch.get(b"data")
    if not fmt or not data or len(fmt) < 48 or struct.unpack_from("<H", fmt, 0)[0] != 0xFFFE:
        raise ValueError("not an ATRAC9 file")
    config = bytes(fmt[44:48])
    total = delay = 0
    fact = ch.get(b"fact")
    if fact and len(fact) >= 4:
        total = struct.unpack_from("<I", fact, 0)[0]
        if len(fact) >= 12:
            delay = struct.unpack_from("<I", fact, 8)[0]
    h = lib.Atrac9GetHandle()
    try:
        if lib.Atrac9InitDecoder(h, config) != 0:
            raise ValueError("unsupported ATRAC9 configuration")
        info = CodecInfo()
        lib.Atrac9GetCodecInfo(h, ctypes.byref(info))
        nch, frame = info.channels, info.frameSamples
        pcm = (ctypes.c_short * (frame * nch))()
        used = ctypes.c_int()
        out = bytearray()
        limit = (total or 1 << 62) + delay
        limit = min(limit, delay + max_seconds * info.samplingRate)
        produced, pos = 0, 0
        buf = bytes(data)
        while pos + info.superframeSize <= len(buf) and produced < limit:
            sf = buf[pos:pos + info.superframeSize]
            off = 0
            for _ in range(info.framesInSuperframe):
                if lib.Atrac9Decode(h, sf[off:], pcm, ctypes.byref(used), 0) != 0:
                    raise ValueError("ATRAC9 decode error")
                off += used.value
                out += bytes(pcm)
                produced += frame
            pos += info.superframeSize
        bps = 2 * nch
        out = out[delay * bps:limit * bps]
        with wave.open(str(wav_path), "wb") as w:
            w.setnchannels(nch)
            w.setsampwidth(2)
            w.setframerate(info.samplingRate)
            w.writeframes(bytes(out))
        return wav_path
    finally:
        lib.Atrac9ReleaseHandle(h)
