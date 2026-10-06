# -*- coding: utf-8 -*-
"""
نافذة «محرر الوسائط»: قص الصوت والفيديو ودمجهما، بأربع صفحات:

    قص ملف       يقسم ملفًا لجزأين عند وقت
    قص عدة ملفات  يقسم كل ملف في القائمة لجزأين عند نفس الوقت
    مقاطع من ملف  يأخذ مقاطع متفرقة من ملف ويضمها في ملف واحد
    دمج ملفات     يضم الملفات بالترتيب في ملف واحد

العمل كله في core/media_editor.py داخل البرنامج نفسه (PyAV)، في خيط خلفي
فلا تتجمد النافذة. الناتج بنفس صيغة الأصل. وقائمة «طريقة قص الفيديو»
تختار بين السريع بنفس الجودة (من أقرب إطار مفتاحي) والدقيق بالثانية.

ملفات القص تُحفظ بجانب الأصل، والدمج والمقاطع يُسأل المستخدم أين يحفظها.
"""

import os

import wx

from core.media_editor import (
    EditJobRunner,
    extract_segments,
    get_duration,
    merge_files,
    split_file,
)
from core.formats import ConversionError
from core.notification_sound import play_completion_chime, play_error_chime
from core.time_input import TimeParseError, format_time_precise, parse_time
from gui.dialog_helpers import bind_escape_closes
from i18n.plural import count_phrase
from accessibility.announcer import _resource_path

PAGE_SPLIT, PAGE_SPLIT_MANY, PAGE_SEGMENTS, PAGE_MERGE = range(4)


def unique_path(path):
    """مسار غير مستخدم: يضيف (2) و(3)... قبل الامتداد لو الاسم موجود."""
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 2
    while os.path.exists(f"{base} ({counter}){ext}"):
        counter += 1
    return f"{base} ({counter}){ext}"


def split_output_paths(tr, path):
    """مسارا جزأي التقسيم بجانب الأصل: «اسم - الجزء 1» و«اسم - الجزء 2»."""
    base, ext = os.path.splitext(path)
    names = [f"{base} - {tr.t('editor_part_name', number=n)}" for n in (1, 2)]
    # رقم التمييز واحد للجزأين، فلا يصير «الجزء 1 (2)» مع «الجزء 2»
    counter = 1
    while True:
        suffix = "" if counter == 1 else f" ({counter})"
        candidates = tuple(f"{name}{suffix}{ext}" for name in names)
        if not any(os.path.exists(c) for c in candidates):
            return candidates
        counter += 1


