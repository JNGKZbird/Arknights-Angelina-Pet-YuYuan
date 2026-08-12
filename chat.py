# Chat workers
from PySide6.QtCore import QThread, Signal
from core import chat_api_request, CHATTER_PROMPT

class ChatWorker(QThread):
    reply_ready = Signal(str, bool)

    def __init__(self, base_url, api_key, model, messages, parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.messages = messages

    def run(self):
        try:
            reply = chat_api_request(
                self.base_url,
                self.api_key,
                self.model,
                self.messages,
            )
            self.reply_ready.emit(reply, True)
        except Exception as exc:
            self.reply_ready.emit(str(exc), False)

class ChatterWorker(QThread):
    reply_ready = Signal(str, bool)

    def __init__(self, base_url, api_key, model, system_prompt, parent=None):
        super().__init__(parent)
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.system_prompt = system_prompt

    def run(self):
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": CHATTER_PROMPT},
            ]
            reply = chat_api_request(
                self.base_url, self.api_key, self.model, messages
            )
            self.reply_ready.emit(reply, True)
        except Exception as exc:
            self.reply_ready.emit(str(exc), False)

