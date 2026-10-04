# -*- coding: utf-8 -*-
import logging
import os
import wx
from core.formats import AUDIO_FORMATS, VIDEO_FORMATS
from core.audio_devices import group_devices
from core.audio_recorder import SUPPORTED_SAMPLE_RATES, RecorderError
from core.version import APP_VERSION
from i18n.plural import count_phrase
from gui.audio_bitrate_widget import current_audio_bitrate_bps, refresh_audio_bitrate_choice
from gui.dialog_helpers import bind_escape_closes, bind_space_like_enter

logger = logging.getLogger(__name__)


def _safe_get_setting(settings_obj, key_name, default=True):
    """قراءة آمنة وشاملة لأي عنصر من كائن الإعدادات"""
    getter_name = f"get_{key_name}"
    if hasattr(settings_obj, getter_name) and callable(getattr(settings_obj, getter_name)):
        try:
            return getattr(settings_obj, getter_name)()
        except Exception:
            pass
    if hasattr(settings_obj, "get") and callable(getattr(settings_obj, "get")):
        try:
            val = settings_obj.get(key_name)
            if val is not None:
                return val
        except Exception:
            pass
    if hasattr(settings_obj, "_data") and isinstance(settings_obj._data, dict):
        return settings_obj._data.get(key_name, default)
    return default


def _safe_set_setting(settings_obj, key_name, value):
    """
    حفظ عنصر في الإعدادات، بسلسلة بدائل: setter مخصص -> set() عامة ->
    كتابة مباشرة في _data.

    الصمت بين البدائل مقصود (كل واحدة بتجرّب اللي بعدها). اللي مش مقصود
    هو إن كل البدائل تفشل والمستخدم يفتكر إن الخيار اتحفظ - ده صنف
    "الخيارات ما بتتطبقش" اللي اشتكى منه. فآخر السلسلة بيسجّل.
    """
    setter_name = f"set_{key_name}"
    if hasattr(settings_obj, setter_name) and callable(getattr(settings_obj, setter_name)):
        try:
            getattr(settings_obj, setter_name)(value)
            return
        except Exception:
            logger.warning("فشل %s، بنجرّب set() العامة", setter_name, exc_info=True)
    if hasattr(settings_obj, "set") and callable(getattr(settings_obj, "set")):
        try:
            settings_obj.set(key_name, value)
            return
        except Exception:
            logger.warning("فشلت set(%s)، بنكتب في _data مباشرة", key_name, exc_info=True)
    if hasattr(settings_obj, "_data") and isinstance(settings_obj._data, dict):
        settings_obj._data[key_name] = value
    elif hasattr(settings_obj, "settings") and isinstance(settings_obj.settings, dict):
        settings_obj.settings[key_name] = value
    else:
        # كل البدائل فشلت: لازم يبان في السجل، لأن المستخدم هيفتكر إن
        # الخيار اتحفظ
        logger.error("تعذّر حفظ الخيار %s نهائيًا - القيمة المطلوبة %r", key_name, value)


def _add_group_box(panel: wx.Window, outer_sizer: wx.Sizer, title: str) -> wx.StaticBoxSizer:
    box = wx.StaticBox(panel, label=title)
    box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
    outer_sizer.Add(box_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)
    return box_sizer


# الأقسام بعناوين خفيفة لا بإطارات: شوف _add_section.
# ووصف كل عنصر بيروح لاسمه الإمكانيّ ولتلميحه معًا: شوف _describe.
# (المساعدات دي بتستعملها نافذة الخيارات كلها)
# (_add_group_box فاضلة لنافذة "حول")
# الثلاث دوال بترجّع العنصر نفسه عشان الاستدعاء يبقى سطر واحد.
# مثال: _describe(wx.CheckBox(...), name, hint)
# بدل إنشاء ثم ضبط في سطرين.
# والأقسام بتتبني بالترتيب اللي بيتقرا بيه.
# (من فوق لتحت، ومن اليمين للشمال في العربي)
def _describe(control, name: str, description: str = ""):
    """
    يضبط الاسم الإمكانيّ والتلميح على عنصر تحكّم.

    نفس النص بيروح للاتنين عن قصد: قارئ الشاشة بيقراه عند التركيز،
    والمبصر بيشوفه كتلميح عند مرور الفأرة.
    """
    try:
        if name:
            control.SetName(name)
        if description:
            control.SetToolTip(description)
            if hasattr(control, "SetHelpText"):
                control.SetHelpText(description)
    except Exception:
        pass
    return control


