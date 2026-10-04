# -*- coding: utf-8 -*-
"""
روابط البث وقوائم التشغيل المحفوظة: نافذة فتح رابط، ونافذة تحرير
القائمة، وحفظ وفتح ملفات M3U8.

القراءة والكتابة نفسها في core/playlist_files.py، والقائمة في
core/playlist.py. هنا الواجهة والربط بالنافذة الرئيسية.
"""

import os

import wx

from core.playlist import SUPPORTED_EXTENSIONS
from core.playlist_files import (
    PLAYLIST_EXTENSIONS,
    PlaylistFileError,
    is_playlist_file,
    read_playlist,
    write_m3u8,
)
from core.streams import is_stream_url, normalize_stream_url, stream_display_name
from gui.dialog_helpers import bind_escape_closes, bind_space_like_enter
from i18n.plural import count_phrase


def _patterns(extensions):
    return ";".join(f"*{ext}" for ext in sorted(extensions))


def open_media_wildcard(tr):
    """
    فلتر نافذة الفتح من قائمة الصيغ المدعومة فعلًا.

    الفلتر القديم كان نص ثابت فيه 11 صيغة بس، فملفات زي m4b (الكتب
    المسموعة) وogg وopus ما كانتش بتظهر إلا باختيار "كل الملفات".
    """
    everything = _patterns(SUPPORTED_EXTENSIONS | set(PLAYLIST_EXTENSIONS))
    return "|".join([
        f"{tr.t('wildcard_media')}|{everything}",
        f"{tr.t('wildcard_playlists')}|{_patterns(PLAYLIST_EXTENSIONS)}",
        f"{tr.t('wildcard_all')}|*.*",
    ])


def _clipboard_url():
    """رابط من الحافظة لو موجود - عشان اللي نسخ الرابط ما يلصقش بإيده."""
    text = None
    try:
        if wx.TheClipboard.Open():
            try:
                data = wx.TextDataObject()
                if wx.TheClipboard.GetData(data):
                    text = data.GetText()
            finally:
                wx.TheClipboard.Close()
    except Exception:
        return ""
    return normalize_stream_url(text) or ""


