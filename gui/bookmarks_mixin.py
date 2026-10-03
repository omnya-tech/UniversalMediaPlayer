# -*- coding: utf-8 -*-
"""
توابع النقاط المحفوظة (العلامات المرجعية).

    اتفصلت عن MainWindow اللي كانت 98 تابع في ملف واحد. الـmixin
    بيحافظ على نفس self ونفس السلوك بالظبط - مجرد تقسيم للملف.
"""

import wx

from gui.format_utils import format_time


class BookmarksMixin:
    """توابع النقاط المحفوظة (العلامات المرجعية)."""

    def _add_bookmark(self):
        if not self._current_file_path: return
        position = self.engine.get_effective_position()
        if self.settings.add_bookmark(self._current_file_path, position): self._announce(self.tr.t("announce_bookmark_added", time=format_time(position)), "announce_bookmarks")
        else: self._announce(self.tr.t("announce_bookmark_duplicate"), "announce_bookmarks")

    def _jump_bookmark(self, forward: bool):
        if not self._current_file_path: return
        bookmarks = self.settings.get_bookmarks(self._current_file_path)
        if not bookmarks:
            self._announce(self.tr.t("announce_bookmark_none"), "announce_bookmarks")
            return
        current = self.engine.get_effective_position()
        epsilon = 0.5
        if forward: target = next((point for point in bookmarks if point > current + epsilon), bookmarks[0])
        else: target = next((point for point in reversed(bookmarks) if point < current - epsilon), bookmarks[-1])
        self.engine.seek(target)
        # العلامة المسمّاة تُعلَن باسمها، فالمستخدم يعرف أين وصل لا عند
        # أي دقيقة فقط
        name = self.settings.get_bookmark_name(self._current_file_path, target)
        key = "announce_bookmark_jumped_named" if name else "announce_bookmark_jumped"
        self._announce(
            self.tr.t(key, time=format_time(target), name=name), "announce_bookmarks"
        )

    def _rename_bookmark(self):
        """
        يسمّي أقرب علامة للموضع الحالي.

        العلامة بلا اسم مجرد رقم: المستخدم بيسمع "علامة عند 42 دقيقة"
        وما يعرفش ليه حطّها. الاسم بيحوّلها لأداة حقيقية.
        """
        if not self._current_file_path:
            return
        entries = self.settings.get_bookmark_entries(self._current_file_path)
        if not entries:
            self._announce(self.tr.t("announce_no_bookmarks"), force=True)
            return

        position = self.engine.get_effective_position()
        at, current_name = min(entries, key=lambda entry: abs(entry[0] - position))

        with wx.TextEntryDialog(
            self,
            self.tr.t("bookmark_name_prompt", time=format_time(at)),
            self.tr.t("bookmark_name_title"),
            value=current_name,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            name = dialog.GetValue().strip()

        if self.settings.rename_bookmark(self._current_file_path, at, name):
            key = "announce_bookmark_named" if name else "announce_bookmark_name_cleared"
            self._announce(
                self.tr.t(key, name=name, time=format_time(at)), "announce_bookmarks"
            )

    def _clear_bookmarks(self):
        if not self._current_file_path: return
        self.settings.clear_bookmarks(self._current_file_path)
        self._announce(self.tr.t("announce_bookmarks_cleared"), "announce_bookmarks")
