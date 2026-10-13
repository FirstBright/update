"""Independent Windows topmost windows; no network or reservation calls."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def launch_alert(details: dict) -> bool:
    if sys.platform != "win32":
        return False
    try:
        # A separate GUI process keeps payment notifications and browser updates moving.
        executable = Path(sys.executable).with_name("pythonw.exe")
        if not executable.exists():
            executable = Path(sys.executable)
        process = subprocess.Popen(
            [str(executable), str(Path(__file__).resolve())],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        process.communicate(json.dumps(details, ensure_ascii=False).encode("utf-8"), timeout=2)
        return process.returncode == 0
    except subprocess.TimeoutExpired:
        # The window remains open until acknowledged; it need not finish now.
        return True
    except Exception as exc:
        print(f"[알림 경고] Windows 알림을 열지 못했습니다: {exc}")
        return False


def monitor_areas():
    import ctypes
    from ctypes import wintypes

    areas = []
    callback_type = ctypes.WINFUNCTYPE(
        wintypes.BOOL, wintypes.HANDLE, wintypes.HDC,
        ctypes.POINTER(wintypes.RECT), wintypes.LPARAM,
    )

    @callback_type
    def collect(monitor, dc, rect, data):
        r = rect.contents
        areas.append((r.left, r.top, r.right, r.bottom))
        return True

    ctypes.windll.user32.EnumDisplayMonitors(None, None, collect, 0)
    return areas


def show_alert(details: dict, *, demo: bool = False) -> None:
    import ctypes
    import tkinter as tk
    import winsound

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    root.withdraw()
    areas = monitor_areas() or [(0, 0, root.winfo_screenwidth(), root.winfo_screenheight())]
    background = "#1757a6" if demo else "#087443"
    for left, top, right, bottom in areas:
        window = tk.Toplevel(root)
        window.title("알림 미리보기 · 실제 예약 아님" if demo else "코레일 예약 성공 · 결제 필요")
        width, height = min(1100, right - left - 80), min(680, bottom - top - 100)
        window.geometry(f"{width}x{height}")
        window.configure(bg=background)
        window.attributes("-topmost", True)
        window.protocol("WM_DELETE_WINDOW", root.destroy)
        for text, size, bold in [
            ("알림 미리보기" if demo else "예약 성공!", 64, True),
            ("실제 예약이 아닙니다" if demo else "지금 코레일 앱에서 결제하세요", 30, True),
            (f"{details.get('route', '')}  {details.get('departure', '')}", 26, False),
            (f"결제 마감: {details.get('deadline', '앱에서 확인하세요')}", 30, True),
            ("아직 미결제 상태입니다. 기한 내 미결제 시 자동 취소됩니다.", 18, False),
        ]:
            tk.Label(window, text=text, font=("Malgun Gothic", size, "bold" if bold else "normal"),
                     bg=background, fg="white", wraplength=width - 60).pack(pady=12)
        tk.Button(window, text="확인 · 모든 모니터의 알림 닫기", command=root.destroy,
                  font=("Malgun Gothic", 22, "bold"), padx=25, pady=12).pack(pady=16)
        window.update_idletasks()
        # SetWindowPos supports monitors positioned left/above the primary display.
        user32 = ctypes.windll.user32
        user32.GetAncestor.restype = ctypes.c_void_p
        handle = user32.GetAncestor(ctypes.c_void_p(window.winfo_id()), 2)
        user32.SetWindowPos(
            ctypes.c_void_p(handle), ctypes.c_void_p(-1),
            left + (right - left - width) // 2, top + (bottom - top - height) // 2,
            0, 0, 0x0001 | 0x0010,
        )
        window.lift()
    winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
    if demo:
        root.after(12000, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    if "--demo" in sys.argv:
        show_alert({"route": "동탄 → 익산", "departure": "09:30", "deadline": "미리보기"}, demo=True)
    else:
        show_alert(json.loads(sys.stdin.buffer.read().decode("utf-8")))
