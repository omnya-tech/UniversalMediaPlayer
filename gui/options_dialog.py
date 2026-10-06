# -*- coding: utf-8 -*-
"""
نافذة الخيارات (Ctrl+Shift+P) بتبويباتها الستة.

تبويبات المحول والمسجّل ومحرر الوسائط في gui/options_tabs_mixin.py.
نُقلت كما هي من gui/dialogs.py.
"""

import logging
import os

import wx

from i18n.plural import count_phrase
from gui.dialog_helpers import bind_escape_closes, bind_space_like_enter
from gui import theme
from gui.value_choice import RECENT_FILES_COUNTS, ValueChoice
from gui.editor_hotkeys import combo_text, find_duplicates
from gui.options_helpers import (
    _SEEK_STEP_ROWS,
    _add_group_box,
    _add_hint,
    _describe,
    _safe_get_setting,
    _safe_set_setting,
    _seek_amount_text,
)
from gui.options_tabs_mixin import OptionsTabsMixin


logger = logging.getLogger(__name__)


class OptionsDialog(OptionsTabsMixin, wx.Dialog):
    # رقم تبويب محرر الوسائط؛ زر «إعدادات المحرر» يفتح الخيارات عليه
    EDITOR_TAB = 5

    def __init__(self, parent, tr, settings):
        super().__init__(parent, title=tr.t("options_dialog_title"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.tr = tr
        self.settings = settings

        # Freeze لحد ما البناء يخلص: من غيره كل عنصر بيترسم لوحده والنافذة
        # بتاخد وقت ملحوظ تفتح
        # (والقارئ بيعلن أجزاء نص مبنية)
        self.Freeze()
        try:
            self._build(tr, settings)
        finally:
            self.Thaw()

    def _build(self, tr, settings):
        outer_panel = wx.Panel(self)
        outer_sizer = wx.BoxSizer(wx.VERTICAL)

        notebook = wx.Notebook(outer_panel)
        self.notebook = notebook

        # كل التبويبات قابلة للتمرير: الخطوط الكبيرة وأحجام الشاشة الصغيرة
        # كانت بتقصّ آخر الخيارات من غير ما يبان إن فيه حاجة تحت
        def _scrollable_tab():
            page = wx.ScrolledWindow(notebook, style=wx.VSCROLL)
            page.SetScrollRate(0, 20)
            return page

        # تبويبا المحوّل والمسجّل بيتبنوا أول ما يتفتحوا بس: مسح أجهزة
        # الصوت والصيغ كان بياخد أغلب وقت فتح النافذة
        general_panel = _scrollable_tab()
        playback_nav_panel = _scrollable_tab()
        accessibility_panel = _scrollable_tab()
        converter_panel = _scrollable_tab()
        recorder_panel = _scrollable_tab()
        editor_panel = _scrollable_tab()

        # ---------------- 1. تبويب عام ----------------
        general_sizer = wx.BoxSizer(wx.VERTICAL)
        panel = general_panel

        lang_box = _add_group_box(panel, general_sizer, tr.t("options_language_label"))
        self.language_choice = wx.Choice(
            panel,
            choices=[tr.t("options_language_ar"), tr.t("options_language_en")],
        )
        self.language_choice.SetName(tr.t("options_language_label"))
        current_lang = _safe_get_setting(settings, "language", "ar")
        self.language_choice.SetSelection(0 if current_lang == "ar" else 1)
        lang_box.Add(self.language_choice, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=4)

        restart_note = wx.StaticText(panel, label=tr.t("options_restart_note"))
        lang_box.Add(restart_note, flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, border=8)

        # مظهر البرنامج (gui/theme.py): يتبع ويندوز أو فاتح أو داكن
        theme_box = _add_group_box(panel, general_sizer, tr.t("options_theme_label"))
        self.theme_choice = wx.Choice(panel, choices=[tr.t(f"options_theme_{name}") for name in theme.THEMES])
        self.theme_choice.SetName(tr.t("options_theme_label"))
        self._initial_theme = settings.get_ui_theme()
        self.theme_choice.SetSelection(theme.THEMES.index(self._initial_theme))
        theme_box.Add(self.theme_choice, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=4)
        theme_note = wx.StaticText(panel, label=tr.t("options_theme_note"))
        theme_note.Wrap(560)
        theme_box.Add(theme_note, flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, border=8)
        self.theme_changed = False

        recent_box = _add_group_box(panel, general_sizer, tr.t("options_max_recent_label"))
        max_recent = _safe_get_setting(settings, "max_recent_files", 10)
        self.max_recent_spin = ValueChoice(panel, RECENT_FILES_COUNTS, initial=max_recent)
        self.max_recent_spin.SetName(tr.t("options_max_recent_label"))
        recent_box.Add(self.max_recent_spin, flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, border=8)

        windows_box = _add_group_box(panel, general_sizer, tr.t("options_windows_integration_section_label"))
        self.open_default_apps_button = wx.Button(
            panel, label=tr.t("options_open_default_apps_button")
        )
        self.open_default_apps_button.Bind(wx.EVT_BUTTON, self._on_open_default_apps_settings)
        windows_box.Add(self.open_default_apps_button, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=8)

        self.open_mic_settings_button = wx.Button(
            panel, label=tr.t("options_open_mic_settings_button")
        )
        self.open_mic_settings_button.Bind(wx.EVT_BUTTON, self._on_open_mic_privacy_settings)
        windows_box.Add(self.open_mic_settings_button, flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, border=8)

        sound_box = _add_group_box(panel, general_sizer, tr.t("options_notification_sound_section_label"))
        self.enable_completion_sound_checkbox = wx.CheckBox(
            panel, label=tr.t("options_enable_completion_sound_label")
        )
        self.enable_completion_sound_checkbox.SetValue(_safe_get_setting(settings, "enable_completion_sound", True))
        sound_box.Add(self.enable_completion_sound_checkbox, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=8)

        self.enable_media_keys_checkbox = wx.CheckBox(
            panel, label=tr.t("options_enable_global_media_keys_label")
        )
        self.enable_media_keys_checkbox.SetValue(_safe_get_setting(settings, "enable_global_media_keys", True))
        sound_box.Add(self.enable_media_keys_checkbox, flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, border=8)

        general_sizer.AddSpacer(10)
        general_panel.SetSizer(general_sizer)

        # ---------------- 2. تبويب التشغيل والتنقل ----------------
        playback_nav_sizer = wx.BoxSizer(wx.VERTICAL)
        panel = playback_nav_panel

        resume_nav_box = _add_group_box(
            panel, playback_nav_sizer, tr.t("options_accessibility_resume_section_label")
        )
        self.auto_resume_checkbox = wx.CheckBox(panel, label=tr.t("options_auto_resume_label"))
        self.auto_resume_checkbox.SetValue(_safe_get_setting(settings, "auto_resume", True))
        resume_nav_box.Add(self.auto_resume_checkbox, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=8)

        self.folder_navigation_checkbox = wx.CheckBox(
            panel, label=tr.t("options_folder_navigation_label")
        )
        self.folder_navigation_checkbox.SetValue(_safe_get_setting(settings, "enable_folder_navigation", True))
        resume_nav_box.Add(self.folder_navigation_checkbox, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=8)

        on_ended_label = wx.StaticText(panel, label=tr.t("options_on_playback_ended_label"))
        # «إيقاف الكمبيوتر» اتشال من هنا: شوف Settings.load
        self._on_playback_ended_values = ("none", "next_file")
        self.on_playback_ended_choice = wx.Choice(
            panel,
            choices=[
                tr.t("options_on_playback_ended_none"),
                tr.t("options_on_playback_ended_next_file"),
            ],
        )
        self.on_playback_ended_choice.SetName(tr.t("options_on_playback_ended_label"))
        current_ended_action = _safe_get_setting(settings, "on_playback_ended_action", "next_file")
        self.on_playback_ended_choice.SetSelection(
            self._on_playback_ended_values.index(current_ended_action)
            if current_ended_action in self._on_playback_ended_values
            else 1
        )
        on_ended_row = wx.BoxSizer(wx.HORIZONTAL)
        on_ended_row.Add(on_ended_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        on_ended_row.Add(self.on_playback_ended_choice)
        resume_nav_box.Add(on_ended_row, flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, border=8)

        # لكل نوع تقديم قائمة بمقادير جاهزة، كل منها مكتوب بوحدته (ثوانٍ أو
        # دقائق)، بلا خانة كتابة
        seek_box = _add_group_box(panel, playback_nav_sizer, tr.t("options_seek_steps_section"))
        _add_hint(panel, seek_box, tr.t("options_seek_steps_hint"))
        self.seek_step_choices = {}
        for kind, label_key, amounts in _SEEK_STEP_ROWS:
            current = settings.get_seek_step(kind)
            # مقدار محفوظ من قبل ليس في القائمة يبقى ظاهرًا ولا يضيع
            amounts = tuple(sorted(set(amounts) | {current}))
            row = wx.BoxSizer(wx.HORIZONTAL)
            label = wx.StaticText(panel, label=tr.t(label_key))
            choice = wx.Choice(panel, choices=[_seek_amount_text(tr, a) for a in amounts])
            choice.SetName(tr.t(label_key))
            choice.SetSelection(amounts.index(current))
            row.Add(label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
            row.Add(choice, flag=wx.ALIGN_CENTER_VERTICAL)
            seek_box.Add(row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=8)
            self.seek_step_choices[kind] = (choice, amounts)
        reset_seek_button = wx.Button(panel, label=tr.t("options_seek_steps_reset"))
        reset_seek_button.Bind(wx.EVT_BUTTON, self._on_reset_seek_steps)
        seek_box.Add(reset_seek_button, flag=wx.ALL, border=8)

        playback_nav_sizer.AddSpacer(15)
        playback_nav_panel.SetSizer(playback_nav_sizer)

        # ---------------- 3. تبويب إمكانية الوصول ----------------
        accessibility_sizer = wx.BoxSizer(wx.VERTICAL)
        panel = accessibility_panel

        accessibility_intro_label = wx.StaticText(panel, label=tr.t("options_accessibility_intro_label"))
        accessibility_intro_label.Wrap(580)
        accessibility_sizer.Add(accessibility_intro_label, flag=wx.LEFT | wx.TOP | wx.RIGHT, border=12)

        # المفتاح الرئيسي في أول التبويب: من غيره المستخدم ممكن يدوّر على
        # سبب سكوت البرنامج في الخانات الفرعية وهي كلها مفعّلة
        # (Ctrl+Alt+A بيقلبه من أي مكان)
        accessibility_box_main = _add_group_box(
            panel, accessibility_sizer, tr.t("accessibility_status_title")
        )
        self.toggle_accessibility_checkbox = wx.CheckBox(
            panel, label=tr.t("enable_screen_reader_announcements")
        )
        self.toggle_accessibility_checkbox.SetValue(
            bool(_safe_get_setting(settings, "announce_accessibility", True))
        )
        accessibility_box_main.Add(
            self.toggle_accessibility_checkbox,
            flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, border=8,
        )

        self._announce_checkboxes = []
        self._current_announce_box = None

        def _add_announce_section(label_key):
            self._current_announce_box = _add_group_box(panel, accessibility_sizer, tr.t(label_key))
            return self._current_announce_box

        def _add_announce_checkbox(attr_name, label_key, setting_key, shortcut=""):
            label_text = tr.t(label_key)
            if shortcut:
                label_text += f" [{shortcut}]"
            checkbox = wx.CheckBox(panel, label=label_text)
            init_val = _safe_get_setting(settings, setting_key, True)
            checkbox.SetValue(bool(init_val))
            setattr(self, attr_name, checkbox)
            self._current_announce_box.Add(checkbox, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=6)
            self._announce_checkboxes.append((attr_name, setting_key, checkbox))

        # الأقسام بترتيب استعمالها: فتح الملف، ثم التنقل، ثم الصوت والقفز،
        # ثم الاستعلامات، ثم الباقي
        # (المستخدم بيلاقي الخيار جنب اللي بيأثر عليه)
        _add_announce_section("options_announce_section_on_open")
        _add_announce_checkbox(
            "announce_file_loaded_checkbox", "options_announce_file_loaded_label", "announce_file_loaded"
        )
        _add_announce_checkbox(
            "announce_file_info_checkbox", "options_announce_file_info_label", "announce_file_info"
        )
        _add_announce_checkbox(
            "announce_playlist_position_checkbox",
            "options_announce_playlist_position_label",
            "announce_playlist_position",
        )
        _add_announce_checkbox(
            "announce_resume_position_checkbox",
            "options_announce_resume_position_label",
            "announce_resume_position",
        )
        self._current_announce_box.AddSpacer(4)

        _add_announce_section("options_announce_section_navigation")
        _add_announce_checkbox(
            "announce_navigation_blocked_checkbox",
            "options_announce_navigation_blocked_label",
            "announce_navigation_blocked",
        )
        _add_announce_checkbox(
            "announce_playback_checkbox", "options_announce_playback_label", "announce_playback_state", shortcut="Space / Ctrl+Space"
        )
        _add_announce_checkbox(
            "announce_buffering_checkbox", "options_announce_buffering_label", "announce_buffering"
        )
        self._current_announce_box.AddSpacer(4)

        _add_announce_section("options_announce_section_volume_seek")
        _add_announce_checkbox(
            "announce_volume_checkbox", "options_announce_volume_label", "announce_volume_changes", shortcut="Up / Down"
        )
        _add_announce_checkbox(
            "announce_mute_checkbox", "options_announce_mute_label", "announce_mute_toggle", shortcut="M"
        )

        seek_box = self._current_announce_box

        # إعلان القفز خانة اختيار زي باقي الإعلانات بدل قائمة بخيارين:
        # القائمة كانت شاذة وسط الخانات، والقارئ بيقرا "مفعّل" و"معطّل"
        # كقيم من غير ما يوضح إنها عن القفز.
        # (القيمة المحفوظة لسه نصية للتوافق مع الإعدادات القديمة)
        self.announce_seek_checkbox = wx.CheckBox(
            panel, label=tr.t("options_announce_seek_label")
        )
        _describe(
            self.announce_seek_checkbox,
            tr.t("options_announce_seek_label"),
            tr.t("options_announce_seek_hint"),
        )
        # أي قيمة غير المعطّلة الصريحة بتتحسب مفعّلة
        # (ومنها "all" اللي كانت بتكتبها نسخة قديمة)
        raw_seek_mode = str(
            _safe_get_setting(settings, "announce_seek_mode", "enabled")
        ).lower()
        self.announce_seek_checkbox.SetValue(
            raw_seek_mode not in ("disabled", "false", "off", "0")
        )
        seek_box.Add(self.announce_seek_checkbox, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=6)

        # أصغر قفزة يُعلن عندها الموضع: سهم العشر ثواني المتكرر بيتحول
        # لثرثرة لو كل ضغطة اتعلنت.
        # (شوف Settings.get_announce_seek_min_seconds)
        # والقيم هي نفس مقادير القفز في البرنامج.
        self.seek_min_label = wx.StaticText(panel, label=tr.t("options_seek_min_label"))
        seek_box.Add(self.seek_min_label, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=6)

        self._seek_min_values = (0, 60, 300, 600, 1800)
        self.seek_min_choice = wx.Choice(panel, choices=[
            tr.t("options_seek_min_all"),
            count_phrase(tr, "count_minutes", 1),
            count_phrase(tr, "count_minutes", 5),
            count_phrase(tr, "count_minutes", 10),
            count_phrase(tr, "count_minutes", 30),
        ])
        _describe(self.seek_min_choice, tr.t("options_seek_min_label"),
                  tr.t("options_seek_min_hint"))
        current_min = _safe_get_setting(settings, "announce_seek_min_seconds", 0)
        try:
            current_min = int(current_min)
        except (TypeError, ValueError):
            current_min = 0
        self.seek_min_choice.SetSelection(
            self._seek_min_values.index(current_min)
            if current_min in self._seek_min_values else 0
        )
        seek_box.Add(self.seek_min_choice,
                     flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, border=6)
        self.announce_seek_checkbox.Bind(
            wx.EVT_CHECKBOX, lambda event: self._update_seek_min_state()
        )

        # (الإعلانات الجاية بتتقال عند الطلب بمفاتيحها)
        _add_announce_section("options_announce_section_time_queries")
        _add_announce_checkbox(
            "announce_time_status_checkbox", "options_announce_time_status_label", "announce_time_status", shortcut="T"
        )
        _add_announce_checkbox(
            "announce_duration_announce_checkbox",
            "options_announce_duration_key_label",
            "announce_duration_announce",
            shortcut="E"
        )
        _add_announce_checkbox(
            "announce_remaining_time_checkbox",
            "options_announce_remaining_time_label",
            "announce_remaining_time",
            shortcut="R"
        )
        self._current_announce_box.AddSpacer(4)

        _add_announce_section("options_announce_section_extra")
        _add_announce_checkbox(
            "announce_speed_checkbox", "options_announce_speed_label", "announce_playback_speed", shortcut="Alt+Up / Alt+Down"
        )
        _add_announce_checkbox(
            "announce_bookmarks_checkbox", "options_announce_bookmarks_label", "announce_bookmarks", shortcut="Ctrl+B / F2"
        )
        _add_announce_checkbox(
            "announce_sleep_timer_checkbox", "options_announce_sleep_timer_label", "announce_sleep_timer"
        )
        _add_announce_checkbox(
            "announce_equalizer_checkbox", "options_announce_equalizer_label", "announce_equalizer", shortcut="Q / Shift+Q"
        )
        _add_announce_checkbox(
            "announce_stream_title_checkbox", "options_announce_stream_title_label", "announce_stream_title", shortcut="N"
        )
        _add_announce_checkbox(
            "announce_import_export_checkbox",
            "options_announce_import_export_label",
            "announce_settings_import_export",
        )
        _add_announce_checkbox(
            "announce_fullscreen_checkbox", "options_announce_fullscreen_label", "announce_fullscreen", shortcut="F11"
        )
        self._current_announce_box.AddSpacer(4)

        accessibility_sizer.AddSpacer(15)
        accessibility_panel.SetSizer(accessibility_sizer)
        self.toggle_accessibility_checkbox.Bind(
            wx.EVT_CHECKBOX, lambda event: self._update_accessibility_ui_state()
        )
        self._update_accessibility_ui_state()

        # ---------------- 4 و 5. المحوّل والمسجّل: بناء مؤجّل ----------------
        self._converter_panel = converter_panel
        self._recorder_panel = recorder_panel
        self._built_tabs = set()

        notebook.AddPage(general_panel, tr.t("options_tab_general"))
        notebook.AddPage(playback_nav_panel, tr.t("options_tab_playback_nav"))
        notebook.AddPage(accessibility_panel, tr.t("options_tab_accessibility"))
        notebook.AddPage(converter_panel, tr.t("options_tab_converter"))
        notebook.AddPage(recorder_panel, tr.t("options_tab_recorder"))
        self._build_editor_tab(editor_panel)
        notebook.AddPage(editor_panel, tr.t("options_tab_editor"))

        notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_tab_changed)

        outer_sizer.Add(notebook, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        save_button = wx.Button(outer_panel, wx.ID_OK, label=tr.t("options_save_button"))
        # اختصاران بنفس المفاتيح لا يُحفظان: التحقق قبل إغلاق النافذة
        save_button.Bind(wx.EVT_BUTTON, self._on_save_clicked)
        cancel_button = wx.Button(outer_panel, wx.ID_CANCEL, label=tr.t("options_cancel_button"))
        save_button.SetDefault()
        bind_space_like_enter(self)
        bind_escape_closes(self)
        button_sizer.Add(cancel_button, flag=wx.RIGHT, border=8)
        button_sizer.Add(save_button)
        outer_sizer.Add(button_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=12)

        outer_panel.SetSizer(outer_sizer)
        dialog_sizer = wx.BoxSizer(wx.VERTICAL)
        dialog_sizer.Add(outer_panel, 1, wx.EXPAND)
        self.SetSizerAndFit(dialog_sizer)
        self.SetSize((650, 560))

        self._describe_controls()
        self._bind_tab_navigation(notebook)

        notebook.SetSelection(0)
        # التركيز على شريط التبويبات لا على أول خيار: القارئ بيعلن اسم
        # التبويب وعددها، فالمستخدم يعرف هو فين قبل ما يتنقل.
        # (كان بيقع على قائمة اللغة مباشرة)
        # و Ctrl+Tab بتشتغل من هناك.
        notebook.SetFocus()

    def _describe_controls(self):
        """
        وصف إمكانية وصول + تلميح لكل عنصر أساسي.

        الوصف بيشرح **أثر** الخيار لا اسمه بس: قارئ الشاشة بيقرا الاسم
        لوحده أصلًا، فالقيمة المضافة هي إن المستخدم يعرف الخيار ده بيعمل
        إيه من غير ما يجرّبه ويستنى النتيجة.
        """
        tr = self.tr
        pairs = [
            (self.language_choice, "options_language_label", "options_language_hint"),
            (self.max_recent_spin, "options_max_recent_label", "options_max_recent_hint"),
            (self.auto_resume_checkbox, "options_auto_resume_label", "options_auto_resume_hint"),
            (self.folder_navigation_checkbox, "options_folder_navigation_label",
             "options_folder_navigation_hint"),
            (self.toggle_accessibility_checkbox, "enable_screen_reader_announcements",
             "options_master_announce_hint"),
        ]
        for control, name_key, hint_key in pairs:
            _describe(control, tr.t(name_key), tr.t(hint_key))

    # رقم كل تبويب مؤجّل في الدفتر
    _LAZY_TABS = {"converter": 3, "recorder": 4}

    def _on_tab_changed(self, event):
        self._ensure_tab_built(event.GetSelection())
        event.Skip()

    def _ensure_tab_built(self, page_index):
        """يبني التبويب المؤجّل أول مرة يتفتح فيها بس."""
        for name, index in self._LAZY_TABS.items():
            if index != page_index or name in self._built_tabs:
                continue
            panel = getattr(self, f"_{name}_panel")
            panel.Freeze()
            try:
                getattr(self, f"_build_{name}_tab")()
                self._built_tabs.add(name)
                panel.Layout()
            finally:
                panel.Thaw()

    def ensure_all_tabs_built(self):
        """للاختبارات ولأي كود محتاج كل العناصر موجودة."""
        for index in self._LAZY_TABS.values():
            self._ensure_tab_built(index)

    # ---------------- محرر الوسائط ----------------

    def _on_reset_seek_steps(self, event):
        for kind, (choice, amounts) in self.seek_step_choices.items():
            choice.SetSelection(amounts.index(self.settings.SEEK_STEP_DEFAULTS[kind]))
        wx.MessageBox(self.tr.t("options_seek_steps_reset_done"), self.tr.t("options_dialog_title"),
                      wx.ICON_INFORMATION, self)

    def select_tab(self, index):
        self._ensure_tab_built(index)
        self._go_to_tab(index)

    def _on_save_clicked(self, event):
        duplicates = find_duplicates(self._editor_hotkey_mapping())
        if duplicates:
            first, second = duplicates[0]
            mapping = self._editor_hotkey_mapping()
            wx.MessageBox(
                self.tr.t("options_editor_hotkeys_duplicate",
                          keys=combo_text(mapping[first]),
                          first=self.tr.t(f"ghost_action_{first}"),
                          second=self.tr.t(f"ghost_action_{second}")),
                self.tr.t("title_error"), wx.ICON_ERROR, self)
            self._go_to_tab(self.EDITOR_TAB)
            self.editor_hotkey_choices[second][1].SetFocus()
            return
        event.Skip()

    def _save_seek_steps(self):
        for kind, (choice, amounts) in self.seek_step_choices.items():
            self.settings.set_seek_step(kind, amounts[choice.GetSelection()])

    def _bind_tab_navigation(self, notebook):
        """Ctrl+Tab للتالي، Ctrl+Shift+Tab للسابق، و Ctrl+1..5 للقفز المباشر."""
        entries = []
        for index in range(notebook.GetPageCount()):
            command_id = wx.NewIdRef()
            self.Bind(
                wx.EVT_MENU,
                lambda event, page=index: self._go_to_tab(page),
                id=command_id,
            )
            entries.append((wx.ACCEL_CTRL, ord(str(index + 1)), command_id))

        next_id, prev_id = wx.NewIdRef(), wx.NewIdRef()
        self.Bind(wx.EVT_MENU, lambda event: self._cycle_tab(1), id=next_id)
        self.Bind(wx.EVT_MENU, lambda event: self._cycle_tab(-1), id=prev_id)
        entries.append((wx.ACCEL_CTRL, wx.WXK_TAB, next_id))
        entries.append((wx.ACCEL_CTRL | wx.ACCEL_SHIFT, wx.WXK_TAB, prev_id))

        self.SetAcceleratorTable(wx.AcceleratorTable(entries))

    def _go_to_tab(self, index):
        if 0 <= index < self.notebook.GetPageCount():
            self.notebook.SetSelection(index)
            self.notebook.SetFocus()

    def _cycle_tab(self, step):
        count = self.notebook.GetPageCount()
        self._go_to_tab((self.notebook.GetSelection() + step) % count)

    def _update_accessibility_ui_state(self):
        """
        المفتاح مقفول = كل الخانات تبان معطّلة.

        من غير كده، المستخدم بيشوف 18 خانة مفعّلة وما بيسمعش حاجة،
        وما فيش أي إشارة للسبب.
        """
        enabled = self.toggle_accessibility_checkbox.GetValue()
        for _attr, _key, checkbox in self._announce_checkboxes:
            checkbox.Enable(enabled)
        self.announce_seek_checkbox.Enable(enabled)
        self._update_seek_min_state()

    def _update_seek_min_state(self):
        """الحد بلا معنى لو النطق مقفول أو إعلان التقديم نفسه متوقف."""
        enabled = (
            self.toggle_accessibility_checkbox.GetValue()
            and self.announce_seek_checkbox.GetValue()
        )
        # (الخانة نفسها بتفضل ظاهرة: القارئ بيقرا إنها معطّلة)
        self.seek_min_label.Enable(enabled)
        self.seek_min_choice.Enable(enabled)

    def apply_to_settings(self) -> bool:
        old_lang = _safe_get_setting(self.settings, "language", "ar")
        new_lang = "ar" if self.language_choice.GetSelection() == 0 else "en"

        try:
            logger.info("Saving program options from options dialog...")

            batch_ctx = self.settings.batch() if hasattr(self.settings, "batch") else None

            def _do_save():
                _safe_set_setting(self.settings, "language", new_lang)
                new_theme = theme.THEMES[self.theme_choice.GetSelection()]
                self.theme_changed = new_theme != self._initial_theme
                self.settings.set_ui_theme(new_theme)
                _safe_set_setting(self.settings, "auto_resume", self.auto_resume_checkbox.GetValue())
                _safe_set_setting(self.settings, "max_recent_files", self.max_recent_spin.GetValue())
                _safe_set_setting(self.settings, "enable_folder_navigation", self.folder_navigation_checkbox.GetValue())
                _safe_set_setting(self.settings, "enable_completion_sound", self.enable_completion_sound_checkbox.GetValue())
                _safe_set_setting(self.settings, "enable_global_media_keys", self.enable_media_keys_checkbox.GetValue())
                _safe_set_setting(
                    self.settings,
                    "on_playback_ended_action",
                    self._on_playback_ended_values[self.on_playback_ended_choice.GetSelection()]
                )

                # المفتاح الرئيسي بمفتاح واحد: النسخ القديمة كانت بتكتبه
                # تحت أربع أسماء، والقارئ بيقرا واحد بس منها.
                # (شوف Settings.is_announcement_enabled)
                _safe_set_setting(
                    self.settings, "announce_accessibility",
                    self.toggle_accessibility_checkbox.GetValue(),
                )

                # حفظ جميع مربعات اختيار النطق
                # (القيم المحفوظة منطقية، والقارئ بيتعامل مع أي نوع)
                # (شوف Settings._get_announce_flag)
                for _attr_name, setting_key, checkbox in self._announce_checkboxes:
                    _safe_set_setting(self.settings, setting_key, checkbox.GetValue())

                # نمط إعلان القفز بقيمتين صالحتين بس: كانت بتتكتب "all"
                # بتلات مفاتيح، ودي مش من القيم الصالحة
                # (شوف Settings._purge_dead_keys)
                # والقيمة النصية للتوافق مع الإعدادات القديمة.
                _safe_set_setting(
                    self.settings, "announce_seek_mode",
                    "enabled" if self.announce_seek_checkbox.GetValue() else "disabled",
                )
                _safe_set_setting(
                    self.settings, "announce_seek_min_seconds",
                    self._seek_min_values[self.seek_min_choice.GetSelection()],
                )

                # التبويبات المؤجّلة بتتحفظ بس لو اتبنت: لو ما اتفتحتش
                # عناصرها مش موجودة أصلًا، وخياراتها ما اتعدّلتش.
                # (شوف _ensure_tab_built)
                # والحفظ وقتها كان هيكتب قيمًا افتراضية فوق المحفوظ.
                self._save_seek_steps()
                self._save_editor_tab()
                if "converter" in self._built_tabs:
                    self._save_converter_tab()
                if "recorder" in self._built_tabs:
                    self._save_recorder_tab()
                    self._save_recorder_quality()

            if batch_ctx:
                with batch_ctx:
                    _do_save()
            else:
                _do_save()

            logger.info("All settings saved successfully.")
        except Exception as exc:
            logger.error(f"Unexpected error while saving settings: {exc}", exc_info=True)

        return old_lang != new_lang

    def _on_open_default_apps_settings(self, event):
        try:
            os.startfile("ms-settings:defaultapps")
        except OSError as exc:
            logger.error(f"Error opening default apps settings: {exc}", exc_info=True)
            wx.MessageBox(str(exc), self.tr.t("options_dialog_title"), wx.ICON_ERROR)

    def _on_open_mic_privacy_settings(self, event):
        try:
            os.startfile("ms-settings:privacy-microphone")
        except OSError as exc:
            logger.error(f"Error opening microphone privacy settings: {exc}", exc_info=True)
            wx.MessageBox(str(exc), self.tr.t("options_dialog_title"), wx.ICON_ERROR)
