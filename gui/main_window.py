# -*- coding: utf-8 -*-
"""
النافذة الرئيسية لمشغل الوسائط (Universal Media Player)
مستقرة، وتدعم أسلوب إعلان موضع التقديم والإرجاع المخصص بالثواني، الدقائق، مع النطق الإجباري لأرقام لوحة الأرقام Numpad،
وإدارة موحدة للمشغل والمحول والمسجل ومحرر الوسائط.
"""

import logging
import os
import threading
import time

import wx

from core.engine import PlayerEngine, PlaybackState
from core.logging_setup import get_app_data_dir
from core.playlist import Playlist, SUPPORTED_EXTENSIONS, is_video_extension
from core.playlist_files import is_playlist_file
from core.settings import Settings
from core.streams import is_stream_url
from accessibility.announcer import ScreenReaderAnnouncer, _resource_path
from i18n.strings import Translator
from gui import player_icons
from gui.format_utils import format_time
from gui.bookmarks_mixin import BookmarksMixin
from gui.editor_hotkeys import EditorHotkeysMixin
from gui.equalizer_mixin import EqualizerMixin
from gui.playlist_mixin import PlaylistMixin, open_media_wildcard
from gui.sleep_timer_mixin import SleepTimerDialog, SleepTimerMixin
from gui.seeking_mixin import SeekingMixin
from gui.tools_mixin import ToolsMixin
from core.version import APP_VERSION

logger = logging.getLogger(__name__)

# عناصر بتترسم بس ما بتاخدش التركيز: التنقل بـ Tab يفضل على العناصر
# اللي ليها اختصارات لوحة مفاتيح أصلًا (شوف _enforce_focusless_behavior)
class FocuslessPanel(wx.Panel):
    def AcceptsFocus(self): return False
    def AcceptsFocusFromKeyboard(self): return False

class FocuslessButton(wx.Button):
    def AcceptsFocus(self): return False
    def AcceptsFocusFromKeyboard(self): return False

class FocuslessSlider(wx.Slider):
    def AcceptsFocus(self): return False
    def AcceptsFocusFromKeyboard(self): return False


class VideoPanel(wx.Panel):
    def __init__(self, parent, name_str):
        super().__init__(parent, style=wx.FULL_REPAINT_ON_RESIZE | wx.NO_BORDER)
        self.SetBackgroundColour(wx.BLACK)
        self.SetName(name_str)
    def AcceptsFocus(self): return False
    def AcceptsFocusFromKeyboard(self): return False
    def clear(self): wx.CallAfter(self.Refresh)


class AudioSpacerPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent, style=wx.FULL_REPAINT_ON_RESIZE | wx.NO_BORDER)
        self.Bind(wx.EVT_PAINT, self._on_paint_bg)
        self.Bind(wx.EVT_SIZE, lambda e: self.Refresh())
    def AcceptsFocus(self): return False
    def AcceptsFocusFromKeyboard(self): return False
    def _on_paint_bg(self, event):
        dc = wx.PaintDC(self)
        bg_color = self.GetParent().GetBackgroundColour()
        dc.SetBackground(wx.Brush(bg_color))
        dc.Clear()
        main_win = self.TopLevelParent
        if not getattr(main_win, "_bg_image_loaded", True):
            main_win._bg_image = main_win._load_background_image()
            main_win._bg_image_loaded = True
        if not getattr(main_win, "_bg_image", None) or not main_win._bg_image.IsOk(): return
        cw, ch = self.GetSize()
        if cw <= 0 or ch <= 0: return
        img = main_win._bg_image
        try:
            scaled_img = img.Scale(cw, ch, wx.IMAGE_QUALITY_HIGH)
            bmp = wx.Bitmap(scaled_img)
            dc.DrawBitmap(bmp, 0, 0, True)
        except Exception: pass


class _MediaDropTarget(wx.FileDropTarget):
    def __init__(self, main_window):
        super().__init__()
        self._main_window = main_window

    def OnDropFiles(self, x, y, filenames):
        if not filenames:
            return False

        if len(filenames) == 1 and os.path.isdir(filenames[0]):
            self._main_window.open_converter_with_folder(filenames[0])
            return True

        if len(filenames) == 1 and is_playlist_file(filenames[0]):
            self._main_window._open_specific_path(filenames[0])
            return True

        media_files = []
        for item in filenames:
            if os.path.isfile(item) and os.path.splitext(item)[1].lower() in SUPPORTED_EXTENSIONS:
                media_files.append(item)
            elif os.path.isdir(item):
                try:
                    for f in sorted(os.listdir(item)):
                        fp = os.path.join(item, f)
                        if os.path.isfile(fp) and os.path.splitext(fp)[1].lower() in SUPPORTED_EXTENSIONS:
                            media_files.append(fp)
                except OSError:
                    pass

        # عند تحديد عدة ملفات، يتم تشغيلها كألبوم بالترتيب بدءاً من أول ملف
        if len(media_files) > 1:
            self._main_window._open_album_paths(media_files)
        elif len(media_files) == 1:
            self._main_window._open_specific_path(media_files[0])

        return True