class OpenUrlDialog(wx.Dialog):
    def __init__(self, parent, tr, initial=""):
        super().__init__(parent, title=tr.t("url_dialog_title"))
        self.tr = tr
        self.url = None

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        label = wx.StaticText(panel, label=tr.t("url_dialog_label"))
        self.text = wx.TextCtrl(panel, value=initial or _clipboard_url(), size=(460, -1))
        self.text.SetName(tr.t("url_dialog_label").rstrip(":"))
        hint = wx.StaticText(panel, label=tr.t("url_dialog_hint"))
        hint.Wrap(460)
        sizer.Add(label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 10)
        sizer.Add(self.text, 0, wx.EXPAND | wx.ALL, 10)
        sizer.Add(hint, 0, wx.LEFT | wx.RIGHT, 10)

        buttons = wx.StdDialogButtonSizer()
        ok_btn = wx.Button(panel, wx.ID_OK, label=tr.t("btn_open"))
        ok_btn.SetDefault()
        buttons.AddButton(ok_btn)
        buttons.AddButton(wx.Button(panel, wx.ID_CANCEL, label=tr.t("btn_cancel")))
        buttons.Realize()
        sizer.Add(buttons, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        panel.SetSizer(sizer)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(outer)
        self.CenterOnParent()

        ok_btn.Bind(wx.EVT_BUTTON, self._on_ok)
        bind_escape_closes(self)
        self.text.SetFocus()
        self.text.SelectAll()

    def _on_ok(self, event):
        url = normalize_stream_url(self.text.GetValue())
        if not url:
            wx.MessageBox(self.tr.t("url_dialog_invalid"), self.tr.t("url_dialog_title"),
                          wx.ICON_WARNING, self)
            self.text.SetFocus()
            return
        self.url = url
        self.EndModal(wx.ID_OK)


def ask_for_url(parent, tr):
    with OpenUrlDialog(parent, tr) as dialog:
        if dialog.ShowModal() == wx.ID_OK:
            return dialog.url
    return None


class PlaylistDialog(wx.Dialog):
    """
    تحرير قائمة التشغيل الحالية مباشرة.

    كل عملية بتتطبّق على القائمة الحقيقية فورًا (مفيش "حفظ" للتعديلات
    نفسها) - المستخدم بيسمع "التالي" يتصرف حسب اللي عمله على طول.
    الأوامر كلها بالكيبورد من القائمة نفسها، والأزرار لنفس الأوامر.
    """

    def __init__(self, parent):
        self.main = parent
        self.tr = parent.tr
        tr = self.tr
        super().__init__(parent, title=tr.t("pl_dialog_title"),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.play_requested = None

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(wx.StaticText(panel, label=tr.t("pl_list_label")), 0, wx.LEFT | wx.TOP, 10)
        self.list = wx.ListBox(panel, size=(520, 300), style=wx.LB_SINGLE)
        self.list.SetName(tr.t("pl_dialog_title"))
        sizer.Add(self.list, 1, wx.EXPAND | wx.ALL, 10)

        hint = wx.StaticText(panel, label=tr.t("pl_hint"))
        hint.Wrap(520)
        sizer.Add(hint, 0, wx.LEFT | wx.RIGHT, 10)

        grid = wx.GridSizer(cols=4, vgap=6, hgap=6)
        actions = [
            ("pl_btn_play", self._on_play),
            ("pl_btn_remove", self._on_remove),
            ("pl_btn_up", lambda e: self._move(-1)),
            ("pl_btn_down", lambda e: self._move(1)),
            ("pl_btn_add_files", self._on_add_files),
            ("pl_btn_add_folder", self._on_add_folder),
            ("pl_btn_add_url", self._on_add_url),
            ("pl_btn_clear", self._on_clear),
            ("pl_btn_open", self._on_open_playlist),
            ("pl_btn_save", self._on_save),
        ]
        self.buttons = {}
        for key, handler in actions:
            button = wx.Button(panel, label=tr.t(key))
            button.Bind(wx.EVT_BUTTON, handler)
            grid.Add(button, 0, wx.EXPAND)
            self.buttons[key] = button
        close_btn = wx.Button(panel, wx.ID_CANCEL, label=tr.t("btn_close"))
        grid.Add(close_btn, 0, wx.EXPAND)
        sizer.Add(grid, 0, wx.EXPAND | wx.ALL, 10)

        panel.SetSizer(sizer)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(outer)
        self.CenterOnParent()

        self.list.Bind(wx.EVT_LISTBOX_DCLICK, self._on_play)
        self.list.Bind(wx.EVT_LISTBOX, lambda e: self._refresh_buttons())
        self.list.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        bind_space_like_enter(self)

        self._refresh(select=max(0, self.main.playlist.current_index))
        self.list.SetFocus()

    # ------------------------------------------------------------------ #

    @property
    def playlist(self):
        return self.main.playlist

    def _refresh(self, select=None):
        entries = self.playlist.entries
        current = self.playlist.current_index
        labels = []
        for index, entry in enumerate(entries):
            name = self.main._display_name(entry)
            labels.append(self.tr.t("pl_item_current", name=name) if index == current else name)
        self.list.Set(labels)
        if entries:
            if select is None:
                select = 0
            self.list.SetSelection(max(0, min(select, len(entries) - 1)))
        self._refresh_buttons()

    def _refresh_buttons(self):
        count = self.list.GetCount()
        selected = self.list.GetSelection()
        has_selection = selected != wx.NOT_FOUND
        self.buttons["pl_btn_play"].Enable(has_selection)
        self.buttons["pl_btn_remove"].Enable(has_selection)
        self.buttons["pl_btn_up"].Enable(has_selection and selected > 0)
        self.buttons["pl_btn_down"].Enable(has_selection and selected < count - 1)
        self.buttons["pl_btn_clear"].Enable(count > 0)
        self.buttons["pl_btn_save"].Enable(count > 0)

    def _announce(self, text):
        # الإعلان هنا رد على أمر صريح من المستخدم، فبيتقال دايمًا
        self.main._announce(text, force=True)

    def _selected(self):
        index = self.list.GetSelection()
        return None if index == wx.NOT_FOUND else index

    # ------------------------------------------------------------------ #

    def _on_char_hook(self, event):
        key = event.GetKeyCode()
        if key == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CANCEL)
            return
        if event.ControlDown() and key == ord("S"):
            self._on_save(None)
            return
        if event.ControlDown() and key == ord("O"):
            self._on_open_playlist(None)
            return
        event.Skip()

    def _on_list_key(self, event):
        key = event.GetKeyCode()
        if key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._on_play(None)
        elif key in (wx.WXK_DELETE, wx.WXK_NUMPAD_DELETE):
            self._on_remove(None)
        elif event.AltDown() and key == wx.WXK_UP:
            self._move(-1)
        elif event.AltDown() and key == wx.WXK_DOWN:
            self._move(1)
        else:
            event.Skip()

    def _on_play(self, event):
        index = self._selected()
        if index is None:
            return
        self.play_requested = index
        self.EndModal(wx.ID_OK)

    def _on_remove(self, event):
        index = self._selected()
        if index is None:
            return
        name = self.main._display_name(self.playlist.entries[index])
        self.playlist.remove(index)
        self._refresh(select=index)
        self._announce(self.tr.t("pl_announce_removed", name=name))
        self.list.SetFocus()

    def _move(self, step):
        index = self._selected()
        if index is None:
            return
        target = self.playlist.move(index, step)
        if target == -1:
            return
        self._refresh(select=target)
        name = self.main._display_name(self.playlist.entries[target])
        self._announce(self.tr.t("pl_announce_moved", name=name, index=target + 1,
                                 total=len(self.playlist)))
        self.list.SetFocus()

    def _after_add(self, added):
        if added:
            self._refresh(select=len(self.playlist) - added)
            self._announce(self.tr.t("pl_announce_added",
                                     items=count_phrase(self.tr, "count_items", added)))
        else:
            self._announce(self.tr.t("pl_announce_nothing_added"))
        self.list.SetFocus()

    def _on_add_files(self, event):
        with wx.FileDialog(self, self.tr.t("pl_btn_add_files").rstrip("."),
                           wildcard=open_media_wildcard(self.tr),
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            paths = dialog.GetPaths()
        self._after_add(self.playlist.add(paths))

    def _on_add_folder(self, event):
        with wx.DirDialog(self, self.tr.t("pl_btn_add_folder").rstrip("."),
                          style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            folder = dialog.GetPath()
        try:
            names = sorted(os.listdir(folder), key=str.lower)
        except OSError:
            names = []
        self._after_add(self.playlist.add([os.path.join(folder, n) for n in names]))

    def _on_add_url(self, event):
        url = ask_for_url(self, self.tr)
        if url:
            self._after_add(self.playlist.add([url]))

    def _on_clear(self, event):
        if not len(self.playlist):
            return
        answer = wx.MessageBox(self.tr.t("pl_clear_confirm"), self.tr.t("pl_dialog_title"),
                               wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION, self)
        if answer != wx.YES:
            return
        self.playlist.clear()
        self._refresh()
        self._announce(self.tr.t("pl_announce_cleared"))
        self.list.SetFocus()

    def _on_save(self, event):
        self.main._save_playlist_as(self)
        self.list.SetFocus()

    def _on_open_playlist(self, event):
        path = self.main._ask_playlist_file(self)
        if path and self.main._load_playlist_file(path, play=False):
            self._refresh(select=0)
        self.list.SetFocus()


class PlaylistMixin:
    """روابط البث وقوائم التشغيل في النافذة الرئيسية."""

    def _init_playlist_state(self):
        # عناوين القائمة المحفوظة (#EXTINF) - أسماء المحطات أوضح من الروابط
        self._entry_titles = {}

    # ------------------------------------------------------------------ #
    # الأسماء

    def _display_name(self, entry):
        title = self._entry_titles.get(entry)
        if title:
            return title
        if is_stream_url(entry):
            return stream_display_name(entry)
        return os.path.basename(entry)

    # ------------------------------------------------------------------ #
    # الروابط

    def _on_open_url(self, event):
        url = ask_for_url(self, self.tr)
        if url:
            self._open_url(url)

    def _open_url(self, url):
        self._save_current_position()
        self.playlist.load_single(url)
        self._load_and_play(url)

    def _on_stream_title_changed(self, title):
        # من خيط VLC
        wx.CallAfter(self._show_stream_title, title)

    def _show_stream_title(self, title):
        if getattr(self, "_is_closing", False) or not self.engine.is_stream:
            return
        text = self.tr.t("announce_stream_title", title=title)
        self.status_bar.SetStatusText(text)
        self._announce(text, "announce_stream_title")

    def _on_announce_stream_title(self, event):
        if not self.engine.is_stream:
            self._announce(self.tr.t("announce_not_a_stream"), force=True)
            return
        title = self.engine.get_stream_title()
        text = (self.tr.t("announce_stream_title", title=title) if title
                else self.tr.t("announce_no_stream_title"))
        self._announce(text, force=True)

    # ------------------------------------------------------------------ #
    # ملفات القوائم

    def _ask_playlist_file(self, parent):
        wildcard = "|".join([
            f"{self.tr.t('wildcard_playlists')}|{_patterns(PLAYLIST_EXTENSIONS)}",
            f"{self.tr.t('wildcard_all')}|*.*",
        ])
        with wx.FileDialog(parent, self.tr.t("pl_btn_open").rstrip("."), wildcard=wildcard,
                           defaultDir=self.settings.get_playlist_last_folder(),
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            return dialog.GetPath()

    def _load_playlist_file(self, path, play=True):
        """يحمّل ملف قائمة ويرجّع True لو فيها حاجة تشتغل."""
        try:
            entries = read_playlist(path)
        except PlaylistFileError as exc:
            self._show_error(self.tr.t("pl_error_open", error=exc))
            return False

        items = [entry for entry, _ in entries]
        if not self.playlist.load_custom_list(items):
            self._show_error(self.tr.t("pl_error_no_playable"))
            return False

        self._entry_titles = {entry: title for entry, title in entries if title}
        self.settings.set_playlist_last_folder(os.path.dirname(path))
        self.settings.add_recent_file(path)
        self._refresh_recent_files_menu()

        name = os.path.splitext(os.path.basename(path))[0]
        self._announce(self.tr.t("pl_announce_loaded", name=name,
                                 items=count_phrase(self.tr, "count_items", len(self.playlist))),
                       "announce_playlist_position")
        missing = len(items) - len(self.playlist)
        if missing:
            self._announce(self.tr.t("pl_announce_missing",
                                     items=count_phrase(self.tr, "count_items", missing)),
                           "announce_navigation_blocked")
        if play:
            self._save_current_position()
            self._load_and_play(self.playlist.current)
        else:
            self._refresh_transport_buttons_state()
        return True

    def _on_save_playlist(self, event):
        self._save_playlist_as(self)

    def _save_playlist_as(self, parent):
        if not len(self.playlist):
            self._announce(self.tr.t("pl_error_empty"), force=True)
            return False
        with wx.FileDialog(parent, self.tr.t("pl_btn_save").rstrip("."),
                           wildcard=f"{self.tr.t('wildcard_m3u8')}|*.m3u8",
                           defaultDir=self.settings.get_playlist_last_folder(),
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return False
            path = dialog.GetPath()
        if not path.lower().endswith(".m3u8"):
            path += ".m3u8"
        entries = self.playlist.entries
        titles = {e: self._display_name(e) for e in entries if is_stream_url(e)}
        try:
            write_m3u8(path, entries, titles)
        except PlaylistFileError as exc:
            self._show_error(self.tr.t("pl_error_save", error=exc))
            return False
        self.settings.set_playlist_last_folder(os.path.dirname(path))
        self._announce(self.tr.t("pl_announce_saved", name=os.path.basename(path)), force=True)
        return True

    # ------------------------------------------------------------------ #
    # نافذة القائمة

    def _on_playlist_dialog(self, event):
        with PlaylistDialog(self) as dialog:
            result = dialog.ShowModal()
            play_index = dialog.play_requested
        self._refresh_transport_buttons_state()
        if result == wx.ID_OK and play_index is not None:
            target = self.playlist.select(play_index)
            if target:
                self._save_current_position()
                self._load_and_play(target)
        self.SetFocus()

    # ------------------------------------------------------------------ #

    def _open_any(self, path):
        """
        مدخل واحد لأي حاجة تتفتح: رابط، أو ملف قائمة، أو ملف وسائط.
        (نافذة الفتح، والسحب والإفلات، وسطر الأوامر، والملفات الأخيرة)
        """
        if is_stream_url(path):
            self._open_url(path)
            return True
        if is_playlist_file(path):
            return self._load_playlist_file(path)
        return False
