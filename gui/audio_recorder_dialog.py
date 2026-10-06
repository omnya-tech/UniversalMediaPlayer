# -*- coding: utf-8 -*-
"""
واجهة مسجل الصوت الاحترافي لمشغل الوسائط (Audio Recorder Dialog)
تدعم التسجيل الفردي والدمج بين المايكروفون والستيريو ميكس (صوت النظام)،
مع إمكانية الفلترة الذكية للأجهزة النشطة وشاشة زمنية ومؤشر صوتي حي.
"""

import os
import tempfile

import wx

from core.audio_recorder import SUPPORTED_BIT_DEPTHS, SUPPORTED_SAMPLE_RATES, AudioRecorder, RecorderError, list_input_devices, replace_with_retry
from core.formats import AUDIO_FORMATS
from core.voice_enhance import DEFAULT_ENHANCE_LEVEL, ENHANCE_LEVELS
from core.logging_setup import configure_logging
from accessibility.announcer import _resource_path
from core.notification_sound import play_completion_chime, play_error_chime
from gui.audio_bitrate_widget import refresh_audio_bitrate_choice
from gui.dialog_helpers import bind_escape_closes
from gui import theme
from i18n.plural import count_phrase
from gui.recorder_widgets import _LevelMeter, _default_recording_path, _format_elapsed
from gui.recorder_devices_mixin import RecorderDevicesMixin
from gui.mic_check_mixin import MicCheckMixin

_logger = configure_logging()


