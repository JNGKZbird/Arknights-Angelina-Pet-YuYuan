# Double-click or run via create_shortcut.bat
import os, subprocess, ctypes
from ctypes import wintypes

# Get desktop path via Windows API (no hardcoded paths)
buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
ctypes.windll.shell32.SHGetFolderPathW(None, 0, None, 0, buf)
desktop = buf.value

script_dir = os.path.dirname(os.path.abspath(__file__))
lnk = os.path.join(desktop, "Angelina-pet-YuYuan.lnk")
target = os.path.join(script_dir, "启动桌宠.bat")
icon = os.path.join(script_dir, "assets", "avatar.ico")

ps = (
    f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
    f"$s.TargetPath='{target}';"
    f"$s.IconLocation='{icon},0';"
    f"$s.WorkingDirectory='{script_dir}';"
    f"$s.Save()"
)
r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
if r.returncode == 0:
    print("Desktop shortcut created: Angelina-pet-YuYuan")
else:
    print("Failed to create shortcut.")
input("Press Enter to exit...")