def _add_section(panel: wx.Window, sizer: wx.Sizer, title: str) -> wx.BoxSizer:
    """
    عنوان قسم خفيف + حاوية لمحتواه.

    أخف من StaticBox: الإطار المرسوم بيضيف طبقة تجميع زيادة قارئ الشاشة
    بيعلنها عند كل دخول وخروج، وبتتقل التصفّح لما الأقسام تبقى كتير.
    """
    header = wx.StaticText(panel, label=title)
    font = header.GetFont()
    font.SetWeight(wx.FONTWEIGHT_BOLD)
    header.SetFont(font)
    sizer.Add(header, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

    line = wx.StaticLine(panel)
    sizer.Add(line, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=12)

    body = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(body, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=18)
    return body


def _add_hint(panel: wx.Window, sizer: wx.Sizer, text: str):
    """سطر شرح صغير تحت الخيار."""
    hint = wx.StaticText(panel, label=text)
    hint.SetForegroundColour(wx.Colour(110, 110, 110))
    font = hint.GetFont()
    font.SetPointSize(max(7, font.GetPointSize() - 1))
    hint.SetFont(font)
    sizer.Add(hint, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=4)
    return hint


class AboutDialog(wx.Dialog):
    def __init__(self, parent, tr, on_open_user_guide=None):
        super().__init__(parent, title=tr.t("menu_about"), style=wx.DEFAULT_DIALOG_STYLE)
        self.tr = tr

        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.Colour(248, 250, 252))
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- القسم العلوي: الأيقونة والعنوان ---
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        icon_path = os.path.join("resources", "omnya_icon.ico")
        if os.path.exists(icon_path):
            try:
                img = wx.Image(icon_path, wx.BITMAP_TYPE_ANY)
                img = img.Scale(75, 75, wx.IMAGE_QUALITY_HIGH)
                bmp = wx.StaticBitmap(panel, bitmap=wx.Bitmap(img))
                header_sizer.Add(bmp, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
            except Exception:
                pass

        title_sizer = wx.BoxSizer(wx.VERTICAL)
        title_label = wx.StaticText(panel, label=tr.t('app_title'))
        title_font = wx.Font(18, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        title_label.SetFont(title_font)
        title_label.SetForegroundColour(wx.Colour(0, 70, 140))

        version_label = wx.StaticText(panel, label=tr.t("about_version", version=APP_VERSION))
        version_font = wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        version_label.SetFont(version_font)
        version_label.SetForegroundColour(wx.Colour(80, 100, 120))

        title_sizer.Add(title_label, 0, wx.BOTTOM, 4)
        title_sizer.Add(version_label, 0, wx.BOTTOM, 0)
        
        header_sizer.Add(title_sizer, 1, wx.ALIGN_CENTER_VERTICAL)
        main_sizer.Add(header_sizer, 0, wx.EXPAND | wx.ALL, 20)

        main_sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        # --- قسم النبذة ---
        intro_label = wx.StaticText(panel, label=tr.t("about_vision_text"))
        intro_label.Wrap(450)
        intro_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        intro_label.SetForegroundColour(wx.Colour(30, 30, 30))
        main_sizer.Add(intro_label, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 20)

        # --- قسم الميزات ---
        features_box = wx.StaticBox(panel, label=tr.t("about_features_title"))
        features_box.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        features_box.SetForegroundColour(wx.Colour(0, 70, 140))
        features_sizer = wx.StaticBoxSizer(features_box, wx.VERTICAL)
        
        features_label = wx.StaticText(panel, label=tr.t("about_features_text"))
        features_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        features_label.SetForegroundColour(wx.Colour(50, 50, 50))
        features_sizer.Add(features_label, 0, wx.ALL, 10)
        
        main_sizer.Add(features_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        main_sizer.AddSpacer(10)

        # --- قسم الناشر وحقوق الملكية ---
        pub_sizer = wx.BoxSizer(wx.VERTICAL)
        
        publisher_label = wx.StaticText(panel, label=tr.t("about_publisher"))
        publisher_label.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        publisher_label.SetForegroundColour(wx.Colour(20, 20, 20))
        
        copyright_label = wx.StaticText(panel, label=tr.t("about_copyright"))
        copyright_label.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        copyright_label.SetForegroundColour(wx.Colour(120, 120, 120))

        pub_sizer.Add(publisher_label, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM, 5)
        pub_sizer.Add(copyright_label, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM, 0)

        main_sizer.Add(pub_sizer, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 15)
        main_sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        # --- قسم الأزرار ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        if on_open_user_guide is not None:
            guide_btn = wx.Button(panel, label=tr.t("menu_user_guide"), size=(130, 38))
            guide_btn.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            guide_btn.Bind(wx.EVT_BUTTON, lambda event: on_open_user_guide())
            btn_sizer.Add(guide_btn, 0, wx.RIGHT, 15)

        close_btn = wx.Button(panel, wx.ID_OK, label=tr.t("converter_close_button"), size=(100, 38))
        close_btn.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        btn_sizer.Add(close_btn, 0, wx.LEFT, 0)

        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 15)

        panel.SetSizer(main_sizer)
        outer_sizer = wx.BoxSizer(wx.VERTICAL)
        outer_sizer.Add(panel, 1, wx.EXPAND)
        
        self.SetSizerAndFit(outer_sizer)
        self.CenterOnParent()
        
        close_btn.SetFocus()
        close_btn.SetDefault()
        bind_escape_closes(self)


class OptionsDialog(wx.Dialog):
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

        recent_box = _add_group_box(panel, general_sizer, tr.t("options_max_recent_label"))
        max_recent = _safe_get_setting(settings, "max_recent_files", 10)
        self.max_recent_spin = wx.SpinCtrl(panel, min=3, max=50, initial=max_recent)
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

        notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._on_tab_changed)

        outer_sizer.Add(notebook, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        save_button = wx.Button(outer_panel, wx.ID_OK, label=tr.t("options_save_button"))
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

    def _build_converter_tab(self):
        tr, settings = self.tr, self.settings
        converter_panel = self._converter_panel

        converter_sizer = wx.BoxSizer(wx.VERTICAL)
        panel = converter_panel

        converter_box = _add_group_box(panel, converter_sizer, tr.t("options_converter_section_label"))
        self.converter_type_radio = wx.RadioBox(
            panel,
            label=tr.t("converter_media_type_label"),
            choices=[tr.t("converter_media_type_audio"), tr.t("converter_media_type_video")],
        )
        self.converter_type_radio.SetName(tr.t("converter_media_type_label"))
        is_vid = _safe_get_setting(settings, "converter_default_is_video", True)
        self.converter_type_radio.SetSelection(1 if is_vid else 0)
        self.Bind(wx.EVT_RADIOBOX, self._on_converter_type_change, self.converter_type_radio)
        converter_box.Add(self.converter_type_radio, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=8)

        converter_row = wx.BoxSizer(wx.HORIZONTAL)
        converter_format_label = wx.StaticText(panel, label=tr.t("converter_target_format_label"))
        self.converter_format_choice = wx.Choice(panel)
        self.converter_format_choice.SetName(tr.t("converter_target_format_label"))
        converter_row.Add(converter_format_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        converter_row.Add(self.converter_format_choice)
        converter_box.Add(converter_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=8)

        bitrate_row = wx.BoxSizer(wx.HORIZONTAL)
        # «أعلى جودة متاحة» بدل رقم ثابت: الرقم الثابت كان بيتحوّل لأقرب
        # قيمة في كل صيغة (شوف HIGHEST_AUDIO_BITRATE)
        self.converter_highest_bitrate_check = wx.CheckBox(
            panel, label=tr.t("audio_bitrate_highest_label")
        )
        converter_audio_bitrate_label = wx.StaticText(panel, label=tr.t("converter_custom_audio_bitrate_label"))
        self.converter_audio_bitrate_spin = wx.SpinCtrl(panel, min=32, max=512, initial=192)
        self.converter_audio_bitrate_spin.SetName(tr.t("converter_custom_audio_bitrate_label"))
        converter_video_bitrate_label = wx.StaticText(panel, label=tr.t("converter_custom_video_bitrate_label"))
        self.converter_video_bitrate_spin = wx.SpinCtrl(panel, min=200, max=20000, initial=4000)
        self.converter_video_bitrate_spin.SetName(tr.t("converter_custom_video_bitrate_label"))
        bitrate_row.Add(self.converter_highest_bitrate_check, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=16)
        bitrate_row.Add(converter_audio_bitrate_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        bitrate_row.Add(self.converter_audio_bitrate_spin, flag=wx.RIGHT, border=16)
        bitrate_row.Add(converter_video_bitrate_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        bitrate_row.Add(self.converter_video_bitrate_spin)
        converter_box.Add(bitrate_row, flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, border=8)

        self._refresh_converter_format_choices()
        saved_format = _safe_get_setting(settings, "converter_default_format", ".mp4")
        format_index = self.converter_format_choice.FindString(saved_format)
        if format_index != wx.NOT_FOUND:
            self.converter_format_choice.SetSelection(format_index)
        saved_audio_kbps = _safe_get_setting(settings, "converter_default_audio_bitrate", 0)
        self.converter_highest_bitrate_check.SetValue(not saved_audio_kbps)
        self.converter_audio_bitrate_spin.SetValue(saved_audio_kbps or 192)
        self.converter_audio_bitrate_spin.Enable(bool(saved_audio_kbps))
        self.converter_highest_bitrate_check.Bind(
            wx.EVT_CHECKBOX,
            lambda event: self.converter_audio_bitrate_spin.Enable(not event.IsChecked()),
        )
        self.converter_video_bitrate_spin.SetValue(_safe_get_setting(settings, "converter_default_video_bitrate", 4000))

        converter_sizer.AddSpacer(10)
        converter_panel.SetSizer(converter_sizer)

    def _build_recorder_tab(self):
        tr, settings = self.tr, self.settings
        recorder_panel = self._recorder_panel

        recorder_sizer = wx.BoxSizer(wx.VERTICAL)
        panel = recorder_panel

        recorder_box = _add_group_box(panel, recorder_sizer, tr.t("options_recorder_section_label"))

        recorder_device_row = wx.BoxSizer(wx.HORIZONTAL)
        recorder_device_label = wx.StaticText(panel, label=tr.t("recorder_device_label"))
        self.recorder_device_choice = wx.Choice(panel)
        self.recorder_device_choice.SetName(tr.t("recorder_device_label"))
        recorder_device_row.Add(recorder_device_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        recorder_device_row.Add(self.recorder_device_choice, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL)
        recorder_box.Add(recorder_device_row, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=8)

        # نفس القائمة المجمّعة اللي في نافذة المسجّل: الاسم المحفوظ هنا
        # لازم يطابق الاسم هناك، وإلا الجهاز الافتراضي ما يتلاقاش.
        # (شوف AudioRecorderDialog._populate_devices)
        # والمسح ممكن يفشل لو سواقة صوت معلّقة.
        try:
            self._recorder_devices = [(d.index, d.name) for d in group_devices()]
        except Exception:
            logger.exception("تعذّر مسح أجهزة الإدخال")
            self._recorder_devices = []

        # Set دفعة واحدة: Append لكل جهاز كان بيعلن كل إضافة
        # (نفس السبب في audio_bitrate_widget)
        # والاختيار الأول "الافتراضي" يعني جهاز النظام.
        self.recorder_device_choice.Set(
            [tr.t("options_recorder_default_device")]
            + [name for _index, name in self._recorder_devices]
        )
        saved_device_name = _safe_get_setting(settings, "recorder_default_device_name", "")
        device_selection = 0
        if saved_device_name:
            found_index = self.recorder_device_choice.FindString(saved_device_name)
            if found_index != wx.NOT_FOUND:
                device_selection = found_index
        self.recorder_device_choice.SetSelection(device_selection)

        recorder_row1 = wx.BoxSizer(wx.HORIZONTAL)
        rate_label = wx.StaticText(panel, label=tr.t("recorder_sample_rate_label"))
        self.recorder_rate_choice = wx.Choice(panel, choices=[f"{rate} Hz" for rate in SUPPORTED_SAMPLE_RATES])
        self.recorder_rate_choice.SetName(tr.t("recorder_sample_rate_label"))
        saved_rate = _safe_get_setting(settings, "recorder_default_sample_rate", 44100)
        self.recorder_rate_choice.SetSelection(
            SUPPORTED_SAMPLE_RATES.index(saved_rate) if saved_rate in SUPPORTED_SAMPLE_RATES else 0
        )

        channels_label = wx.StaticText(panel, label=tr.t("recorder_channels_label"))
        self.recorder_channels_choice = wx.Choice(
            panel, choices=[tr.t("recorder_channels_mono"), tr.t("recorder_channels_stereo")]
        )
        self.recorder_channels_choice.SetName(tr.t("recorder_channels_label"))
        saved_ch = _safe_get_setting(settings, "recorder_default_channels", 2)
        self.recorder_channels_choice.SetSelection(0 if saved_ch == 1 else 1)

        recorder_row1.Add(rate_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        recorder_row1.Add(self.recorder_rate_choice, flag=wx.RIGHT, border=16)
        recorder_row1.Add(channels_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        recorder_row1.Add(self.recorder_channels_choice)
        recorder_box.Add(recorder_row1, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=8)

        recorder_row1b = wx.BoxSizer(wx.HORIZONTAL)
        bit_depth_label = wx.StaticText(panel, label=tr.t("recorder_bit_depth_label"))
        self.recorder_bit_depth_choice = wx.Choice(
            panel, choices=[tr.t("recorder_bit_depth_16"), tr.t("recorder_bit_depth_32")]
        )
        self.recorder_bit_depth_choice.SetName(tr.t("recorder_bit_depth_label"))
        saved_bd = _safe_get_setting(settings, "recorder_default_bit_depth", 16)
        self.recorder_bit_depth_choice.SetSelection(0 if saved_bd == 16 else 1)
        recorder_row1b.Add(bit_depth_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        recorder_row1b.Add(self.recorder_bit_depth_choice)
        recorder_box.Add(recorder_row1b, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=8)

        recorder_row2 = wx.BoxSizer(wx.HORIZONTAL)
        recorder_format_label = wx.StaticText(panel, label=tr.t("recorder_format_label"))

        recorder_extensions = sorted(AUDIO_FORMATS.keys())
        self.recorder_format_choice = wx.Choice(panel, choices=recorder_extensions)
        self.recorder_format_choice.SetName(tr.t("recorder_format_label"))
        saved_recorder_format = _safe_get_setting(settings, "recorder_default_format", ".wav")
        recorder_format_index = self.recorder_format_choice.FindString(saved_recorder_format)
        self.recorder_format_choice.SetSelection(
            recorder_format_index if recorder_format_index != wx.NOT_FOUND else 0
        )
        self.Bind(wx.EVT_CHOICE, self._on_recorder_format_change, self.recorder_format_choice)

        recorder_bitrate_label = wx.StaticText(panel, label=tr.t("converter_custom_audio_bitrate_label"))
        self.recorder_bitrate_choice = wx.Choice(panel)
        self.recorder_bitrate_choice.SetName(tr.t("converter_custom_audio_bitrate_label"))
        self.recorder_bitrate_lossless_note = wx.StaticText(
            panel, label=tr.t("converter_audio_bitrate_not_applicable")
        )
        saved_rec_br = _safe_get_setting(settings, "recorder_default_audio_bitrate", 0)
        refresh_audio_bitrate_choice(
            self.recorder_bitrate_choice,
            self.recorder_bitrate_lossless_note,
            tr,
            saved_recorder_format,
            False,
            saved_rec_br,
        )

        recorder_row2.Add(recorder_format_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        recorder_row2.Add(self.recorder_format_choice, flag=wx.RIGHT, border=16)
        recorder_row2.Add(recorder_bitrate_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        recorder_row2.Add(self.recorder_bitrate_choice, flag=wx.ALIGN_CENTER_VERTICAL)
        recorder_row2.Add(
            self.recorder_bitrate_lossless_note, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=4
        )
        recorder_box.Add(recorder_row2, flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, border=8)

        recorder_sizer.AddSpacer(10)
        recorder_panel.SetSizer(recorder_sizer)

    def _save_converter_tab(self):
        """بتتنادى بس لو التبويب اتفتح واتبنى."""
        # تبويب ما اتفتحش: خياراته ما اتعدّلتش، فالمحفوظ يفضل زي ما هو
        _safe_set_setting(self.settings, "converter_default_is_video", self.converter_type_radio.GetSelection() == 1)
        _safe_set_setting(self.settings, "converter_default_format", self.converter_format_choice.GetStringSelection())
        _safe_set_setting(
            self.settings,
            "converter_default_audio_bitrate",
            0 if self.converter_highest_bitrate_check.GetValue()
            else self.converter_audio_bitrate_spin.GetValue(),
        )
        _safe_set_setting(self.settings, "converter_default_video_bitrate", self.converter_video_bitrate_spin.GetValue())

    def _save_recorder_tab(self):
        """بتتنادى بس لو التبويب اتفتح واتبنى."""
        # (نفس منطق الحفظ القديم بالظبط، بس في دالة لوحده)
        device_selection = self.recorder_device_choice.GetSelection()
        device_name = "" if device_selection == 0 else self.recorder_device_choice.GetString(device_selection)
        _safe_set_setting(self.settings, "recorder_default_device_name", device_name)
        rate_index = self.recorder_rate_choice.GetSelection()
        _safe_set_setting(
            self.settings,
            "recorder_default_sample_rate",
            SUPPORTED_SAMPLE_RATES[rate_index if rate_index != wx.NOT_FOUND else 0]
        )
        _safe_set_setting(
            self.settings,
            "recorder_default_channels",
            1 if self.recorder_channels_choice.GetSelection() == 0 else 2
        )
        _safe_set_setting(
            self.settings,
            "recorder_default_bit_depth",
            16 if self.recorder_bit_depth_choice.GetSelection() == 0 else 32
        )
        _safe_set_setting(self.settings, "recorder_default_format", self.recorder_format_choice.GetStringSelection())
        if self.recorder_bitrate_choice.IsShown():
            fallback_bitrate = _safe_get_setting(self.settings, "recorder_default_audio_bitrate", 0)
            _safe_set_setting(
                self.settings,
                "recorder_default_audio_bitrate",
                current_audio_bitrate_bps(self.recorder_bitrate_choice, fallback_bitrate)
            )

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

    def _refresh_converter_format_choices(self):
        is_video = self.converter_type_radio.GetSelection() == 1
        current = self.converter_format_choice.GetStringSelection()
        self.converter_format_choice.Clear()
        
        extensions = sorted(VIDEO_FORMATS.keys()) if is_video else sorted(AUDIO_FORMATS.keys())
        self.converter_format_choice.AppendItems(extensions)
        
        index = self.converter_format_choice.FindString(current)
        self.converter_format_choice.SetSelection(index if index != wx.NOT_FOUND else 0)

    def _on_converter_type_change(self, event):
        self._refresh_converter_format_choices()

    def _on_recorder_format_change(self, event):
        target_ext = self.recorder_format_choice.GetStringSelection() or ".wav"
        fallback_bitrate = _safe_get_setting(self.settings, "recorder_default_audio_bitrate", 0)
        preferred_bps = current_audio_bitrate_bps(self.recorder_bitrate_choice, fallback_bitrate)
        refresh_audio_bitrate_choice(
            self.recorder_bitrate_choice,
            self.recorder_bitrate_lossless_note,
            self.tr,
            target_ext,
            False,
            preferred_bps,
        )
        # (المعدل المختار بيفضل لو الصيغة الجديدة بتدعمه)
        self.Layout()

    def apply_to_settings(self) -> bool:
        old_lang = _safe_get_setting(self.settings, "language", "ar")
        new_lang = "ar" if self.language_choice.GetSelection() == 0 else "en"

        try:
            logger.info("Saving program options from options dialog...")

            batch_ctx = self.settings.batch() if hasattr(self.settings, "batch") else None

            def _do_save():
                _safe_set_setting(self.settings, "language", new_lang)
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
                if "converter" in self._built_tabs:
                    self._save_converter_tab()
                if "recorder" in self._built_tabs:
                    self._save_recorder_tab()

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
