# -*- coding: utf-8 -*-
"""
ما يُحفظ للوسائط: سرعة كل ملف، والعلامات المرجعية وأسماؤها، والمعادل الصوتي،
ومؤقت النوم، وآخر مجلد لقوائم التشغيل.

نُقلت كما هي من core/settings.py.
"""

import os

from core import equalizer


_MAX_REMEMBERED_POSITIONS = 200
_MAX_BOOKMARKS_PER_FILE = 50
_MIN_PLAYBACK_SPEED = 0.5
_MAX_PLAYBACK_SPEED = 2.0
_DEFAULT_SLEEP_TIMER_MINUTES = 30


class MediaSettingsMixin:
    """سرعة الملفات والعلامات والمعادل ومؤقت النوم."""

    # ------------------------------------------------------------------ #
    # سرعة التشغيل لكل ملف
    # ------------------------------------------------------------------ #
    def get_file_speed(self, path: str) -> float:
        """
        السرعة المحفوظة للملف ده، أو 1.0 لو مفيش.

        السرعة تفضيل بيخص نوع المحتوى لا البرنامج: كتاب صوتي بسرعة 1.5
        وموسيقى بسرعة عادية، والمستخدم ما يعيدش ضبطها كل مرة.
        """
        speeds = self._data.get("file_speeds", {})
        try:
            value = float(speeds.get(path, 1.0))
        except (TypeError, ValueError):
            return 1.0
        return value if _MIN_PLAYBACK_SPEED <= value <= _MAX_PLAYBACK_SPEED else 1.0

    def set_file_speed(self, path: str, speed: float):
        speeds = self._data.setdefault("file_speeds", {})
        value = max(_MIN_PLAYBACK_SPEED, min(_MAX_PLAYBACK_SPEED, float(speed)))
        if abs(value - 1.0) < 0.01:
            speeds.pop(path, None)
        else:
            speeds[path] = value
        # نفس حد المواضع المحفوظة، والأقدم يتشال الأول
        if len(speeds) > _MAX_REMEMBERED_POSITIONS:
            for key in list(speeds)[: len(speeds) - _MAX_REMEMBERED_POSITIONS]:
                speeds.pop(key, None)
        self.save()

    # ------------------------------------------------------------------ #
    # النقاط المرجعية
    # ------------------------------------------------------------------ #
    def get_bookmark_entries(self, path: str):
        """
        العلامات كقائمة من (الثانية، الاسم).

        الإصدارات الأقدم كانت بتخزّن أرقامًا مجردة، فبنقبل الشكلين -
        علامات المستخدم القديمة ما تضيعش لمجرد إننا ضفنا الأسماء.
        """
        entries = []
        for item in self._data.get("bookmarks", {}).get(path, []):
            if isinstance(item, dict):
                try:
                    entries.append((float(item.get("at", 0.0)), str(item.get("name", ""))))
                except (TypeError, ValueError):
                    continue
            else:
                try:
                    entries.append((float(item), ""))
                except (TypeError, ValueError):
                    continue
        entries.sort(key=lambda entry: entry[0])
        return entries

    def get_bookmark_name(self, path: str, seconds: float) -> str:
        for at, name in self.get_bookmark_entries(path):
            if abs(at - seconds) < 0.5:
                return name
        return ""

    def rename_bookmark(self, path: str, seconds: float, name: str) -> bool:
        bookmarks = self._data.setdefault("bookmarks", {})
        points = bookmarks.get(path, [])
        for index, item in enumerate(points):
            at = item.get("at") if isinstance(item, dict) else item
            try:
                at = float(at)
            except (TypeError, ValueError):
                continue
            if abs(at - seconds) < 0.5:
                points[index] = {"at": at, "name": str(name).strip()}
                self.save()
                return True
        return False

    def get_bookmarks(self, path: str):
        """مواضع العلامات فقط - بيمرّ على get_bookmark_entries فبيقبل الشكلين."""
        return [at for at, _name in self.get_bookmark_entries(path)]

    def add_bookmark(self, path: str, seconds: float, name: str = "") -> bool:
        bookmarks = self._data.setdefault("bookmarks", {})
        points = bookmarks.setdefault(path, [])
        existing_seconds = [at for at, _name in self.get_bookmark_entries(path)]
        if any(abs(existing - seconds) < 0.5 for existing in existing_seconds):
            return False
        points.append({"at": float(seconds), "name": str(name).strip()})
        points.sort(key=lambda item: item["at"] if isinstance(item, dict) else item)
        if len(points) > _MAX_BOOKMARKS_PER_FILE:
            points.pop(0)
        self.save()
        return True

    def clear_bookmarks(self, path: str):
        self._data.get("bookmarks", {}).pop(path, None)
        self.save()

    # ------------------------------------------------------------------ #
    # مؤقت النوم
    # ------------------------------------------------------------------ #
    def get_sleep_timer_last_minutes(self) -> int:
        return int(self._data.get("sleep_timer_last_minutes", _DEFAULT_SLEEP_TIMER_MINUTES))

    def set_sleep_timer_last_minutes(self, minutes: int):
        self._data["sleep_timer_last_minutes"] = max(1, int(minutes))
        self.save()

    # ------------------------------------------------------------------ #
    # المعادل
    # ------------------------------------------------------------------ #
    def get_equalizer_mode(self) -> str:
        mode = self._data.get("equalizer_mode", equalizer.MODE_OFF)
        return mode if equalizer.is_valid_mode(mode) else equalizer.MODE_OFF

    def set_equalizer_mode(self, mode: str):
        self._data["equalizer_mode"] = mode if equalizer.is_valid_mode(mode) else equalizer.MODE_OFF
        self.save()

    def get_equalizer_custom(self):
        """(التضخيم المسبق، [عشر قيم]) - دايمًا صالحة ومحصورة في الحدود."""
        preamp = equalizer.clamp_gain(self._data.get("equalizer_custom_preamp", 0.0))
        bands = equalizer.normalize_bands(self._data.get("equalizer_custom_bands"))
        return preamp, bands

    def set_equalizer_custom(self, preamp, bands):
        self._data["equalizer_custom_preamp"] = equalizer.clamp_gain(preamp)
        self._data["equalizer_custom_bands"] = equalizer.normalize_bands(bands)
        self.save()

    def has_equalizer_custom(self) -> bool:
        """هل فيه قيم مخصصة فعلًا (مش كلها أصفار)؟"""
        preamp, bands = self.get_equalizer_custom()
        return any(bands) or bool(preamp)

    # ------------------------------------------------------------------ #
    # قوائم التشغيل
    # ------------------------------------------------------------------ #
    def get_playlist_last_folder(self) -> str:
        folder = self._data.get("playlist_last_folder") or ""
        return folder if isinstance(folder, str) and os.path.isdir(folder) else ""

    def set_playlist_last_folder(self, folder: str):
        self._data["playlist_last_folder"] = folder or ""
        self.save()
