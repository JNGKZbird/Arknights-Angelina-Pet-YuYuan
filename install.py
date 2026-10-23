# -*- coding: utf-8 -*-
"""予愿安洁莉娜桌宠安装器：复制程序到本机 + 创建桌面快捷方式。

打包方式：PyInstaller --onefile --add-data "dist/予愿安洁莉娜桌宠;桌宠" install.py
安装位置：%LOCALAPPDATA%\Programs\酸橙味的信（无需管理员权限，
settings.json 等用户数据保存在程序目录旁，可写）。
"""
import os
import sys
import shutil
import subprocess
import ctypes
from ctypes import wintypes

APP_NAME = "酸橙味的信"
EXE_NAME = "酸橙味的信.exe"


def _install_dir():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "Programs", APP_NAME)


def _create_shortcut(target_dir):
    buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0, None, 0, buf)
    desktop = buf.value
    lnk = os.path.join(desktop, APP_NAME + ".lnk")
    exe = os.path.join(target_dir, EXE_NAME)
    ps = (
        f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
        f"$s.TargetPath='{exe}';"
        f"$s.IconLocation='{exe},0';"
        f"$s.WorkingDirectory='{target_dir}';"
        f"$s.Save()"
    )
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True)
    return r.returncode == 0


def _msgbox(text):
    ctypes.windll.user32.MessageBoxW(None, text, APP_NAME, 0x40)


def main():
    target = _install_dir()
    src = os.path.join(
        getattr(sys, "_MEIPASS",
                os.path.dirname(os.path.abspath(__file__))), "桌宠")
    if not os.path.isdir(src):
        _msgbox("安装数据缺失，安装失败。")
        return
    try:
        # dirs_exist_ok=True：重复安装时覆盖程序、保留用户数据（settings.json 等）
        shutil.copytree(src, target, dirs_exist_ok=True)
    except Exception as e:
        _msgbox(f"安装失败：{e}")
        return
    if _create_shortcut(target):
        _msgbox(f"安装完成！\n\n桌面已生成「{APP_NAME}」快捷方式，双击即可开始。")
    else:
        _msgbox(f"安装完成（快捷方式创建失败）。\n\n请到 {target} 手动运行。")


if __name__ == "__main__":
    main()
