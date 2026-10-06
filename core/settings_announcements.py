# -*- coding: utf-8 -*-
"""
إعدادات الإعلانات المنطوقة: مفتاح لكل إعلان، والمفتاح الرئيسي، وأصغر قفزة
تقديم يُعلَن بعدها الموضع.

نُقلت كما هي من core/settings.py.
"""


class AnnouncementSettingsMixin:
    """ما يُنطق وما يسكت."""

    # ------------------------------------------------------------------ #
    # تخصيص فئات الإعلان الصوتي
    # ------------------------------------------------------------------ #
    def _get_announce_flag(self, key: str) -> bool:
        return bool(self._data.get(key, True))

    def _set_announce_flag(self, key: str, enabled: bool):
        self._data[key] = bool(enabled)
        self.save()

    def get_announce_accessibility(self) -> bool: return self._get_announce_flag("announce_accessibility")

    def set_announce_accessibility(self, enabled: bool): self._set_announce_flag("announce_accessibility", enabled)

    def is_announcement_enabled(self, setting_key: str = None) -> bool:
        """
        هل الإعلان ده مسموح؟ بيفحص المفتاح الرئيسي ثم المفتاح المحدد.

        الطريقة دي بتقرا من _data مباشرة بدل ما تدوّر على get_<key>. القديم
        كان بيتخطّى الفحص بصمت لو الـ getter مش موجود - وده اللي خلّى
        المفتاح الرئيسي بلا أثر لفترة. دلوقتي أي مفتاح جديد بيشتغل من غير
        ما حد يفتكر يضيف له getter.
        """
        if not self._get_announce_flag("announce_accessibility"):
            return False
        if not setting_key:
            return True
        return self._get_announce_flag(setting_key)

    def get_announce_file_loaded(self) -> bool: return self._get_announce_flag("announce_file_loaded")

    def set_announce_file_loaded(self, enabled: bool): self._set_announce_flag("announce_file_loaded", enabled)

    def get_announce_playlist_position(self) -> bool: return self._get_announce_flag("announce_playlist_position")

    def set_announce_playlist_position(self, enabled: bool): self._set_announce_flag("announce_playlist_position", enabled)

    def get_announce_resume_position(self) -> bool: return self._get_announce_flag("announce_resume_position")

    def set_announce_resume_position(self, enabled: bool): self._set_announce_flag("announce_resume_position", enabled)

    def get_announce_navigation_blocked(self) -> bool: return self._get_announce_flag("announce_navigation_blocked")

    def set_announce_navigation_blocked(self, enabled: bool): self._set_announce_flag("announce_navigation_blocked", enabled)

    def get_announce_playback_state(self) -> bool: return self._get_announce_flag("announce_playback_state")

    def set_announce_playback_state(self, enabled: bool): self._set_announce_flag("announce_playback_state", enabled)

    def get_announce_volume_changes(self) -> bool: return self._get_announce_flag("announce_volume_changes")

    def set_announce_volume_changes(self, enabled: bool): self._set_announce_flag("announce_volume_changes", enabled)

    def get_announce_mute_toggle(self) -> bool: return self._get_announce_flag("announce_mute_toggle")

    def set_announce_mute_toggle(self, enabled: bool): self._set_announce_flag("announce_mute_toggle", enabled)

    _VALID_SEEK_MODES = ("disabled", "enabled")

    # صفر، ودقيقة، و5، و10، و30 دقيقة - نفس مقادير القفز في البرنامج
    _VALID_SEEK_MIN_SECONDS = (0, 60, 300, 600, 1800)

    def get_announce_seek_mode(self) -> str:
        value = self._data.get("announce_seek_mode", "enabled")
        return value if value in self._VALID_SEEK_MODES else "enabled"

    def set_announce_seek_mode(self, mode: str):
        self._data["announce_seek_mode"] = mode if mode in self._VALID_SEEK_MODES else "enabled"
        self.save()

    def get_announce_seek_feedback(self) -> bool:
        return self.get_announce_seek_mode() != "disabled"

    def get_announce_seek_min_seconds(self) -> int:
        try:
            value = int(self._data.get("announce_seek_min_seconds", 0))
        except (TypeError, ValueError):
            return 0
        return value if value in self._VALID_SEEK_MIN_SECONDS else 0

    def set_announce_seek_min_seconds(self, seconds: int):
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            seconds = 0
        self._data["announce_seek_min_seconds"] = (
            seconds if seconds in self._VALID_SEEK_MIN_SECONDS else 0
        )
        self.save()

    def get_announce_time_status(self) -> bool: return self._get_announce_flag("announce_time_status")

    def set_announce_time_status(self, enabled: bool): self._set_announce_flag("announce_time_status", enabled)

    def get_announce_duration_announce(self) -> bool: return self._get_announce_flag("announce_duration_announce")

    def set_announce_duration_announce(self, enabled: bool): self._set_announce_flag("announce_duration_announce", enabled)

    def get_announce_remaining_time(self) -> bool: return self._get_announce_flag("announce_remaining_time")

    def set_announce_remaining_time(self, enabled: bool): self._set_announce_flag("announce_remaining_time", enabled)

    def get_announce_file_info(self) -> bool: return self._get_announce_flag("announce_file_info")

    def set_announce_file_info(self, enabled: bool): self._set_announce_flag("announce_file_info", enabled)

    def get_announce_buffering(self) -> bool: return bool(self._data.get("announce_buffering", False))

    def set_announce_buffering(self, enabled: bool): self._set_announce_flag("announce_buffering", enabled)

    def get_announce_playback_speed(self) -> bool: return self._get_announce_flag("announce_playback_speed")

    def set_announce_playback_speed(self, enabled: bool): self._set_announce_flag("announce_playback_speed", enabled)

    def get_announce_bookmarks(self) -> bool: return self._get_announce_flag("announce_bookmarks")

    def set_announce_bookmarks(self, enabled: bool): self._set_announce_flag("announce_bookmarks", enabled)

    def get_announce_sleep_timer(self) -> bool: return self._get_announce_flag("announce_sleep_timer")

    def set_announce_sleep_timer(self, enabled: bool): self._set_announce_flag("announce_sleep_timer", enabled)

    def get_announce_settings_import_export(self) -> bool: return self._get_announce_flag("announce_settings_import_export")

    def set_announce_settings_import_export(self, enabled: bool): self._set_announce_flag("announce_settings_import_export", enabled)

    def get_announce_fullscreen(self) -> bool: return self._get_announce_flag("announce_fullscreen")

    def set_announce_fullscreen(self, enabled: bool): self._set_announce_flag("announce_fullscreen", enabled)

    def get_announce_equalizer(self) -> bool: return self._get_announce_flag("announce_equalizer")

    def set_announce_equalizer(self, enabled: bool): self._set_announce_flag("announce_equalizer", enabled)

    def get_announce_stream_title(self) -> bool: return self._get_announce_flag("announce_stream_title")

    def set_announce_stream_title(self, enabled: bool): self._set_announce_flag("announce_stream_title", enabled)
