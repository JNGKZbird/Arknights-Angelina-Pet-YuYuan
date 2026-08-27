# PetWindow - main desktop pet window
import os, sys, json, random, datetime, time, math, ctypes
from ctypes import wintypes
from PySide6.QtCore import Qt, QTimer, QPoint, QRect, QRectF, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QFontMetrics, QGuiApplication, QIcon, QImage, QPainter
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QSystemTrayIcon, QVBoxLayout, QWidget
from PySide6.QtMultimedia import QSoundEffect
from core import *
from widgets import SubtitleWindow, ChatInputWindow, _frameless_title_bar
from chat import ChatWorker, ChatterWorker
from dialogs import HistoryWindow, SettingsDialog, ContextWindow, MemoryWindow, OperatorManager, OperatorWindow
import numpy as np
from PIL import Image as PILImage
from spine38.pet_engine import SpinePet, STATE_MAP, CHAR_SCALE

# Module-level asset loading
_initial_settings = load_settings()
ACTIVE_PET = resolve_active_pet(_initial_settings)
FRAMES_DIR = os.path.join(PETS_DIR, ACTIVE_PET, "frames")
MANIFEST_PATH = os.path.join(PETS_DIR, ACTIVE_PET, "manifest.json")
with open(MANIFEST_PATH, encoding="utf-8") as _f:
    MANIFEST = json.load(_f)
FPS = int(MANIFEST["fps"])
FULL_SIZE = MANIFEST["size"]
RENDER_SCALE = 0.5
SPINE_DIR = os.path.join(PETS_DIR, ACTIVE_PET, "spine")


class PetWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setMouseTracking(True)

        self.settings = load_settings()
        self.pet_name = ACTIVE_PET
        pet_states = self.settings.get("pet_states") or {}
        pet_state = pet_states.get(self.pet_name, {})
        self.pet_state = pet_state
        self.speed = float(
            pet_state.get("speed", self.settings.get("speed", 1.0))
        )
        self.move_speed_level = int(self.settings.get("move_speed", DEFAULT_MOVE_SPEED_LEVEL))
        self.auto_hide_fullscreen = bool(
            self.settings.get("auto_hide_fullscreen", False)
        )
        self.locked = bool(self.settings.get("locked", True))
        self.mode = str(self.settings.get("mode", "free"))
        self.manual_hidden = False
        self.chat_enabled = bool(self.settings.get("chat_enabled", False))
        self.chat_base_url = str(self.settings.get("chat_base_url", "")).strip()
        self.chat_api_key = str(self.settings.get("chat_api_key", "")).strip()
        self.chat_model = str(self.settings.get("chat_model", "")).strip()
        self.subtitle_size = int(self.settings.get("subtitle_size", 14))
        self.max_fps = int(self.settings.get("max_fps", 0))
        self.context_window_size = int(self.settings.get("context_window_size", 20))
        self.idle_chatter_interval = str(
            self.settings.get("idle_chatter_interval", "中频")
        )

        self.state = "idle"
        self.frame_index = 0
        self.scale = max(
            MIN_SCALE,
            min(
                MAX_SCALE,
                float(
                    pet_state.get(
                        "scale", self.settings.get("scale", 0.5)
                    )
                ),
            ),
        )
        self.cache = {}
        # Spine 骨架引擎（v2：替换 WebP 逐帧）
        self.quality = str(self.settings.get("render_quality", "speed")) == "quality"
        self.combat_view = str(self.settings.get("combat_view", "front"))
        self.spine = SpinePet(SPINE_DIR)
        self.spine.combat_view = self.combat_view
        self.spine.render("idle", 0.0, 96, bilinear=self.quality)
        self.drag = False
        self.pre_drag_state = "idle"
        self.pre_drag_hold = False
        self.hold_state = False
        self.press_global = None
        self.press_window = None
        self.press_time = 0
        self.tray = None
        self.tray_show_action = None
        self.flight_route = []
        self.flight_route_index = 0
        self.flight_phase = 0
        self.chat_history = []
        self.chat_data = load_chat_history()
        self.chat_worker = None
        self.chat_input = None
        self.history_window = None
        self.context_window = None
        self.memory_window = None
        self.memories = load_memory()
        self._chatter_worker = None
        self._chatter_cache = []
        self.subtitle = SubtitleWindow()
        self.pending_double_click = False
        self.facing_right = True
        self._fps_accumulator = 0.0
        self.combat_mode = False
        self._active_skill = None
        self.voice_enabled = bool(self.settings.get("voice_enabled", False))
        self.voice_language = str(self.settings.get("voice_language", "中文"))
        self._voice_player = None
        self._voice_cooldown = False
        self._idle_voice_played = False
        self._operator_window = None
        self._active_operator_chat = None
        self._operator_chats = load_operator_chats()
        self._letter_timer = QTimer(self)
        self._letter_timer.setSingleShot(True)
        self._letter_timer.timeout.connect(self._on_letter_arrive)
        self._reschedule_letter()
        if self.voice_enabled:
            self._idle_voice_timer = QTimer(self)
            self._idle_voice_timer.setSingleShot(True)
            self._idle_voice_timer.setInterval(60000)
            self._idle_voice_timer.timeout.connect(self._idle_voice_trigger)
            self._idle_voice_timer.start()

        self.timer = QTimer(self)
        self.timer.setInterval(self.tick_ms())
        self.timer.timeout.connect(self.next_frame)
        self.timer.start()

        self.sit_timer = QTimer(self)
        self.sit_timer.setSingleShot(True)
        self.sit_timer.timeout.connect(
            lambda: self._auto_rest() if not self.combat_mode else None
        )

        # Recovery timers: auto return to idle after sitting/sleeping
        self.recover_timer = QTimer(self)
        self.recover_timer.setSingleShot(True)
        self.recover_timer.timeout.connect(self._recover_from_rest)

        self.flight_move_timer = QTimer(self)
        self.flight_move_timer.setInterval(30)
        self.flight_move_timer.timeout.connect(self.flight_move_step)

        self.flight_timer = QTimer(self)
        self.flight_timer.setSingleShot(True)
        self.flight_timer.timeout.connect(self.start_flight)

        self.proactive_timer = QTimer(self)
        self.proactive_timer.setSingleShot(True)
        self.proactive_timer.timeout.connect(self.proactive_speech)

        self.set_state("idle")
        self.reschedule_flight()
        self.reschedule_proactive()
        screen = QGuiApplication.primaryScreen().availableGeometry()
        pos_x = pet_state.get("pos_x")
        if pos_x is None:
            pos_x = self.settings.get("pos_x")
        pos_y = pet_state.get("pos_y")
        if pos_y is None:
            pos_y = self.settings.get("pos_y")
        if pos_x is not None and pos_y is not None:
            pos_x = int(pos_x)
            pos_y = int(pos_y)
            pos_x = max(
                screen.x() - self.width() + 60,
                min(pos_x, screen.x() + screen.width() - 60),
            )
            pos_y = max(
                screen.y() - self.height() + 60,
                min(pos_y, screen.y() + screen.height() - 60),
            )
            self.move(pos_x, pos_y)
        else:
            self.move(
                screen.x() + (screen.width() - self.width()) // 2,
                screen.y() + screen.height() - self.height(),
            )
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.save_position)
        self.show()
        self.setup_tray()
        if self.voice_enabled:
            greeting = self._greeting_voice()
            QTimer.singleShot(500, lambda: self._play_voice(greeting))
            def _wait_greeting():
                if self._voice_player and self._voice_player.isPlaying():
                    QTimer.singleShot(300, _wait_greeting)
                else:
                    self.show_chat_hint()
            QTimer.singleShot(1000, _wait_greeting)
        else:
            QTimer.singleShot(1500, self.show_chat_hint)

    def _effective_fps(self):
        state_fps = self.state_fps(self.state)
        if self.max_fps > 0:
            fps = min(state_fps, self.max_fps)
        else:
            fps = state_fps
        # 设备显示上限：按角色所在屏幕的刷新率钳制，避免渲染显示器显示不出的帧
        screen = QGuiApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        rate = screen.refreshRate() if screen else 0.0
        if rate > 0:
            fps = min(fps, int(round(rate)))
        return max(1, fps)

    def tick_ms(self):
        # 定时器固定按屏幕刷新率节拍，速度通过每 tick 推进帧数实现（见 _fps_step）
        return max(10, int(round(1000 / self._effective_fps())))

    def state_fps(self, name):
        info = MANIFEST["states"][name]
        return int(info.get("fps", FPS))

    def state_info(self, name):
        return MANIFEST["states"][name]

    def state_count(self, name):
        """状态帧数：骨架状态按动画时长×帧率换算（一次性动画的结束判定用）。"""
        if name in STATE_MAP:
            return max(1, int(math.ceil(self.spine.anim_duration(name) * self.state_fps(name))))
        return self.state_info(name)["count"]

    def apply_geometry(self, anchor="bottom"):
        old_x, old_y = self.x(), self.y()
        old_w, old_h = self.width(), self.height()
        s = self.scale * RENDER_SCALE
        width = int(FULL_SIZE * s) + PAD * 2
        height = int(FULL_SIZE * s) + PAD * 2
        self.resize(width, height)
        if anchor == "center":
            center_x = old_x + old_w / 2
            center_y = old_y + old_h / 2
            self.move(
                int(center_x - width / 2),
                int(center_y - height / 2),
            )
        else:
            bottom_center_x = old_x + old_w / 2
            bottom_y = old_y + old_h
            self.move(
                int(bottom_center_x - width / 2),
                int(bottom_y - height),
            )

    def set_state(self, name, hold=False):
        if name not in MANIFEST["states"]:
            return
        old_state = self.state
        self.state = name
        self.hold_state = hold
        self.frame_index = 0
        self.cache.clear()
        self.timer.setInterval(self.tick_ms())
        if old_state in FLIGHT_STATES and name in FLIGHT_STATES:
            self.apply_geometry(anchor="center")
        else:
            self.apply_geometry()
        if name in FLIGHT_STATES:
            self.clamp_to_screens()
        if old_state in FLIGHT_STATES and name not in FLIGHT_STATES:
            self.flight_move_timer.stop()
            self.flight_route = []
            self.reschedule_flight()
        self.schedule_idle()
        self.update()
        if name == "fly" and not self.flight_route and not self.flight_move_timer.isActive():
            QTimer.singleShot(0, self.finish_flight)

    def _auto_rest(self):
        self.recover_timer.stop()
        if self.drag or self.combat_mode:
            return
        if random.random() < 0.85:
            self.set_state("sit", hold=True)
            self.recover_timer.start(int(random.normalvariate(40000, 5000)))
        else:
            self.set_state("sleep", hold=True)
            self.recover_timer.start(int(random.normalvariate(50000, 5000)))

    def _recover_from_rest(self):
        if self.state in ("sit", "sleep"):
            self.set_state("idle")
            self.schedule_idle()

    def schedule_idle(self):
        self.sit_timer.stop()
        self.recover_timer.stop()
        if self.state in ("sit", "sleep") or self.state in FLIGHT_STATES or self.combat_mode:
            return
        self.sit_timer.start(int(random.normalvariate(60000, 10000)))

    def cache_key(self):
        return (self.frame_index, self.facing_right)

    def current_image(self):
        """实时渲染当前骨架姿态为 QImage（v2 骨架动画）。

        角色按设备像素比 1:1 物理像素渲染；画布尺寸随状态包围盒变化，角色大小恒定。
        """
        key = self.cache_key()
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        state = self.state
        if state not in STATE_MAP:
            return QImage()
        t = self.frame_index / self.state_fps(state)
        dpr = max(1.0, self.devicePixelRatioF())
        char_px = max(48.0, FULL_SIZE * self.scale * RENDER_SCALE * CHAR_SCALE) * dpr
        if self.quality and char_px <= 320:
            # 画质优先：1.5 倍超采样 + LANCZOS 缩小 + 边缘抗锯齿
            big = self.spine.render(state, t, char_px * 1.5,
                                    mirror=not self.facing_right,
                                    bilinear=True, loop=True)
            layout = self.spine.layout_for(state, char_px)
            arr = np.asarray(PILImage.fromarray(big).resize(
                (layout["w"], layout["h"]), PILImage.LANCZOS))
        else:
            arr = self.spine.render(state, t, char_px,
                                    mirror=not self.facing_right,
                                    bilinear=True, loop=True)
        h, w = arr.shape[:2]
        image = QImage(arr.data, w, h, w * 4, QImage.Format_RGBA8888).copy()
        if len(self.cache) > 5:
            self.cache.clear()
        self.cache[key] = image
        return image

    def _fps_step(self):
        state_fps = self.state_fps(self.state)
        effective = self._effective_fps()
        # 每 tick 推进 = 状态帧率/显示帧率 × 速度（速度>1 时跳帧，渲染负担不随速度增长）
        # 注意：曾因 120Hz 渲染阻塞加过 ×2 补偿，性能优化后已移除——
        # 1.0× 即官方动画原速（与 D:\模型 参考视频 x1 一致）
        self._fps_accumulator += state_fps / effective * self.speed
        advance = int(self._fps_accumulator)
        if advance > 0:
            self._fps_accumulator -= advance
            return advance
        return 0

    def next_frame(self):
        # Safety: if move state but no active route, skip rendering and switch to idle
        if self.state == "move" and not self.flight_route:
            self.flight_move_timer.stop()
            self.set_state("idle")
            self.update()
            return
        count = self.state_count(self.state)
        step = self._fps_step()
        if step == 0:
            self.update()
            return
        if self.state == "sleep":
            if not self.hold_state and self.frame_index + step >= count:
                self.update()
                return
            self.frame_index = (self.frame_index + step) % count
        elif self.state == "fly_begin":
            if not self.hold_state and self.frame_index + step >= count:
                nxt = "fly_idle" if self._active_skill == "skill3" else "fly"
                self.set_state(nxt)
                return
            self.frame_index = (self.frame_index + step) % count
        elif self.state == "fly_end":
            if not self.hold_state and self.frame_index + step >= count:
                if self._active_skill == "skill3":
                    nxt = "fly_idle"
                elif self.combat_mode:
                    nxt = "combat_idle"
                else:
                    nxt = "idle"
                self.set_state(nxt)
                return
            self.frame_index = (self.frame_index + step) % count
        elif self.state == "fly":
            if not self.flight_route and not self.flight_move_timer.isActive():
                self.finish_flight()
                return
            self.frame_index = (self.frame_index + step) % count
        elif self.state in ("interact", "sit"):
            if not self.hold_state and self.frame_index + step >= count:
                self.set_state("idle")
                return
            self.frame_index = (self.frame_index + step) % count
        elif self.state in STATE_CHAIN:
            if not self.hold_state and self.frame_index + step >= count:
                nxt = STATE_CHAIN[self.state]
                # 背面只有一套攻击（素材限制，鸿蒙定案）：平A后直接回战斗待机，不借正面模型补第二击
                if self.state == "attack" and self.combat_view == "back":
                    nxt = "combat_idle"
                # If skill was turned off, end animations go to combat_idle
                if not self._active_skill and nxt in ("skill1_idle", "skill2_idle", "fly_idle"):
                    nxt = "combat_idle"
                # 一技能部署动画（带技能部署）结束 → 技能开启待机
                if self.state == "combat_start2" and self._active_skill == "skill1":
                    nxt = "skill1_idle"
                self.set_state(nxt)
                return
            self.frame_index = (self.frame_index + step) % count
        elif self.state in ("skill1_end", "skill2_end"):
            if not self.hold_state and self.frame_index + step >= count:
                self.set_state("combat_idle")
                return
            self.frame_index = (self.frame_index + step) % count
        elif self.state in LOOP_STATES:
            self.frame_index = (self.frame_index + step) % count
        else:
            self.frame_index = (self.frame_index + step) % count
        self.update()

    def virtual_screen_rect(self):
        rect = QRect()
        for screen in QGuiApplication.screens():
            rect = rect.united(screen.availableGeometry())
        return rect

    def current_screen_rect(self):
        screen = QGuiApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry()

    def clamp_to_screens(self):
        vg = self.current_screen_rect()
        if vg.width() <= 0 or vg.height() <= 0:
            return
        w_margin = self.width() // 2
        h_margin = self.height() // 2
        left = vg.left() + w_margin
        right = max(left, vg.right() - w_margin)
        top = vg.top() + h_margin
        bottom = max(top, vg.bottom() - h_margin)
        cx = max(left, min(self.x() + self.width() // 2, right))
        cy = max(top, min(self.y() + self.height() // 2, bottom))
        self.move(
            cx - self.width() // 2,
            cy - self.height() // 2,
        )

    def reschedule_flight(self, short=False):
        self.flight_timer.stop()
        if self.mode != "free":
            return
        if self.state in GROUND_COMBAT_STATES:
            return
        if self.flight_route or self.flight_move_timer.isActive():
            return
        if short:
            low, high = FLIGHT_RETRY_MIN, FLIGHT_RETRY_MAX
        else:
            low, high = FLIGHT_INTERVAL_MIN, FLIGHT_INTERVAL_MAX
        self.flight_timer.start(normal_interval(low, high))

    def start_flight(self):
        if self.mode != "free":
            return
        if self.state in GROUND_COMBAT_STATES or self.state in SKILL_IDLE_STATES:
            self.reschedule_flight(short=True)
            return
        if (
            self.drag
            or self.state in ("interact", "move")
            or not all(s in MANIFEST["states"] for s in FLIGHT_STATES)
        ):
            self.reschedule_flight(short=True)
            return
        if self.state in FLIGHT_STATES and self.state != "fly_idle":
            self.reschedule_flight(short=True)
            return
        self._stuck_count = 0
        self.sit_timer.stop()
        # sleep_timer removed (merged into sit_timer)
        self.build_flight_route()
        if self.state == "fly_idle":
            self.set_state("fly")
        elif self.combat_mode:
            self.set_state("fly_begin")
        else:
            self.set_state("move")
        self.flight_move_timer.start(30)

    def build_flight_route(self):
        vg = self.current_screen_rect()
        # 边距按窗口实际尺寸（与 clamp_to_screens 一致），保证目标点可达、不会把角色逼到屏幕外
        w_margin = self.width() // 2 + 20
        h_margin = self.height() // 2 + 20
        left = vg.left() + w_margin
        right = max(left, vg.right() - w_margin)
        top = vg.top() + h_margin
        bottom = max(top, vg.bottom() - h_margin)
        points = [QPoint(random.randint(left, right), random.randint(top, bottom))]
        self.flight_route = points
        self.flight_route_index = 0

    def flight_move_step(self):
        if self.state not in ("fly", "move") or not self.isVisible():
            return
        if not self.flight_route:
            self.flight_move_timer.stop()
            return
        target = self.flight_route[self.flight_route_index]
        current = self.frameGeometry().center()
        dx = target.x() - current.x()
        dy = target.y() - current.y()
        dist = math.hypot(dx, dy)
        step = 15.0 * MOVE_SPEED_OPTIONS[self.move_speed_level - 1][1]
        if dist <= step:
            self.flight_route_index += 1
            if self.flight_route_index >= len(self.flight_route):
                self._flight_arrived()
                return
            return
        # Stuck detection: if at screen edge and can't move toward target, give up
        prev = QPoint(int(current.x()), int(current.y()))
        if hasattr(self, '_stuck_pos') and self._stuck_pos == prev:
            self._stuck_count = getattr(self, '_stuck_count', 0) + 1
        else:
            self._stuck_count = 0
        self._stuck_pos = prev
        if self._stuck_count > 30:  # ~1 second stuck
            self._flight_arrived()
            return
        if dx < -2:
            self.facing_right = False
        elif dx > 2:
            self.facing_right = True
        nx = current.x() + dx / dist * step
        ny = current.y() + dy / dist * step
        # 边界即时检测：下一步会被屏幕边界挡住 → 立即停止移动（不再沿边框滑行）
        vg = self.current_screen_rect()
        w_margin = self.width() // 2
        h_margin = self.height() // 2
        left = vg.left() + w_margin
        right = max(left, vg.right() - w_margin)
        top = vg.top() + h_margin
        bottom = max(top, vg.bottom() - h_margin)
        cx = max(left, min(nx, right))
        cy = max(top, min(ny, bottom))
        self.move(int(cx - self.width() // 2), int(cy - self.height() // 2))
        if abs(cx - nx) > 0.5 or abs(cy - ny) > 0.5:
            self.finish_flight()
            self.reschedule_flight()
            return

    def _flight_arrived(self):
        """飞行到达终点/停止：清路线、状态收尾、调度下次飞行。"""
        self.flight_move_timer.stop()
        self.flight_route = []
        self.flight_route_index = 0
        if self.state == "move":
            self.set_state("idle")
        elif self.state in FLIGHT_STATES:
            self.set_state("fly_end")
        self.reschedule_flight()

    def finish_flight(self):
        self.flight_move_timer.stop()
        self.flight_route = []
        if self.state == "move":
            self.set_state("idle")
        else:
            self.set_state("fly_end")

    def end_flight(self):
        self.flight_move_timer.stop()
        self.flight_route = []
        self.set_state("idle")
        self.save_pet_state()

    def drag_return_state(self):
        if self.pre_drag_state in MANIFEST["states"]:
            return self.pre_drag_state
        return "idle"

    def show_subtitle(self, text, duration_ms=12000):
        if not text:
            self.subtitle.hide_text()
            return
        font = self.subtitle.font()
        font.setPointSize(self.subtitle_size)
        self.subtitle.setFont(font)
        self.subtitle.show_text(text, duration_ms)
        self.position_subtitle()

    def position_subtitle(self):
        if not self.subtitle.isVisible():
            return
        vg = self.virtual_screen_rect()
        # Character is drawn bottom-center in the widget
        img = self.current_image()
        if img.isNull():
            return
        dpr = max(1.0, self.devicePixelRatioF())
        if self.state in STATE_MAP:
            # 角色头顶在画布内的位置（物理像素 → 逻辑）
            char_px = max(48.0, FULL_SIZE * self.scale * RENDER_SCALE * CHAR_SCALE) * dpr
            head_y = self.spine.char_top_in_canvas(self.state, char_px) / dpr
            char_top = self.y() + self.height() - PAD - img.height() / dpr + head_y
            char_bottom = self.y() + self.height() - PAD - 8 / dpr
        else:
            char_top = self.y() + self.height() - PAD - img.height() / dpr
            char_bottom = self.y() + self.height() - PAD
        char_cx = self.x() + self.width() // 2
        sw = self.subtitle.width()
        sh = self.subtitle.height()
        gap = 4

        # Priority: above character > below character
        candidates = [
            (char_cx - sw // 2, char_top - sh - gap),         # above head
            (char_cx - sw // 2, char_bottom + gap),            # below feet
        ]
        for x, y in candidates:
            x = max(vg.left() + 2, min(x, vg.right() - sw - 2))
            y = max(vg.top() + 2, min(y, vg.bottom() - sh - 2))
            # Check if enough of the subtitle fits on screen (at least 60%)
            fit_x = min(x + sw, vg.right()) - max(x, vg.left())
            fit_y = min(y + sh, vg.bottom()) - max(y, vg.top())
            if fit_x > sw * 0.5 and fit_y > sh * 0.5:
                self.subtitle.move(x, y)
                return

        # Last resort: above character, clamped to screen
        x = max(vg.left() + 2, min(char_cx - sw // 2, vg.right() - sw - 2))
        y = max(vg.top() + 2, min(char_top - sh - gap, vg.bottom() - sh - 2))
        self.subtitle.move(x, y)

    def reschedule_proactive(self, short=False):
        self.proactive_timer.stop()
        if not self.chat_enabled:
            return
        if short:
            low, high = 15000, 30000
        else:
            low, high = CHATTER_INTERVALS.get(
                self.idle_chatter_interval, CHATTER_INTERVALS["中频"]
            )
        self.proactive_timer.start(normal_interval(low, high))

    def _idle_voice_trigger(self):
        if self._idle_voice_played:
            return
        if self.subtitle.isVisible():
            self._idle_voice_timer.start(15000)
            return
        if self.drag or self.state in ("interact", "move", "combat_idle") or self.combat_mode:
            self._idle_voice_timer.start(60000)
            return
        self._play_voice("闲置")
        self._idle_voice_played = True

    def proactive_speech(self):
        if not self.chat_enabled and not self.voice_enabled:
            return
        # Wait for current subtitle (chat reply) to finish
        if self.subtitle.isVisible():
            self.reschedule_proactive(short=True)
            return
        if self._voice_player and self._voice_player.isPlaying():
            self.reschedule_proactive(short=True)
            return
        if getattr(self, '_letter_displaying', False):
            self.reschedule_proactive(short=True)
            return
        if self.drag or self.state in ("interact", "move"):
            self.reschedule_proactive(short=True)
            return
        api_ok = all([self.chat_base_url, self.chat_api_key, self.chat_model])
        if api_ok:
            self._generate_chatter()
        else:
            if self.state in FLIGHT_STATES:
                text = FLIGHT_PROACTIVE_LINE
            else:
                text = IDLE_PROACTIVE_LINE
            self.show_subtitle(text, 12000)
        self.reschedule_proactive()

    def _generate_chatter(self):
        if self._chatter_worker is not None and self._chatter_worker.isRunning():
            return
        sys_prompt, _ = self._effective_system_prompt()
        worker = ChatterWorker(
            self.chat_base_url,
            self.chat_api_key,
            self.chat_model,
            sys_prompt,
            self,
        )
        worker.reply_ready.connect(self._on_chatter_reply)
        self._chatter_worker = worker
        worker.start()

    def _on_chatter_reply(self, reply, ok):
        if ok and reply.strip():
            text = reply.strip()
            if text in self._chatter_cache:
                return
            self._chatter_cache.append(text)
            if len(self._chatter_cache) > 5:
                self._chatter_cache.pop(0)
            self.show_subtitle(text, 10000)
        self._chatter_worker = None

    def enter_chat_mode(self):
        # 进入安洁莉娜本人的聊天：清智能体通信状态（否则发送会走智能体路径）
        self._active_operator_chat = None
        if not self.chat_enabled:
            self.show_subtitle("聊天功能没有开启哦，博士。", 6000)
            return
        if not self.chat_base_url or not self.chat_api_key or not self.chat_model:
            self.show_subtitle(CHAT_API_HINT, 8000)
            return
        sys_prompt, is_egg = self._effective_system_prompt()
        if not self.chat_history:
            sid = self.chat_data["active_session"]
            session = self.chat_data["sessions"].get(sid, {})
            msgs = session.get("messages", [])
            self.chat_history = [{"role": "system", "content": sys_prompt}]
            if not is_egg:
                self.chat_history.append({"role": "system", "content": CHAT_LORE})
            if msgs:
                limit = self.context_window_size
                for m in msgs[-limit:]:
                    self.chat_history.append({"role": m["role"], "content": m["content"]})
            else:
                self.chat_history.append(
                    {"role": "assistant", "content": CHAT_GREETING},
                )
        elif self.chat_history and self.chat_history[0]["role"] == "system":
            self.chat_history[0]["content"] = sys_prompt
        self.show_subtitle(CHAT_GREETING, 10000)
        self.show_chat_input()

    def show_chat_hint(self):
        if not self.chat_enabled or not self.chat_base_url or not self.chat_api_key or not self.chat_model:
            text = CHAT_HINT + " " + CHAT_API_HINT
        else:
            text = CHAT_HINT
        self.show_subtitle(text, 8000)

    def _position_dialog(self, dlg):
        vg = self.virtual_screen_rect()
        # Calculate actual character visual bounds (bottom-center aligned)
        img = self.current_image()
        s = self.scale * RENDER_SCALE
        char_w = (img.width() * s) if not img.isNull() else 0
        char_h = (img.height() * s) if not img.isNull() else 0
        char_right = self.x() + (self.width() + char_w) / 2
        char_top = self.y() + self.height() - PAD - char_h

        x = int(char_right) + 2
        y = int(char_top)
        if x + dlg.width() > vg.right() - 4:
            x = int(self.x() + (self.width() - char_w) / 2 - dlg.width()) - 2
        if x < vg.left():
            x = vg.left() + 4
        if y + dlg.height() > vg.bottom():
            y = vg.bottom() - dlg.height() - 4
        y = max(vg.top() + 4, y)
        dlg.move(x, y)

    def show_chat_history(self):
        if self._active_operator_chat:
            self._operator_show_history(self._active_operator_chat)
            return
        if self.history_window is not None:
            self.history_window._override_operator(None, None)
        if self.history_window is None:
            self.history_window = HistoryWindow(self)
        else:
            self.history_window._refresh_sessions()
        self.history_window.show()
        self._position_dialog(self.history_window)
        self.history_window.raise_()

    def new_session(self):
        if self._active_operator_chat:
            self._operator_new_session(self._active_operator_chat)
            return
        sid = make_session_id()
        self.chat_data["active_session"] = sid
        self.chat_data["sessions"][sid] = {
            "title": "新对话",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "messages": [],
        }
        self.chat_history = []
        self.hide_chat_windows()
        save_chat_history(self.chat_data)
        self.show_subtitle("新的对话开始了，博士。", 4000)

    def switch_session(self, sid):
        if sid not in self.chat_data["sessions"]:
            return
        self.chat_data["active_session"] = sid
        self.chat_history = []
        self.hide_chat_windows()
        save_chat_history(self.chat_data)
        session = self.chat_data["sessions"][sid]
        title = session.get("title", "未命名")
        self.show_subtitle(f"切换到了「{title}」，博士。双击以继续对话。", 5000)

    def delete_session(self, sid):
        sessions = self.chat_data["sessions"]
        if sid not in sessions or len(sessions) <= 1:
            self.show_subtitle("至少保留一个对话哦，博士。", 4000)
            return
        del sessions[sid]
        if self.chat_data["active_session"] == sid:
            self.chat_data["active_session"] = list(sessions.keys())[-1]
            self.chat_history = []
            self.hide_chat_windows()
        save_chat_history(self.chat_data)
        self.show_subtitle("对话已删除，博士。", 4000)

    def show_memory_manager(self):
        if self.memory_window is None:
            self.memory_window = MemoryWindow(self)
        self.memory_window.show()
        self._position_dialog(self.memory_window)
        self.memory_window.raise_()

    def show_operator_window(self):
        w = OperatorWindow(self)
        w._refresh()
        w.show()
        self._position_dialog(w)
        w.raise_()

    def show_operator_manager(self):
        if self._operator_window is None:
            self._operator_window = OperatorManager(self)
        self._operator_window.show()
        self._position_dialog(self._operator_window)
        self._operator_window.raise_()

    def _reschedule_letter(self):
        self._letter_timer.stop()
        self._letter_cooldown = False
        self._pending_letter = None
        if not self.settings.get("letter_enabled", False):
            return
        low, high = LETTER_INTERVALS.get(
            self.settings.get("letter_interval", "中频"), LETTER_INTERVALS["中频"]
        )
        if self.settings.get("letter_interval") == "拟真":
            self._letter_timer.start(skewed_interval(low, high))
        else:
            self._letter_timer.start(normal_interval(low, high))

    def _on_letter_arrive(self):
        if not self.settings.get("letter_enabled", False):
            return
        if self.settings.get("dnd_enabled", False):
            now = datetime.datetime.now().strftime("%H:%M")
            start = self.settings.get("dnd_start", "22:00")
            end = self.settings.get("dnd_end", "07:00")
            if start <= end:
                in_dnd = start <= now <= end
            else:
                in_dnd = now >= start or now <= end
            if in_dnd:
                self._reschedule_letter()
                return
        agents = self.settings.get("operators", {})
        enabled = {aid: a for aid, a in agents.items() if a.get("letter_enabled")}
        if not enabled:
            self._reschedule_letter()
            return
        aid = random.choice(list(enabled.keys()))
        a = enabled[aid]
        if not all([self.chat_base_url, self.chat_api_key, self.chat_model]):
            self._reschedule_letter()
            return
        # Track unanswered count (reset when user replies)
        count = a.get("_unanswered", 0) + 1
        a["_unanswered"] = count
        self.settings["operators"][aid] = a
        save_settings(self.settings)
        if count > 3:
            self._reschedule_letter()
            return
        now = datetime.datetime.now()
        time_hint = f"现在是{now.strftime('%H:%M')}，" + (
            "凌晨" if 0 <= now.hour < 6 else
            "清晨" if 6 <= now.hour < 9 else
            "上午" if 9 <= now.hour < 12 else
            "中午" if 12 <= now.hour < 14 else
            "下午" if 14 <= now.hour < 18 else
            "傍晚" if 18 <= now.hour < 20 else "晚上"
        )
        # Escalating urgency
        if count == 1:
            instruction = (
                f"{time_hint}。你正在做一件日常小事（自己想一件合理的），"
                f"忽然想到博士，就随手发了一条消息。语气自然随意，像朋友间随手发的微信，"
                f"30字以内。只需要写消息内容，不需要称呼。"
            )
        elif count == 2:
            instruction = (
                f"你之前给博士发了条消息，博士还没回。{time_hint}。"
                f"再发一条，带一点点挂念但不刻意。30字以内。只需要写消息内容。"
            )
        else:
            instruction = (
                f"你发了两次消息博士都没回。{time_hint}。"
                f"这次有点担心了，语气里带着催促和关切。30字以内。只需要写消息内容。"
            )
        op_data = self._operator_chats.setdefault(aid, new_chat_data())
        sid = op_data["active_session"]
        session = op_data["sessions"].setdefault(sid, {"title": "来信", "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "messages": []})
        history_msgs = session.get("messages", [])
        messages = [{"role": "system", "content": a["system_prompt"]}]
        limit = self.context_window_size
        for m in history_msgs[-limit:]:
            messages.append({"role": m["role"], "content": m["content"]})
        messages.append({"role": "user", "content": instruction})
        def _deliver():
            try:
                text = chat_api_request(self.chat_base_url, self.chat_api_key, self.chat_model, messages)
                name = a["name"]
                self._pending_letter = f"「{name}」来信：{text}"
                self.show_subtitle(f"博士，{name}给你寄了封信~ 点击安洁莉娜查看", 15000)
                session["messages"].append({"role": "assistant", "content": text, "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
                save_operator_chats(self._operator_chats)
            except Exception:
                import traceback
                try:
                    with open(ERROR_LOG, "a", encoding="utf-8") as f:
                        f.write(f"letter error {time.ctime()}\n")
                        traceback.print_exc(file=f)
                except OSError:
                    pass
        QTimer.singleShot(200, _deliver)
        self._reschedule_letter()

    def open_operator_chat(self, aid):
        agents = self.settings.get("operators", {})
        a = agents.get(aid, {})
        if not a:
            return
        if not all([self.chat_base_url, self.chat_api_key, self.chat_model]):
            self.show_subtitle("聊天还没有配置好哦，博士。", 6000)
            return
        self._active_operator_chat = aid
        self._operator_chat_data = self._operator_chats.setdefault(
            aid, new_chat_data()
        )
        sid = self._operator_chat_data["active_session"]
        session = self._operator_chat_data["sessions"].get(sid, {})
        msgs = session.get("messages", [])
        sys_prompt = a.get("system_prompt", "")
        self._operator_chat_history = [{"role": "system", "content": sys_prompt}]
        limit = self.context_window_size
        for m in msgs[-limit:]:
            self._operator_chat_history.append({"role": m["role"], "content": m["content"]})
        self.show_chat_input()
        name = a["name"]
        self.show_subtitle(f"正在与「{name}」通信（由安洁莉娜送达），博士。", 5000)

    def _build_system_prompt(self):
        sys_prompt = get_angelina_skill()
        player_name = self.settings.get("player_name", "").strip()
        name_style = self.settings.get("name_style", "ID")
        if player_name:
            if name_style == "Dr.":
                sys_prompt += f"\n\n博士名叫\"{player_name}\"，你必须称呼他为\"Dr.{player_name}\"。"
            else:
                sys_prompt += f"\n\n博士名叫\"{player_name}\"，你直接称呼他为\"{player_name}\"。"
        extra = self.settings.get("extra_prompt", "").strip()
        if extra:
            sys_prompt += "\n\n" + extra
        if self.memories:
            relevant = sorted(
                self.memories,
                key=lambda m: m.get("importance", 0.5) * (m.get("access_count", 0) + 1),
                reverse=True,
            )[:20]
            lines = "\n".join(
                f"- {m['content']}" for m in relevant if m.get("content", "").strip()
            )
            if lines:
                sys_prompt += f"\n\n[博士相关的长期记忆]\n{lines}"
        return sys_prompt

    def _effective_system_prompt(self):
        """实际发送用系统提示词：额外提示词命中彩蛋时整体替换为彩蛋 Skill。

        前端（上下文查看）仍走 _build_system_prompt（予愿安洁莉娜）——
        彩蛋人格对用户隐藏。返回 (prompt, is_easter_egg)。"""
        extra = self.settings.get("extra_prompt", "").strip()
        egg = match_easter_egg(extra) if extra else None
        if egg:
            return egg[0], True
        return self._build_system_prompt(), False

    def show_context(self):
        if self._active_operator_chat:
            self._operator_show_context(self._active_operator_chat)
            return
        # Always rebuild from saved session data
        sid = self.chat_data["active_session"]
        session_msgs = self.chat_data["sessions"].get(sid, {}).get("messages", [])
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "system", "content": CHAT_LORE},
        ]
        if session_msgs:
            for m in session_msgs[-self.context_window_size:]:
                messages.append({"role": m["role"], "content": m["content"]})
        else:
            messages.append({"role": "assistant", "content": CHAT_GREETING})
        if self.context_window is None:
            self.context_window = ContextWindow(self)
        self.context_window.set_messages(messages)
        self.context_window.show()
        self._position_dialog(self.context_window)
        self.context_window.raise_()

    def show_chat_input(self):
        if self.chat_input is None:
            self.chat_input = ChatInputWindow()
            self.chat_input.submitted.connect(self.send_chat_message)
        self.chat_input.show()
        self.chat_input.raise_()
        self.position_chat_input()
        self.chat_input.activateWindow()
        self.chat_input.edit.setFocus()
        # Pause auto-flight while chatting
        self.flight_move_timer.stop()
        self.flight_route = []
        self.flight_timer.stop()

    def position_chat_input(self):
        if self.chat_input is None:
            return
        vg = self.virtual_screen_rect()
        x = self.x() + (self.width() - self.chat_input.width()) // 2
        y = self.y() + self.height() + 10
        if y + self.chat_input.height() > vg.bottom():
            y = self.y() - self.chat_input.height() - 10
        x = max(vg.left() + 2, min(x, vg.right() - self.chat_input.width() - 2))
        y = max(vg.top() + 2, min(y, vg.bottom() - self.chat_input.height() - 2))
        self.chat_input.move(x, y)

    def send_chat_message(self, text):
        if self._active_operator_chat:
            self._send_operator_message(text)
            return
        if not self.chat_enabled:
            self.show_subtitle("聊天功能没有开启哦，博士。", 6000)
            return
        if not self.chat_base_url or not self.chat_api_key or not self.chat_model:
            self.show_subtitle(
                "聊天还没有配置好哦，博士。请右键 -> 设置... 里填写 API 地址、密钥和模型。",
                8000,
            )
            return
        if self.chat_worker is not None and self.chat_worker.isRunning():
            return
        # 刷新系统提示词（extra_prompt 可能在会话中修改 → 彩蛋状态可能变化）
        sys_prompt, is_egg = self._effective_system_prompt()
        if self.chat_history and self.chat_history[0]["role"] == "system":
            self.chat_history[0]["content"] = sys_prompt
            has_lore = (len(self.chat_history) > 1
                        and self.chat_history[1].get("role") == "system")
            if is_egg and has_lore:
                del self.chat_history[1]
            elif not is_egg and not has_lore:
                self.chat_history.insert(1, {"role": "system", "content": CHAT_LORE})
        # Inject time awareness directly into user message so LLM can't miss it
        # (kept out of system prompt to preserve prompt cache hits)
        if self.settings.get("time_awareness", False):
            now = datetime.datetime.now()
            launch = datetime.datetime(2019, 5, 1)
            days = (now - launch).days
            years = days // 365
            rem = days % 365
            months = rem // 30
            if years > 0:
                seniority = f"{years}年{months}个月"
            else:
                seniority = f"{months}个月"
            time_hint = f"[{now.strftime('%H:%M')}，入职{seniority}] {text}"
            self.chat_history.append({"role": "user", "content": time_hint})
        else:
            self.chat_history.append({"role": "user", "content": text})
        sid = self.chat_data["active_session"]
        session = self.chat_data["sessions"].setdefault(
            sid,
            {
                "title": text[:15],
                "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "messages": [],
            },
        )
        if not session.get("title") or session["title"] == "新对话":
            session["title"] = text[:15]
        session["messages"].append(
            {
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "role": "user",
                "content": text,
            }
        )
        save_chat_history(self.chat_data)
        if self.context_window_size > 0 and len(self.chat_history) > self.context_window_size + 3:
            self.chat_history = self.chat_history[:2] + self.chat_history[-self.context_window_size:]
        if self.chat_input is not None:
            self.chat_input.set_busy(True)
        self.show_subtitle("嗯，我在听哦，博士。", 4000)
        worker = ChatWorker(
            self.chat_base_url,
            self.chat_api_key,
            self.chat_model,
            list(self.chat_history),
            self,
        )
        worker.reply_ready.connect(self.on_chat_reply)
        self.chat_worker = worker
        worker.start()

    def on_chat_reply(self, reply, ok):
        if not self.chat_enabled:
            if self.chat_input is not None:
                self.chat_input.set_busy(False)
            self.chat_worker = None
            return
        if ok:
            self.chat_history.append({"role": "assistant", "content": reply})
            sid = self.chat_data["active_session"]
            session = self.chat_data["sessions"].get(sid)
            if session is not None:
                session["messages"].append(
                    {
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "role": "assistant",
                        "content": reply,
                    }
                )
            save_chat_history(self.chat_data)
            self.show_subtitle(reply, 15000)
        else:
            self.show_subtitle(
                f"消息好像没有送出去呢，博士……（{reply}）",
                10000,
            )
        if self.chat_input is not None:
            self.chat_input.set_busy(False)
        self.chat_worker = None
        self._active_operator_chat = None
        self.reschedule_flight()

    def _send_operator_message(self, text):
        aid = self._active_operator_chat
        agents = self.settings.get("operators", {})
        a = agents.get(aid, {})
        if not a or not aid:
            return
        if self.chat_worker is not None and self.chat_worker.isRunning():
            return
        # Reset unanswered counter and add 2-min cooldown
        a["_unanswered"] = 0
        self.settings["operators"][aid] = a
        save_settings(self.settings)
        self._letter_timer.stop()
        self._letter_cooldown = True
        QTimer.singleShot(120000, self._reschedule_letter)
        # Inject time awareness if enabled
        if self.settings.get("time_awareness", False):
            now = datetime.datetime.now()
            launch = datetime.datetime(2019, 5, 1)
            days = (now - launch).days
            years = days // 365
            rem = days % 365
            months = rem // 30
            seniority = f"{years}年{months}个月" if years > 0 else f"{months}个月"
            text_with_time = f"[{now.strftime('%H:%M')}，入职{seniority}] {text}"
        else:
            text_with_time = text
        self._operator_chat_history.append({"role": "user", "content": text_with_time})
        # Write to operator session
        sid = self._operator_chat_data["active_session"]
        session = self._operator_chat_data["sessions"].setdefault(
            sid, {"title": text[:15], "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "messages": []}
        )
        session["messages"].append({"role": "user", "content": text, "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        save_operator_chats(self._operator_chats)
        # Trim and send
        if self.context_window_size > 0 and len(self._operator_chat_history) > self.context_window_size + 2:
            self._operator_chat_history = [self._operator_chat_history[0]] + self._operator_chat_history[-self.context_window_size:]
        if self.chat_input is not None:
            self.chat_input.set_busy(True)
        self.show_subtitle("正在送信中...", 4000)
        worker = ChatWorker(self.chat_base_url, self.chat_api_key, self.chat_model, list(self._operator_chat_history), self)
        worker.reply_ready.connect(self._on_operator_reply)
        self.chat_worker = worker
        worker.start()

    def _on_operator_reply(self, reply, ok):
        aid = self._active_operator_chat
        if not aid or not ok:
            if self.chat_input is not None:
                self.chat_input.set_busy(False)
            self.chat_worker = None
            self._active_operator_chat = None
            return
        self._operator_chat_history.append({"role": "assistant", "content": reply})
        agents = self.settings.get("operators", {})
        a = agents.get(aid, {})
        sid = self._operator_chat_data["active_session"]
        session = self._operator_chat_data["sessions"].get(sid)
        if session is not None:
            session["messages"].append({"role": "assistant", "content": reply,
                "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        save_operator_chats(self._operator_chats)
        name = a.get("name", "")
        self.show_subtitle(f"「{name}」：{reply}", 15000)
        if self.chat_input is not None:
            self.chat_input.set_busy(False)
        self.chat_worker = None

    def hide_chat_windows(self):
        self.subtitle.hide_text()
        if self.chat_input is not None:
            self.chat_input.hide()

    def paintEvent(self, event):
        image = self.current_image()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        if not image.isNull():
            # 渲染输出为物理像素，除以 DPR 得到逻辑尺寸绘制（1:1 物理像素）
            dpr = max(1.0, self.devicePixelRatioF())
            iw = image.width() / dpr
            ih = image.height() / dpr
            # Bottom-center align
            x = (self.width() - iw) / 2
            y = self.height() - PAD - ih
            target = QRectF(x, y, iw, ih)
            painter.drawImage(target, image)

    def _reposition_dialogs(self):
        for dlg in [self.history_window, self.context_window, self.memory_window]:
            if dlg and dlg.isVisible():
                self._position_dialog(dlg)

    def moveEvent(self, event):
        super().moveEvent(event)
        self.position_subtitle()
        self._reposition_dialogs()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.contextMenuEvent(event)
            return
        if event.button() == Qt.LeftButton:
            self.drag = False
            self.pre_drag_state = self.state
            self.pre_drag_hold = self.hold_state
            self.press_global = event.globalPosition().toPoint()
            self.press_window = self.pos()
            self.press_time = time.monotonic()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.pending_double_click = True
            self.enter_chat_mode()

    def mouseMoveEvent(self, event):
        if self.press_global is None:
            return
        if self.locked:
            return
        current = event.globalPosition().toPoint()
        dx = current.x() - self.press_global.x()
        dy = current.y() - self.press_global.y()
        if not self.drag and (dx * dx + dy * dy) > 36:
            self.drag = True
            self._last_drag_x = current.x()
            if hasattr(self, '_idle_voice_timer') and not self._idle_voice_played:
                self._idle_voice_timer.start(60000)
            self.sit_timer.stop()
            # sleep_timer removed (merged into sit_timer)
            if self.state not in ("move", "sit", "sleep"):
                if self._active_skill == "skill3" and self.state in FLIGHT_STATES:
                    pass
                else:
                    self.set_state("move")
        if self.drag and not (event.buttons() & Qt.LeftButton):
            self.drag = False
            self.press_global = None
            self.press_window = None
            self.set_state(
                self.drag_return_state(), hold=self.pre_drag_hold
            )
        elif self.drag:
            frame_dx = current.x() - getattr(self, '_last_drag_x', current.x())
            self._last_drag_x = current.x()
            if frame_dx < -1:
                self.facing_right = False
            elif frame_dx > 1:
                self.facing_right = True
            self.move(self.press_window.x() + dx, self.press_window.y() + dy)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        if self.drag:
            self.drag = False
            self.press_global = None
            self.press_window = None
            self.set_state(
                self.drag_return_state(), hold=self.pre_drag_hold
            )
            self.save_pet_state()
            return
        double = self.pending_double_click
        self.pending_double_click = False
        if double:
            self.press_global = None
            return
        if self.press_global is None:
            return
        current = event.globalPosition().toPoint()
        moved = (current.x() - self.press_global.x()) ** 2 + (
            current.y() - self.press_global.y()
        ) ** 2
        held = time.monotonic() - self.press_time
        self.press_global = None
        self.press_window = None
        if held < 0.5 and moved < 36:
            if self._pending_letter:
                self.show_subtitle(self._pending_letter, 15000)
                self._letter_displaying = True
                QTimer.singleShot(15000, lambda: setattr(self, '_letter_displaying', False))
                self._pending_letter = None
                self.reschedule_proactive(short=True)
                self.press_global = None
                return
            if hasattr(self, '_idle_voice_timer') and not self._idle_voice_played:
                self._idle_voice_timer.start(60000)
            if self.voice_enabled and not self.combat_mode:
                self._voice_click()
                self.set_state("interact")
            elif self.combat_mode:
                if self._active_skill == "skill3":
                    if self.voice_enabled:
                        self._play_voice(random.choice(COMBAT_FIGHT))
                    self._play_skill_chain("fly_combat", reschedule=False)
                elif self._active_skill == "skill2":
                    if self.voice_enabled:
                        self._play_voice(random.choice(COMBAT_FIGHT))
                    self._play_skill_chain("skill2_loop", reschedule=False)
                elif self._active_skill == "skill1":
                    if self.voice_enabled:
                        self._play_voice(random.choice(COMBAT_FIGHT))
                    self._play_skill_chain("skill1_loop", reschedule=False)
                else:
                    if self.voice_enabled:
                        self._play_voice(random.choice(COMBAT_SELECT))
                    self._play_skill_chain("attack", reschedule=False)
            else:
                self.set_state("interact")

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        if not self.combat_mode:
            menu.addAction(
                QAction(
                    "坐下",
                    self,
                    triggered=lambda: self.set_state("sit", hold=True),
                )
            )
            menu.addAction(
                QAction(
                    "放松",
                    self,
                    triggered=lambda: self.set_state("idle", hold=True),
                )
            )
            menu.addAction(
                QAction(
                    "睡觉",
                    self,
                    triggered=lambda: self.set_state("sleep", hold=True),
                )
            )
        menu.addSeparator()
        mode_menu = menu.addMenu("形态")
        mode_group = QActionGroup(self)
        mode_group.setExclusive(True)
        fixed_action = QAction("固定形态", self, checkable=True)
        fixed_action.setChecked(self.mode == "fixed")
        fixed_action.triggered.connect(lambda: self.set_mode("fixed"))
        free_action = QAction("自由移动形态", self, checkable=True)
        free_action.setChecked(self.mode == "free")
        free_action.triggered.connect(lambda: self.set_mode("free"))
        mode_group.addAction(fixed_action)
        mode_group.addAction(free_action)
        mode_menu.addAction(fixed_action)
        mode_menu.addAction(free_action)
        menu.addSeparator()
        chat_menu = menu.addMenu("聊天")
        chat_menu.addAction(
            QAction("打开聊天", self, triggered=self.enter_chat_mode)
        )
        chat_menu.addAction(
            QAction("新对话", self, triggered=self.new_session)
        )
        chat_menu.addAction(
            QAction("历史对话", self, triggered=self.show_chat_history)
        )
        chat_menu.addAction(
            QAction("上下文查看", self, triggered=self.show_context)
        )
        chat_menu.addAction(
            QAction("记忆管理", self, triggered=self.show_memory_manager)
        )
        chat_menu.addAction(
            QAction("聊天设置...", self, triggered=self.open_settings)
        )
        menu.addSeparator()
        full_action = QAction("全屏应用时自动隐藏", self, checkable=True)
        full_action.setChecked(self.auto_hide_fullscreen)
        full_action.triggered.connect(self.toggle_fullscreen_auto_hide)
        menu.addAction(full_action)
        menu.addSeparator()
        mode_action = QAction(
            "切换至战斗形态" if not self.combat_mode else "切换至基建形态",
            self,
            triggered=self.toggle_combat_mode,
        )
        menu.addAction(mode_action)
        if self.combat_mode:
            view_action = QAction(
                "切换至正面视角" if self.combat_view == "back" else "切换至背面视角",
                self,
                triggered=self.toggle_combat_view,
            )
            menu.addAction(view_action)
        if self.combat_mode:
            skill_menu = menu.addMenu("技能")
            icons_dir = os.path.join(PETS_DIR, "技能图标")
            s1 = QAction(
                "极速送达" if self._active_skill != "skill1" else "极速送达 ✓",
                self,
                triggered=lambda: self._toggle_skill("skill1"),
            )
            s1.setIcon(QIcon(os.path.join(icons_dir, "一技能_极速送达.png")))
            skill_menu.addAction(s1)
            s2 = QAction(
                "重力自定义" if self._active_skill != "skill2" else "重力自定义 ✓",
                self,
                triggered=lambda: self._toggle_skill("skill2"),
            )
            s2.setIcon(QIcon(os.path.join(icons_dir, "二技能_重力自定义.png")))
            skill_menu.addAction(s2)
            s3 = QAction(
                "酸橙的心事" if self._active_skill != "skill3" else "酸橙的心事 ✓",
                self,
                triggered=lambda: self._toggle_skill("skill3"),
            )
            s3.setIcon(QIcon(os.path.join(icons_dir, "三技能_酸橙的心事.png")))
            skill_menu.addAction(s3)

        letter_menu = menu.addMenu("来信")
        ops = self.settings.get("operators", {})
        roots = {oid: o for oid, o in ops.items() if o.get("enabled") and not o.get("parent")}
        children = {oid: o for oid, o in ops.items() if o.get("enabled") and o.get("parent")}

        def _add_op_submenu(parent_menu, oid, o):
            sub = parent_menu.addMenu(o.get("name", "未命名"))
            sub.addAction(QAction("通信", self, triggered=lambda checked, id=oid: self.open_operator_chat(id)))
            sub.addAction(QAction("新对话", self, triggered=lambda checked, id=oid: self._operator_new_session(id)))
            sub.addAction(QAction("历史对话", self, triggered=lambda checked, id=oid: self._operator_show_history(id)))
            sub.addAction(QAction("上下文查看", self, triggered=lambda checked, id=oid: self._operator_show_context(id)))

        for oid, o in roots.items():
            kids = {cid: co for cid, co in children.items() if co.get("parent") == oid}
            if kids:
                grp = letter_menu.addMenu(o.get("name", "未命名"))
                _add_op_submenu(grp, oid, o)
                grp.addSeparator()
                for cid, co in kids.items():
                    _add_op_submenu(grp, cid, co)
            else:
                _add_op_submenu(letter_menu, oid, o)

        letter_menu.addSeparator()
        letter_menu.addAction(
            QAction("管理干员...", self, triggered=self.show_operator_manager)
        )
        menu.addSeparator()
        menu.addAction(
            QAction(
                "解锁拖动" if self.locked else "锁定拖动",
                self,
                triggered=self.toggle_lock,
            )
        )
        menu.addSeparator()
        menu.addAction(QAction("设置...", self, triggered=self.open_settings))
        menu.addSeparator()
        menu.addAction(
            QAction("退出", self, triggered=self.quit_pet)
        )
        menu.exec(event.globalPos())


    def _operator_new_session(self, aid):
        ops = self.settings.get("operators", {})
        a = ops.get(aid, {})
        if not a:
            return
        data = self._operator_chats.setdefault(aid, new_chat_data())
        sid = make_session_id()
        data["active_session"] = sid
        data["sessions"][sid] = {"title": "新对话", "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "messages": []}
        save_operator_chats(self._operator_chats)
        name = a.get("name", "")
        self.show_subtitle(f"「{name}」开始了新的对话，博士。", 4000)
        self.open_operator_chat(aid)

    def _operator_show_history(self, aid):
        ops = self.settings.get("operators", {})
        if not ops.get(aid):
            return
        data = self._operator_chats.setdefault(aid, new_chat_data())
        if self.history_window is None:
            self.history_window = HistoryWindow(self)
        self.history_window._override_operator(aid, data)
        self.history_window._refresh_sessions()
        self.history_window.show()
        self._position_dialog(self.history_window)
        self.history_window.raise_()

    def _operator_show_context(self, aid):
        ops = self.settings.get("operators", {})
        a = ops.get(aid, {})
        if not a:
            return
        sys_prompt = a.get("system_prompt", "")
        messages = [{"role": "system", "content": sys_prompt}]
        if self._active_operator_chat == aid and hasattr(self, '_operator_chat_history'):
            messages = list(self._operator_chat_history)
        else:
            data = self._operator_chats.setdefault(aid, new_chat_data())
            sid = data["active_session"]
            msgs = data["sessions"].get(sid, {}).get("messages", [])
            for m in msgs[-self.context_window_size:]:
                messages.append({"role": m["role"], "content": m["content"]})
        if self.context_window is None:
            self.context_window = ContextWindow(self)
        self.context_window.set_messages(messages)
        self.context_window.show()
        self._position_dialog(self.context_window)
        self.context_window.raise_()

    def scale_up(self):
        self.set_scale(self.scale + 0.1)

    def scale_down(self):
        self.set_scale(self.scale - 0.1)

    def set_scale(self, value):
        self.scale = max(MIN_SCALE, min(MAX_SCALE, round(value, 1)))
        self.apply_geometry()
        self.settings["scale"] = self.scale
        self.save_pet_state()
        self.update()

    def _play_voice(self, name, subtitle_text=None):
        if not self.voice_enabled:
            return
        voice_dir = VOICE_DIR_CN if self.voice_language == "中文" else VOICE_DIR_JP
        path = os.path.join(voice_dir, f"{name}.wav")
        if not os.path.isfile(path):
            return
        if self._voice_player is None:
            self._voice_player = QSoundEffect(self)
            self._voice_player.setVolume(1.0)
        self._voice_player.setSource(QUrl.fromLocalFile(path))
        self._voice_player.play()
        text = subtitle_text or VOICE_LINES.get(name, "")
        if text:
            self.show_subtitle(text, 60000)
            # Poll until voice ends, then start subtitle hide timer
            def _wait_voice_end():
                if self._voice_player and self._voice_player.isPlaying():
                    QTimer.singleShot(200, _wait_voice_end)
                else:
                    self.subtitle._hide_timer.start(3000)
            QTimer.singleShot(300, _wait_voice_end)

    def _greeting_voice(self):
        now = datetime.datetime.now()
        today = now.strftime("%m-%d")
        # Check birthday setting
        birthday = self.settings.get("birthday", "")
        is_birthday = birthday == today

        # Priority: 周年庆典 (May 1-4) > 新年祝福 (Jan 1-3 / Spring Festival) > 生日 > 问候
        if "05-01" <= today <= "05-04":
            return "周年庆典"
        if "01-01" <= today <= "01-03":
            return "新年祝福"
        # Spring Festival: roughly late Jan to mid Feb (simplified check)
        sf_ranges = [("01-28", "02-05"), ("02-15", "02-22")]
        for start, end in sf_ranges:
            if start <= today <= end:
                return "新年祝福"
        if is_birthday:
            return "生日"
        return "问候"

    def _voice_click(self):
        if self._voice_cooldown:
            self._play_voice("戳一下")
            return
        if self.combat_mode:
            pool = COMBAT_SELECT
        else:
            pool = BASE_TALK
        name = random.choice(pool)
        self._play_voice(name)
        self._voice_cooldown = True
        QTimer.singleShot(10000, lambda: setattr(self, '_voice_cooldown', False))

    def toggle_combat_mode(self):
        self.combat_mode = not self.combat_mode
        if self.combat_mode:
            self._active_skill = None
            self.set_state("combat_start")
            if self.voice_enabled:
                self._play_voice(random.choice(COMBAT_DEPLOY))
            else:
                self.show_subtitle("进入战斗形态，博士。", 3000)
        else:
            self._active_skill = None
            self.flight_move_timer.stop()
            self.flight_route = []
            self.set_state("idle")
            self.reschedule_flight()
            if self.voice_enabled:
                self._play_voice("任命助理")
            else:
                self.show_subtitle("回到基建形态，博士。", 3000)

    def _toggle_skill(self, skill_name):
        if self._active_skill == skill_name:
            self._active_skill = None
            if skill_name == "skill3":
                self._play_skill_chain("fly_end")
            elif skill_name == "skill2":
                self._play_skill_chain("skill2_end")
            elif skill_name == "skill1":
                self._play_skill_chain("skill1_end")
        else:
            self._active_skill = skill_name
            if self.voice_enabled:
                self._play_voice(random.choice(COMBAT_FIGHT))
            if skill_name == "skill3":
                self._play_skill_chain("fly_begin")
            elif skill_name == "skill2":
                self._play_skill_chain("skill2_begin")
            elif skill_name == "skill1":
                # 部署动画（Start_2 = 带技能部署）→ 技能开启待机
                self._play_skill_chain("combat_start2")

    def _play_skill_chain(self, start_state, reschedule=True):
        if start_state not in MANIFEST["states"]:
            return
        if self.state in FLIGHT_STATES:
            self.flight_move_timer.stop()
            self.flight_route = []
        self.sit_timer.stop()
        # sleep_timer removed (merged into sit_timer)
        if start_state in FLIGHT_STATES:
            self.flight_route = []
            self.flight_move_timer.stop()
            if reschedule:
                self.reschedule_flight(short=True)
        self.set_state(start_state, hold=False)

    def set_mode(self, mode):
        if mode not in ("fixed", "free") or mode == self.mode:
            return
        self.mode = mode
        self.settings["mode"] = mode
        save_settings(self.settings)
        if mode == "fixed" and self.state in FLIGHT_STATES:
            self.flight_move_timer.stop()
            self.flight_route = []
            self.set_state("idle")
        else:
            self.reschedule_flight()

    def save_pet_state(self):
        pet_states = self.settings.setdefault("pet_states", {})
        pet_states[self.pet_name] = {
            "scale": self.scale,
            "speed": self.speed,
            "pos_x": self.x(),
            "pos_y": self.y(),
        }
        self.settings["scale"] = self.scale
        self.settings["pos_x"] = self.x()
        self.settings["pos_y"] = self.y()
        save_settings(self.settings)

    def save_position(self):
        self.save_pet_state()

    def toggle_fullscreen_auto_hide(self):
        self.auto_hide_fullscreen = not self.auto_hide_fullscreen
        self.settings["auto_hide_fullscreen"] = self.auto_hide_fullscreen
        save_settings(self.settings)
        self.check_fullscreen()

    def toggle_combat_view(self):
        self.combat_view = "back" if self.combat_view == "front" else "front"
        self.spine.combat_view = self.combat_view
        self.settings["combat_view"] = self.combat_view
        save_settings(self.settings)
        self.cache.clear()
        self.update()

    def check_fullscreen(self):
        if self.manual_hidden:
            return

    def setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = QIcon(AVATAR_PATH)
        if icon.isNull():
            icon = QIcon(os.path.join(FRAMES_DIR, "idle", "frame_0000.webp"))
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(icon)
        self.tray.setToolTip("酸橙味的信")

        self.tray_menu = QMenu(self)
        self.tray_show_action = QAction(self)
        self.tray_show_action.triggered.connect(self.toggle_pet_visible)
        self.update_tray_show_text()
        auto_action = QAction("开机自启动", self, checkable=True)
        auto_action.setChecked(is_autostart_enabled())
        auto_action.triggered.connect(self.toggle_autostart)
        quit_action = QAction("关闭", self, triggered=self.quit_pet)
        self.tray_menu.addAction(self.tray_show_action)
        self.tray_menu.addAction(auto_action)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(quit_action)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def toggle_pet_visible(self):
        if self.isVisible():
            self.manual_hidden = True
            self.hide_chat_windows()
            self.hide()
        else:
            self.manual_hidden = False
            self.show()
            self.raise_()
            self.activateWindow()
        self.update_tray_show_text()

    def update_tray_show_text(self):
        if self.tray_show_action is not None:
            self.tray_show_action.setText(
                "隐藏桌宠" if self.isVisible() else "显示桌宠"
            )

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.toggle_pet_visible()

    def toggle_autostart(self, checked):
        if set_autostart(bool(checked)):
            return
        QMessageBox.warning(self, "桌宠", "设置开机自启动失败。")
        action = self.sender()
        if action is not None:
            action.setChecked(not checked)

    def quit_pet(self):
        self.hide_chat_windows()
        if self.tray is not None:
            self.tray.hide()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def toggle_lock(self):
        self.locked = not self.locked
        self.settings["locked"] = self.locked
        save_settings(self.settings)
        self.drag = False
        self.press_global = None
        self.press_window = None

    def open_settings(self):
        self.settings["speed"] = self.speed
        dialog = SettingsDialog(self.settings, self)
        self._position_dialog(dialog)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.values()
        if data["mode"] != self.mode:
            self.set_mode(data["mode"])
        self.chat_enabled = bool(data["chat_enabled"])
        self.chat_base_url = str(data["chat_base_url"]).strip()
        self.chat_api_key = str(data["chat_api_key"]).strip()
        self.chat_model = str(data["chat_model"]).strip()
        self.subtitle_size = int(data["subtitle_size"])
        if not self.chat_enabled:
            self.chat_history = []
            self.hide_chat_windows()
        else:
            self.reschedule_proactive()
            QTimer.singleShot(300, self.show_chat_hint)
        merged = dict(self.settings)
        merged.update(data)
        self.settings = merged
        save_settings(merged)
        self.speed = float(data["speed"])
        if "move_speed" in data:
            self.move_speed_level = int(data["move_speed"])
        if "scale" in data:
            self.set_scale(data["scale"])
        if "render_quality" in data:
            self.quality = str(data["render_quality"]) == "quality"
            self.cache.clear()
        self.auto_hide_fullscreen = bool(data["auto_hide_fullscreen"])
        was_voice_off = not self.voice_enabled
        self.voice_enabled = bool(data["voice_enabled"])
        self.voice_language = str(data["voice_language"])
        if "_letter_operators" in data:
            ops = self.settings.setdefault("operators", {})
            for oid, checked in data["_letter_operators"].items():
                if oid in ops:
                    ops[oid]["letter_enabled"] = checked
            save_settings(self.settings)
        if was_voice_off and self.voice_enabled:
            QTimer.singleShot(300, lambda: self._play_voice("干员报到"))
        self.max_fps = int(data["max_fps"])
        self.context_window_size = int(data["context_window_size"])
        self.idle_chatter_interval = str(data["idle_chatter_interval"])
        self._fps_accumulator = 0.0
        self.timer.setInterval(self.tick_ms())
        self.save_pet_state()
        self.update()
