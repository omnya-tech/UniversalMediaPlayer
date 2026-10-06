# -*- coding: utf-8 -*-
"""
إعلانات قارئ الشاشة في النافذة الرئيسية: الإعلان العام، وموضع التقديم،
وإعلانات الوقت (T وR وE)، والمفتاح الرئيسي Ctrl+Alt+A.

نُقلت كما هي من gui/main_window.py لتصغيره.
"""

import wx

from gui.format_utils import format_time


class AnnounceMixin:
    """ما يُنطق للمستخدم من النافذة الرئيسية."""

    def _announce(self, text: str, setting_key: str = None, force: bool = False):
        if not text: return
        if not force:
            # الفحص كله في الإعدادات: المفتاح الرئيسي ثم المفتاح المحدد
            # (شوف Settings.is_announcement_enabled)
            # force للإعلانات اللي المستخدم طلبها صراحةً
            if not self.settings.is_announcement_enabled(setting_key): return
        if hasattr(self, "announcer") and self.announcer:
            self.announcer.announce(text)

    def _announce_seek(self, position: float, seek_type: str = "seconds",
                       jump_seconds: float = None):
        """
        ينطق الموضع بعد قفزة.

        jump_seconds هو مقدار القفزة. لو المستخدم ضابط حدًّا أدنى في
        الخيارات، القفزات الأصغر منه بتفضل ساكتة - علشان الضغط المتكرر
        على سهم العشر ثواني ما يبقاش ثرثرة. قفزات لوحة الأرقام والذهاب
        لوقت محدد بتتعلن دايمًا: دي نقلة مقصودة لمكان بعينه.
        """
        mode = "all"
        if hasattr(self.settings, "get_announce_seek_mode"):
            try: mode = self.settings.get_announce_seek_mode()
            except Exception: pass
        if mode == "disabled": return

        if jump_seconds is not None:
            try:
                minimum = self.settings.get_announce_seek_min_seconds()
            except Exception:
                minimum = 0
            if minimum and abs(jump_seconds) < minimum:
                return

        should_announce = False
        if mode in ("enabled", "all"): should_announce = True
        elif mode == "seconds_only" and seek_type in ("seconds", "numpad"): should_announce = True
        elif mode == "minutes_only" and seek_type in ("minutes", "numpad"): should_announce = True
        if should_announce:
            msg = self.tr.t("announce_seek_position", time=format_time(position))
            self._announce(msg)

    def _on_toggle_accessibility_shortcut(self, event):
        current = True
        if hasattr(self.settings, "get_announce_accessibility"):
            try: current = self.settings.get_announce_accessibility()
            except Exception: pass
        elif hasattr(self.settings, "get_enable_accessibility"):
            try: current = self.settings.get_enable_accessibility()
            except Exception: pass
        new_state = not current
        for setter_name in ["set_announce_accessibility", "set_enable_accessibility", "set_announce_enabled", "set_accessibility_enabled"]:
            if hasattr(self.settings, setter_name):
                try: getattr(self.settings, setter_name)(new_state)
                except Exception: pass
        if hasattr(self.settings, "set"):
            try:
                self.settings.set("announce_accessibility", new_state)
                self.settings.set("enable_accessibility", new_state)
            except Exception: pass
        msg_key = "announce_accessibility_enabled" if new_state else "announce_accessibility_disabled"
        self._announce(self.tr.t(msg_key), force=True)

    def _on_announce_time_status(self, event):
        # الوقت الحالي وحده: المتبقي له R والمدة الكاملة لها E
        current = self.engine.get_current_position()
        message = self.tr.t("announce_time_status", current=format_time(current))
        self.status_bar.SetStatusText(message)
        self._announce_debounced(message, "announce_time_status")

    def _on_announce_duration(self, event):
        message = self.tr.t("announce_duration", total=format_time(self.engine.duration))
        self.status_bar.SetStatusText(message)
        self._announce_debounced(message, "announce_duration_announce")

    def _on_announce_remaining_time(self, event):
        current = self.engine.get_current_position()
        remaining = max(0.0, self.engine.duration - current)
        message = self.tr.t("announce_remaining_only", remaining=format_time(remaining))
        self.status_bar.SetStatusText(message)
        self._announce_debounced(message, "announce_remaining_time")

    def _announce_debounced(self, message, setting_key=None):
        self._pending_manual_announce_message = (message, setting_key)
        self._manual_announce_timer.Stop()
        self._manual_announce_timer.Start(120, wx.TIMER_ONE_SHOT)

    def _on_manual_announce_timer(self, event):
        if self._pending_manual_announce_message is not None:
            msg, key = self._pending_manual_announce_message
            self._announce(msg, setting_key=key)
            self._pending_manual_announce_message = None