class _TimeField:
    """
    عنوان وخانة وقت وزر «الموضع الحالي» يملؤها من المشغّل.

    file_getter (اختياري) يرجع ملف الصفحة، فيظهر زر «من العلامات» يملأ
    الخانة من علامات الملف التي وضعها المستخدم بـ Ctrl+B وهو يسمع.
    """

    def __init__(self, parent, sizer, label, dialog, file_getter=None):
        self.dialog = dialog
        row = wx.BoxSizer(wx.HORIZONTAL)
        # العنوان قبل الخانة: قارئ الشاشة يسمّي الخانة بالنص الذي يسبقها
        caption = wx.StaticText(parent, label=label)
        self.text = wx.TextCtrl(parent, size=(120, -1))
        self.text.SetName(label)
        self.text.SetHint(dialog.tr.t("editor_time_hint"))
        self.position_button = wx.Button(parent, label=dialog.tr.t("editor_use_position"))
        self.position_button.SetName(f"{dialog.tr.t('editor_use_position')} - {label}")
        self.position_button.Bind(wx.EVT_BUTTON, self._on_position)
        row.Add(caption, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        row.Add(self.text, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        row.Add(self.position_button, flag=wx.ALIGN_CENTER_VERTICAL)
        self.file_getter = file_getter
        if file_getter is not None:
            bookmark_button = wx.Button(parent, label=dialog.tr.t("editor_from_bookmark"))
            bookmark_button.SetName(f"{dialog.tr.t('editor_from_bookmark')} - {label}")
            bookmark_button.Bind(wx.EVT_BUTTON, self._on_bookmark)
            row.Add(bookmark_button, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=8)
        sizer.Add(row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)
        self.label = label

    def _on_bookmark(self, event):
        seconds = self.dialog.choose_bookmark(self.file_getter(), self.label)
        if seconds is None:
            return
        value = format_time_precise(seconds)
        self.text.SetValue(value)
        self.text.SetFocus()
        self.dialog.announce(self.dialog.tr.t("editor_position_set", time=value))

    def _on_position(self, event):
        position = self.dialog.player_position()
        if position is None:
            self.dialog.announce(self.dialog.tr.t("editor_no_position"))
            return
        value = format_time_precise(position)
        self.text.SetValue(value)
        self.dialog.announce(self.dialog.tr.t("editor_position_set", time=value))

    def value(self):
        """الوقت بالثواني، أو None بعد إبلاغ المستخدم بالخطأ."""
        raw = self.text.GetValue()
        try:
            return parse_time(raw)
        except TimeParseError:
            self.dialog.show_error(self.dialog.tr.t("editor_err_time", field=self.label))
            self.text.SetFocus()
            return None

    def clear(self):
        self.text.SetValue("")


class _SingleFile:
    """عنوان وخانة اسم الملف المختار (للقراءة) وزر «اختيار ملف»."""

    def __init__(self, parent, sizer, dialog, on_change=None):
        self.dialog = dialog
        self.path = None
        self.on_change = on_change
        tr = dialog.tr
        caption = wx.StaticText(parent, label=tr.t("editor_file_label"))
        sizer.Add(caption, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)
        row = wx.BoxSizer(wx.HORIZONTAL)
        self.text = wx.TextCtrl(parent, style=wx.TE_READONLY, value=tr.t("editor_no_file"))
        self.text.SetName(tr.t("editor_file_label"))
        button = wx.Button(parent, label=tr.t("editor_choose_file"))
        button.Bind(wx.EVT_BUTTON, self._on_choose)
        row.Add(self.text, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        row.Add(button, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(row, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=12)

    def _on_choose(self, event):
        paths = self.dialog.ask_open_files(multiple=False)
        if paths:
            self.set_path(paths[0])
            self.dialog.announce(self.text.GetValue())

    def set_path(self, path):
        self.path = path
        name = os.path.basename(path)
        try:
            duration = format_time_precise(get_duration(path))
            self.text.SetValue(self.dialog.tr.t("editor_file_with_duration", name=name, duration=duration))
        except ConversionError:
            self.text.SetValue(name)
        if self.on_change:
            self.on_change()


class _FileList:
    """قائمة ملفات بأزرار الإضافة والحذف والترتيب."""

    def __init__(self, parent, sizer, dialog, label, ordered):
        self.dialog = dialog
        self.paths = []
        tr = dialog.tr
        caption = wx.StaticText(parent, label=label)
        sizer.Add(caption, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)
        self.listbox = wx.ListBox(parent, style=wx.LB_EXTENDED, size=(-1, 140))
        self.listbox.SetName(label)
        sizer.Add(self.listbox, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        row = wx.BoxSizer(wx.HORIZONTAL)
        buttons = [("editor_add_files", self._on_add), ("editor_remove", self._on_remove)]
        if ordered:
            buttons += [("editor_move_up", lambda e: self._move(-1)),
                        ("editor_move_down", lambda e: self._move(1))]
        buttons.append(("editor_clear", self._on_clear))
        for key, handler in buttons:
            button = wx.Button(parent, label=tr.t(key))
            button.Bind(wx.EVT_BUTTON, handler)
            row.Add(button, flag=wx.RIGHT, border=8)
        sizer.Add(row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

    def add(self, paths):
        added = 0
        for path in paths:
            if path not in self.paths:
                self.paths.append(path)
                self.listbox.Append(os.path.basename(path))
                added += 1
        if added and not self.listbox.GetSelections():
            self.listbox.SetSelection(len(self.paths) - added)
        return added

    def _on_add(self, event):
        added = self.add(self.dialog.ask_open_files(multiple=True))
        if added:
            self.dialog.announce(self.dialog.tr.t(
                "editor_files_added", files=count_phrase(self.dialog.tr, "count_files", added)))

    def _on_remove(self, event):
        selected = sorted(self.listbox.GetSelections(), reverse=True)
        if not selected:
            return
        for index in selected:
            del self.paths[index]
            self.listbox.Delete(index)
        if self.paths:
            self.listbox.SetSelection(min(selected[-1], len(self.paths) - 1))
        self.dialog.announce(self.dialog.tr.t(
            "editor_files_removed", files=count_phrase(self.dialog.tr, "count_files", len(selected))))

    def _on_clear(self, event):
        self.paths = []
        self.listbox.Clear()
        self.dialog.announce(self.dialog.tr.t("editor_list_cleared"))

    def _move(self, step):
        selected = self.listbox.GetSelections()
        if len(selected) != 1:
            return
        index = selected[0]
        target = index + step
        if not 0 <= target < len(self.paths):
            return
        self.paths[index], self.paths[target] = self.paths[target], self.paths[index]
        self.listbox.SetString(index, os.path.basename(self.paths[index]))
        self.listbox.SetString(target, os.path.basename(self.paths[target]))
        self.listbox.SetSelection(wx.NOT_FOUND)
        self.listbox.SetSelection(target)
        self.listbox.SetFocus()
        self.dialog.announce(self.dialog.tr.t(
            "editor_moved", name=os.path.basename(self.paths[target]), position=target + 1))


class MediaEditorDialog(wx.Frame):
    """
    نافذة مستقلة مثل المسجّل: لا تختفي مع تصغير المشغّل.

    position_provider: دالة ترجع (مسار الملف المفتوح، الموضع بالثواني) أو
    None، فيملأ زر «الموضع الحالي» الوقت من المشغّل وأنت تسمع.
    """

    def __init__(self, tr, announcer=None, initial_path=None, position_provider=None,
                 bookmarks_provider=None):
        super().__init__(None, title=tr.t("editor_title"), size=(640, 600),
                         style=wx.DEFAULT_FRAME_STYLE)
        self.tr = tr
        self.announcer = announcer
        self.position_provider = position_provider
        # دالة ترجع علامات ملف كقائمة (الثانية، الاسم)
        self.bookmarks_provider = bookmarks_provider
        self._segments = []
        self._runner = None
        self._last_pct = -1

        icon_path = _resource_path("resources", "omnya_icon.ico")
        if os.path.isfile(icon_path):
            try:
                self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO))
            except Exception:
                pass

        self._build_ui()
        bind_escape_closes(self)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        if initial_path:
            self.load_file(initial_path)

    # ---- البناء ----

    def _build_ui(self):
        tr = self.tr
        panel = wx.Panel(self)
        outer = wx.BoxSizer(wx.VERTICAL)

        # طريقة قص الفيديو تخص الصفحات الثلاث الأولى؛ الصوت يُقص بدقة دائمًا
        mode_row = wx.BoxSizer(wx.HORIZONTAL)
        mode_caption = wx.StaticText(panel, label=tr.t("editor_video_mode_label"))
        self.video_mode_choice = wx.Choice(panel, choices=[tr.t("editor_video_mode_fast"),
                                                           tr.t("editor_video_mode_precise")])
        self.video_mode_choice.SetName(tr.t("editor_video_mode_label"))
        self.video_mode_choice.SetSelection(0)
        mode_row.Add(mode_caption, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        mode_row.Add(self.video_mode_choice, flag=wx.ALIGN_CENTER_VERTICAL)
        outer.Add(mode_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        self.notebook = wx.Notebook(panel)
        self.notebook.SetName(tr.t("editor_mode_label"))
        self.notebook.AddPage(self._build_split_page(), tr.t("editor_page_split"))
        self.notebook.AddPage(self._build_split_many_page(), tr.t("editor_page_split_many"))
        self.notebook.AddPage(self._build_segments_page(), tr.t("editor_page_segments"))
        self.notebook.AddPage(self._build_merge_page(), tr.t("editor_page_merge"))
        outer.Add(self.notebook, proportion=1, flag=wx.EXPAND | wx.ALL, border=8)

        self.progress_label = wx.StaticText(panel, label=tr.t("editor_progress_idle"))
        outer.Add(self.progress_label, flag=wx.LEFT | wx.RIGHT, border=12)
        self.progress_gauge = wx.Gauge(panel, range=100)
        self.progress_gauge.SetName(tr.t("editor_progress_label"))
        outer.Add(self.progress_gauge, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        self.start_button = wx.Button(panel, label=tr.t("editor_start"))
        self.cancel_button = wx.Button(panel, label=tr.t("editor_cancel"))
        self.cancel_button.Disable()
        close_button = wx.Button(panel, wx.ID_CLOSE, label=tr.t("editor_close"))
        self.start_button.Bind(wx.EVT_BUTTON, self._on_start)
        self.cancel_button.Bind(wx.EVT_BUTTON, self._on_cancel)
        close_button.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        for button in (self.start_button, self.cancel_button, close_button):
            buttons.Add(button, flag=wx.RIGHT, border=8)
        outer.Add(buttons, flag=wx.ALIGN_RIGHT | wx.ALL, border=12)

        panel.SetSizer(outer)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, proportion=1, flag=wx.EXPAND)
        self.SetSizer(frame_sizer)

    def _page(self, description_key):
        page = wx.Panel(self.notebook)
        sizer = wx.BoxSizer(wx.VERTICAL)
        page.SetSizer(sizer)
        description = wx.StaticText(page, label=self.tr.t(description_key))
        description.Wrap(560)
        sizer.Add(description, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)
        return page, sizer

    def _build_split_page(self):
        page, sizer = self._page("editor_split_description")
        self.split_file = _SingleFile(page, sizer, self)
        self.split_time = _TimeField(page, sizer, self.tr.t("editor_split_at"), self,
                                     file_getter=lambda: self.split_file.path)
        return page

    def _build_split_many_page(self):
        page, sizer = self._page("editor_split_many_description")
        self.split_many_list = _FileList(page, sizer, self, self.tr.t("editor_files_label"), ordered=False)
        self.split_many_time = _TimeField(page, sizer, self.tr.t("editor_split_at"), self)
        return page

    def _build_segments_page(self):
        tr = self.tr
        page, sizer = self._page("editor_segments_description")
        self.segments_file = _SingleFile(page, sizer, self, on_change=self._clear_segments)
        segments_file = lambda: self.segments_file.path  # noqa: E731
        self.segment_start = _TimeField(page, sizer, tr.t("editor_segment_start"), self, segments_file)
        self.segment_end = _TimeField(page, sizer, tr.t("editor_segment_end"), self, segments_file)
        add_row = wx.BoxSizer(wx.HORIZONTAL)
        add_button = wx.Button(page, label=tr.t("editor_add_segment"))
        add_button.Bind(wx.EVT_BUTTON, self._on_add_segment)
        add_row.Add(add_button, flag=wx.RIGHT, border=8)
        # كل علامتين متتاليتين مقطع: بداية ونهاية
        pairs_button = wx.Button(page, label=tr.t("editor_segments_from_bookmarks"))
        pairs_button.Bind(wx.EVT_BUTTON, self._on_segments_from_bookmarks)
        add_row.Add(pairs_button)
        sizer.Add(add_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

        caption = wx.StaticText(page, label=tr.t("editor_segments_label"))
        sizer.Add(caption, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)
        self.segments_listbox = wx.ListBox(page, size=(-1, 110))
        self.segments_listbox.SetName(tr.t("editor_segments_label"))
        sizer.Add(self.segments_listbox, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=12)
        row = wx.BoxSizer(wx.HORIZONTAL)
        for key, handler in (("editor_remove", self._on_remove_segment),
                             ("editor_move_up", lambda e: self._move_segment(-1)),
                             ("editor_move_down", lambda e: self._move_segment(1))):
            button = wx.Button(page, label=tr.t(key))
            button.Bind(wx.EVT_BUTTON, handler)
            row.Add(button, flag=wx.RIGHT, border=8)
        sizer.Add(row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)
        return page

    def _build_merge_page(self):
        page, sizer = self._page("editor_merge_description")
        self.merge_list = _FileList(page, sizer, self, self.tr.t("editor_merge_order_label"), ordered=True)
        return page

    # ---- أدوات مشتركة ----

    def announce(self, text):
        if self.announcer:
            self.announcer.announce(text)

    def show_error(self, text):
        play_error_chime()
        wx.MessageBox(text, self.tr.t("title_error"), wx.ICON_ERROR, self)

    def player_position(self):
        """موضع المشغّل لو الملف المفتوح فيه هو ملف الصفحة الحالية."""
        if not self.position_provider:
            return None
        current = self.position_provider()
        if not current:
            return None
        path, position = current
        page = self.notebook.GetSelection()
        expected = {PAGE_SPLIT: self.split_file.path, PAGE_SEGMENTS: self.segments_file.path}.get(page)
        if expected is not None and os.path.normcase(expected) != os.path.normcase(path or ""):
            return None
        return position

    def _bookmarks(self, path):
        """علامات الملف، أو None بعد إبلاغ المستخدم لماذا لا توجد."""
        if not path:
            self.show_error(self.tr.t("editor_err_choose_file"))
            return None
        entries = self.bookmarks_provider(path) if self.bookmarks_provider else []
        if not entries:
            wx.MessageBox(self.tr.t("editor_no_bookmarks"), self.tr.t("editor_title"),
                          wx.ICON_INFORMATION, self)
            return None
        return entries

    def _bookmark_text(self, seconds, name):
        time = format_time_precise(seconds)
        if name:
            return self.tr.t("editor_bookmark_named", name=name, time=time)
        return self.tr.t("editor_bookmark_unnamed", time=time)

    def choose_bookmark(self, path, label):
        """يعرض علامات الملف ليختار المستخدم واحدة؛ يرجع وقتها أو None."""
        entries = self._bookmarks(path)
        if not entries:
            return None
        with wx.SingleChoiceDialog(self, self.tr.t("editor_choose_bookmark", field=label),
                                   self.tr.t("editor_from_bookmark"),
                                   [self._bookmark_text(at, name) for at, name in entries]) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return None
            return entries[dialog.GetSelection()][0]

    def _on_segments_from_bookmarks(self, event):
        entries = self._bookmarks(self.segments_file.path)
        if not entries:
            return
        points = [at for at, _name in entries]
        pairs = [(points[i], points[i + 1]) for i in range(0, len(points) - 1, 2)
                 if points[i + 1] > points[i]]
        if not pairs:
            self.show_error(self.tr.t("editor_err_one_bookmark"))
            return
        self._segments.extend(pairs)
        self._refresh_segments(select=len(self._segments) - 1)
        message = self.tr.t("editor_segments_added_from_bookmarks",
                            segments=count_phrase(self.tr, "count_segments", len(pairs)),
                            total=len(self._segments))
        # علامة أخيرة بلا شريك لا تُهمل بصمت
        if len(points) % 2:
            message += " " + self.tr.t("editor_bookmark_left_over",
                                       time=format_time_precise(points[-1]))
        self.announce(message)
        self.segments_listbox.SetFocus()

    def ask_open_files(self, multiple):
        style = wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | (wx.FD_MULTIPLE if multiple else 0)
        with wx.FileDialog(self, self.tr.t("editor_choose_file"),
                           wildcard=self.tr.t("dialog_open_wildcard"), style=style) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return []
            return dialog.GetPaths()

    def _ask_save_path(self, suggested):
        folder, name = os.path.split(suggested)
        ext = os.path.splitext(name)[1]
        with wx.FileDialog(self, self.tr.t("editor_save_as"), defaultDir=folder, defaultFile=name,
                           wildcard=f"{ext[1:].upper()}|*{ext}",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return None
            path = dialog.GetPath()
        # الناتج بصيغة الأصل دائمًا، فالامتداد يُفرض
        if os.path.splitext(path)[1].lower() != ext.lower():
            path += ext
        return path

    def load_file(self, path):
        """يضع الملف في كل الصفحات، كأن المستخدم اختاره فيها."""
        self.split_file.set_path(path)
        self.segments_file.set_path(path)
        self.split_many_list.add([path])
        self.merge_list.add([path])

    # ---- المقاطع ----

    def _segment_text(self, number, start, end):
        return self.tr.t("editor_segment_item", number=number,
                         start=format_time_precise(start), end=format_time_precise(end))

    def _refresh_segments(self, select=None):
        self.segments_listbox.Set([self._segment_text(i + 1, s, e)
                                   for i, (s, e) in enumerate(self._segments)])
        if select is not None and self._segments:
            self.segments_listbox.SetSelection(select)

    def _clear_segments(self):
        self._segments = []
        self._refresh_segments()

    def _on_add_segment(self, event):
        if not self.segments_file.path:
            self.show_error(self.tr.t("editor_err_choose_file"))
            return
        start = self.segment_start.value()
        if start is None:
            return
        end = self.segment_end.value()
        if end is None:
            return
        if end <= start:
            self.show_error(self.tr.t("editor_err_segment"))
            self.segment_end.text.SetFocus()
            return
        self._segments.append((start, end))
        self._refresh_segments(select=len(self._segments) - 1)
        self.segment_start.clear()
        self.segment_end.clear()
        self.announce(self.tr.t("editor_segment_added", count=len(self._segments),
                                start=format_time_precise(start), end=format_time_precise(end)))
        self.segment_start.text.SetFocus()

    def _on_remove_segment(self, event):
        index = self.segments_listbox.GetSelection()
        if index == wx.NOT_FOUND:
            return
        del self._segments[index]
        self._refresh_segments(select=min(index, len(self._segments) - 1))
        self.announce(self.tr.t("editor_segment_removed"))

    def _move_segment(self, step):
        index = self.segments_listbox.GetSelection()
        target = index + step
        if index == wx.NOT_FOUND or not 0 <= target < len(self._segments):
            return
        self._segments[index], self._segments[target] = self._segments[target], self._segments[index]
        self._refresh_segments(select=target)
        self.segments_listbox.SetFocus()
        self.announce(self.segments_listbox.GetString(target))

    # ---- التنفيذ ----

    def _precise(self):
        return self.video_mode_choice.GetSelection() == 1

    def _collect_jobs(self):
        """المهام حسب الصفحة الحالية: قائمة (اسم، دالة)، أو None لو ينقص شيء."""
        tr = self.tr
        page = self.notebook.GetSelection()

        if page == PAGE_SPLIT:
            path = self.split_file.path
            if not path:
                self.show_error(tr.t("editor_err_choose_file"))
                return None
            at = self.split_time.value()
            if at is None:
                return None
            first, second = split_output_paths(tr, path)
            precise = self._precise()

            def job(cancel, progress):
                point = split_file(path, at, first, second, cancel, progress, tr, precise)
                # القص السريع للفيديو يقع على إطار مفتاحي؛ المستخدم يعرف أين بالظبط
                if abs(point - at) >= 0.05:
                    self._notes.append(tr.t("editor_split_moved", time=format_time_precise(point)))
            return [(os.path.basename(path), job)]

        if page == PAGE_SPLIT_MANY:
            paths = list(self.split_many_list.paths)
            if not paths:
                self.show_error(tr.t("editor_err_no_files"))
                return None
            at = self.split_many_time.value()
            if at is None:
                return None
            jobs = []
            precise = self._precise()
            for path in paths:
                def job(cancel, progress, path=path):
                    first, second = split_output_paths(tr, path)
                    split_file(path, at, first, second, cancel, progress, tr, precise)
                jobs.append((os.path.basename(path), job))
            return jobs

        if page == PAGE_SEGMENTS:
            path = self.segments_file.path
            if not path:
                self.show_error(tr.t("editor_err_choose_file"))
                return None
            if not self._segments:
                self.show_error(tr.t("editor_err_no_segments"))
                return None
            base, ext = os.path.splitext(path)
            output = self._ask_save_path(unique_path(f"{base} - {tr.t('editor_segments_name')}{ext}"))
            if not output:
                return None
            segments = list(self._segments)
            precise = self._precise()
            return [(os.path.basename(output),
                     lambda cancel, progress: extract_segments(path, segments, output, cancel,
                                                               progress, tr, precise))]

        paths = list(self.merge_list.paths)
        if len(paths) < 2:
            self.show_error(tr.t("editor_err_merge_count"))
            return None
        base, ext = os.path.splitext(paths[0])
        output = self._ask_save_path(unique_path(f"{base} - {tr.t('editor_merged_name')}{ext}"))
        if not output:
            return None
        if any(os.path.normcase(output) == os.path.normcase(p) for p in paths):
            self.show_error(tr.t("editor_err_overwrite_source"))
            return None
        return [(os.path.basename(output),
                 lambda cancel, progress: merge_files(paths, output, cancel, progress, tr))]

    def _on_start(self, event):
        if self._runner is not None and self._runner.is_running():
            return
        jobs = self._collect_jobs()
        if not jobs:
            return
        self._last_pct = -1
        self.progress_gauge.SetValue(0)
        self._set_working(True)
        self.progress_label.SetLabel(self.tr.t("editor_working"))
        self.announce(self.tr.t("editor_working"))
        self._errors = []
        self._notes = []
        self._runner = EditJobRunner(
            on_progress=lambda i, n, f: wx.CallAfter(self._apply_progress, i, n, f),
            on_job_done=lambda i, n, name, err: wx.CallAfter(self._apply_job_done, name, err),
            on_all_done=lambda ok, bad, cancelled: wx.CallAfter(self._apply_all_done, ok, bad, cancelled),
        )
        self._runner.start(jobs)

    def _on_cancel(self, event):
        if self._runner is not None:
            self._runner.cancel()

    def _set_working(self, working):
        self.notebook.Enable(not working)
        self.start_button.Enable(not working)
        self.cancel_button.Enable(working)
        (self.cancel_button if working else self.start_button).SetFocus()

    def _apply_progress(self, index, total, fraction):
        if not self:
            return
        pct = int(((index - 1) + fraction) / total * 100)
        self.progress_gauge.SetValue(pct)
        # إعلان كل 25% يكفي ليعرف المستخدم أن العمل يتقدم دون إزعاج
        if pct // 25 > self._last_pct // 25 and 0 < pct < 100:
            self.announce(f"{pct}%")
        self._last_pct = max(self._last_pct, pct)

    def _apply_job_done(self, name, error):
        if error:
            self._errors.append(f"{name}: {error}")

    def _apply_all_done(self, succeeded, failed, cancelled):
        if not self:
            return
        self._set_working(False)
        self.progress_gauge.SetValue(0 if cancelled else 100)
        if cancelled:
            message = self.tr.t("editor_cancelled")
        elif failed:
            message = self.tr.t("editor_done_with_errors", ok=succeeded, failed=failed)
        else:
            message = self.tr.t("editor_done")
        if self._notes and not cancelled:
            message = " ".join([message] + self._notes)
        self.progress_label.SetLabel(message)
        self.announce(message)
        if failed:
            play_error_chime()
            wx.MessageBox("\n".join(self._errors), self.tr.t("editor_title"), wx.ICON_WARNING, self)
        elif not cancelled:
            play_completion_chime()

    def _on_close(self, event):
        if self._runner is not None and self._runner.is_running():
            answer = wx.MessageBox(self.tr.t("editor_confirm_close"), self.tr.t("title_warning"),
                                   wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING, self)
            if answer != wx.YES:
                event.Veto()
                return
            self._runner.cancel()
        self.Destroy()
