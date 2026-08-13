# Dialog windows
from PySide6.QtCore import Qt, QTimer, QUrl, QPoint, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QFontMetrics, QGuiApplication, QIcon, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGraphicsDropShadowEffect, QGridLayout, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox, QVBoxLayout, QWidget
import json, os, random, datetime, base64, gzip, time
from core import *
from widgets import _frameless_title_bar

class HistoryWindow(QDialog):
    def __init__(self, pet_window):
        super().__init__(pet_window)
        self._pet = pet_window
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setMinimumSize(560, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        _frameless_title_bar(layout, "对话管理", self.reject)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(12, 10, 12, 4)
        self.session_combo = QComboBox()
        self.session_combo.currentIndexChanged.connect(self._on_session_changed)
        toolbar.addWidget(self.session_combo, 1)
        new_btn = QPushButton("+ 新对话")
        new_btn.clicked.connect(self._new_session)
        rename_btn = QPushButton("重命名")
        rename_btn.clicked.connect(lambda: self._rename_session(self.session_combo.currentData()))
        toolbar.addWidget(rename_btn)
        new_btn.setStyleSheet(
            f"QPushButton{{background:{THEME_ORANGE};color:white;border:none;"
            "padding:4px 12px;border-radius:6px;font-weight:600;}}"
            f"QPushButton:hover{{background:{THEME_ORANGE_LIGHT};}}"
        )
        toolbar.addWidget(new_btn)
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(self._delete_session)
        toolbar.addWidget(del_btn)
        layout.addLayout(toolbar)

        # Message list
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_layout.setSpacing(8)
        self.scroll_layout.setContentsMargins(12, 8, 12, 8)
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll, 1)

        # Bottom bar
        bottom = QHBoxLayout()
        bottom.setContentsMargins(12, 4, 12, 10)
        add_btn = QPushButton("新增消息")
        add_btn.clicked.connect(self._add_message)
        bottom.addWidget(add_btn)
        bottom.addStretch()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save)
        save_btn.setStyleSheet(
            f"QPushButton{{background:{THEME_ORANGE};color:white;border:none;"
            "padding:4px 16px;border-radius:6px;font-weight:600;}}"
            f"QPushButton:hover{{background:{THEME_ORANGE_LIGHT};}}"
        )
        bottom.addWidget(save_btn)
        layout.addLayout(bottom)

        self._operator_id = None
        self._operator_data = None
        self._message_widgets = []
        self._refresh_sessions()

    def _override_operator(self, oid, data):
        self._operator_id = oid
        self._operator_data = data

    def _refresh_sessions(self):
        self.session_combo.blockSignals(True)
        self.session_combo.clear()
        if self._operator_id:
            chat_data = self._operator_data or new_chat_data()
            for sid in reversed(list(chat_data["sessions"].keys())):
                s = chat_data["sessions"][sid]
                title = s.get("title", "未命名")[:20]
                self.session_combo.addItem(title, sid)
            idx = self.session_combo.findData(chat_data["active_session"])
            if idx >= 0:
                self.session_combo.setCurrentIndex(idx)
            self.session_combo.blockSignals(False)
            self._rebuild_messages()
            return
        chat_data = self._pet.chat_data
        for sid in reversed(list(chat_data["sessions"].keys())):
            session = chat_data["sessions"][sid]
            title = session.get("title", "未命名")[:20]
            self.session_combo.addItem(title, sid)
        active = chat_data["active_session"]
        idx = self.session_combo.findData(active)
        if idx >= 0:
            self.session_combo.setCurrentIndex(idx)
        self.session_combo.blockSignals(False)
        self._rebuild_messages()

    def _rebuild_messages(self):
        for w in self._message_widgets:
            self.scroll_layout.removeWidget(w)
            w.deleteLater()
        self._message_widgets = []
        sid = self.session_combo.currentData()
        if not sid:
            return
        chat_data = self._operator_data if self._operator_id else self._pet.chat_data
        msgs = chat_data["sessions"].get(sid, {}).get("messages", [])
        for i, msg in enumerate(msgs):
            w = self._create_message_widget(i, msg)
            self.scroll_layout.addWidget(w)
            self._message_widgets.append(w)

    def _create_message_widget(self, idx, msg):
        role = msg.get("role", "user")
        is_user = role == "user"
        w = QWidget()
        w.setStyleSheet("background:palette(Base);border-radius:8px;")
        card = QVBoxLayout(w)
        card.setContentsMargins(12, 8, 12, 8)
        card.setSpacing(4)
        header = QHBoxLayout()
        if not is_user and self._operator_id:
            op_name = self._pet.settings.get("operators", {}).get(self._operator_id, {}).get("name", "干员")
            lbl = QLabel(op_name)
        else:
            lbl = QLabel("博士" if is_user else "安洁莉娜")
        lbl.setStyleSheet(
            f"font-weight:bold;color:#4a90d9;font-size:11px;"
            if is_user else f"font-weight:bold;color:{THEME_ORANGE};font-size:11px;"
        )
        header.addWidget(lbl)
        header.addStretch()
        del_btn = QPushButton("删除")
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet(
            "QPushButton{background:transparent;border:none;color:#888;font-size:10px;padding:2px 6px;border-radius:4px;}"
            "QPushButton:hover{background:#e81123;color:white;}"
        )
        del_btn.clicked.connect(lambda c, i=idx: self._delete_message(i))
        header.addWidget(del_btn)
        card.addLayout(header)
        edit = QPlainTextEdit()
        edit.setPlainText(msg.get("content", ""))
        edit.setMaximumHeight(80)
        card.addWidget(edit)
        return w

    def _on_session_changed(self, idx):
        sid = self.session_combo.itemData(idx)
        if not sid:
            return
        if self._operator_id:
            data = self._pet._operator_chats.setdefault(self._operator_id, new_chat_data())
            if sid != data.get("active_session"):
                data["active_session"] = sid
                save_operator_chats(self._pet._operator_chats)
        elif sid != self._pet.chat_data.get("active_session"):
            self._pet.switch_session(sid)
        self._rebuild_messages()

    def _new_session(self):
        title, ok = QInputDialog.getText(self, "新对话", "对话名称:", text="新对话")
        if not ok:
            return
        title = title.strip() or "新对话"
        if self._operator_id:
            data = self._pet._operator_chats.setdefault(self._operator_id, new_chat_data())
            sid = make_session_id()
            data["active_session"] = sid
            data["sessions"][sid] = {"title": title, "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "messages": []}
            save_operator_chats(self._pet._operator_chats)
        else:
            sid = make_session_id()
            self._pet.chat_data["active_session"] = sid
            self._pet.chat_data["sessions"][sid] = {"title": title, "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "messages": []}
            save_chat_history(self._pet.chat_data)
            self._pet.chat_history = []
        self._refresh_sessions()

    def _delete_session(self):
        sid = self.session_combo.currentData()
        if not sid:
            return
        if self._operator_id:
            data = self._pet._operator_chats.setdefault(self._operator_id, new_chat_data())
            if len(data.get("sessions", {})) <= 1:
                QMessageBox.information(self, "删除", "至少保留一个对话。")
                return
        else:
            if len(self._pet.chat_data.get("sessions", {})) <= 1:
                QMessageBox.information(self, "删除", "至少保留一个对话。")
                return
        if QMessageBox.question(self, "删除", "确定删除此对话？",
            QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            if self._operator_id:
                data = self._pet._operator_chats.get(self._operator_id, {})
                data.get("sessions", {}).pop(sid, None)
                if data.get("active_session") == sid:
                    data["active_session"] = list(data["sessions"].keys())[-1]
                save_operator_chats(self._pet._operator_chats)
            else:
                self._pet.delete_session(sid)
            self._refresh_sessions()

    def _add_message(self):
        sid = self.session_combo.currentData()
        if not sid:
            return
        s = self._pet.chat_data["sessions"].setdefault(sid, {
            "title": "新对话",
            "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "messages": [],
        })
        s["messages"].append({
            "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "role": "user", "content": "",
        })
        self._rebuild_messages()

    def _delete_message(self, idx):
        sid = self.session_combo.currentData()
        if not sid:
            return
        chat_data = self._operator_data if self._operator_id else self._pet.chat_data
        msgs = chat_data["sessions"].get(sid, {}).get("messages", [])
        if 0 <= idx < len(msgs):
            del msgs[idx]
        self._rebuild_messages()

    def _save(self):
        sid = self.session_combo.currentData()
        if not sid:
            return
        chat_data = self._operator_data if self._operator_id else self._pet.chat_data
        msgs = chat_data["sessions"].get(sid, {}).get("messages", [])
        for i, w in enumerate(self._message_widgets):
            if i >= len(msgs):
                break
            edit = w.findChild(QPlainTextEdit)
            if edit:
                msgs[i]["content"] = edit.toPlainText()
        if self._operator_id:
            save_operator_chats(self._pet._operator_chats)
        else:
            save_chat_history(self._pet.chat_data)
            self._pet.chat_history = []
        QMessageBox.information(self, "保存", "对话已保存。")

    def _rename_session(self, sid):
        chat_data = self._operator_data if self._operator_id else self._pet.chat_data
        old = chat_data["sessions"].get(sid, {}).get("title", "")
        title, ok = QInputDialog.getText(self, "重命名", "新标题:", text=old)
        if ok and title.strip():
            chat_data["sessions"][sid]["title"] = title.strip()
            if self._operator_id:
                save_operator_chats(self._pet._operator_chats)
            else:
                save_chat_history(self._pet.chat_data)
            self._refresh_sessions()

class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setModal(True)
        self.setMinimumSize(460, 480)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        _frameless_title_bar(main_layout, "桌宠设置", self.reject)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setStyleSheet("background:transparent;")
        form = QFormLayout(body)
        form.setContentsMargins(20, 16, 20, 16)
        form.setSpacing(8)
        scroll.setWidget(body)
        main_layout.addWidget(scroll, 1)

        def _section(title):
            lbl = QLabel(title)
            lbl.setStyleSheet("font-size:12px;font-weight:bold;color:#888;padding-top:8px;")
            form.addRow(lbl)
            sep = QWidget()
            sep.setFixedHeight(1)
            sep.setStyleSheet(f"background:{THEME_DARK_BORDER};")
            form.addRow(sep)

        # ── 动画 ──
        _section("动画")
        self.speed_combo = QComboBox()
        for label, value in SPEED_OPTIONS:
            self.speed_combo.addItem(label, value)
        self.speed_combo.setCurrentIndex(self._idx_speed(settings.get("speed", 1.0)))
        form.addRow("动作倍速", self.speed_combo)

        self.move_speed_combo = QComboBox()
        for label, _ in MOVE_SPEED_OPTIONS:
            self.move_speed_combo.addItem(label)
        move_idx = int(settings.get("move_speed", DEFAULT_MOVE_SPEED_LEVEL)) - 1
        self.move_speed_combo.setCurrentIndex(max(0, min(len(MOVE_SPEED_OPTIONS) - 1, move_idx)))
        form.addRow("移动速度", self.move_speed_combo)

        self.fps_combo = QComboBox()
        for label, value in [("120帧（原生）", 0), ("60帧", 60), ("30帧", 30)]:
            self.fps_combo.addItem(label, value)
        self.fps_combo.setCurrentIndex(self._idx_fps(int(settings.get("max_fps", 0))))
        form.addRow("帧率上限", self.fps_combo)

        screen = QGuiApplication.primaryScreen()
        rate = int(round(screen.refreshRate())) if screen and screen.refreshRate() > 0 else 0
        if rate:
            hint = QLabel(
                f"已检测屏幕刷新率 {rate}Hz：所选档位高于屏幕刷新率时，将自动按 {rate}Hz 实际渲染"
            )
            hint.setWordWrap(True)
            hint.setStyleSheet("color: #888888; font-size: 12px;")
            form.addRow("", hint)

        self.quality_combo = QComboBox()
        self.quality_combo.addItem("速度优先", "speed")
        self.quality_combo.addItem("画质优先", "quality")
        self.quality_combo.setCurrentIndex(
            0 if settings.get("render_quality", "speed") == "speed" else 1
        )
        form.addRow("渲染画质", self.quality_combo)

        self.mode_combo = QComboBox()
        self.mode_combo.addItem("自由移动", "free")
        self.mode_combo.addItem("固定位置", "fixed")
        self.mode_combo.setCurrentIndex(0 if settings.get("mode", "free") == "free" else 1)
        form.addRow("形态", self.mode_combo)

        scale_row = QHBoxLayout()
        self.scale_slider = QSlider(Qt.Horizontal)
        self.scale_slider.setRange(20, 200)
        self.scale_slider.setValue(int(settings.get("scale", 0.8) * 100))
        self.scale_label = QLabel(f"{settings.get('scale', 0.8):.1f}x")
        self.scale_slider.valueChanged.connect(
            lambda v: self.scale_label.setText(f"{v / 100:.1f}x")
        )
        # Real-time scale preview
        self.scale_slider.valueChanged.connect(
            lambda v: self.parent().set_scale(v / 100.0) if hasattr(self.parent(), 'set_scale') else None
        )
        scale_row.addWidget(self.scale_slider, 1)
        scale_row.addWidget(self.scale_label)
        form.addRow("角色缩放", scale_row)

        self.subtitle_size_spin = QSpinBox()
        self.subtitle_size_spin.setRange(10, 30)
        self.subtitle_size_spin.setValue(int(settings.get("subtitle_size", 14)))
        form.addRow("字幕字号", self.subtitle_size_spin)

        # ── 聊天 ──
        _section("聊天")
        self.chat_enabled = QCheckBox("启用聊天")
        self.chat_enabled.setChecked(bool(settings.get("chat_enabled", False)))
        form.addRow(self.chat_enabled)

        self.chat_base_url = QLineEdit(str(settings.get("chat_base_url", "")))
        self.chat_base_url.setPlaceholderText("https://api.deepseek.com")
        form.addRow("API 地址", self.chat_base_url)

        self.chat_api_key = QLineEdit(str(settings.get("chat_api_key", "")))
        self.chat_api_key.setEchoMode(QLineEdit.Password)
        self.chat_api_key.setPlaceholderText("sk-...")
        form.addRow("API 密钥", self.chat_api_key)

        self.chat_model = QLineEdit(str(settings.get("chat_model", "")))
        self.chat_model.setPlaceholderText("deepseek-v4-flash")
        form.addRow("模型", self.chat_model)

        test_btn = QPushButton("测试连接")
        test_btn.clicked.connect(self._test_api)
        form.addRow("", test_btn)

        ctx = int(settings.get("context_window_size", 20))
        self.context_unlimited_check = QCheckBox("不限制")
        self.context_unlimited_check.setChecked(ctx == 0)
        self.context_unlimited_check.toggled.connect(
            lambda checked: self.context_window_spin.setEnabled(not checked)
        )
        self.context_window_spin = QSpinBox()
        self.context_window_spin.setRange(1, 9999)
        self.context_window_spin.setValue(ctx if ctx > 0 else 20)
        self.context_window_spin.setEnabled(ctx != 0)
        ctx_row = QHBoxLayout()
        ctx_row.addWidget(self.context_window_spin, 1)
        ctx_row.addWidget(self.context_unlimited_check)
        form.addRow("上下文窗口", ctx_row)

        self.chatter_combo = QComboBox()
        for label in ["低频", "中频", "高频"]:
            self.chatter_combo.addItem(label)
        idx = self.chatter_combo.findText(str(settings.get("idle_chatter_interval", "中频")))
        if idx >= 0:
            self.chatter_combo.setCurrentIndex(idx)
        form.addRow("碎碎念频率", self.chatter_combo)

        # ── 语音 ──
        _section("语音")
        self.voice_check = QCheckBox("开启语音")
        self.voice_check.setChecked(bool(settings.get("voice_enabled", False)))
        form.addRow(self.voice_check)

        self.voice_lang_combo = QComboBox()
        self.voice_lang_combo.addItems(["中文", "日文"])
        lang = str(settings.get("voice_language", "中文"))
        idx = self.voice_lang_combo.findText(lang)
        if idx >= 0:
            self.voice_lang_combo.setCurrentIndex(idx)
        form.addRow("语音语言", self.voice_lang_combo)

        # ── 角色 ──
        _section("角色")
        self.time_aware_check = QCheckBox("时间感知（知道当前时间和入职时长）")
        self.time_aware_check.setChecked(bool(settings.get("time_awareness", False)))
        form.addRow(self.time_aware_check)

        self.player_name_edit = QLineEdit(str(settings.get("player_name", "")))
        self.player_name_edit.setPlaceholderText("你的名字（留空则叫\"博士\"）")
        form.addRow("你的名字", self.player_name_edit)

        self.name_prefix_check = QCheckBox("添加 Dr. 前缀")
        self.name_prefix_check.setChecked(bool(settings.get("name_style", "Dr.") == "Dr."))
        form.addRow(self.name_prefix_check)

        self.birthday_edit = QLineEdit(str(settings.get("birthday", "")))
        self.birthday_edit.setPlaceholderText("MM-DD")
        form.addRow("生日", self.birthday_edit)

        self.extra_prompt_edit = QPlainTextEdit()
        self.extra_prompt_edit.setPlainText(str(settings.get("extra_prompt", "")))
        self.extra_prompt_edit.setMaximumHeight(60)
        self.extra_prompt_edit.setPlaceholderText("补充人设（核心不可改）...")
        form.addRow("人设补充", self.extra_prompt_edit)

        # ── 来信 ──
        _section("来信")
        self.letter_enabled_check = QCheckBox("开启干员来信")
        self.letter_enabled_check.setChecked(bool(settings.get("letter_enabled", False)))
        form.addRow(self.letter_enabled_check)

        self.letter_interval_combo = QComboBox()
        for label in ["低频", "中频", "高频", "拟真"]:
            self.letter_interval_combo.addItem(label)
        idx = self.letter_interval_combo.findText(str(settings.get("letter_interval", "中频")))
        if idx >= 0:
            self.letter_interval_combo.setCurrentIndex(idx)
        form.addRow("来信频率", self.letter_interval_combo)

        self.letter_ops_layout = QVBoxLayout()
        self.letter_checks = {}
        ops = settings.get("operators", {})
        for oid, o in ops.items():
            cb = QCheckBox(o.get("name", "未命名"))
            cb.setChecked(bool(o.get("letter_enabled", False)))
            cb.toggled.connect(lambda checked, c=cb: self._limit_letter_checks(c, checked))
            self.letter_checks[oid] = cb
            self.letter_ops_layout.addWidget(cb)
        form.addRow("选择干员（仅一位）", self.letter_ops_layout)

        self.dnd_check = QCheckBox("开启免打扰")
        self.dnd_check.setChecked(bool(settings.get("dnd_enabled", False)))
        form.addRow(self.dnd_check)

        dnd_row = QHBoxLayout()
        self.dnd_start_edit = QLineEdit(str(settings.get("dnd_start", "22:00")))
        self.dnd_start_edit.setFixedWidth(60)
        self.dnd_start_edit.setPlaceholderText("22:00")
        dnd_row.addWidget(QLabel("从"))
        dnd_row.addWidget(self.dnd_start_edit)
        dnd_row.addWidget(QLabel("至"))
        self.dnd_end_edit = QLineEdit(str(settings.get("dnd_end", "07:00")))
        self.dnd_end_edit.setFixedWidth(60)
        self.dnd_end_edit.setPlaceholderText("07:00")
        dnd_row.addWidget(self.dnd_end_edit)
        dnd_row.addStretch()
        form.addRow("免打扰时段", dnd_row)

        # ── 其他 ──
        _section("其他")
        self.fullscreen_check = QCheckBox("全屏应用时自动隐藏")
        self.fullscreen_check.setChecked(bool(settings.get("auto_hide_fullscreen", False)))
        form.addRow(self.fullscreen_check)

        # Bottom
        btns = QHBoxLayout()
        btns.setContentsMargins(20, 8, 20, 14)
        btns.addStretch()
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        ok = QPushButton("确定")
        ok.clicked.connect(self.accept)
        ok.setStyleSheet(
            f"QPushButton{{background:{THEME_ORANGE};color:white;border:none;"
            "padding:6px 24px;border-radius:6px;font-weight:bold;}}"
            f"QPushButton:hover{{background:{THEME_ORANGE_LIGHT};}}"
        )
        btns.addWidget(ok)
        main_layout.addLayout(btns)

    def _test_api(self):
        url = self.chat_base_url.text().strip()
        key = self.chat_api_key.text().strip()
        model = self.chat_model.text().strip()
        if not all([url, key, model]):
            QMessageBox.warning(self, "测试连接", "请先填写 API 地址、密钥和模型。")
            return
        try:
            reply = chat_api_request(url, key, model, [{"role": "user", "content": "Hi"}])
            QMessageBox.information(self, "测试连接", f"连接成功！\n回复：{reply[:80]}...")
        except Exception as e:
            QMessageBox.critical(self, "测试连接", f"连接失败：{e}")

    def _limit_letter_checks(self, cb, checked):
        if checked:
            count = sum(1 for c in self.letter_checks.values() if c.isChecked())
            if count > 1:
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)
                QMessageBox.information(self, "来信限制", "一次只能选择一位干员来信哦，博士。")

    @staticmethod
    def _idx_speed(value):
        for i, (_, s) in enumerate(SPEED_OPTIONS):
            if abs(s - float(value)) < 1e-6:
                return i
        return 2

    @staticmethod
    def _idx_fps(value):
        fps_opts = [0, 60, 30]
        try:
            return fps_opts.index(int(value))
        except (ValueError, IndexError):
            return 0

    def values(self):
        # Force commit typed text by clearing focus on spinners
        self.context_window_spin.clearFocus()
        self.subtitle_size_spin.clearFocus()
        return {
            "speed": self.speed_combo.currentData(),
            "scale": self.scale_slider.value() / 100.0,
            "mode": self.mode_combo.currentData(),
            "chat_enabled": self.chat_enabled.isChecked(),
            "chat_base_url": self.chat_base_url.text().strip(),
            "chat_api_key": self.chat_api_key.text().strip(),
            "chat_model": self.chat_model.text().strip(),
            "subtitle_size": self.subtitle_size_spin.value(),
            "auto_hide_fullscreen": self.fullscreen_check.isChecked(),
            "max_fps": self.fps_combo.currentData(),
            "move_speed": self.move_speed_combo.currentIndex() + 1,
            "render_quality": self.quality_combo.currentData(),
            "context_window_size": 0 if self.context_unlimited_check.isChecked() else self.context_window_spin.value(),
            "extra_prompt": self.extra_prompt_edit.toPlainText().strip(),
            "idle_chatter_interval": self.chatter_combo.currentText(),
            "time_awareness": self.time_aware_check.isChecked(),
            "voice_enabled": self.voice_check.isChecked(),
            "voice_language": self.voice_lang_combo.currentText(),
            "birthday": self.birthday_edit.text().strip(),
            "player_name": self.player_name_edit.text().strip(),
            "name_style": "Dr." if self.name_prefix_check.isChecked() else "ID",
            "letter_enabled": self.letter_enabled_check.isChecked(),
            "letter_interval": self.letter_interval_combo.currentText(),
            "dnd_enabled": self.dnd_check.isChecked(),
            "dnd_start": self.dnd_start_edit.text().strip() or "22:00",
            "dnd_end": self.dnd_end_edit.text().strip() or "07:00",
            "_letter_operators": {oid: cb.isChecked() for oid, cb in self.letter_checks.items()},
        }

class ContextWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setMinimumSize(540, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        _frameless_title_bar(layout, "上下文查看", self.reject)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_layout.setSpacing(6)
        self.scroll.setWidget(self.scroll_content)
        layout.addWidget(self.scroll, 1)

        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        copy_btn = QPushButton("复制原始上下文")
        copy_btn.clicked.connect(self._copy_raw)
        toolbar.addWidget(copy_btn)
        layout.addLayout(toolbar)

        self._messages = []
        self._raw_text = ""
        self._dark = True

    def set_dark(self, dark):
        self._dark = dark
        self._rebuild()

    def _bubble_styles(self):
        if self._dark:
            return (
                # user (right-aligned blue)
                "background:#2563eb;color:#fff;border-radius:12px 2px 12px 12px;"
                "padding:10px 14px;margin:4px 16px 4px 80px;",
                # assistant (left-aligned gray)
                "background:#334155;color:#e2e8f0;border-radius:2px 12px 12px 12px;"
                "padding:10px 14px;margin:4px 80px 4px 16px;",
                # system
                "background:#1e1b2e;color:#a5b4fc;border:1px solid #4338ca;"
                "border-radius:8px;padding:10px 14px;margin:4px 8px;"
                "font-family:Consolas,monospace;font-size:12px;",
            )
        else:
            return (
                "background:#2563eb;color:#fff;border-radius:12px 2px 12px 12px;"
                "padding:10px 14px;margin:4px 16px 4px 80px;",
                "background:#f0f0f0;color:#333;border-radius:2px 12px 12px 12px;"
                "padding:10px 14px;margin:4px 80px 4px 16px;",
                "background:#f5f0ff;color:#5b4fa8;border:1px solid #c4b5fd;"
                "border-radius:8px;padding:10px 14px;margin:4px 8px;"
                "font-family:Consolas,monospace;font-size:12px;",
            )

    def set_messages(self, messages):
        self._messages = list(messages)
        self._rebuild()

    def _rebuild(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        raw_lines = []
        for i, m in enumerate(self._messages):
            role = m.get("role", "?")
            content = m.get("content", "")
            raw_lines.append(f"[{role}]\n{content}\n")
            self.scroll_layout.addWidget(self._bubble(role, content, i))
        self._raw_text = "\n".join(raw_lines)
        self.scroll_layout.addStretch()

    def _bubble(self, role, text, idx):
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 2, 0, 2)

        user_style, assistant_style, system_style = self._bubble_styles()

        if role == "system":
            header = QHBoxLayout()
            label = QLabel("系统提示词")
            label.setStyleSheet("color:#a5b4fc;font-size:11px;font-weight:bold;margin-left:12px;")
            header.addWidget(label)
            header.addStretch()
            collapsed = len(text) > 80
            toggle = QPushButton("▾" if collapsed else "▴")
            toggle.setFixedSize(24, 24)
            toggle.setCursor(Qt.PointingHandCursor)
            toggle.setStyleSheet("QPushButton{background:transparent;border:none;color:#888;font-size:14px;}QPushButton:hover{color:#ccc;}")
            header.addWidget(toggle)
            layout.addLayout(header)
            bubble = QLabel(text)
            bubble.setStyleSheet(system_style)
            bubble.setWordWrap(True)
            layout.addWidget(bubble)
            toggle.clicked.connect(lambda checked, b=bubble, t=toggle, tx=text: self._toggle_collapse(b, t, tx))
            if len(text) > 80:
                bubble.setText(text[:80] + "...")
                bubble.setFixedHeight(40)
        elif role == "user":
            label = QLabel("博士")
            label.setStyleSheet("color:#93c5fd;font-size:11px;font-weight:bold;")
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            layout.addWidget(label)
            bubble = QLabel(text)
            bubble.setStyleSheet(user_style)
        else:
            label = QLabel("安洁莉娜")
            label.setStyleSheet(f"color:{THEME_ORANGE};font-size:11px;font-weight:bold;margin-left:20px;")
            layout.addWidget(label)
            bubble = QLabel(text)
            bubble.setStyleSheet(assistant_style)

        bubble.setWordWrap(True)
        bubble.setTextFormat(Qt.PlainText)
        layout.addWidget(bubble)
        return w

    def _refresh(self):
        pet = self.parent()
        if pet and hasattr(pet, "show_context"):
            pet.show_context()

    def _toggle_collapse(self, bubble, toggle, full_text):
        if toggle.text() == "▴":
            bubble.setText(full_text[:80] + "...")
            bubble.setFixedHeight(40)
            toggle.setText("▾")
        else:
            bubble.setText(full_text)
            bubble.setMinimumHeight(0)
            bubble.setMaximumHeight(16777215)
            toggle.setText("▴")

    def _copy_raw(self):
        QApplication.clipboard().setText(self._raw_text)
        QMessageBox.information(self, "已复制", "原始上下文已复制到剪贴板。")

class MemoryWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setMinimumSize(620, 460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        _frameless_title_bar(layout, "记忆管理", self.reject)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(12, 10, 12, 6)
        self.category_combo = QComboBox()
        self.category_combo.addItem("全部分类", "")
        self.category_combo.currentIndexChanged.connect(self._rebuild)
        toolbar.addWidget(QLabel("筛选:"))
        toolbar.addWidget(self.category_combo)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索记忆...")
        self.search_edit.textChanged.connect(self._rebuild)
        toolbar.addWidget(self.search_edit, 1)
        add_btn = QPushButton("+ 新增")
        add_btn.clicked.connect(self._add_memory)
        add_btn.setStyleSheet(
            f"QPushButton{{background:{THEME_ORANGE};color:white;border:none;"
            "padding:6px 14px;border-radius:6px;font-weight:bold;}}"
            f"QPushButton:hover{{background:{THEME_ORANGE_LIGHT};}}"
        )
        toolbar.addWidget(add_btn)
        layout.addLayout(toolbar)

        # Card grid
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.grid_content = QWidget()
        self.grid = QGridLayout(self.grid_content)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.grid.setSpacing(10)
        self.scroll.setWidget(self.grid_content)
        layout.addWidget(self.scroll, 1)

        # Bottom
        bottom = QHBoxLayout()
        bottom.setContentsMargins(12, 6, 12, 10)
        bottom.addStretch()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save)
        save_btn.setStyleSheet(
            f"QPushButton{{background:{THEME_ORANGE};color:white;border:none;"
            "padding:6px 20px;border-radius:6px;font-weight:bold;}}"
            f"QPushButton:hover{{background:{THEME_ORANGE_LIGHT};}}"
        )
        bottom.addWidget(save_btn)
        layout.addLayout(bottom)

        self._memories = load_memory()
        self._widgets = []
        self._rebuild()

    def _rebuild(self):
        for w in self._widgets:
            self.grid.removeWidget(w)
            w.deleteLater()
        self._widgets = []
        while self.grid.count():
            self.grid.takeAt(0)

        # Update categories
        self.category_combo.blockSignals(True)
        cur = self.category_combo.currentData()
        existing = {self.category_combo.itemData(i) for i in range(self.category_combo.count())}
        for m in self._memories:
            cat = m.get("category", "")
            if cat and cat not in existing:
                self.category_combo.addItem(cat, cat)
                existing.add(cat)
        idx = self.category_combo.findData(cur)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        self.category_combo.blockSignals(False)

        cat_filter = self.category_combo.currentData()
        keyword = self.search_edit.text().strip().lower()
        filtered = [m for m in self._memories
                    if (not cat_filter or m.get("category") == cat_filter)
                    and (not keyword or keyword in m.get("content", "").lower())]
        filtered.sort(key=lambda m: m.get("importance", 0.5) * (m.get("access_count", 0) + 1),
                      reverse=True)

        cols = 2
        for i, mem in enumerate(filtered):
            orig_idx = self._memories.index(mem)
            card = self._create_card(orig_idx, mem)
            self.grid.addWidget(card, i // cols, i % cols)
            self._widgets.append(card)

    def _create_card(self, idx, mem):
        card = QWidget()
        card.setMinimumWidth(260)
        bg = THEME_DARK_CARD
        border = THEME_DARK_BORDER
        card.setStyleSheet(f"background:{bg};border:1px solid {border};border-radius:8px;")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header: importance bar + category
        header = QHBoxLayout()
        imp = mem.get("importance", 0.8)
        dots = "●" * int(imp * 10) + "○" * (10 - int(imp * 10))
        imp_label = QLabel(dots[:10])
        imp_label.setStyleSheet(f"color:{THEME_ORANGE};font-size:10px;")
        header.addWidget(imp_label)
        header.addStretch()
        cat_label = QLabel(mem.get("category", "未分类"))
        cat_label.setStyleSheet("color:#888;font-size:10px;border:1px solid #444;border-radius:4px;padding:1px 6px;")
        header.addWidget(cat_label)
        layout.addLayout(header)

        # Content
        content = QPlainTextEdit()
        content.setPlainText(mem.get("content", ""))
        content.setMaximumHeight(50)
        content.setPlaceholderText("输入记忆内容...")
        content.textChanged.connect(self._mark_dirty)
        layout.addWidget(content)

        # Actions
        actions = QHBoxLayout()
        actions.addStretch()
        del_btn = QPushButton("删除")
        del_btn.setFixedSize(50, 24)
        del_btn.setCursor(Qt.PointingHandCursor)
        del_btn.setStyleSheet("QPushButton{background:transparent;border:1px solid #555;border-radius:4px;color:#888;font-size:11px;}QPushButton:hover{background:#e81123;color:white;border-color:#e81123;}")
        del_btn.clicked.connect(lambda c, i=idx: self._delete_memory(i))
        actions.addWidget(del_btn)
        layout.addLayout(actions)
        return card

    def _mark_dirty(self):
        pass  # edits go to _memories on save

    def _add_memory(self):
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._memories.append({
            "id": memory_id(), "content": "", "category": "",
            "importance": 0.8, "created_at": now, "accessed_at": now, "access_count": 0,
        })
        self._rebuild()

    def _delete_memory(self, idx):
        if 0 <= idx < len(self._memories):
            del self._memories[idx]
        self._rebuild()

    def _save(self):
        for i, card in enumerate(self._widgets):
            edit = card.findChild(QPlainTextEdit)
            if edit and i < len(self._memories):
                self._memories[i]["content"] = edit.toPlainText()
        save_memory(self._memories)
        QMessageBox.information(self, "保存", "记忆已保存。")

    def _extract_from_history(self):
        QMessageBox.information(self, "提取记忆",
            "此功能需要调用 LLM 分析历史对话。\n请在聊天配置好 API 后使用。")

class OperatorManager(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._pet = parent
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        self.setMinimumSize(500, 420)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        _frameless_title_bar(layout, "干员管理", self.reject)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget{background:transparent;border:none;}"
            "QListWidget::item{padding:10px 12px;border-radius:8px;margin:2px 8px;}"
            f"QListWidget::item:selected{{background:{THEME_ORANGE};color:white;}}"
        )
        self.list_widget.itemDoubleClicked.connect(
            lambda item: self._edit_operator(item.data(Qt.UserRole))
        )
        layout.addWidget(self.list_widget, 1)

        btns = QHBoxLayout()
        btns.setContentsMargins(12, 6, 12, 10)
        add_btn = QPushButton("+ 新增")
        add_btn.clicked.connect(self._add_operator)
        btns.addWidget(add_btn)
        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self._export_prompt)
        btns.addWidget(export_btn)
        import_btn = QPushButton("导入")
        import_btn.clicked.connect(self._import_prompt)
        btns.addWidget(import_btn)
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(self._delete_operator)
        btns.addWidget(del_btn)
        btns.addStretch()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self._save)
        save_btn.setStyleSheet(
            f"QPushButton{{background:{THEME_ORANGE};color:white;border:none;"
            "padding:4px 16px;border-radius:6px;font-weight:600;}}"
            f"QPushButton:hover{{background:{THEME_ORANGE_LIGHT};}}"
        )
        btns.addWidget(save_btn)
        layout.addLayout(btns)

        self._agents = {}
        self._refresh()

    def _refresh(self):
        agents = self._pet.settings.get("operators", {})
        self._agents = dict(agents)
        self._refresh_list()

    def _refresh_list(self):
        self.list_widget.clear()
        for aid, a in self._agents.items():
            name = a.get("name", "未命名")
            enabled = "✓" if a.get("enabled", False) else "✗"
            pre = "* " if a.get("preset") else ""
            item = QListWidgetItem(f"{pre}{enabled}  {name}")
            item.setData(Qt.UserRole, aid)
            self.list_widget.addItem(item)

    def _add_operator(self):
        aid = memory_id()
        self._agents[aid] = {"name": "新干员", "system_prompt": "", "enabled": False}
        self._refresh_list()
        # Auto-open edit dialog
        self._edit_operator(aid)

    def _export_prompt(self):
        item = self.list_widget.currentItem()
        if not item:
            return QMessageBox.information(self, "导出", "请先选择一位干员。")
        aid = item.data(Qt.UserRole)
        a = self._agents.get(aid, {})
        text = json.dumps({"name": a.get("name", ""), "prompt": a.get("system_prompt", "")}, ensure_ascii=False, indent=2)
        dlg = QDialog(self)
        dlg.setWindowTitle("导出提示词")
        dlg.setMinimumSize(420, 280)
        dl = QVBoxLayout(dlg)
        edit = QPlainTextEdit()
        edit.setPlainText(text)
        edit.setReadOnly(True)
        dl.addWidget(edit)
        btn = QPushButton("复制到剪贴板")
        btn.clicked.connect(lambda: (QApplication.clipboard().setText(text), QMessageBox.information(dlg, "已复制", "已复制到剪贴板。")))
        dl.addWidget(btn)
        dlg.exec()

    def _import_prompt(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("导入提示词")
        dlg.setMinimumSize(420, 280)
        dl = QVBoxLayout(dlg)
        edit = QPlainTextEdit()
        edit.setPlaceholderText("粘贴 JSON 格式的提示词...")
        dl.addWidget(edit)
        btn = QPushButton("导入")
        btn.clicked.connect(dlg.accept)
        dl.addWidget(btn)

        def _do_import():
            try:
                data = json.loads(edit.toPlainText().strip())
                name = data.get("name", "新干员")
                prompt = data.get("prompt", "")
            except Exception:
                return QMessageBox.warning(dlg, "导入失败", "JSON 格式错误。")
            for a in self._agents.values():
                if a.get("name") == name and a.get("system_prompt") == prompt:
                    return QMessageBox.information(dlg, "导入", f"「{name}」已存在。")
            aid = memory_id()
            self._agents[aid] = {"name": name, "system_prompt": prompt, "enabled": True}
            self._refresh_list()
            QMessageBox.information(dlg, "导入成功", f"已导入「{name}」。")
            dlg.close()

        btn.clicked.connect(_do_import)
        dlg.exec()

    def _save(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            aid = item.data(Qt.UserRole)
            if aid in self._agents:
                self._agents[aid]["enabled"] = item.text().startswith("✓")
        self._pet.settings["operators"] = self._agents
        save_settings(self._pet.settings)
        QMessageBox.information(self, "保存", "干员列表已保存。双击干员可编辑名称和提示词。")

    def _edit_operator(self, aid):
        a = self._agents.get(aid, {})
        if a.get("preset"):
            QMessageBox.information(self, "预设干员", "预设干员不可编辑。")
            return
        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog)
        dlg.setMinimumSize(400, 300)
        dl = QVBoxLayout(dlg)
        dl.setContentsMargins(0, 0, 0, 0)
        _frameless_title_bar(dl, "编辑干员", dlg.reject)
        form = QFormLayout()
        form.setContentsMargins(16, 12, 16, 12)
        name_edit = QLineEdit(a.get("name", ""))
        form.addRow("名称", name_edit)
        prompt_edit = QPlainTextEdit()
        prompt_edit.setPlainText(a.get("system_prompt", ""))
        form.addRow("提示词", prompt_edit)
        enabled_check = QCheckBox("启用干员")
        enabled_check.setChecked(bool(a.get("enabled", False)))
        form.addRow(enabled_check)
        dl.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        dl.addWidget(btns)
        if dlg.exec() == QDialog.Accepted:
            self._agents[aid] = {
                "name": name_edit.text().strip() or "新干员",
                "system_prompt": prompt_edit.toPlainText().strip(),
                "enabled": enabled_check.isChecked(),
            }
            self._refresh_list()

    def _delete_operator(self):
        item = self.list_widget.currentItem()
        if not item:
            return QMessageBox.information(self, "删除", "请先选择一位干员。")
        aid = item.data(Qt.UserRole)
        a = self._agents.get(aid, {})
        if a.get("preset"):
            return QMessageBox.information(self, "预设干员", "预设干员不可删除。")
        name = a.get("name", "未命名")
        if QMessageBox.question(self, "删除", f"确定删除「{name}」？\n该干员的对话记录也会被清除。",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        del self._agents[aid]
        if self._pet._operator_chats and aid in self._pet._operator_chats:
            del self._pet._operator_chats[aid]
            save_operator_chats(self._pet._operator_chats)
        self._refresh_list()

class OperatorWindow(QDialog):
    def __init__(self, pet_window):
        super().__init__(pet_window)
        self._pet = pet_window
        self.setWindowTitle("来信")
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        lbl = QLabel("选择一位干员通信（由安洁莉娜送达）")
        lbl.setStyleSheet("font-size:12px;color:#888;")
        layout.addWidget(lbl)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(
            "QListWidget{background:transparent;border:none;}"
            "QListWidget::item{padding:10px 12px;border-radius:8px;margin:2px 0;font-size:13px;}"
            f"QListWidget::item:selected{{background:{THEME_ORANGE};color:white;}}"
        )
        self.list_widget.itemDoubleClicked.connect(self._chat_with)
        layout.addWidget(self.list_widget, 1)

        btns = QHBoxLayout()
        mgr_btn = QPushButton("管理干员...")
        mgr_btn.clicked.connect(lambda: (self.close(), self._pet.show_operator_manager()))
        btns.addWidget(mgr_btn)
        btns.addStretch()
        chat_btn = QPushButton("通信")
        chat_btn.clicked.connect(self._chat_with)
        chat_btn.setStyleSheet(
            f"QPushButton{{background:{THEME_ORANGE};color:white;border:none;"
            "padding:4px 16px;border-radius:6px;font-weight:600;}}"
            f"QPushButton:hover{{background:{THEME_ORANGE_LIGHT};}}"
        )
        btns.addWidget(chat_btn)
        layout.addLayout(btns)

        self._refresh()

    def _refresh(self):
        self.list_widget.clear()
        ops = self._pet.settings.get("operators", {})
        for oid, o in ops.items():
            if o.get("enabled"):
                item = QListWidgetItem(o.get("name", "未命名"))
                item.setData(Qt.UserRole, oid)
                self.list_widget.addItem(item)

    def _chat_with(self):
        item = self.list_widget.currentItem()
        if item:
            oid = item.data(Qt.UserRole)
            self.close()
            self._pet.open_operator_chat(oid)

