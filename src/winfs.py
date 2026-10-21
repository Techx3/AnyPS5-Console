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

    def fullscreen_when_ready(exe_path, ref_hwnd, timeout=90, stop=lambda: False):
        end = time.time() + timeout
        while time.time() < end and not stop():
            wins = _windows_of(exe_path)
            if wins:
                time.sleep(0.4)
                for hwnd in wins:
                    make_borderless(hwnd, ref_hwnd)
                return True
            time.sleep(0.5)
        return False
else:
    def fullscreen_when_ready(exe_path, ref_hwnd, timeout=90, stop=lambda: False):
        return False