class MainWindow(BookmarksMixin, SeekingMixin, SleepTimerMixin, ToolsMixin,
                 EqualizerMixin, PlaylistMixin, EditorHotkeysMixin, wx.Frame):
    # مقادير التقديم والإرجاع يضبطها المستخدم من الخيارات (تبويب التشغيل
    # والتنقل)؛ خصائص بنفس أسماء الثوابت القديمة فتبقى كل الاستدعاءات كما هي
    SEEK_NORMAL_SECONDS = property(lambda self: self.settings.get_seek_step("normal"))
    SEEK_CTRL_SECONDS = property(lambda self: self.settings.get_seek_step("ctrl"))
    SEEK_SHIFT_SECONDS = property(lambda self: self.settings.get_seek_step("shift"))
    SEEK_ALT_SECONDS = property(lambda self: self.settings.get_seek_step("alt"))
    SEEK_CTRL_SHIFT_SECONDS = property(lambda self: self.settings.get_seek_step("ctrl_shift"))
    MAX_VOLUME = 100
    _MEDIA_HOTKEY_PLAY_PAUSE = 0xB301
    _MEDIA_HOTKEY_STOP = 0xB302
    _MEDIA_HOTKEY_NEXT = 0xB303
    _MEDIA_HOTKEY_PREV = 0xB304
    def _update_window_title(self):
        base_title = f"{self.tr.t('app_title')} {APP_VERSION}"
        if self._current_file_name:
            self.SetTitle(f"{self._current_file_name} — {base_title}")
        else:
            self.SetTitle(base_title)

    def _set_app_icon(self):
        icon_path = _resource_path("resources", "omnya_icon.ico")
        try:
            if os.path.isfile(icon_path):
                self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO))
        except Exception:
            pass

    def _load_background_image(self):
        candidates = [
            _resource_path("resources", "background.png"), _resource_path("resources", "background.jpg"),
            _resource_path("background.png"), os.path.join(get_app_data_dir(), "background.png"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                try:
                    img = wx.Image(path, wx.BITMAP_TYPE_ANY)
                    if img.IsOk(): return img
                except Exception: pass
        return None

    def __init__(self, lang=None):
        self.settings = Settings()
        lang = lang or self.settings.get_language()
        self.tr = Translator(lang)

        super().__init__(None, title=f"{self.tr.t('app_title')} {APP_VERSION}", size=(880, 640))
        self.SetMinSize((720, 520))
        self._set_app_icon()

        # صورة الخلفية بتتحمّل عند أول حاجة ليها بدل وقت الفتح: قراءة
        # الصورة كانت بتأخّر ظهور النافذة على الأجهزة البطيئة.
        self._bg_image_loaded = False
        self._bg_image = None

        self.engine = PlayerEngine(on_state_change=self._on_state_change,
                                   on_error=self._on_error, tr=self.tr,
                                   on_stream_title=self._on_stream_title_changed)
        # تجهيز المحرك في الخلفية من دلوقتي (شوف PlayerEngine.warm_up):
        # أول ملف بيتفتح كان بيستنى تحميل المكتبات كلها.
        # كده الانتظار ده بيحصل والمستخدم لسه بيختار الملف.
        # (_load_and_play بيعلن الانتظار لو لسه ما خلصش)
        self.engine.warm_up()
        self.playlist = Playlist()
        self._init_playlist_state()
        self._current_file_name = ""
        self._current_file_path = None
        self._current_format = ""
        self._is_loading_file = False
        self._pending_open_path = None
        self._pending_seek_action = None
        self._quick_record_dialog = None
        self._user_is_dragging_slider = False
        self._last_seek_time = 0.0

        self._holding_key = None
        self._is_holding_seek = False
        self._hold_target_position = None
        self._hold_start_position = None
        self._seek_speed_multiplier = 1.0
        self._hold_seek_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_hold_seek_timer, self._hold_seek_timer)

        self._sleep_timer_end_time = 0.0
        self._is_sleep_timer_active = False
        self._sleep_timer_action_key = "pause"
        self._sleep_timer_action_idx = 0
        self._sleep_at_end_of_file = False

        self._build_omnya_ui()
        self._bind_shortcuts()
        self._refresh_transport_buttons_state()

        initial_volume = max(0, min(self.MAX_VOLUME, self.settings.get_volume()))
        self.volume_slider.SetValue(initial_volume)
        self.engine.set_volume(initial_volume / 100.0)
        self.vol_pct_label.SetLabel(f"{initial_volume}%")
        self._restore_equalizer()

        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)
        self.Bind(wx.EVT_KEY_UP, self._on_key_up)
        self.Bind(wx.EVT_HOTKEY, self._on_global_media_hotkey)

        self._registered_media_hotkey_ids = set()
        self._register_global_media_keys()
        self._init_editor_hotkeys()

        self._ui_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_timer_tick, self._ui_timer)
        self._ui_timer.Start(150)

        self._manual_announce_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_manual_announce_timer, self._manual_announce_timer)
        self._pending_manual_announce_message = None

        self._sleep_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_sleep_timer_fired, self._sleep_timer)

        self._autosave_tick_counter = 0
        self._is_closing = False
        self.ipc_cleanup_callback = None
        self._enforce_focusless_behavior()
        if not self._restore_window_geometry():
            self.Centre()

    def _restore_window_geometry(self):
        """
        يرجّع النافذة لحجمها وموضعها الأخيرين.

        بنتأكد إن الموضع لسه على شاشة موجودة: المستخدم ممكن يكون فصل شاشة
        تانية، والنافذة ساعتها كانت هتفتح برّه حدود المعروض ويبقى مستحيل
        يوصلها - وده أسوأ بكتير من إنها تفتح في النص.
        """
        geometry = self.settings.get_window_geometry()
        if not geometry:
            return False
        width, height, x, y = geometry
        if wx.Display.GetFromPoint(wx.Point(x + width // 2, y + 20)) == wx.NOT_FOUND:
            return False
        self.SetSize(width, height)
        self.SetPosition(wx.Point(x, y))
        return True

    def _save_window_geometry(self):
        # المصغّرة والمكبّرة وملء الشاشة مش حجم المستخدم الحقيقي
        if self.IsIconized() or self.IsMaximized() or self.IsFullScreen():
            return
        try:
            width, height = self.GetSize()
            x, y = self.GetPosition()
            self.settings.set_window_geometry(width, height, x, y)
        except Exception:
            pass

    def _enforce_focusless_behavior(self):
        def _block_nav(event): pass
        def _force_focus(event):
            event.Skip()
            wx.CallAfter(self.SetFocus)
        # Tab ما بيتنقلش بين الأزرار: كل وظيفة ليها اختصار، والتركيز على
        # زر كان بيبلع المسافة والأسهم بدل ما توصل للمشغّل
        self.Bind(wx.EVT_NAVIGATION_KEY, _block_nav)
        self.main_panel.Bind(wx.EVT_NAVIGATION_KEY, _block_nav)
        self.controls_panel.Bind(wx.EVT_NAVIGATION_KEY, _block_nav)
        self.header_panel.Bind(wx.EVT_NAVIGATION_KEY, _block_nav)
        for child in self.controls_panel.GetChildren(): child.Bind(wx.EVT_SET_FOCUS, _force_focus)
        for child in self.header_panel.GetChildren(): child.Bind(wx.EVT_SET_FOCUS, _force_focus)

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

    def _build_omnya_ui(self):
        self._build_menu()
        # لوحات وأزرار ومنزلقات ما بتاخدش التركيز (شوف FocuslessPanel):
        # التركيز يفضل على النافذة نفسها فكل الاختصارات توصل للمشغّل
        self.main_panel = FocuslessPanel(self, style=wx.NO_BORDER)
        self.main_panel.SetBackgroundColour(wx.Colour(240, 243, 246))
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.header_panel = FocuslessPanel(self.main_panel, style=wx.NO_BORDER)
        self.header_panel.SetBackgroundColour(wx.Colour(30, 35, 45))
        header_sizer = wx.BoxSizer(wx.VERTICAL)
        font_title = wx.Font(15, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.file_label = wx.StaticText(self.header_panel, label=self.tr.t("label_no_file"))
        self.file_label.SetFont(font_title)
        self.file_label.SetForegroundColour(wx.Colour(255, 255, 255))
        info_row = wx.BoxSizer(wx.HORIZONTAL)
        font_info = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.media_info_label = wx.StaticText(self.header_panel, label=self.tr.t("status_waiting_file"))
        self.media_info_label.SetFont(font_info)
        self.media_info_label.SetForegroundColour(wx.Colour(170, 185, 205))
        self.sleep_timer_badge = wx.StaticText(self.header_panel, label="")
        self.sleep_timer_badge.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.sleep_timer_badge.SetForegroundColour(wx.Colour(255, 190, 80))
        self.sleep_timer_badge.Hide()
        info_row.Add(self.media_info_label, 1, wx.EXPAND)
        info_row.Add(self.sleep_timer_badge, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        header_sizer.Add(self.file_label, 0, wx.ALL | wx.EXPAND, 14)
        header_sizer.Add(info_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 14)
        self.header_panel.SetSizer(header_sizer)
        self.main_sizer.Add(self.header_panel, 0, wx.EXPAND)

        self.video_panel = VideoPanel(self.main_panel, self.tr.t("panel_video"))
        self.audio_spacer_panel = AudioSpacerPanel(self.main_panel)
        self.main_sizer.Add(self.video_panel, 1, wx.EXPAND | wx.ALL, 0)
        self.main_sizer.Add(self.audio_spacer_panel, 1, wx.EXPAND | wx.ALL, 0)

        try: self.engine.set_video_widget_handle(self.video_panel.GetHandle())
        except Exception: pass
        for tw in (self, self.main_panel, self.video_panel): tw.SetDropTarget(_MediaDropTarget(self))

        self.controls_panel = FocuslessPanel(self.main_panel, style=wx.NO_BORDER)
        self.controls_panel.SetBackgroundColour(wx.Colour(250, 252, 255))
        controls_sizer = wx.BoxSizer(wx.VERTICAL)
        time_labels_sizer = wx.BoxSizer(wx.HORIZONTAL)
        font_time = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.time_current_label = wx.StaticText(self.controls_panel, label="00:00")
        self.time_current_label.SetFont(font_time)
        self.time_remaining_total_label = wx.StaticText(self.controls_panel, label="-00:00 / 00:00")
        self.time_remaining_total_label.SetFont(font_time)
        time_labels_sizer.Add(self.time_current_label, 0, wx.ALIGN_BOTTOM | wx.LEFT, 16)
        time_labels_sizer.AddStretchSpacer(1)
        time_labels_sizer.Add(self.time_remaining_total_label, 0, wx.ALIGN_BOTTOM | wx.RIGHT, 16)
        controls_sizer.Add(time_labels_sizer, 0, wx.EXPAND | wx.TOP, 14)

        self.seek_slider = FocuslessSlider(self.controls_panel, minValue=0, maxValue=100, value=0, style=wx.SL_HORIZONTAL | wx.SL_AUTOTICKS)
        self.seek_slider.SetName(self.tr.t("label_seek"))
        self.seek_slider.SetHelpText(self._format_seek_help_text())
        self.seek_slider.Bind(wx.EVT_SCROLL_THUMBTRACK, self._on_seek_drag)
        self.seek_slider.Bind(wx.EVT_SCROLL_THUMBRELEASE, self._on_seek_release)
        self.seek_slider.Bind(wx.EVT_SCROLL_CHANGED, self._on_seek_release)
        self.seek_slider.Bind(wx.EVT_MOTION, self._on_slider_mouse_move)
        self.seek_slider.Bind(wx.EVT_LEAVE_WINDOW, self._on_slider_mouse_leave)
        controls_sizer.Add(self.seek_slider, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)

        action_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        btn_size = (62, 38)

        # الأزرار بأيقونات مرسومة (شوف gui/player_icons.py) بدل رموز
        # اليونيكود: الرموز كانت بتظهر مربعات على بعض الخطوط، وقارئ
        # الشاشة كان بينطقها بأسمائها الحرفية.
        # الاسم المنطوق نص صريح عن طريق SetName والتلميح.
        # والأيقونة بتترسم بمقياس الشاشة علشان تفضل حادّة على
        # الشاشات عالية الدقة.
        # (اللون بيتظبط مع السمة: شوف _retint_button_icons)
        self._icon_scale = self.GetContentScaleFactor() or 1.0

        def icon_button(icon_maker, accessible_name, size=btn_size):
            button = FocuslessButton(self.controls_panel, label="", size=size)
            button.SetBitmap(icon_maker(size=18, scale=self._icon_scale))
            button.SetName(accessible_name)
            button.SetToolTip(accessible_name)
            return button

        self.stop_button = icon_button(player_icons.stop_icon, self.tr.t("btn_stop"))
        self.seek_backward_button = icon_button(player_icons.rewind_icon, self.tr.t("btn_seek_backward"))
        self.previous_button = icon_button(player_icons.previous_icon, self.tr.t("menu_previous_file"))
        self.next_button = icon_button(player_icons.next_icon, self.tr.t("menu_next_file"))
        self.seek_forward_button = icon_button(player_icons.forward_icon, self.tr.t("btn_seek_forward"))

        self.play_pause_button = FocuslessButton(
            self.controls_panel, label=self.tr.t("btn_play"), size=(120, 42)
        )
        self.play_pause_button.SetBitmap(player_icons.play_icon(size=18, scale=self._icon_scale))
        self.play_pause_button.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.play_pause_button.SetName(self.tr.t("btn_play"))
        self.play_pause_button.SetToolTip(self.tr.t("btn_play"))

        for btn in (self.stop_button, self.previous_button, self.seek_backward_button,
                    self.seek_forward_button, self.next_button):
            btn.SetFont(btn_font)

        self.Bind(wx.EVT_BUTTON, self._on_stop, self.stop_button)
        self.Bind(wx.EVT_BUTTON, lambda e: self._seek_relative(-self.SEEK_NORMAL_SECONDS), self.seek_backward_button)
        self.Bind(wx.EVT_BUTTON, self._on_previous, self.previous_button)
        self.Bind(wx.EVT_BUTTON, self._on_play_pause, self.play_pause_button)
        self.Bind(wx.EVT_BUTTON, self._on_next, self.next_button)
        self.Bind(wx.EVT_BUTTON, lambda e: self._seek_relative(self.SEEK_NORMAL_SECONDS), self.seek_forward_button)

        action_row.Add(self.stop_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        action_row.Add(self.previous_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        action_row.Add(self.seek_backward_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        action_row.Add(self.play_pause_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        action_row.Add(self.seek_forward_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        action_row.Add(self.next_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        action_row.AddStretchSpacer(1)

        self.volume_label = wx.StaticText(self.controls_panel, label=self.tr.t("lbl_volume_icon"))
        self.volume_label.SetFont(btn_font)
        self.volume_slider = FocuslessSlider(self.controls_panel, minValue=0, maxValue=self.MAX_VOLUME, value=100, size=(110, 30), style=wx.SL_HORIZONTAL | wx.SL_AUTOTICKS)
        self.volume_slider.SetName(self.tr.t("label_volume"))
        self.Bind(wx.EVT_SLIDER, self._on_volume_change, self.volume_slider)
        self.vol_pct_label = wx.StaticText(self.controls_panel, label="100%")
        self.vol_pct_label.SetFont(btn_font)

        action_row.Add(self.volume_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        action_row.Add(self.volume_slider, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        action_row.Add(self.vol_pct_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)
        controls_sizer.Add(action_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 16)

        self.controls_panel.SetSizer(controls_sizer)
        self.main_sizer.Add(self.controls_panel, 0, wx.EXPAND)

        self.status_bar = self.CreateStatusBar()
        self.status_bar.SetStatusText(self.tr.t("status_stopped"))
        self.announcer = ScreenReaderAnnouncer(self.main_panel)
        self.main_panel.SetSizer(self.main_sizer)
        self.video_panel.Hide()
        self.audio_spacer_panel.Show()
        self._current_media_has_video = False
        self.main_panel.Layout()
        self.Layout()
        self._apply_ui_theme()

    def _on_slider_mouse_move(self, event):
        if self.engine.duration and not self._user_is_dragging_slider:
            x = event.GetX()
            width = self.seek_slider.GetSize().GetWidth()
            padding = 12
            track_width = width - (padding * 2)

            if track_width > 0:
                adjusted_x = x - padding
                fraction = max(0.0, min(1.0, adjusted_x / track_width))
                target = fraction * self.engine.duration

                self.time_current_label.SetLabel(f"🎯 {format_time(target)}")
                self.time_current_label.SetForegroundColour(wx.Colour(230, 120, 0))
                self.seek_slider.SetToolTip(self.tr.t("seek_tooltip", time=format_time(target)))
                self.controls_panel.Layout()
        event.Skip()

    def _on_slider_mouse_leave(self, event):
        if not self._user_is_dragging_slider:
            self._update_info_labels()
        event.Skip()

    def _on_seek_drag(self, event):
        self._user_is_dragging_slider = True
        target_seconds = float(self.seek_slider.GetValue())
        self._update_info_labels(is_seeking=True, seek_target=target_seconds)
        event.Skip()

    def _on_seek_release(self, event):
        target_seconds = float(self.seek_slider.GetValue())
        self.engine.seek(target_seconds)

        self._last_seek_time = time.time()
        self._user_is_dragging_slider = False

        self._update_info_labels()
        self._announce_seek(target_seconds, seek_type="seconds")
        event.Skip()

    def _update_info_labels(self, is_seeking=False, seek_target=0):
        duration_val = self.engine.duration

        if duration_val and duration_val > 0:
            total_str = format_time(duration_val)

            if is_seeking:
                current_str = format_time(seek_target)
                remaining_val = max(0.0, duration_val - seek_target)
                current_label_text = f"🎯 {current_str}"
                current_label_color = wx.Colour(230, 120, 0)
            else:
                pos = self.engine.get_current_position()
                current_str = format_time(pos)
                remaining_val = max(0.0, duration_val - pos)

                current_label_text = current_str
                is_dark = self.settings.get_ui_theme() == "dark"
                current_label_color = wx.Colour(0, 120, 215) if not is_dark else wx.Colour(100, 180, 255)

            remaining_str = format_time(remaining_val)
            remaining_label_text = f"-{remaining_str} / {total_str}"
        else:
            current_label_text = "00:00"
            is_dark = self.settings.get_ui_theme() == "dark"
            current_label_color = wx.BLACK if not is_dark else wx.WHITE
            remaining_label_text = "-00:00 / 00:00"

        if self.time_current_label.GetLabel() != current_label_text:
            self.time_current_label.SetLabel(current_label_text)
            self.time_current_label.SetForegroundColour(current_label_color)

        if self.time_remaining_total_label.GetLabel() != remaining_label_text:
            self.time_remaining_total_label.SetLabel(remaining_label_text)

        status_text = self.tr.t(f"state_{self.engine.state.value if hasattr(self.engine.state, 'value') else 'stopped'}")

        info = self.engine.get_media_info()
        bitrate_str = ""
        if info and info.get("bit_rate"):
            bitrate_str = self.tr.t("info_bitrate", bitrate=int(info['bit_rate'] / 1000))

        fmt_str = self.tr.t("info_format", format=self._current_format) if self._current_format else ""
        display_info = f"{status_text}  |  {fmt_str}{bitrate_str}"

        if self.media_info_label.GetLabel() != display_info:
            self.media_info_label.SetLabel(display_info)

        self.controls_panel.Layout()
        self.header_panel.Layout()

    def _apply_ui_theme(self):
        is_dark = self.settings.get_ui_theme() == "dark"

        main_bg = wx.Colour(20, 20, 20) if is_dark else wx.Colour(240, 243, 246)
        header_bg = wx.Colour(30, 35, 45)
        controls_bg = wx.Colour(35, 40, 50) if is_dark else wx.Colour(250, 252, 255)

        text_primary = wx.WHITE
        text_secondary = wx.Colour(170, 185, 205)
        accent_color = wx.Colour(0, 120, 215)

        self.main_panel.SetBackgroundColour(main_bg)
        self.header_panel.SetBackgroundColour(header_bg)
        self.controls_panel.SetBackgroundColour(controls_bg)

        self.file_label.SetForegroundColour(text_primary)
        self.media_info_label.SetForegroundColour(text_secondary)

        seek_text = wx.Colour(100, 180, 255) if is_dark else wx.Colour(40, 50, 65)
        self.time_current_label.SetForegroundColour(seek_text)
        self.time_remaining_total_label.SetForegroundColour(wx.Colour(180, 190, 205) if is_dark else wx.Colour(100, 110, 125))

        vol_text = wx.Colour(100, 255, 100) if is_dark else wx.Colour(0, 120, 0)
        self.volume_label.SetForegroundColour(vol_text)
        self.vol_pct_label.SetForegroundColour(vol_text)

        btn_bg = wx.Colour(55, 60, 75) if is_dark else wx.Colour(255, 255, 255)
        btn_fg = wx.WHITE if is_dark else wx.Colour(30, 35, 45)

        for btn in [self.previous_button, self.seek_backward_button, self.stop_button, self.seek_forward_button, self.next_button]:
            btn.SetBackgroundColour(btn_bg)
            btn.SetForegroundColour(btn_fg)

        self.play_pause_button.SetBackgroundColour(accent_color)
        self.play_pause_button.SetForegroundColour(wx.WHITE)

        # الأيقونات مرسومة بلون نص الزر وقت رسمها، فلازم تترسم من جديد
        # بعد تغيير الألوان وإلا تفضل بلون السمة القديمة
        # (شوف _retint_button_icons)
        # والرسم بعد الألوان مش قبلها.
        self._retint_button_icons()
        self.main_panel.Refresh()

    def _retint_button_icons(self):
        """يعيد رسم أيقونات الأزرار بلون نص كل زر."""
        pairs = (
            (self.stop_button, player_icons.stop_icon),
            (self.seek_backward_button, player_icons.rewind_icon),
            (self.previous_button, player_icons.previous_icon),
            (self.next_button, player_icons.next_icon),
            (self.seek_forward_button, player_icons.forward_icon),
        )
        for button, maker in pairs:
            button.SetBitmap(maker(size=18, scale=self._icon_scale,
                                   colour=button.GetForegroundColour()))
        # زر التشغيل أيقونته بتتبع الحالة
        playing = self.engine.state == PlaybackState.PLAYING
        maker = player_icons.pause_icon if playing else player_icons.play_icon
        self.play_pause_button.SetBitmap(
            maker(size=18, scale=self._icon_scale,
                  colour=self.play_pause_button.GetForegroundColour())
        )

    def _build_menu(self):
        menubar = wx.MenuBar()

        file_menu = wx.Menu()
        open_item = file_menu.Append(wx.ID_OPEN, f"{self.tr.t('menu_open')}\tCtrl+O")
        open_folder_item = file_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_open_folder')}\tCtrl+Shift+O")
        open_url_item = file_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_open_url')}\tCtrl+U")
        file_menu.AppendSeparator()
        playlist_item = file_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_playlist')}\tCtrl+L")
        save_playlist_item = file_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_save_playlist')}\tCtrl+S")
        file_menu.AppendSeparator()
        self._recent_menu = wx.Menu()
        file_menu.AppendSubMenu(self._recent_menu, self.tr.t("menu_recent_files"))
        file_menu.AppendSeparator()
        exit_item = file_menu.Append(wx.ID_EXIT, f"{self.tr.t('menu_exit')}\tCtrl+Q")
        menubar.Append(file_menu, self.tr.t("menu_file"))

        playback_menu = wx.Menu()
        play_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('btn_play')}/{self.tr.t('btn_pause')}\tSpace")
        stop_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('btn_stop')}\tCtrl+Space")
        mute_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('btn_mute')}\tM")
        next_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_next_file')}\tPageDown")
        previous_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_previous_file')}\tPageUp")
        playback_menu.AppendSeparator()

        accessibility_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_toggle_accessibility')}\tCtrl+Alt+A")
        self.Bind(wx.EVT_MENU, self._on_toggle_accessibility_shortcut, accessibility_item)

        playback_menu.AppendSeparator()
        remaining_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_announce_remaining')}\tR")
        duration_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_announce_duration')}\tE")
        time_status_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_time_status')}\tT")
        stream_title_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_stream_title')}\tN")
        playback_menu.AppendSeparator()
        speed_increase_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_speed_increase')}\tAlt+Up")
        speed_decrease_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_speed_decrease')}\tAlt+Down")
        speed_reset_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_speed_reset')}\tAlt+Numpad 0")
        playback_menu.AppendSeparator()
        bookmark_add_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_bookmark_add')}\tCtrl+B")
        bookmark_next_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_bookmark_next')}\tF2")
        bookmark_previous_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_bookmark_previous')}\tShift+F2")
        bookmark_clear_item = playback_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_bookmark_clear')}\tCtrl+Shift+B")
        menubar.Append(playback_menu, self.tr.t("menu_playback"))

        audio_menu = wx.Menu()
        equalizer_item = audio_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_equalizer')}\tCtrl+E")
        equalizer_next_item = audio_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_equalizer_next')}\tQ")
        equalizer_previous_item = audio_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_equalizer_previous')}\tShift+Q")
        menubar.Append(audio_menu, self.tr.t("menu_audio"))

        tools_menu = wx.Menu()
        options_item = tools_menu.Append(wx.ID_PREFERENCES, f"{self.tr.t('menu_options')}\tCtrl+Shift+P")
        tools_menu.AppendSeparator()
        converter_item = tools_menu.Append(wx.ID_ANY, self.tr.t("menu_converter"))
        recorder_item = tools_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_recorder')}\tCtrl+Shift+R")
        media_editor_item = tools_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_media_editor')}\tCtrl+Shift+X")
        self._editor_hotkeys_menu_item = tools_menu.AppendCheckItem(
            wx.ID_ANY, self.tr.t("menu_editor_hotkeys", keys=self.editor_hotkey_text("toggle")))
        self._editor_hotkeys_menu_item.Check(self.settings.get_enable_editor_hotkeys())

        tools_menu.AppendSeparator()
        sleep_timer_item = tools_menu.Append(wx.ID_ANY, self.tr.t("menu_sleep_timer"))
        tools_menu.AppendSeparator()
        export_settings_item = tools_menu.Append(wx.ID_ANY, self.tr.t("menu_export_settings"))
        import_settings_item = tools_menu.Append(wx.ID_ANY, self.tr.t("menu_import_settings"))
        menubar.Append(tools_menu, self.tr.t("menu_tools"))

        help_menu = wx.Menu()
        guide_item = help_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_user_guide')}\tF1")
        export_shortcuts_item = help_menu.Append(wx.ID_ANY, f"{self.tr.t('menu_export_shortcuts_doc')}\tCtrl+Shift+H")
        help_menu.AppendSeparator()

        about_item = help_menu.Append(wx.ID_ABOUT, self.tr.t("menu_about"))
        menubar.Append(help_menu, self.tr.t("menu_help"))

        self.SetMenuBar(menubar)

        self.Bind(wx.EVT_MENU, self._on_open, open_item)
        self.Bind(wx.EVT_MENU, self._on_open_folder, open_folder_item)
        self.Bind(wx.EVT_MENU, self._on_open_url, open_url_item)
        self.Bind(wx.EVT_MENU, self._on_playlist_dialog, playlist_item)
        self.Bind(wx.EVT_MENU, self._on_save_playlist, save_playlist_item)
        self.Bind(wx.EVT_MENU, self._on_announce_stream_title, stream_title_item)
        self.Bind(wx.EVT_MENU, self._on_equalizer, equalizer_item)
        self.Bind(wx.EVT_MENU, lambda e: self._cycle_equalizer(1), equalizer_next_item)
        self.Bind(wx.EVT_MENU, lambda e: self._cycle_equalizer(-1), equalizer_previous_item)
        self.Bind(wx.EVT_MENU, self._on_options, options_item)
        self.Bind(wx.EVT_MENU, lambda e: self.Close(), exit_item)
        self.Bind(wx.EVT_MENU, self._on_play_pause, play_item)
        self.Bind(wx.EVT_MENU, self._on_stop, stop_item)
        self.Bind(wx.EVT_MENU, self._on_toggle_mute, mute_item)
        self.Bind(wx.EVT_MENU, self._on_next, next_item)
        self.Bind(wx.EVT_MENU, self._on_previous, previous_item)
        self.Bind(wx.EVT_MENU, self._on_announce_time_status, time_status_item)
        self.Bind(wx.EVT_MENU, self._on_announce_duration, duration_item)
        self.Bind(wx.EVT_MENU, self._on_announce_remaining_time, remaining_item)
        self.Bind(wx.EVT_MENU, self._on_about, about_item)
        self.Bind(wx.EVT_MENU, self._on_user_guide, guide_item)
        self.Bind(wx.EVT_MENU, self._on_export_shortcuts_doc, export_shortcuts_item)
        self.Bind(wx.EVT_MENU, self._on_converter, converter_item)
        self.Bind(wx.EVT_MENU, self._on_recorder, recorder_item)
        self.Bind(wx.EVT_MENU, self._on_media_editor, media_editor_item)
        self.Bind(wx.EVT_MENU, self._on_editor_hotkeys_menu, self._editor_hotkeys_menu_item)
        self.Bind(wx.EVT_MENU, lambda e: self._change_speed(0.25), speed_increase_item)
        self.Bind(wx.EVT_MENU, lambda e: self._change_speed(-0.25), speed_decrease_item)
        self.Bind(wx.EVT_MENU, lambda e: self._reset_speed(), speed_reset_item)
        self.Bind(wx.EVT_MENU, lambda e: self._add_bookmark(), bookmark_add_item)
        self.Bind(wx.EVT_MENU, lambda e: self._jump_bookmark(forward=True), bookmark_next_item)
        self.Bind(wx.EVT_MENU, lambda e: self._jump_bookmark(forward=False), bookmark_previous_item)
        self.Bind(wx.EVT_MENU, lambda e: self._clear_bookmarks(), bookmark_clear_item)
        self.Bind(wx.EVT_MENU, self._on_sleep_timer, sleep_timer_item)
        self.Bind(wx.EVT_MENU, self._on_export_settings, export_settings_item)
        self.Bind(wx.EVT_MENU, self._on_import_settings, import_settings_item)

        self._refresh_recent_files_menu()

    def _seek_duration_kwargs(self):
        return {
            "normal": self.SEEK_NORMAL_SECONDS,
            "shift": self.SEEK_SHIFT_SECONDS,
            "ctrl": self.SEEK_CTRL_SECONDS,
            "ctrl_shift": self.SEEK_CTRL_SHIFT_SECONDS,
            "minutes": self.SEEK_ALT_SECONDS // 60,
        }

    def _format_seek_help_text(self):
        return self.tr.t("help_seek", **self._seek_duration_kwargs())

    def _register_global_media_keys(self):
        if not self.settings.get_enable_global_media_keys():
            return
        hotkeys = (
            (self._MEDIA_HOTKEY_PLAY_PAUSE, getattr(wx, "WXK_MEDIA_PLAY_PAUSE", 0xB3)),
            (self._MEDIA_HOTKEY_STOP, getattr(wx, "WXK_MEDIA_STOP", 0xB2)),
            (self._MEDIA_HOTKEY_NEXT, getattr(wx, "WXK_MEDIA_NEXT_TRACK", 0xB0)),
            (self._MEDIA_HOTKEY_PREV, getattr(wx, "WXK_MEDIA_PREV_TRACK", 0xB1)),
        )
        for hotkey_id, keycode in hotkeys:
            try:
                if self.RegisterHotKey(hotkey_id, wx.MOD_NONE, keycode):
                    self._registered_media_hotkey_ids.add(hotkey_id)
            except Exception:
                pass

    def _unregister_global_media_keys(self):
        for hotkey_id in list(self._registered_media_hotkey_ids):
            try: self.UnregisterHotKey(hotkey_id)
            except Exception: pass
        self._registered_media_hotkey_ids.clear()

    def _refresh_global_media_keys(self):
        self._unregister_global_media_keys()
        self._register_global_media_keys()

    def _on_global_media_hotkey(self, event):
        hotkey_id = event.GetId()
        if hotkey_id == self._MEDIA_HOTKEY_PLAY_PAUSE:
            self._on_play_pause(event)
        elif hotkey_id == self._MEDIA_HOTKEY_STOP:
            self._on_stop(event)
        elif hotkey_id == self._MEDIA_HOTKEY_NEXT:
            self._on_next(event)
        elif hotkey_id == self._MEDIA_HOTKEY_PREV:
            self._on_previous(event)
        elif self.is_editor_hotkey(hotkey_id):
            self._on_editor_hotkey(hotkey_id)

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

    def _refresh_transport_buttons_state(self):
        has_file = self._current_file_path is not None and not self._is_loading_file
        self.play_pause_button.Enable(has_file)
        self.stop_button.Enable(has_file)
        self.seek_backward_button.Enable(has_file)
        self.seek_forward_button.Enable(has_file)
        self.previous_button.Enable(has_file and self.playlist.has_previous())
        self.next_button.Enable(has_file and self.playlist.has_next())

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

        # إلغاء التركيز عن العناصر ونقله للنافذة الرئيسية للتحكم باختصارات لوحة المفاتيح
        self.SetFocus()

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

    def _on_play_pause(self, event):
        self.engine.toggle_play_pause()

    def _on_stop(self, event):
        self.engine.stop()
        self._reset_playback_ui()

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

    def _save_current_position(self):
        if self._current_file_path and not is_stream_url(self._current_file_path):
            self.settings.set_last_position(self._current_file_path, self.engine.get_current_position())

    def _on_toggle_mute(self, event):
        muted = not self.engine.is_muted
        self.engine.set_muted(muted)
        self._announce(self.tr.t("announce_muted" if muted else "announce_unmuted"), "announce_mute_toggle")

    def _on_announce_time_status(self, event):
        current = self.engine.get_current_position()
        total = self.engine.duration
        remaining = max(0.0, total - current)
        message = self.tr.t("announce_time_status", current=format_time(current), total=format_time(total), remaining=format_time(remaining))
        self.status_bar.SetStatusText(message)
        self._announce_debounced(message, "announce_time_status")

    def _on_announce_duration(self, event):
        message = self.tr.t("announce_duration", total=format_time(self.engine.duration))
        self.status_bar.SetStatusText(message)
        self._announce_debounced(message, "announce_duration_announce")

    def _on_toggle_fullscreen(self, event):
        going_fullscreen = not self.IsFullScreen()
        self.ShowFullScreen(going_fullscreen)

        if going_fullscreen:
            self.header_panel.Hide()
            self.controls_panel.Hide()
        else:
            self.header_panel.Show()
            self.controls_panel.Show()
        self.main_panel.Layout()

        message = self.tr.t("announce_fullscreen_on" if going_fullscreen else "announce_fullscreen_off")
        self.status_bar.SetStatusText(message)
        self._announce(message, "announce_fullscreen")

    def _on_escape_exit_fullscreen(self, event):
        if self.IsFullScreen():
            self._on_toggle_fullscreen(event)
        else:
            event.Skip()

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

    def _apply_media_layout(self, has_video: bool):
        if self._current_media_has_video == has_video:
            if has_video:
                self.video_panel.Show()
                self.audio_spacer_panel.Hide()
                self.engine.set_video_widget_handle(self.video_panel.GetHandle())
                self.video_panel.Refresh()
            else:
                self.video_panel.Hide()
                self.audio_spacer_panel.Show()
                try: self.engine.set_video_widget_handle(0)
                except Exception: pass
                self.audio_spacer_panel.Refresh()
            return

        self._current_media_has_video = has_video

        if has_video:
            self.video_panel.Show()
            self.audio_spacer_panel.Hide()
            self.engine.set_video_widget_handle(self.video_panel.GetHandle())
            self.video_panel.Refresh()
        else:
            self.video_panel.Hide()
            self.audio_spacer_panel.Show()
            try: self.engine.set_video_widget_handle(0)
            except Exception: pass
            self.audio_spacer_panel.Refresh()

        self.main_panel.Layout()
        self.Layout()
        self.Refresh()

    def _on_go_to_time(self, event):
        """
        القفز لوقت مكتوب.

        لمستخدم كتاب صوتي طوله ثماني ساعات، "روح للساعة 3 والدقيقة 12"
        أسرع بمراحل من التقديم بالسهم أو من النسب المئوية.
        """
        from core.time_input import TimeParseError, format_time_for_input, parse_time

        duration = self.engine.duration
        if not duration:
            self._announce(self.tr.t("goto_no_file"), force=True)
            return

        current = format_time_for_input(self.engine.get_effective_position())
        with wx.TextEntryDialog(
            self,
            self.tr.t("goto_prompt", total=format_time_for_input(duration)),
            self.tr.t("goto_title"),
            value=current,
        ) as dialog:
            if dialog.ShowModal() != wx.ID_OK:
                return
            raw = dialog.GetValue()

        try:
            target = parse_time(raw)
        except TimeParseError:
            self._announce(self.tr.t("goto_invalid"), force=True)
            return

        if target > duration:
            self._announce(
                self.tr.t("goto_past_end", total=format_time_for_input(duration)),
                force=True,
            )
            return

        self._perform_seek(target)
        self._last_seek_time = time.time()
        self._update_info_labels(is_seeking=True, seek_target=target)
        self._announce(self.tr.t("goto_done", time=format_time_for_input(target)), force=True)

    def _change_speed(self, delta: float):
        self.engine.set_speed(round(self.engine.speed + delta, 2))
        self._remember_speed()
        self._announce(self.tr.t("announce_playback_speed", speed=f"{self.engine.speed:g}"), "announce_playback_speed")

    def _reset_speed(self):
        self.engine.set_speed(1.0)
        self._remember_speed()
        self._announce(self.tr.t("announce_playback_speed", speed=f"{self.engine.speed:g}"), "announce_playback_speed")

    def _remember_speed(self):
        if self._current_file_path:
            self.settings.set_file_speed(self._current_file_path, self.engine.speed)

    def _on_close(self, event):
        if getattr(self, "_quick_record_dialog", None) is not None and getattr(self._quick_record_dialog, "recorder", None) and self._quick_record_dialog.recorder.is_recording:
            dlg = wx.MessageDialog(
                self,
                self.tr.t("msg_confirm_exit_recording_options"),
                self.tr.t("title_warning"),
                wx.YES_NO | wx.CANCEL | wx.ICON_WARNING
            )
            dlg.SetYesNoCancelLabels(
                yes=self.tr.t("btn_exit_and_save"),
                no=self.tr.t("btn_exit_discard"),
                cancel=self.tr.t("btn_cancel_action")
            )
            result = dlg.ShowModal()
            dlg.Destroy()

            if result == wx.ID_YES:
                # فشل الحفظ كان بيتبلع بصمت والبرنامج يقفل: المستخدم يفتكر
                # تسجيله اتحفظ وهو ضاع. دلوقتي بيتقال له، ومعاه مسار الملف
                # المؤقت لو لسه موجود عشان يقدر ينقذه بنفسه.
                try:
                    if self._quick_record_dialog:
                        self._quick_record_dialog.stop_and_save()
                except Exception as exc:
                    logger.exception("فشل حفظ التسجيل عند الخروج")
                    temp_path = getattr(self._quick_record_dialog, "_temp_wav_path", None)
                    details = f"\n\n{temp_path}" if temp_path and os.path.exists(temp_path) else ""
                    wx.MessageBox(
                        self.tr.t("recorder_error_save_failed", error=str(exc)) + details,
                        self.tr.t("recorder_dialog_title"),
                        wx.ICON_ERROR,
                    )
            elif result == wx.ID_NO:
                try:
                    if self._quick_record_dialog:
                        self._quick_record_dialog.recorder.stop()
                        # الملف المؤقت هو اللي بيتكتب أثناء التسجيل؛ _wav_path
                        # كان اسم غلط مش موجود في النافذة، فالحذف ما كانش
                        # بيحصل والملفات المؤقتة بتتراكم.
                        # (شوف AudioRecorderDialog._start_recording)
                        temp_path = self._quick_record_dialog._temp_wav_path
                        if temp_path and os.path.exists(temp_path):
                            os.remove(temp_path)
                except Exception:
                    logger.exception("فشل حذف الملف المؤقت للتسجيل عند الخروج")
            else:
                event.Veto()
                return

        # الحفظ دفعة واحدة: الموضع والحجم كانوا بيكتبوا الملف مرتين
        # عند كل خروج.
        # (شوف Settings.batch)
        # والكتابة الذرّية بتخلّي كل كتابة أغلى من الأول.
        # (شوف Settings._write_to_disk)
        # فدمجهم بيفرق فعلًا على الأجهزة البطيئة.
        with self.settings.batch():
            self._save_current_position()
            self._save_window_geometry()

        # العلامة دي بتسكّت تحديثات الحالة اللي بتيجي من المحرك أثناء
        # الإيقاف: من غيرها "متوقف" بيتقال والنافذة بتتقفل.
        # (شوف _apply_state_change)
        self._is_closing = True
        self.engine.stop()
        self._unregister_global_media_keys()
        self._unregister_editor_hotkeys()
        # المحرر يُخفى عند إغلاقه ولا يُهدم (انظر gui/editor_hotkeys.py)
        editor = getattr(self, "_media_editor_dialog", None)
        if editor:
            if editor._runner is not None:
                editor._runner.cancel()
            editor.Destroy()

        if hasattr(self, "ipc_cleanup_callback") and self.ipc_cleanup_callback:
            self.ipc_cleanup_callback()

        self.Destroy()
        app = wx.GetApp()
        if app:
            app.ExitMainLoop()

    def _on_state_change(self, state):
        wx.CallAfter(self._apply_state_change, state)

    def _apply_state_change(self, state):
        if getattr(self, "_is_closing", False):
            return

        status_map = {
            PlaybackState.PLAYING: self.tr.t("state_playing"),
            PlaybackState.PAUSED: self.tr.t("state_paused"),
            PlaybackState.STOPPED: self.tr.t("state_stopped"),
            PlaybackState.ENDED: self.tr.t("state_ended"),
            PlaybackState.LOADING: self.tr.t("state_loading"),
        }
        if state in status_map:
            status_text = status_map[state]
            self.status_bar.SetStatusText(status_text)
            if state == PlaybackState.LOADING: self._announce(status_text, "announce_buffering")
            else: self._announce(status_text, "announce_playback_state")

        is_playing = state == PlaybackState.PLAYING
        if is_playing and self.engine.is_stream:
            self._apply_media_layout(self.engine.has_video)

        # الزر بأيقونة مرسومة والاسم المنطوق نص صريح: الأيقونات القديمة
        # كانت رموز يونيكود بيقراها القارئ حرفيًا
        label = self.tr.t("btn_pause") if is_playing else self.tr.t("btn_play")
        icon = player_icons.pause_icon if is_playing else player_icons.play_icon
        # الأيقونة بلون نص الزر نفسه: بتتبع السمة الحالية
        # (شوف _retint_button_icons)
        self.play_pause_button.SetBitmap(
            icon(size=18, scale=self._icon_scale,
                 colour=self.play_pause_button.GetForegroundColour())
        )
        self.play_pause_button.SetLabel(label)
        self.play_pause_button.SetName(label)
        self.play_pause_button.SetToolTip(label)
        self._update_info_labels()
        if state == PlaybackState.ENDED: self._handle_playback_ended()

    def _reset_playback_ui(self):
        self.video_panel.clear()
        self.seek_slider.SetValue(0)
        self._update_info_labels()

    def _handle_playback_ended(self):
        if self._current_file_path: self.settings.clear_last_position(self._current_file_path)

        # مؤقّت النوم على "نهاية الملف" بيسبق إجراء النهاية العادي: المستخدم
        # طالب يقف هنا بالتحديد، فالانتقال للملف التالي يخالف طلبه.
        # (شوف SleepTimerMixin._on_sleep_timer)
        # والإجراء نفسه هو اللي اختاره في نافذة المؤقّت.
        if getattr(self, "_sleep_at_end_of_file", False):
            self._sleep_at_end_of_file = False
            self._announce(self.tr.t("announce_sleep_timer_fired"), "announce_sleep_timer")
            self._apply_sleep_timer_action()
            return

        # «إيقاف الكمبيوتر» اتشال من إجراءات النهاية: شوف Settings.load.
        # مؤقّت النوم بيعمله لمن يريده صراحةً.
        # (والقيمة القديمة بتتحوّل للملف التالي عند التحميل)
        # فالإجراءات الباقية: لا شيء، أو الملف التالي.
        action = self.settings.get_on_playback_ended_action()
        if action == "next_file" and self.playlist.has_next(): self._load_and_play(self.playlist.next())

    def _on_error(self, message):
        wx.CallAfter(self._show_error, message)

    def _show_error(self, message):
        self.status_bar.SetStatusText(self.tr.t("status_error_open"))
        self._announce(self.tr.t("status_error_open"))
        wx.MessageBox(message, self.tr.t("status_error_open"), wx.ICON_ERROR)

    def _on_timer_tick(self, event):
        if self._is_sleep_timer_active:
            remaining_secs = int(self._sleep_timer_end_time - time.time())
            if remaining_secs <= 0:
                self._is_sleep_timer_active = False
                self.sleep_timer_badge.Hide()
                self.header_panel.Layout()
            else:
                m, s = divmod(remaining_secs, 60)
                h, m = divmod(m, 60)
                time_str = f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
                badge_text = self.tr.t("sleep_timer_badge", time=time_str)
                if self.sleep_timer_badge.GetLabel() != badge_text:
                    self.sleep_timer_badge.SetLabel(badge_text)
                    self.header_panel.Layout()

        if self._is_holding_seek:
            if not (wx.GetKeyState(wx.WXK_RIGHT) or wx.GetKeyState(wx.WXK_LEFT)):
                self._stop_hold_seek()

        if self.engine.state == PlaybackState.PLAYING:
            is_recovering_from_seek = (time.time() - self._last_seek_time) <= 1.0

            if self.engine.duration and self.engine.duration > 0:
                duration_secs = int(self.engine.duration)
                if self.seek_slider.GetMax() != duration_secs:
                    self.seek_slider.SetMax(duration_secs)
                    self.seek_slider.SetPageSize(max(1, duration_secs // 10))
                    self.seek_slider.SetLineSize(max(1, duration_secs // 50))

                pos = self.engine.get_current_position()
                if not self._user_is_dragging_slider and not self._is_holding_seek and not is_recovering_from_seek:
                    self.seek_slider.SetValue(int(pos))

            if not self._user_is_dragging_slider and not self._is_holding_seek and not is_recovering_from_seek:
                self._update_info_labels()

            self._autosave_tick_counter += 1
            if self._autosave_tick_counter >= 40:
                self._autosave_tick_counter = 0
                self._save_current_position()
        else:
            self._autosave_tick_counter = 0

    def _on_start_recording_shortcut(self, event):
        from gui.audio_recorder_dialog import AudioRecorderDialog

        if getattr(self, "_quick_record_dialog", None) is not None and getattr(self._quick_record_dialog, "recorder", None) and self._quick_record_dialog.recorder.is_recording:
            self._quick_record_dialog.stop_and_save()
            return
        if getattr(self, "_quick_record_dialog", None) is None:
            self._quick_record_dialog = AudioRecorderDialog(None, self.tr, None, self.settings)
            self._quick_record_dialog.announcer = ScreenReaderAnnouncer(self._quick_record_dialog)
            self._quick_record_dialog.Bind(wx.EVT_CLOSE, self._on_quick_record_dialog_closed)
        self._quick_record_dialog.Show()
        self._quick_record_dialog.start_recording()

    def _on_quick_record_dialog_closed(self, event):
        if getattr(self, "_quick_record_dialog", None) is not None:
            if getattr(self._quick_record_dialog, "recorder", None) and self._quick_record_dialog.recorder.is_recording:
                self._quick_record_dialog.Hide()
                self._announce(self.tr.t("recorder_announce_hidden"))
                event.Veto()
                return
        # النافذة بلا أب (شوف ToolsMixin._on_recorder)، فلازم تتدمّر صراحةً
        if getattr(self, "_quick_record_dialog", None):
            self._quick_record_dialog.Destroy()
            self._quick_record_dialog = None

    def _on_volume_change(self, event):
        value = self.volume_slider.GetValue()
        self.engine.set_volume(value / 100.0)
        self.settings.set_volume(value)
        self.vol_pct_label.SetLabel(f"{value}%")
        self.controls_panel.Layout()
        self._announce(self.tr.t("announce_volume", percent=value), "announce_volume_changes")

    def _volume_relative(self, delta):
        new_value = max(0, min(self.MAX_VOLUME, self.volume_slider.GetValue() + delta))
        self.volume_slider.SetValue(new_value)
        self.engine.set_volume(new_value / 100.0)
        self.settings.set_volume(new_value)
        self.vol_pct_label.SetLabel(f"{new_value}%")
        self.controls_panel.Layout()
        self._announce(self.tr.t("announce_volume", percent=new_value), "announce_volume_changes")

    def _bind_shortcuts(self):
        accel_entries = []

        def bind(modifier, key, handler):
            new_id = wx.NewIdRef()
            self.Bind(wx.EVT_MENU, handler, id=new_id)
            accel_entries.append(wx.AcceleratorEntry(modifier, key, new_id))

        bind(wx.ACCEL_NORMAL, wx.WXK_UP, lambda e: self._volume_relative(5))
        bind(wx.ACCEL_NORMAL, wx.WXK_DOWN, lambda e: self._volume_relative(-5))
        bind(wx.ACCEL_CTRL, wx.WXK_UP, lambda e: self._volume_relative(20))
        bind(wx.ACCEL_CTRL, wx.WXK_DOWN, lambda e: self._volume_relative(-20))
        bind(wx.ACCEL_NORMAL, ord("M"), lambda e: self._on_toggle_mute(e))

        bind(wx.ACCEL_CTRL, wx.WXK_SPACE, self._on_stop)

        bind(wx.ACCEL_NORMAL, ord("R"), self._on_announce_remaining_time)
        bind(wx.ACCEL_NORMAL, ord("E"), self._on_announce_duration)
        bind(wx.ACCEL_NORMAL, ord("T"), self._on_announce_time_status)
        bind(wx.ACCEL_NORMAL, ord("N"), self._on_announce_stream_title)

        bind(wx.ACCEL_SHIFT, ord("Q"), lambda e: self._cycle_equalizer(-1))
        bind(wx.ACCEL_NORMAL, ord("Q"), lambda e: self._cycle_equalizer(1))
        bind(wx.ACCEL_CTRL, ord("E"), self._on_equalizer)
        bind(wx.ACCEL_CTRL, ord("U"), self._on_open_url)
        bind(wx.ACCEL_CTRL, ord("L"), self._on_playlist_dialog)
        bind(wx.ACCEL_CTRL, ord("S"), self._on_save_playlist)

        bind(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("R"), self._on_recorder)
        bind(wx.ACCEL_CTRL, ord("R"), self._on_start_recording_shortcut)
        bind(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("X"), self._on_media_editor)

        bind(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("P"), self._on_options)

        bind(wx.ACCEL_CTRL | wx.ACCEL_ALT, ord("A"), self._on_toggle_accessibility_shortcut)
        bind(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("H"), self._on_export_shortcuts_doc)
        # تقرير التشخيص (شوف ToolsMixin._on_export_diagnostics)
        bind(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("D"), self._on_export_diagnostics)

        if self.settings.get_enable_folder_navigation():
            bind(wx.ACCEL_NORMAL, wx.WXK_PAGEDOWN, self._on_next)
            bind(wx.ACCEL_NORMAL, wx.WXK_PAGEUP, self._on_previous)

        numpad_keys = (wx.WXK_NUMPAD1, wx.WXK_NUMPAD2, wx.WXK_NUMPAD3, wx.WXK_NUMPAD4, wx.WXK_NUMPAD5, wx.WXK_NUMPAD6, wx.WXK_NUMPAD7, wx.WXK_NUMPAD8, wx.WXK_NUMPAD9)
        for index, numpad_key in enumerate(numpad_keys, start=1):
            bind(wx.ACCEL_NORMAL, numpad_key, lambda e, p=index * 10: self._seek_to_percent(p))

        bind(wx.ACCEL_NORMAL, wx.WXK_NUMPAD0, lambda e: self._seek_to_start())
        bind(wx.ACCEL_NORMAL, wx.WXK_HOME, lambda e: self._seek_to_start())
        bind(wx.ACCEL_NORMAL, wx.WXK_END, lambda e: self._seek_to_near_end())

        bind(wx.ACCEL_ALT, wx.WXK_UP, lambda e: self._change_speed(0.25))
        bind(wx.ACCEL_ALT, wx.WXK_DOWN, lambda e: self._change_speed(-0.25))
        bind(wx.ACCEL_ALT, wx.WXK_NUMPAD0, lambda e: self._reset_speed())

        bind(wx.ACCEL_CTRL, ord("G"), self._on_go_to_time)

        # Ctrl+Alt+B قبل Ctrl+B: جدول المسرّعات بياخد أول تطابق
        bind(wx.ACCEL_CTRL | wx.ACCEL_ALT, ord("B"), lambda e: self._rename_bookmark())
        bind(wx.ACCEL_CTRL, ord("B"), lambda e: self._add_bookmark())
        bind(wx.ACCEL_NORMAL, wx.WXK_F2, lambda e: self._jump_bookmark(forward=True))
        bind(wx.ACCEL_SHIFT, wx.WXK_F2, lambda e: self._jump_bookmark(forward=False))
        bind(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("B"), lambda e: self._clear_bookmarks())

        bind(wx.ACCEL_NORMAL, wx.WXK_F11, self._on_toggle_fullscreen)
        bind(wx.ACCEL_NORMAL, wx.WXK_ESCAPE, self._on_escape_exit_fullscreen)

        self.SetAcceleratorTable(wx.AcceleratorTable(accel_entries))

    def _start_hold_seek(self, keycode, initial_delta_seconds):
        if not self._is_holding_seek:
            self._is_holding_seek = True
            self._holding_key = keycode
            self._seek_speed_multiplier = 1.0
            self._hold_target_position = self.engine.get_effective_position()
            # نقطة البداية علشان مقدار القفزة الكلي يتحسب عند الإفلات
            # (شوف _announce_seek وحدّ الإعلان الأدنى)
            self._hold_start_position = self._hold_target_position
            self.engine.set_muted(True)
            self._step_hold_seek(initial_delta_seconds)
            self._hold_seek_timer.Start(80)

    def _step_hold_seek(self, base_delta):
        if not self.engine.duration:
            return
        if self._hold_target_position is None:
            self._hold_target_position = self.engine.get_effective_position()

        self._seek_speed_multiplier = min(60.0, self._seek_speed_multiplier * 1.25)
        step = base_delta * self._seek_speed_multiplier

        self._hold_target_position = max(0.0, min(self.engine.duration, self._hold_target_position + step))
        self.seek_slider.SetValue(int(self._hold_target_position))
        self._update_info_labels(is_seeking=True, seek_target=self._hold_target_position)

    def _on_hold_seek_timer(self, event):
        if not (wx.GetKeyState(wx.WXK_RIGHT) or wx.GetKeyState(wx.WXK_LEFT)):
            self._stop_hold_seek()
            return

        if self._holding_key in (wx.WXK_RIGHT, wx.WXK_LEFT):
            base_delta = 1.5 if self._holding_key == wx.WXK_RIGHT else -1.5
            self._step_hold_seek(base_delta)
        else:
            self._stop_hold_seek()

    def _stop_hold_seek(self):
        if self._is_holding_seek:
            self._is_holding_seek = False
            self._holding_key = None
            self._hold_seek_timer.Stop()

            if hasattr(self, '_hold_target_position') and self._hold_target_position is not None:
                self.engine.seek(self._hold_target_position)
                self._last_seek_time = time.time()
                target = self._hold_target_position
                self._hold_target_position = None
                start = getattr(self, "_hold_start_position", None)
                jump = target - start if start is not None else None
                self._hold_start_position = None
                self._announce_seek(target, seek_type="seconds", jump_seconds=jump)

            self.engine.set_muted(False)
            self._update_info_labels()

    def _on_key_up(self, event):
        keycode = event.GetKeyCode()
        if keycode in (wx.WXK_RIGHT, wx.WXK_LEFT) and self._holding_key == keycode:
            self._stop_hold_seek()
        event.Skip()

    def _on_char_hook(self, event):
        keycode = event.GetKeyCode()
        # Tab مقفول: التنقّل بين الأزرار ممنوع (شوف _enforce_focusless_behavior)
        if keycode == wx.WXK_TAB: return
        alt = event.AltDown()
        ctrl = event.ControlDown() or event.CmdDown()
        shift = event.ShiftDown()

        focused = wx.Window.FindFocus()
        interactive_controls = (wx.Button, wx.TextCtrl, wx.CheckBox, wx.ComboBox, wx.ListBox, wx.RadioButton, wx.SpinCtrl)

        if focused and isinstance(focused, interactive_controls):
            if keycode in (wx.WXK_SPACE, wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
                event.Skip()
                return

        if keycode in (wx.WXK_RIGHT, wx.WXK_LEFT):
            delta = self.SEEK_NORMAL_SECONDS
            if ctrl and shift: delta = self.SEEK_CTRL_SHIFT_SECONDS
            elif ctrl: delta = self.SEEK_CTRL_SECONDS
            elif shift: delta = self.SEEK_SHIFT_SECONDS
            elif alt: delta = self.SEEK_ALT_SECONDS

            if keycode == wx.WXK_LEFT: delta = -delta

            if not (alt or ctrl or shift):
                if self._holding_key != keycode:
                    self._holding_key = keycode
                    self._start_hold_seek(keycode, delta)
            else:
                self._seek_relative(delta)
            return

        if keycode == wx.WXK_SPACE:
            if ctrl and not (alt or shift):
                self._on_stop(event)
                return
            elif not (alt or ctrl or shift):
                self._on_play_pause(event)
                return

        event.Skip()
