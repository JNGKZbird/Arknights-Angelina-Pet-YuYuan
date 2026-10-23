# -*- coding: utf-8 -*-
"""First-run asset setup for the YuYuan desktop pet.

Game assets are not covered by the project's MIT license. They are
distributed separately and installed here after a verified download or a
manual zip import.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from core import BASE_DIR, THEME_ORANGE, THEME_ORANGE_LIGHT

APP_DIR = Path(BASE_DIR)
DEFAULT_MANIFEST = APP_DIR / "asset_manifest.json"
MARKER_NAME = ".assets.json"
DOWNLOAD_TMP = ".asset_download.tmp"
EXTRACT_TMP = "_asset_tmp"
USER_AGENT = "AngelinaPet-AssetInstaller/1.0"


class AssetError(Exception):
    pass


class DownloadCancelled(AssetError):
    pass


def current_manifest_path() -> Path:
    override = os.environ.get("ANGELINA_ASSET_MANIFEST")
    if override:
        return Path(override)
    candidates = [DEFAULT_MANIFEST]
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        candidates.append(Path(bundle_dir) / "asset_manifest.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return DEFAULT_MANIFEST


def current_asset_url(manifest: dict) -> str:
    return os.environ.get("ANGELINA_ASSET_URL") or str(manifest["url"])


def load_manifest(path: Path | None = None) -> dict:
    path = Path(path) if path else current_manifest_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AssetError(f"无法读取素材清单：{path}\n{exc}") from exc
    if data.get("schema") != 1:
        raise AssetError("素材清单版本不受支持。")
    if not data.get("files") or not data.get("sha256") or not data.get("url"):
        raise AssetError("素材清单缺少必要字段。")
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, dest: Path, progress_cb=None, stop_cb=None) -> Path:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with dest.open("wb") as out:
                while True:
                    if stop_cb and stop_cb():
                        raise DownloadCancelled("已取消下载。")
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if progress_cb:
                        progress_cb(done, total)
    except Exception:
        try:
            dest.unlink()
        except OSError:
            pass
        raise
    return dest


class AssetStore:
    def __init__(self, app_dir: Path, manifest: dict):
        self.app_dir = Path(app_dir)
        self.manifest = manifest
        self.files = manifest["files"]
        self.expected = {item["path"]: item for item in self.files}

    @property
    def marker(self) -> Path:
        return self.app_dir / MARKER_NAME

    def is_installed(self) -> bool:
        for item in self.files:
            path = self.app_dir / item["path"]
            try:
                if not path.is_file() or path.stat().st_size != item["size"]:
                    return False
            except OSError:
                return False
        self.write_marker()
        return True

    def write_marker(self) -> None:
        payload = {
            "asset_version": self.manifest.get("asset_version"),
            "sha256": self.manifest.get("sha256"),
            "installed_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        try:
            self.marker.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError:
            pass

    def verify_zip(self, zip_path: Path, check_hash: bool = True) -> None:
        zip_path = Path(zip_path)
        if not zip_path.is_file():
            raise AssetError(f"找不到 zip 文件：{zip_path}")
        if check_hash:
            actual = sha256_file(zip_path)
            if actual.lower() != str(self.manifest["sha256"]).lower():
                raise AssetError("zip 的 SHA-256 与素材清单不一致。")
        try:
            with zipfile.ZipFile(zip_path) as zf:
                infos = [info for info in zf.infolist() if not info.is_dir()]
                if len(infos) != len(self.files):
                    raise AssetError(
                        f"zip 文件数量不符：{len(infos)}，应为 {len(self.files)}。"
                    )
                seen: set[str] = set()
                total = 0
                for info in infos:
                    name = info.filename.replace("\\", "/")
                    if name.startswith("/") or ".." in name.split("/"):
                        raise AssetError(f"zip 内含不安全路径：{name}")
                    if name in seen:
                        raise AssetError(f"zip 内含重名文件：{name}")
                    seen.add(name)
                    expected = self.expected.get(name)
                    if expected is None:
                        raise AssetError(f"zip 内含未知文件：{name}")
                    if info.file_size != expected["size"]:
                        raise AssetError(f"文件大小不符：{name}")
                    mode = (info.external_attr >> 16) & 0o170000
                    if stat.S_ISLNK(mode):
                        raise AssetError(f"zip 内含符号链接：{name}")
                    total += info.file_size
                limit = int(self.manifest["uncompressed_size"] * 1.05) + 1048576
                if total > limit:
                    raise AssetError("zip 解压后体积异常。")
                for info in infos:
                    name = info.filename.replace("\\", "/")
                    expected_sha = self.expected[name].get("sha256")
                    if not expected_sha:
                        continue
                    digest = hashlib.sha256()
                    with zf.open(info) as src:
                        for chunk in iter(lambda: src.read(1024 * 1024), b""):
                            digest.update(chunk)
                    if digest.hexdigest().lower() != expected_sha.lower():
                        raise AssetError(f"文件内容校验失败：{name}")
        except zipfile.BadZipFile as exc:
            raise AssetError(f"不是有效的 zip 文件：{exc}") from exc

    def install_zip(self, zip_path: Path, check_hash: bool = True) -> None:
        self.verify_zip(zip_path, check_hash=check_hash)
        temp = self.app_dir / EXTRACT_TMP
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)
        temp.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(zip_path) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    name = info.filename.replace("\\", "/")
                    target = temp / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst)
            for item in self.files:
                name = item["path"]
                source = temp / name
                target = self.app_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, target)
            self.write_marker()
        finally:
            shutil.rmtree(temp, ignore_errors=True)


class DownloadThread(QThread):
    progress = Signal(int, int)
    succeeded = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, url: str, dest: Path):
        super().__init__()
        self.url = url
        self.dest = Path(dest)
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        try:
            download_file(
                self.url,
                self.dest,
                progress_cb=lambda done, total: self.progress.emit(done, total),
                stop_cb=lambda: self._stop,
            )
            self.succeeded.emit(str(self.dest))
        except DownloadCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class AssetSetupDialog(QDialog):
    def __init__(self, store: AssetStore, parent=None):
        super().__init__(parent)
        self.store = store
        self.manifest = store.manifest
        self._thread: DownloadThread | None = None
        self._download_path = APP_DIR / DOWNLOAD_TMP
        self._url = current_asset_url(self.manifest)

        self.setWindowTitle("安装角色素材")
        self.setModal(True)
        self.setFixedWidth(620)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        download_mb = self.manifest["size"] / 1048576
        install_mb = self.manifest["uncompressed_size"] / 1048576
        pet_name = self.manifest.get("pet_name", "予愿安洁莉娜")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        band = QFrame()
        band.setStyleSheet("QFrame{background:#FFF0E0;border:none;}")
        band_layout = QHBoxLayout(band)
        band_layout.setContentsMargins(28, 22, 28, 22)
        band_layout.setSpacing(16)

        icon = QLabel()
        icon.setFixedSize(64, 64)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("background:#FFFFFF;border-radius:14px;")
        icon_path = APP_DIR / "assets" / "avatar.ico"
        pix = QIcon(str(icon_path)).pixmap(64, 64) if icon_path.exists() else QPixmap()
        if not pix.isNull():
            icon.setPixmap(pix)
        else:
            icon.setText("予")
            icon.setStyleSheet(
                "background:#FFFFFF;border-radius:14px;color:#E8913A;"
                "font-size:24px;font-weight:600;"
            )
        band_layout.addWidget(icon)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(4)
        name_label = QLabel("酸橙味的信")
        name_label.setStyleSheet("font-size:20px;font-weight:600;color:#1F2329;")
        pet_label = QLabel(f"{pet_name} · 角色素材")
        pet_label.setStyleSheet("font-size:12px;color:#6B7280;")
        types_label = QLabel("Spine 动画 · 中文/日文语音 · 技能图标")
        types_label.setStyleSheet("font-size:11px;color:#9AA1AD;")
        brand_text.addWidget(name_label)
        brand_text.addWidget(pet_label)
        brand_text.addWidget(types_label)
        band_layout.addLayout(brand_text, 1)
        root.addWidget(band)

        content = QFrame()
        content.setStyleSheet("QFrame{background:#FFFFFF;border:none;}")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 22)
        layout.setSpacing(14)

        headline = QLabel("给安洁莉娜写封信，\n她会来到你身边的。")
        headline.setWordWrap(True)
        headline.setStyleSheet("font-size:24px;font-weight:600;color:#1F2329;")
        layout.addWidget(headline)

        body = QLabel(
            "Spine 模型、语音与角色图标不随应用分发。下载一次，之后就能正常陪在你身边。"
        )
        body.setWordWrap(True)
        body.setStyleSheet("font-size:14px;color:#3F454D;")
        layout.addWidget(body)

        info = QFrame()
        info.setStyleSheet("QFrame{background:#FFF4EA;border:none;border-radius:10px;}")
        info_layout = QHBoxLayout(info)
        info_layout.setContentsMargins(14, 12, 14, 12)
        info_layout.setSpacing(20)

        left = QVBoxLayout()
        left.setSpacing(2)
        left_label = QLabel("下载")
        left_label.setStyleSheet("font-size:11px;color:#9AA1AD;")
        left_value = QLabel(f"{download_mb:.1f} MB")
        left_value.setStyleSheet("font-size:18px;font-weight:600;color:#1F2329;")
        left.addWidget(left_label)
        left.addWidget(left_value)
        info_layout.addLayout(left, 1)

        divider = QFrame()
        divider.setFixedWidth(1)
        divider.setFixedHeight(32)
        divider.setStyleSheet("background:#E4D2BC;border:none;")
        info_layout.addWidget(divider)

        right = QVBoxLayout()
        right.setSpacing(2)
        right_label = QLabel("安装后")
        right_label.setStyleSheet("font-size:11px;color:#9AA1AD;")
        right_value = QLabel(f"{install_mb:.1f} MB")
        right_value.setStyleSheet("font-size:18px;font-weight:600;color:#1F2329;")
        right.addWidget(right_label)
        right.addWidget(right_value)
        info_layout.addLayout(right, 1)
        layout.addWidget(info)

        source = QLabel("来源：GitHub Releases（官方素材库） · 整包 SHA-256 校验")
        source.setStyleSheet("font-size:11px;color:#9AA1AD;")
        layout.addWidget(source)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"font-size:13px;color:{THEME_ORANGE};")
        layout.addWidget(self.status)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        self.error_label.setStyleSheet(
            "background:#FFF1F0;color:#B3261E;border:1px solid #FAD2CF;"
            "border-radius:8px;padding:10px;font-size:13px;"
        )
        layout.addWidget(self.error_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setStyleSheet(
            "QProgressBar{background:#FFF0E0;border:none;border-radius:3px;}"
            f"QProgressBar::chunk{{background:{THEME_ORANGE};border-radius:3px;}}"
        )
        self.progress.hide()
        layout.addWidget(self.progress)

        self.download_btn = QPushButton("下载并安装")
        self.download_btn.setStyleSheet(
            f"QPushButton{{background:{THEME_ORANGE};color:white;border:none;"
            "padding:12px;border-radius:10px;font-size:15px;font-weight:600;}}"
            f"QPushButton:hover{{background:{THEME_ORANGE_LIGHT};}}"
            "QPushButton:disabled{background:#CCC;}"
        )
        layout.addWidget(self.download_btn)

        self.import_btn = QPushButton("手动导入官方 zip")
        self.import_btn.setStyleSheet(
            "QPushButton{background:#FFFFFF;color:#3F454D;border:1px solid #E4D2BC;"
            "padding:10px;border-radius:10px;font-size:14px;}"
            "QPushButton:hover{background:#FFF9F3;}"
        )
        layout.addWidget(self.import_btn)

        hint = QLabel("手动导入同样校验整包 SHA-256；不是官方包会被拒绝")
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size:11px;color:#9AA1AD;")
        layout.addWidget(hint)

        self.cancel_btn = QPushButton("取消下载")
        self.cancel_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#6B7280;border:none;font-size:13px;}"
        )
        self.cancel_btn.hide()
        cancel_row = QHBoxLayout()
        cancel_row.addStretch(1)
        cancel_row.addWidget(self.cancel_btn)
        layout.addLayout(cancel_row)

        footer_row = QHBoxLayout()
        footer_row.addStretch(1)
        self.exit_btn = QPushButton("退出")
        self.exit_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#9AA1AD;border:none;font-size:13px;}"
        )
        footer_row.addWidget(self.exit_btn)
        layout.addLayout(footer_row)

        copyright_label = QLabel("素材版权归上海鹰角网络有限公司所有 · 仅供个人非商业使用")
        copyright_label.setWordWrap(True)
        copyright_label.setStyleSheet("font-size:11px;color:#B6BCC7;")
        layout.addWidget(copyright_label)

        root.addWidget(content)

        self.download_btn.clicked.connect(self.start_download)
        self.import_btn.clicked.connect(self.import_zip)
        self.cancel_btn.clicked.connect(self.cancel_download)
        self.exit_btn.clicked.connect(self.reject)
        self.adjustSize()

    def _set_busy(self, busy: bool) -> None:
        self.download_btn.setEnabled(not busy)
        self.import_btn.setEnabled(not busy)
        self.exit_btn.setEnabled(not busy)
        self.cancel_btn.setVisible(busy)
        self.progress.setVisible(busy)
        self.adjustSize()

    def _set_error(self, text: str) -> None:
        self.error_label.setText(text)
        self.error_label.setVisible(bool(text))
        self.adjustSize()

    def _clear_error(self) -> None:
        self._set_error("")

    def _reset_status(self, text: str = "") -> None:
        self.status.setText(text)
        self._clear_error()
        self._set_busy(False)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = self.frameGeometry()
            geo.moveCenter(screen.availableGeometry().center())
            self.move(geo.topLeft())

    def start_download(self) -> None:
        if self._thread and self._thread.isRunning():
            return
        self._clear_error()
        self.status.setText("正在连接下载源…")
        self.progress.setValue(0)
        self._set_busy(True)
        self._thread = DownloadThread(self._url, self._download_path)
        self._thread.progress.connect(self._on_progress)
        self._thread.succeeded.connect(self._on_downloaded)
        self._thread.failed.connect(self._on_download_failed)
        self._thread.cancelled.connect(self._on_download_cancelled)
        self._thread.start()

    def _on_progress(self, done: int, total: int) -> None:
        if total <= 0:
            total = int(self.manifest["size"])
        if total > 0:
            self.progress.setValue(min(100, int(done * 100 / total)))
            self.status.setText(
                f"正在下载… {done / 1048576:.1f} / {total / 1048576:.1f} MB"
            )

    def cancel_download(self) -> None:
        if self._thread and self._thread.isRunning():
            self.status.setText("正在取消…")
            self.cancel_btn.setEnabled(False)
            self._thread.stop()

    def _on_download_cancelled(self) -> None:
        self.cancel_btn.setEnabled(True)
        self._reset_status("已取消下载。")

    def _on_download_failed(self, message: str) -> None:
        self.cancel_btn.setEnabled(True)
        self.status.setText("")
        self._set_busy(False)
        self._set_error(f"下载失败：{message}")

    def _on_downloaded(self, path: str) -> None:
        self._set_busy(False)
        self.status.setText("正在校验并安装…")
        self._clear_error()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.store.install_zip(Path(path), check_hash=True)
        except Exception as exc:
            self.status.setText("")
            self._set_error(f"安装失败：{exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()
            try:
                Path(path).unlink()
            except OSError:
                pass
        self.accept()

    def import_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择官方素材 zip", str(APP_DIR), "Zip 文件 (*.zip)"
        )
        if not path:
            return
        self._clear_error()
        self.status.setText("正在校验并安装…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.store.install_zip(Path(path), check_hash=True)
        except Exception as exc:
            self.status.setText("")
            self._set_error(f"导入失败：{exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.accept()

    def _stop_thread(self) -> bool:
        if self._thread and self._thread.isRunning():
            self._thread.stop()
            if not self._thread.wait(5000):
                return False
        self._thread = None
        return True

    def reject(self) -> None:
        if self._thread and self._thread.isRunning():
            answer = QMessageBox.question(
                self, "取消下载", "下载还在进行，确定取消并退出吗？"
            )
            if answer != QMessageBox.Yes:
                return
            if not self._stop_thread():
                self.status.setText("正在取消下载，请稍候…")
                return
        self._thread = None
        try:
            self._download_path.unlink()
        except OSError:
            pass
        super().reject()


def ensure_assets() -> bool:
    try:
        manifest = load_manifest()
    except AssetError as exc:
        QMessageBox.critical(None, "素材清单错误", str(exc))
        return False
    store = AssetStore(APP_DIR, manifest)
    if store.is_installed():
        return True
    dialog = AssetSetupDialog(store)
    return dialog.exec() == QDialog.Accepted and store.is_installed()
