# -*- coding: utf-8 -*-
"""
فتح الملفات والمجلدات في النافذة الرئيسية، والانتقال بين ملفات المجلد،
وقائمة الملفات الأخيرة.

نُقلت كما هي من gui/main_window.py لتصغيره.
"""

import os
import threading

import wx

from core.playlist import SUPPORTED_EXTENSIONS, is_video_extension
from core.playlist_files import is_playlist_file
from core.streams import is_stream_url
from gui.format_utils import format_time
from gui.playlist_mixin import open_media_wildcard


class FileOpenMixin:
    """فتح الوسائط والتنقل بين الملفات."""

    def _on_open(self, event):
        with wx.FileDialog(
            self,
            self.tr.t("dialog_open_title"),
            wildcard=open_media_wildcard(self.tr),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            dlg.SetFilterIndex(0)
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            path = dlg.GetPath()
        self._open_specific_path(path)

    def _on_open_folder(self, event):
        with wx.DirDialog(
            self,
            self.tr.t("dialog_open_folder_title"),
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            folder = dlg.GetPath()
        self._open_folder_path(folder)

    def _open_folder_path(self, folder):
        try: entries = sorted(os.listdir(folder), key=str.lower)
        except OSError:
            self._announce(self.tr.t("announce_folder_no_media"), "announce_navigation_blocked")
            return
        first_file = next((os.path.join(folder, n) for n in entries if os.path.splitext(n)[1].lower() in SUPPORTED_EXTENSIONS), None)
        if first_file is None:
            self._announce(self.tr.t("announce_folder_no_media"), "announce_navigation_blocked")
            return
        self._open_specific_path(first_file)

    def _open_specific_path(self, path):
        # روابط وملفات قوائم ليها طريقها (شوف PlaylistMixin._open_any)
        if self._open_any(path):
            return
        if is_playlist_file(path) or is_stream_url(path):
            # قائمة فشلت (والخطأ اتعرض): ما تتسلّمش لـ VLC كملف وسائط
            return
        self._save_current_position()
        self.playlist.load_folder_of(path)
        self._load_and_play(self.playlist.current or path)

    def _open_album_paths(self, paths):
        # فتح وتشغيل مجموعة ملفات كألبوم مترابط بالترتيب بدءاً من أول ملف
        if not paths: return
        self._save_current_position()
        self.playlist.load_custom_list(paths, initial_path=paths[0])
        self._load_and_play(self.playlist.current or paths[0])

    def _load_and_play(self, path):
        if self._is_loading_file:
            self._pending_open_path = path
            return
        self._pending_open_path = None
        self._is_loading_file = True
        self.status_bar.SetStatusText(self.tr.t("status_loading"))
        self._update_info_labels()
        self._refresh_transport_buttons_state()

        # أول ملف بعد فتح البرنامج ممكن يستنى تجهيز المحرك (شوف
        # PlayerEngine.warm_up). الانتظار ده بيتقال بدل سكوت محيّر.
        # الطلب اللي بيوصل أثناء التحميل بيتحفظ ويتنفّذ بعده
        # (شوف _on_file_opened) بدل ما يترمي.
        # (ضغطة PageDown سريعة كانت بتضيع)
        engine_ready = self.engine.is_ready
        if not engine_ready:
            self._announce(self.tr.t("status_engine_warming"), "announce_playback_state")

        def worker():
            ok = self.engine.open(path)
            wx.CallAfter(self._on_file_opened, path, ok)
        threading.Thread(target=worker, daemon=True).start()

    def _on_file_opened(self, path, ok):
        self._is_loading_file = False

        # طلب وصل أثناء التحميل (شوف _load_and_play): الأحدث هو اللي
        # المستخدم عايزه، فبنفتحه بدل اللي خلص
        pending = getattr(self, "_pending_open_path", None)
        if pending is not None and pending != path:
            self._pending_open_path = None
            self._load_and_play(pending)
            return
        self._pending_open_path = None

        if not ok:
            self._keep_focus_on_open = False
            self._refresh_transport_buttons_state()
            return

        is_stream = is_stream_url(path)
        if is_stream:
            self._current_format = self.tr.t("stream_format")
        else:
            self._current_format = os.path.splitext(path)[1].lstrip(".").upper()
        self._current_file_path = path
        self._current_file_name = self._display_name(path)
        self._update_window_title()

        # البث: الفيديو بيبان بعد ما يبدأ (شوف _apply_state_change)
        has_video = False if is_stream else is_video_extension(os.path.splitext(path)[1])
        self._apply_media_layout(has_video)

        self.file_label.SetLabel(self._current_file_name)
        self.file_label.SetName(self._current_file_name)

        if self.engine.duration and self.engine.duration > 0:
            duration_secs = int(self.engine.duration)
            self.seek_slider.SetMax(duration_secs)
            self.seek_slider.SetPageSize(max(1, duration_secs // 10))
            self.seek_slider.SetLineSize(max(1, duration_secs // 50))
        else:
            self.seek_slider.SetMax(100)

        self.seek_slider.SetValue(0)
        self._update_info_labels()
        self._refresh_transport_buttons_state()

        self.settings.add_recent_file(path)
        self._refresh_recent_files_menu()

        # السرعة المحفوظة للملف ده (شوف Settings.get_file_speed)
        saved_speed = self.settings.get_file_speed(path)
        if abs(saved_speed - self.engine.speed) > 0.01:
            self.engine.set_speed(saved_speed)
        self._announce(self.tr.t("announce_file_loaded", name=self._current_file_name), "announce_file_loaded")

        info = self.engine.get_media_info()
        if is_stream:
            self._announce(self.tr.t("announce_stream_info"), "announce_file_info")
        elif info:
            duration_text = format_time(info["duration"])
            bit_rate = info.get("bit_rate")
            if bit_rate:
                kbps = int(bit_rate / 1000)
                text = self.tr.t("announce_file_info", format=self._current_format, bitrate=kbps, duration=duration_text)
            else:
                text = self.tr.t("announce_file_info_no_bitrate", format=self._current_format, duration=duration_text)
            self._announce(text, "announce_file_info")
        if len(self.playlist) > 1:
            self._announce(self.tr.t("announce_playlist_position", index=self.playlist.current_position, total=len(self.playlist)), "announce_playlist_position")

        # إلغاء التركيز عن العناصر ونقله للنافذة الرئيسية للتحكم باختصارات لوحة المفاتيح.
        # إلا لو المحرر هو اللي فتح الملف: SetFocus كان بينقل المستخدم من
        # نافذة المحرر للمشغّل وهو شغّال فيها
        if not getattr(self, "_keep_focus_on_open", False):
            self.SetFocus()
        self._keep_focus_on_open = False

        # البث المباشر مالوش موضع يتستكمل منه
        last_position = 0.0 if is_stream else self.settings.get_last_position(path)
        if last_position > 1.0 and self.settings.get_auto_resume():
            self.engine.play_and_seek(last_position)
            self._announce(self.tr.t("announce_resume_position", time=format_time(last_position)), "announce_resume_position")
        else: self.engine.play()

        # قفزة اتطلبت والملف بيتحمّل (End أو أرقام النم باد بعد PageDown)
        # بتتنفّذ دلوقتي إن المدة بقت معروفة.
        # (شوف SeekingMixin._defer_until_duration_known)
        # والمدة ممكن تكون لسه صفر هنا لو التحليل اتأخر؛ ساعتها بتضيع.
        self._run_pending_seek()

    def _refresh_recent_files_menu(self):
        for item in list(self._recent_menu.GetMenuItems()):
            self._recent_menu.Delete(item.GetId())

        recent = self.settings.get_recent_files()
        if not recent:
            empty_item = self._recent_menu.Append(wx.ID_ANY, self.tr.t("menu_recent_files_empty"))
            self._recent_menu.Enable(empty_item.GetId(), False)
            return

        for path in recent:
            item = self._recent_menu.Append(wx.ID_ANY, self._display_name(path))
            self.Bind(wx.EVT_MENU, lambda evt, p=path: self._open_specific_path(p), item)

    def _on_next(self, event):
        self._advance_to(self.playlist.next(), no_target_key="announce_no_next_file")

    def _on_previous(self, event):
        self._advance_to(self.playlist.previous(), no_target_key="announce_no_previous_file")

    def _advance_to(self, target_path, no_target_key):
        if target_path is None:
            self._announce(self.tr.t(no_target_key), "announce_navigation_blocked")
            return
        self._save_current_position()
        self._load_and_play(target_path)
