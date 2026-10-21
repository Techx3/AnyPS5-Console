import os
import time

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    GWL_STYLE = -16
    WS_POPUP = 0x80000000
    WS_VISIBLE = 0x10000000
    WS_OVERLAPPEDWINDOW = 0x00CF0000
    SWP_FRAMECHANGED = 0x0020
    SWP_SHOWWINDOW = 0x0040
    HWND_TOP = 0
    MONITOR_DEFAULTTONEAREST = 2
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
    user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    user32.MonitorFromWindow.restype = wintypes.HMONITOR
    user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MONITORINFO)]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    ctypes.c_int, wintypes.UINT]

    def _process_path(pid):
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return buf.value
            return ""
        finally:
            kernel32.CloseHandle(h)

    def _windows_of(exe_path):
        target = os.path.normcase(os.path.abspath(exe_path))
        found = []

        def cb(hwnd, _):
            if not user32.IsWindowVisible(hwnd) or user32.GetWindowTextLengthW(hwnd) == 0:
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            path = _process_path(pid.value)
            if path and os.path.normcase(path) == target:
                found.append(hwnd)
            return True

        user32.EnumWindows(EnumWindowsProc(cb), 0)
        return found

    def _monitor_rect(ref_hwnd):
        mon = user32.MonitorFromWindow(ref_hwnd, MONITOR_DEFAULTTONEAREST)
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(mon, ctypes.byref(info)):
            return None
        r = info.rcMonitor
        return r.left, r.top, r.right - r.left, r.bottom - r.top

    def make_borderless(hwnd, ref_hwnd):
        rect = _monitor_rect(ref_hwnd or hwnd)
        if not rect:
            return False
        cur = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(cur))
        if (cur.left, cur.top, cur.right - cur.left, cur.bottom - cur.top) == rect:
            return True
        style = user32.GetWindowLongPtrW(hwnd, GWL_STYLE)
        user32.SetWindowLongPtrW(hwnd, GWL_STYLE, (style & ~WS_OVERLAPPEDWINDOW) | WS_POPUP | WS_VISIBLE)
        user32.SetWindowPos(hwnd, HWND_TOP, rect[0], rect[1], rect[2], rect[3], SWP_FRAMECHANGED | SWP_SHOWWINDOW)
        user32.SetForegroundWindow(hwnd)
        return True

    def _covers_monitor(hwnd, ref_hwnd):
        rect = _monitor_rect(ref_hwnd or hwnd)
        cur = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(cur))
        return rect is not None and (cur.left, cur.top, cur.right - cur.left, cur.bottom - cur.top) == rect

    VK_F11, SCAN_F11, KEYEVENTF_KEYUP = 0x7A, 0x57, 0x0002

    def _press_f11(hwnd):
        """AnyPS5 toggles fullscreen (SDL fullscreen desktop) with F11 when its window has the keyboard focus."""
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.25)
        if user32.GetForegroundWindow() != hwnd:
            return False
        user32.keybd_event(VK_F11, SCAN_F11, 0, 0)
        time.sleep(0.05)
        user32.keybd_event(VK_F11, SCAN_F11, KEYEVENTF_KEYUP, 0)
        return True

    def fullscreen_when_ready(exe_path, ref_hwnd, timeout=90, stop=lambda: False):
        """Make the game fullscreen without changing AnyPS5: its own F11 toggle first, borderless window as fallback."""
        end = time.time() + timeout
        while time.time() < end and not stop():
            wins = _windows_of(exe_path)
            if wins:
                time.sleep(1.0)  # let the game finish creating its window and swapchain
                for hwnd in _windows_of(exe_path) or wins:
                    if _covers_monitor(hwnd, ref_hwnd):
                        continue  # already fullscreen
                    for _ in range(2):
                        if _press_f11(hwnd):
                            time.sleep(1.2)
                            if _covers_monitor(hwnd, ref_hwnd):
                                break
                    else:
                        make_borderless(hwnd, ref_hwnd)
                return True
            time.sleep(0.5)
        return False

    def focus(exe_path):
        for hwnd in _windows_of(exe_path):
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
            return True
        return False

    def has_window(exe_path):
        return bool(_windows_of(exe_path))

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.HDC,
                             ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                                ctypes.c_void_p, wintypes.UINT]
    user32.GetDC.restype = wintypes.HDC
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user32.GetForegroundWindow.restype = wintypes.HWND
    SRCCOPY = 0x00CC0020

    def _grab(hwnd, w, h, from_screen):
        src = user32.GetDC(None if from_screen else hwnd)
        mem = gdi32.CreateCompatibleDC(src)
        bmp = gdi32.CreateCompatibleBitmap(src, w, h)
        old = gdi32.SelectObject(mem, bmp)
        try:
            if from_screen:
                pt = wintypes.POINT(0, 0)
                user32.ClientToScreen(hwnd, ctypes.byref(pt))
                ok = gdi32.BitBlt(mem, 0, 0, w, h, src, pt.x, pt.y, SRCCOPY)
            else:
                ok = user32.PrintWindow(hwnd, mem, 3)  # PW_CLIENTONLY | PW_RENDERFULLCONTENT
            if not ok:
                return None
            info = BITMAPINFOHEADER()
            info.biSize = ctypes.sizeof(BITMAPINFOHEADER)
            info.biWidth, info.biHeight, info.biPlanes, info.biBitCount = w, -h, 1, 32
            buf = ctypes.create_string_buffer(w * h * 4)
            if not gdi32.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(info), 0):
                return None
            return buf.raw
        finally:
            gdi32.SelectObject(mem, old)
            gdi32.DeleteObject(bmp)
            gdi32.DeleteDC(mem)
            user32.ReleaseDC(None if from_screen else hwnd, src)

    def _blank(data):
        step = 4 * 97
        return not data or max(max(data[c::step]) for c in range(3)) < 8  # B, G, R only; alpha is unreliable

    def capture(exe_path):
        """Game window client area as (BGRA bytes, width, height), only that window; None if not possible."""
        best = None
        for hwnd in _windows_of(exe_path):
            r = wintypes.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(r))
            if r.right * r.bottom > (best[1] * best[2] if best else 0):
                best = (hwnd, r.right, r.bottom)
        if not best or best[1] < 64 or best[2] < 64:
            return None
        hwnd, w, h = best
        data = _grab(hwnd, w, h, False)
        if (data is None or _blank(data)) and user32.GetForegroundWindow() == hwnd:
            data = _grab(hwnd, w, h, True)  # the game is on top, so the screen area is the game
        if data is None or _blank(data):
            return None
        return data, w, h
else:
    def focus(exe_path):
        return False

    def has_window(exe_path):
        return False

    def capture(exe_path):
        return None

    def fullscreen_when_ready(exe_path, ref_hwnd, timeout=90, stop=lambda: False):
        return False