class AudioRecorderDialog(MicCheckMixin, RecorderDevicesMixin, wx.Frame):
    def __init__(self, parent, tr, announcer, settings=None):
        super().__init__(
            parent,
            title=tr.t("recorder_dialog_title"),
            size=(580, 610),
            style=wx.DEFAULT_FRAME_STYLE & ~(wx.MAXIMIZE_BOX),
        )
        self.tr = tr
        self.announcer = announcer
        self.settings = settings
        self._set_app_icon()
        # المترجِم بيتمرّر للمسجّل عشان رسائل فشل فتح الجهاز توصل بلغة
        # المستخدم (شوف AudioRecorder._describe_open_failure)
        self.recorder = AudioRecorder(on_level=self._on_level,
                                      on_error=self._on_error, tr=tr)
        self._last_level = (0.0, 0.0)
        self._clipping_warning_shown = False
        # مستوى المايك المختار في ويندوز (شوف _refresh_mic_level)
        self._mic_level = None

        self._temp_wav_path = None
        default_format = self.settings.get_recorder_default_format() if self.settings is not None else ".wav"
        default_folder = (
            self.settings.get_recorder_output_folder() if self.settings is not None else tempfile.gettempdir()
        )
        file_prefix = self.tr.t("recorder_file_prefix")
        self._output_path = _default_recording_path(default_folder, default_format, file_prefix)
        self._output_path_is_default = True

        self._build_ui()
        self.Bind(wx.EVT_CLOSE, self._on_close)
        bind_escape_closes(self)

        accel_id = wx.NewIdRef()
        level_id = wx.NewIdRef()
        self.Bind(wx.EVT_MENU, self._on_ctrl_r_local, id=accel_id)
        self.Bind(wx.EVT_MENU, self._on_announce_level, id=level_id)
        self.SetAcceleratorTable(wx.AcceleratorTable([
            (wx.ACCEL_CTRL, ord("R"), accel_id),
            (wx.ACCEL_CTRL, ord("L"), level_id),
        ]))

    def _on_ctrl_r_local(self, event):
        if self.recorder.is_recording:
            self.stop_and_save()
        else:
            self._start_recording()

    def _set_app_icon(self):
        icon_path = _resource_path("resources", "omnya_icon.ico")
        try:
            if os.path.isfile(icon_path):
                self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO))
        except Exception:
            pass

    def _build_ui(self):
        panel = wx.Panel(self)
        # الخلفية الفاتحة في المظهر الفاتح وحده؛ في الداكن والتباين العالي
        # لون النظام (كانت ثابتة، فتبقى لوحة فاتحة وسط نافذة داكنة)
        if theme.custom_colours_allowed() and not theme.is_dark():
            panel.SetBackgroundColour(wx.Colour(245, 247, 250))
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        tr = self.tr

        # 1. شاشة العرض والمؤشر الصوتي
        display_panel = wx.Panel(panel)
        display_panel.SetBackgroundColour(wx.Colour(28, 35, 49))
        display_sizer = wx.BoxSizer(wx.VERTICAL)

        self.elapsed_label = wx.StaticText(display_panel, label="00:00")
        # أرقام لاتينية كعدّاد المشغّل: في الواجهة العربية يحوّلها ويندوز إلى
        # أرقام هندية، وصفرها نقطة، فبدا العدّاد بالخط الكبير «•• : ••»
        self.elapsed_label.SetLayoutDirection(wx.Layout_LeftToRight)
        self.elapsed_label.SetForegroundColour(wx.Colour(255, 255, 255))
        font_time = wx.Font(28, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        self.elapsed_label.SetFont(font_time)
        display_sizer.Add(self.elapsed_label, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        self.level_meter = _LevelMeter(display_panel)
        display_sizer.Add(self.level_meter, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=12)

        # تحذير التشبّع: بيظهر أثناء التسجيل لو الصوت عالي لدرجة التشويه
        # (شوف _show_clipping_warning)
        self.clipping_warning = wx.StaticText(display_panel, label="")
        self.clipping_warning.SetForegroundColour(wx.Colour(255, 209, 102))
        warning_font = self.clipping_warning.GetFont()
        warning_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.clipping_warning.SetFont(warning_font)
        self.clipping_warning.Hide()
        display_sizer.Add(self.clipping_warning,
                          flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=12)

        display_panel.SetSizer(display_sizer)
        main_sizer.Add(display_panel, flag=wx.EXPAND | wx.ALL, border=10)

        # 2. إعدادات المصدر والأجهزة
        settings_box = wx.StaticBox(panel, label=tr.t("recorder_settings_box"))
        settings_sizer = wx.StaticBoxSizer(settings_box, wx.VERTICAL)

        # الجهاز الرئيسي (المايك)
        dev_pri_row = wx.BoxSizer(wx.HORIZONTAL)
        lbl_dev_pri = wx.StaticText(panel, label=tr.t("recorder_device_label"))
        self.device_choice = wx.Choice(panel)
        self.device_choice.SetName(tr.t("recorder_device_label"))
        self.Bind(wx.EVT_CHOICE, self._on_capabilities_changed, self.device_choice)
        dev_pri_row.Add(lbl_dev_pri, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        dev_pri_row.Add(self.device_choice, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL)
        settings_sizer.Add(dev_pri_row, flag=wx.EXPAND | wx.ALL, border=6)

        # مستوى المايك في ويندوز: التشبّع بيحصل داخل المايك، فالحل الوحيد
        # تخفيض مستواه هو، وبيتغيّر أثناء التسجيل وعين المستخدم على المؤشر
        # (شوف core/mic_level.py)
        level_row = wx.BoxSizer(wx.HORIZONTAL)
        self.mic_level_label = wx.StaticText(panel, label=tr.t("recorder_mic_level_label"))
        self.mic_level_slider = wx.Slider(panel, value=100, minValue=0, maxValue=100)
        self.mic_level_slider.SetName(tr.t("recorder_mic_level_label"))
        self.mic_level_slider.SetToolTip(tr.t("recorder_mic_level_hint"))
        self.mic_level_slider.SetPageSize(10)
        self.mic_level_value = wx.StaticText(panel, label="", size=(48, -1))
        self.mic_level_value.SetLayoutDirection(wx.Layout_LeftToRight)
        self.Bind(wx.EVT_SLIDER, self._on_mic_level_change, self.mic_level_slider)
        level_row.Add(self.mic_level_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        level_row.Add(self.mic_level_slider, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL)
        level_row.Add(self.mic_level_value, flag=wx.ALIGN_CENTER_VERTICAL | wx.LEFT, border=6)
        settings_sizer.Add(level_row, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=6)
        self.mic_level_note = wx.StaticText(panel, label="")
        self.mic_level_note.Hide()
        settings_sizer.Add(self.mic_level_note, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=6)

        # خيار دمج جهاز إدخال ثانٍ (الستيريو ميكس)
        self.chk_dual_input = wx.CheckBox(panel, label=tr.t("recorder_dual_input"))
        self.chk_dual_input.Bind(wx.EVT_CHECKBOX, self._on_toggle_dual_input)
        settings_sizer.Add(self.chk_dual_input, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=6)

        dev_sec_row = wx.BoxSizer(wx.HORIZONTAL)
        self.lbl_dev_sec = wx.StaticText(panel, label=tr.t("recorder_secondary_device"))
        self.secondary_device_choice = wx.Choice(panel)
        self.secondary_device_choice.Disable()
        self.lbl_dev_sec.Disable()

        dev_sec_row.Add(self.lbl_dev_sec, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        dev_sec_row.Add(self.secondary_device_choice, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL)
        settings_sizer.Add(dev_sec_row, flag=wx.EXPAND | wx.ALL, border=6)

        self._populate_devices()

        # معدل العينة والقنوات
        format_row = wx.BoxSizer(wx.HORIZONTAL)
        rate_label = wx.StaticText(panel, label=tr.t("recorder_sample_rate_label"))
        self.rate_choice = wx.Choice(panel)
        self.rate_choice.SetName(tr.t("recorder_sample_rate_label"))

        channels_label = wx.StaticText(panel, label=tr.t("recorder_channels_label"))
        self.channels_choice = wx.Choice(panel)
        self.channels_choice.SetName(tr.t("recorder_channels_label"))

        format_row.Add(rate_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        format_row.Add(self.rate_choice, proportion=1, flag=wx.RIGHT, border=12)
        format_row.Add(channels_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        format_row.Add(self.channels_choice, proportion=1)
        settings_sizer.Add(format_row, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=6)

        # ملاحظة بتظهر لما معدل الجهاز أعلى من المقترح
        # (شوف _update_rate_headroom_note)
        self.rate_headroom_note = wx.StaticText(panel, label="")
        self.rate_headroom_note.Hide()
        settings_sizer.Add(self.rate_headroom_note,
                           flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=6)

        self._refresh_capabilities()

        # عمق البت والصيغة (مع إضافة .ts صراحة للقائمة)
        quality_row = wx.BoxSizer(wx.HORIZONTAL)
        bit_depth_label = wx.StaticText(panel, label=tr.t("recorder_bit_depth_label"))
        self.bit_depth_choice = wx.Choice(
            panel, choices=[tr.t(f"recorder_bit_depth_{depth}") for depth in SUPPORTED_BIT_DEPTHS]
        )
        self.bit_depth_choice.SetName(tr.t("recorder_bit_depth_label"))
        default_bit_depth = self.settings.get_recorder_default_bit_depth() if self.settings is not None else 16
        self._select_bit_depth(default_bit_depth)

        # أي تغيير في إعدادات الجهاز بيتحفظ له وحده
        # (شوف _remember_device_profile)
        for control in (self.rate_choice, self.channels_choice, self.bit_depth_choice):
            self.Bind(wx.EVT_CHOICE, self._on_device_setting_changed, control)

        target_label = wx.StaticText(panel, label=tr.t("recorder_format_label"))
        supported_audio_exts = sorted(list(AUDIO_FORMATS.keys()))
        if ".ts" not in supported_audio_exts:
            supported_audio_exts.append(".ts")
            supported_audio_exts.sort()
        self.format_choice = wx.Choice(panel, choices=supported_audio_exts)
        self.format_choice.SetName(tr.t("recorder_format_label"))
        default_format = self.settings.get_recorder_default_format() if self.settings is not None else ".wav"
        if self.format_choice.GetCount():
            index = self.format_choice.FindString(default_format)
            self.format_choice.SetSelection(index if index != wx.NOT_FOUND else 0)
        self.Bind(wx.EVT_CHOICE, self._on_format_change, self.format_choice)

        quality_row.Add(bit_depth_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        quality_row.Add(self.bit_depth_choice, proportion=1, flag=wx.RIGHT, border=12)
        quality_row.Add(target_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        quality_row.Add(self.format_choice, proportion=1)
        settings_sizer.Add(quality_row, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=6)

        # تحسين صوت المايكروفون والوضع الحصري (core/voice_enhance.py و
        # wasapi_exclusive_settings). يُحفظ الاختيار فورًا للمرة القادمة
        enhance_row = wx.BoxSizer(wx.HORIZONTAL)
        enhance_label = wx.StaticText(panel, label=tr.t("recorder_enhance_label"))
        self.enhance_choice = wx.Choice(
            panel, choices=[tr.t(f"recorder_enhance_{level}") for level in ENHANCE_LEVELS])
        self.enhance_choice.SetName(tr.t("recorder_enhance_label"))
        level = self.settings.get_recorder_enhance_level() if self.settings is not None else DEFAULT_ENHANCE_LEVEL
        self.enhance_choice.SetSelection(ENHANCE_LEVELS.index(level))
        self.Bind(wx.EVT_CHOICE, self._on_enhance_change, self.enhance_choice)
        enhance_row.Add(enhance_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        enhance_row.Add(self.enhance_choice, proportion=1)
        settings_sizer.Add(enhance_row, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=6)

        self.exclusive_check = wx.CheckBox(panel, label=tr.t("recorder_exclusive_label"))
        self.exclusive_check.SetValue(self.settings.get_recorder_exclusive() if self.settings is not None else True)
        self.exclusive_check.Bind(wx.EVT_CHECKBOX, self._on_exclusive_change)
        settings_sizer.Add(self.exclusive_check, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=6)

        # معدل البت
        bitrate_row = wx.BoxSizer(wx.HORIZONTAL)
        bitrate_label = wx.StaticText(panel, label=tr.t("converter_custom_audio_bitrate_label"))
        self.bitrate_choice = wx.Choice(panel)
        self.bitrate_choice.SetName(tr.t("converter_custom_audio_bitrate_label"))
        self.bitrate_lossless_note = wx.StaticText(
            panel, label=tr.t("converter_audio_bitrate_not_applicable")
        )
        bitrate_row.Add(bitrate_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        bitrate_row.Add(self.bitrate_choice, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        settings_sizer.Add(bitrate_row, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=6)
        # الملاحظة في سطر وحدها ملفوفة: بجانب عنوانها كانت تُقص من آخرها
        self.bitrate_lossless_note.Wrap(500)
        settings_sizer.Add(self.bitrate_lossless_note, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=6)

        preferred_bps = (
            self.settings.get_recorder_default_audio_bitrate() if self.settings is not None else 0
        )
        refresh_audio_bitrate_choice(
            self.bitrate_choice, self.bitrate_lossless_note, tr, default_format, False, preferred_bps
        )

        # مسار الحفظ
        output_row = wx.BoxSizer(wx.HORIZONTAL)
        output_title_lbl = wx.StaticText(panel, label=tr.t("recorder_save_path"))
        # المسار الطويل يُختصر من الوسط بـ«...» بدل أن يُقص آخره (اسم الملف)،
        # ويظهر كاملًا في التلميح
        self.output_path_label = wx.StaticText(panel, label=self._output_path,
                                               style=wx.ST_ELLIPSIZE_MIDDLE)
        self.output_path_label.SetToolTip(self._output_path)
        # بلا عرض أدنى صغير يأخذ النص عرضه كاملًا فيمدّ النافذة ولا يُختصر
        self.output_path_label.SetMinSize((60, -1))
        self.output_path_label.SetName(tr.t("recorder_output_label"))
        output_row.Add(output_title_lbl, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        output_row.Add(self.output_path_label, proportion=1, flag=wx.ALIGN_CENTER_VERTICAL)
        settings_sizer.Add(output_row, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=6)

        main_sizer.Add(settings_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=10)

        main_sizer.AddSpacer(10)

        # 3. أزرار التشغيل
        buttons_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        
        self.record_button = wx.Button(panel, label=tr.t("recorder_start_button"), size=(130, 42))
        self.pause_button = wx.Button(panel, label=tr.t("recorder_pause_button"), size=(110, 42))
        self.stop_button = wx.Button(panel, label=tr.t("recorder_stop_button"), size=(130, 42))
        
        for btn in [self.record_button, self.pause_button, self.stop_button]:
            btn.SetFont(btn_font)

        self.pause_button.Disable()
        self.stop_button.Disable()
        
        self.Bind(wx.EVT_BUTTON, self._on_record, self.record_button)
        self.Bind(wx.EVT_BUTTON, self._on_pause_resume, self.pause_button)
        self.Bind(wx.EVT_BUTTON, self._on_stop_click, self.stop_button)

        # اختبار المايكروفون: بديل نصي لمؤشر المستوى المرئي
        self.mic_check_button = wx.Button(panel, label=tr.t("mic_check_button"), size=(150, 42))
        self.mic_check_button.SetFont(btn_font)
        self.mic_check_button.SetToolTip(tr.t("mic_check_button_hint"))
        self.Bind(wx.EVT_BUTTON, self._on_mic_check, self.mic_check_button)

        buttons_row.AddStretchSpacer(1)
        buttons_row.Add(self.mic_check_button, flag=wx.RIGHT, border=8)
        buttons_row.Add(self.record_button, flag=wx.RIGHT, border=8)
        buttons_row.Add(self.pause_button, flag=wx.RIGHT, border=8)
        buttons_row.Add(self.stop_button)
        buttons_row.AddStretchSpacer(1)

        main_sizer.Add(buttons_row, flag=wx.EXPAND | wx.BOTTOM, border=12)

        panel.SetSizer(main_sizer)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND)
        self.SetSizer(outer)

        self._describe_controls()
        self._refresh_mic_level()
        # ويندوز ممكن يغيّر المستوى من بره (إعدادات الصوت أو برنامج تاني)
        self.Bind(wx.EVT_ACTIVATE, self._on_activate)

        self._ui_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_ui_timer, self._ui_timer)

        self.CenterOnParent()
        self.device_choice.SetFocus()

    def _describe_controls(self):
        """
        اسم منطوق وتلميح لكل عنصر في النافذة.

        ستة عناصر كان اسمها المنطوق حرفيًا "button" و"check" و"choice"،
        فقارئ الشاشة بيقول "زر" بلا ما يقول زر إيه - وأزرار التسجيل
        والإيقاف من دول. والتلميح بيدّي المبصر نفس الشرح.
        """
        tr = self.tr
        described = (
            (self.device_choice, "recorder_device_label", "recorder_device_hint"),
            (self.rate_choice, "recorder_sample_rate_label", "recorder_sample_rate_hint"),
            (self.channels_choice, "recorder_channels_label", "recorder_channels_hint"),
            (self.bit_depth_choice, "recorder_bit_depth_label", "recorder_bit_depth_hint"),
            (self.format_choice, "recorder_format_label", "recorder_format_hint"),
            (self.bitrate_choice, "converter_custom_audio_bitrate_label", "recorder_bitrate_hint"),
            (self.chk_dual_input, "recorder_dual_input", "recorder_dual_input_hint"),
            (self.secondary_device_choice, "recorder_secondary_device", "recorder_secondary_device_hint"),
            (self.record_button, "recorder_start_button", "recorder_start_button_hint"),
            (self.pause_button, "recorder_pause_button", "recorder_pause_button_hint"),
            (self.stop_button, "recorder_stop_button", "recorder_stop_button_hint"),
            (self.mic_check_button, "mic_check_button", "mic_check_button_hint"),
            (self.mic_level_slider, "recorder_mic_level_label", "recorder_mic_level_hint"),
        )
        for control, name_key, hint_key in described:
            try:
                control.SetName(tr.t(name_key))
                control.SetToolTip(tr.t(hint_key))
            except Exception:
                continue

    def _on_record(self, event):
        self._start_recording()

    def start_recording(self):
        self._start_recording()

    def stop_and_save(self):
        self._perform_stop()

    def _on_stop_click(self, event):
        self._perform_stop()

    def _start_recording(self):
        if not self._devices:
            wx.MessageBox(
                self.tr.t("recorder_error_no_device"),
                self.tr.t("recorder_dialog_title"),
                wx.ICON_WARNING,
            )
            return
        if not self._output_path:
            wx.MessageBox(
                self.tr.t("recorder_error_no_output"),
                self.tr.t("recorder_dialog_title"),
                wx.ICON_WARNING,
            )
            return

        if self.rate_choice.GetCount() == 0:
            wx.MessageBox(
                self.tr.t("recorder_error_no_valid_rate"),
                self.tr.t("recorder_dialog_title"),
                wx.ICON_WARNING,
            )
            return

        self._reset_clipping_warning()

        device_index = self._devices[self.device_choice.GetSelection()][0]
        sec_idx = None
        if self.chk_dual_input.IsChecked() and self.secondary_device_choice.GetSelection() >= 0:
            sec_idx = self._devices[self.secondary_device_choice.GetSelection()][0]

        rate_string = self.rate_choice.GetStringSelection()
        try:
            sample_rate = int(rate_string.split()[0])
        except (ValueError, IndexError):
            sample_rate = SUPPORTED_SAMPLE_RATES[0]

        channels = 1 if self.channels_choice.GetSelection() == 0 else 2
        bit_depth = self._selected_bit_depth()
        target_ext = self.format_choice.GetStringSelection() or ".wav"

        final_dir = os.path.dirname(self._output_path) or "."
        try:
            os.makedirs(final_dir, exist_ok=True)
        except OSError as exc:
            wx.MessageBox(
                self.tr.t("recorder_error_save_failed", error=str(exc)),
                self.tr.t("recorder_dialog_title"),
                wx.ICON_ERROR,
            )
            return

        fd, temp_path = tempfile.mkstemp(suffix=target_ext, prefix=".ump_rec_", dir=final_dir)
        os.close(fd)
        self._temp_wav_path = temp_path

        try:
            self.recorder.start(
                device_index,
                sample_rate,
                channels,
                temp_path,
                bit_depth=bit_depth,
                target_ext=target_ext,
                audio_bitrate=self._get_audio_bitrate(),
                secondary_device_index=sec_idx,
                enhance_level=self._selected_enhance_level(),
                exclusive=self.exclusive_check.GetValue(),
            )
        except RecorderError as exc:
            try:
                os.remove(temp_path)
            except OSError:
                pass
            wx.MessageBox(str(exc), self.tr.t("recorder_dialog_title"), wx.ICON_ERROR)
            return

        self.record_button.Disable()
        self.pause_button.Enable()
        self.pause_button.SetLabel(self.tr.t("recorder_pause_button"))
        self.stop_button.Enable()

        self.chk_dual_input.Disable()
        self.device_choice.Disable()
        self.secondary_device_choice.Disable()

        for control in (
            self.rate_choice,
            self.channels_choice,
            self.bit_depth_choice,
            self.format_choice,
            self.bitrate_choice,
            self.enhance_choice,
            self.exclusive_check,
        ):
            control.Disable()

        self._ui_timer.Start(200)
        started = self.tr.t("recorder_announce_started")
        # الحصري طُلب ورفضه الكرت: المستخدم يعرف أن التسجيل بالمشترك
        if self.recorder.exclusive_requested and not self.recorder.used_exclusive:
            started += ". " + self.tr.t("recorder_exclusive_fallback")
        self.announcer.announce(started)

    def _on_pause_resume(self, event):
        if self.recorder.is_paused:
            self.recorder.resume()
            self.pause_button.SetLabel(self.tr.t("recorder_pause_button"))
            self.announcer.announce(self.tr.t("recorder_announce_resumed"))
        else:
            self.recorder.pause()
            self.pause_button.SetLabel(self.tr.t("recorder_resume_button"))
            self.announcer.announce(self.tr.t("recorder_announce_paused"))

    def _perform_stop(self):
        if not self.stop_button.IsEnabled():
            return
        self.stop_button.Disable()
        self.pause_button.Disable()

        _, duration = self.recorder.stop()
        no_audio_captured = self.recorder.last_recording_had_no_audio
        had_clipping = self.recorder.had_clipping
        clip_events = self.recorder.clip_events
        self._ui_timer.Stop()
        self.level_meter.set_level(0.0)

        target_ext = self.format_choice.GetStringSelection() or ".wav"

        if no_audio_captured:
            try:
                if self._temp_wav_path and os.path.exists(self._temp_wav_path):
                    os.remove(self._temp_wav_path)
            except OSError:
                pass
            wx.MessageBox(
                self.tr.t("recorder_error_no_audio_captured"),
                self.tr.t("recorder_dialog_title"),
                wx.ICON_WARNING,
            )
            final_path = None
        else:
            try:
                final_target = os.path.splitext(self._output_path)[0] + target_ext
                replace_with_retry(self._temp_wav_path, final_target)
                final_path = final_target
            except Exception as exc:
                wx.MessageBox(
                    self.tr.t("recorder_error_save_failed", error=str(exc)),
                    self.tr.t("recorder_dialog_title"),
                    wx.ICON_ERROR,
                )
                final_path = None
                if self.settings is None or self.settings.get_enable_completion_sound():
                    play_error_chime()

        self.record_button.Enable()
        self.chk_dual_input.Enable()
        self.device_choice.Enable()
        if self.chk_dual_input.IsChecked():
            self.secondary_device_choice.Enable()

        for control in (
            self.rate_choice,
            self.channels_choice,
            self.bit_depth_choice,
            self.format_choice,
            self.bitrate_choice,
            self.enhance_choice,
            self.exclusive_check,
        ):
            control.Enable()

        self.elapsed_label.SetLabel("00:00")
        if final_path:
            message = self.tr.t(
                "recorder_announce_saved", duration=_format_elapsed(duration), path=final_path
            )
            # التشبّع بيتقال مع الحفظ: المستخدم ما يكتشفش الخشونة بعد ما يبعت الملف
            if had_clipping:
                message += " " + self.tr.t("recorder_announce_clipping",
                                           spots=count_phrase(self.tr, "count_spots", clip_events))
            self.announcer.announce(message)
            if self.settings is None or self.settings.get_enable_completion_sound():
                play_completion_chime()

    def _on_level(self, rms_level: float, peak_level: float = None):
        self._last_level = (rms_level, peak_level if peak_level is not None else rms_level)
        wx.CallAfter(self.level_meter.set_level, rms_level, peak_level)

        # التحذير بيظهر مرة واحدة لكل تسجيل لما التشبّع يتكرر، لا مع كل
        # كتلة: الكتل بتيجي عشرات المرات في الثانية من خيط الكتابة.
        # (CallAfter لأن الدالة دي بتتنادى من خيط الكتابة لا الواجهة)
        # (شوف AudioRecorder.had_clipping)
        # والتحذير المكتوب بيفضل ظاهر لحد التسجيل الجاي.
        if self.recorder.had_clipping and not self._clipping_warning_shown:
            self._clipping_warning_shown = True
            wx.CallAfter(self._show_clipping_warning)

    def _show_clipping_warning(self):
        warning = getattr(self, "clipping_warning", None)
        if warning is None or not self.recorder.is_recording:
            return
        warning.SetLabel(self.tr.t("recorder_clipping_live_warning"))
        warning.Wrap(max(240, self.GetSize().width - 80))
        warning.Show()
        self.Layout()

    def _reset_clipping_warning(self):
        self._clipping_warning_shown = False
        warning = getattr(self, "clipping_warning", None)
        if warning is not None and warning.IsShown():
            warning.Hide()
            self.Layout()

    def _on_announce_level(self, event):
        """
        ينطق مستوى الإدخال الحالي.

        عند الطلب لا تلقائيًا عن قصد: نطق قارئ الشاشة بيخرج من السماعات،
        فإعلان دوري كان هيتسجّل جوه الملف نفسه لو المستخدم مش على هيدفون.
        بالمفتاح، المستخدم بيتحقق وقت ما يحب وبيقدر يوقف الكلام قبل ما
        يكمل تسجيل.
        """
        if not self.announcer:
            return
        if not self.recorder.is_recording:
            self.announcer.announce(self.tr.t("recorder_level_not_recording"))
            return

        rms, peak = self._last_level
        key = "recorder_level_clipping" if peak >= 0.98 else "recorder_level_report"
        self.announcer.announce(
            self.tr.t(key, level=int(round(rms * 100)), peak=int(round(peak * 100)))
        )

    def _on_error(self, message: str):
        wx.CallAfter(self._apply_recording_error, message)

    def _apply_recording_error(self, message: str):
        wx.MessageBox(
            self.tr.t("recorder_error_runtime", error=message),
            self.tr.t("recorder_dialog_title"),
            wx.ICON_ERROR,
        )
        self._perform_stop()

    def _on_ui_timer(self, event):
        elapsed = self.recorder.get_elapsed_seconds()
        self.elapsed_label.SetLabel(_format_elapsed(elapsed))

    def _on_close(self, event):
        if self.recorder.is_recording:
            self.recorder.stop()
        if self._mic_level is not None:
            self._mic_level.close()
            self._mic_level = None
        self.Destroy()