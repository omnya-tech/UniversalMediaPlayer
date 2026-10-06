# -*- coding: utf-8 -*-
"""
تبويبات المحول والمسجّل ومحرر الوسائط في نافذة الخيارات: بناؤها وحفظها.

تُبنى عند فتح التبويب أول مرة (شوف OptionsDialog._ensure_tab_built).
نُقلت كما هي من gui/dialogs.py.
"""

import logging

import wx

from core.formats import AUDIO_FORMATS, VIDEO_FORMATS
from core.audio_devices import group_devices
from core.audio_recorder import SUPPORTED_SAMPLE_RATES
from gui.audio_bitrate_widget import current_audio_bitrate_bps, refresh_audio_bitrate_choice
from core.audio_recorder import SUPPORTED_BIT_DEPTHS
from core.voice_enhance import ENHANCE_LEVELS
from gui.value_choice import VIDEO_BITRATES_KBPS, ValueChoice
from gui.editor_hotkeys import (
    ACTIONS as EDITOR_HOTKEY_ACTIONS,
    DEFAULT_HOTKEYS as EDITOR_DEFAULT_HOTKEYS,
    KEY_CHOICES as EDITOR_KEY_CHOICES,
    MODIFIER_CHOICES as EDITOR_MODIFIER_CHOICES,
    current_hotkeys,
)
from gui.options_helpers import _safe_get_setting, _safe_set_setting, _add_group_box, _add_hint, _EDITOR_PROGRESS_STEPS

logger = logging.getLogger(__name__)


class OptionsTabsMixin:
    """تبويبات المحول والمسجّل ومحرر الوسائط."""

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
        # معدلات بت الصيغة المختارة نفسها، وأولها «أعلى جودة متاحة»، كما
        # في نافذة المحوّل والمسجّل (gui/audio_bitrate_widget.py). كانت
        # قائمة واحدة لكل الصيغ فيها أرقام لا تقبلها الصيغة
        converter_audio_bitrate_label = wx.StaticText(panel, label=tr.t("converter_custom_audio_bitrate_label"))
        self.converter_audio_bitrate_choice = wx.Choice(panel)
        self.converter_audio_bitrate_choice.SetName(tr.t("converter_custom_audio_bitrate_label"))
        self.converter_audio_bitrate_note = wx.StaticText(
            panel, label=tr.t("converter_audio_bitrate_not_applicable"))
        converter_video_bitrate_label = wx.StaticText(panel, label=tr.t("converter_custom_video_bitrate_label"))
        self.converter_video_bitrate_spin = ValueChoice(panel, VIDEO_BITRATES_KBPS, initial=4000)
        self.converter_video_bitrate_spin.SetName(tr.t("converter_custom_video_bitrate_label"))
        bitrate_row.Add(converter_audio_bitrate_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        bitrate_row.Add(self.converter_audio_bitrate_choice, flag=wx.RIGHT, border=8)
        bitrate_row.Add(self.converter_audio_bitrate_note, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=16)
        bitrate_row.Add(converter_video_bitrate_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        bitrate_row.Add(self.converter_video_bitrate_spin)
        converter_box.Add(bitrate_row, flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, border=8)

        self._refresh_converter_format_choices()
        saved_format = _safe_get_setting(settings, "converter_default_format", ".mp4")
        format_index = self.converter_format_choice.FindString(saved_format)
        if format_index != wx.NOT_FOUND:
            self.converter_format_choice.SetSelection(format_index)
        saved_audio_kbps = _safe_get_setting(settings, "converter_default_audio_bitrate", 0)
        self._refresh_converter_audio_bitrates(int(saved_audio_kbps or 0) * 1000)
        self.Bind(wx.EVT_CHOICE, lambda event: self._refresh_converter_audio_bitrates(),
                  self.converter_format_choice)
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
        self.recorder_rate_choice = wx.Choice(panel, choices=[tr.t("sample_rate_value", rate=rate) for rate in SUPPORTED_SAMPLE_RATES])
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
            panel, choices=[tr.t(f"recorder_bit_depth_{depth}") for depth in SUPPORTED_BIT_DEPTHS]
        )
        self.recorder_bit_depth_choice.SetName(tr.t("recorder_bit_depth_label"))
        saved_bd = _safe_get_setting(settings, "recorder_default_bit_depth", 16)
        self.recorder_bit_depth_choice.SetSelection(
            SUPPORTED_BIT_DEPTHS.index(saved_bd) if saved_bd in SUPPORTED_BIT_DEPTHS else 0)
        recorder_row1b.Add(bit_depth_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        recorder_row1b.Add(self.recorder_bit_depth_choice)
        recorder_box.Add(recorder_row1b, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=8)

        enhance_row = wx.BoxSizer(wx.HORIZONTAL)
        enhance_label = wx.StaticText(panel, label=tr.t("recorder_enhance_label"))
        self.recorder_enhance_choice = wx.Choice(
            panel, choices=[tr.t(f"recorder_enhance_{level}") for level in ENHANCE_LEVELS])
        self.recorder_enhance_choice.SetName(tr.t("recorder_enhance_label"))
        self.recorder_enhance_choice.SetSelection(ENHANCE_LEVELS.index(settings.get_recorder_enhance_level()))
        enhance_row.Add(enhance_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=6)
        enhance_row.Add(self.recorder_enhance_choice)
        recorder_box.Add(enhance_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=8)

        self.recorder_exclusive_check = wx.CheckBox(panel, label=tr.t("recorder_exclusive_label"))
        self.recorder_exclusive_check.SetValue(settings.get_recorder_exclusive())
        recorder_box.Add(self.recorder_exclusive_check, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=8)

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

    def _build_editor_tab(self, panel):
        tr, settings = self.tr, self.settings
        sizer = wx.BoxSizer(wx.VERTICAL)

        general_box = _add_group_box(panel, sizer, tr.t("options_editor_general_section"))
        mode_row = wx.BoxSizer(wx.HORIZONTAL)
        mode_label = wx.StaticText(panel, label=tr.t("editor_video_mode_label"))
        self.editor_video_mode_choice = wx.Choice(
            panel, choices=[tr.t("editor_video_mode_fast"), tr.t("editor_video_mode_precise")])
        self.editor_video_mode_choice.SetName(tr.t("editor_video_mode_label"))
        self.editor_video_mode_choice.SetSelection(1 if settings.get_editor_video_precise() else 0)
        mode_row.Add(mode_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        mode_row.Add(self.editor_video_mode_choice, flag=wx.ALIGN_CENTER_VERTICAL)
        general_box.Add(mode_row, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=8)

        progress_row = wx.BoxSizer(wx.HORIZONTAL)
        progress_label = wx.StaticText(panel, label=tr.t("options_editor_progress_label"))
        self.editor_progress_choice = wx.Choice(panel, choices=[
            tr.t("options_editor_progress_every", percent=step) if step else tr.t("options_editor_progress_off")
            for step in _EDITOR_PROGRESS_STEPS])
        self.editor_progress_choice.SetName(tr.t("options_editor_progress_label"))
        current_step = settings.get_editor_progress_step()
        self.editor_progress_choice.SetSelection(
            _EDITOR_PROGRESS_STEPS.index(current_step) if current_step in _EDITOR_PROGRESS_STEPS else 1)
        progress_row.Add(progress_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=8)
        progress_row.Add(self.editor_progress_choice, flag=wx.ALIGN_CENTER_VERTICAL)
        general_box.Add(progress_row, flag=wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM, border=8)

        hotkeys_box = _add_group_box(panel, sizer, tr.t("options_editor_hotkeys_section"))
        self.editor_hotkeys_checkbox = wx.CheckBox(panel, label=tr.t("options_editor_hotkeys_enable"))
        self.editor_hotkeys_checkbox.SetValue(settings.get_enable_editor_hotkeys())
        hotkeys_box.Add(self.editor_hotkeys_checkbox, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=8)
        _add_hint(panel, hotkeys_box, tr.t("options_editor_hotkeys_hint"))

        # لكل اختصار: وصفه، ثم قائمة المفاتيح المساعدة، ثم قائمة المفتاح.
        # قائمتان بدل «اضغط الاختصار»: قارئ الشاشة يعترض بعض الضغطات قبل
        # أن تصل للنافذة، والقائمة تُقرأ وتُختار بالأسهم أو بالماوس
        self._editor_modifier_names = [name for name, _code, _label in EDITOR_MODIFIER_CHOICES]
        self._editor_key_names = [name for name, _code in EDITOR_KEY_CHOICES]
        self.editor_hotkey_choices = {}
        mapping = current_hotkeys(settings)
        grid = wx.FlexGridSizer(cols=3, vgap=6, hgap=8)
        for action in EDITOR_HOTKEY_ACTIONS:
            action_text = tr.t(f"ghost_action_{action}")
            label = wx.StaticText(panel, label=action_text)
            modifiers_choice = wx.Choice(
                panel, choices=[label_text for _n, _c, label_text in EDITOR_MODIFIER_CHOICES])
            modifiers_choice.SetName(tr.t("options_editor_modifiers_name", action=action_text))
            key_choice = wx.Choice(panel, choices=self._editor_key_names)
            key_choice.SetName(tr.t("options_editor_key_name", action=action_text))
            grid.Add(label, flag=wx.ALIGN_CENTER_VERTICAL)
            grid.Add(modifiers_choice)
            grid.Add(key_choice)
            self.editor_hotkey_choices[action] = (modifiers_choice, key_choice)
        self._set_editor_hotkey_choices(mapping)
        hotkeys_box.Add(grid, flag=wx.ALL, border=8)

        reset_button = wx.Button(panel, label=tr.t("options_editor_hotkeys_reset"))
        reset_button.Bind(wx.EVT_BUTTON, self._on_reset_editor_hotkeys)
        hotkeys_box.Add(reset_button, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=8)

        sizer.AddSpacer(10)
        panel.SetSizer(sizer)

    def _set_editor_hotkey_choices(self, mapping):
        for action, (modifiers_choice, key_choice) in self.editor_hotkey_choices.items():
            modifiers, key = mapping[action]
            modifiers_choice.SetSelection(self._editor_modifier_names.index(modifiers))
            key_choice.SetSelection(self._editor_key_names.index(key))

    def _editor_hotkey_mapping(self):
        return {
            action: (self._editor_modifier_names[m.GetSelection()], self._editor_key_names[k.GetSelection()])
            for action, (m, k) in self.editor_hotkey_choices.items()
        }

    def _on_reset_editor_hotkeys(self, event):
        self._set_editor_hotkey_choices(dict(EDITOR_DEFAULT_HOTKEYS))
        wx.MessageBox(self.tr.t("options_editor_hotkeys_reset_done"), self.tr.t("options_dialog_title"),
                      wx.ICON_INFORMATION, self)

    def _save_editor_tab(self):
        _safe_set_setting(self.settings, "editor_video_precise",
                          self.editor_video_mode_choice.GetSelection() == 1)
        _safe_set_setting(self.settings, "editor_progress_step",
                          _EDITOR_PROGRESS_STEPS[self.editor_progress_choice.GetSelection()])
        _safe_set_setting(self.settings, "enable_editor_hotkeys", self.editor_hotkeys_checkbox.GetValue())
        self.settings.set_editor_hotkeys(self._editor_hotkey_mapping())

    def _save_converter_tab(self):
        """بتتنادى بس لو التبويب اتفتح واتبنى."""
        # تبويب ما اتفتحش: خياراته ما اتعدّلتش، فالمحفوظ يفضل زي ما هو
        _safe_set_setting(self.settings, "converter_default_is_video", self.converter_type_radio.GetSelection() == 1)
        _safe_set_setting(self.settings, "converter_default_format", self.converter_format_choice.GetStringSelection())
        # الصيغة بلا معدل بت (wav وflac): المحفوظ يبقى كما هو
        if self.converter_audio_bitrate_choice.IsShown():
            saved_kbps = _safe_get_setting(self.settings, "converter_default_audio_bitrate", 0)
            bps = current_audio_bitrate_bps(self.converter_audio_bitrate_choice, int(saved_kbps or 0) * 1000)
            _safe_set_setting(self.settings, "converter_default_audio_bitrate", int(bps or 0) // 1000)
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
            SUPPORTED_BIT_DEPTHS[max(0, self.recorder_bit_depth_choice.GetSelection())]
        )
        _safe_set_setting(self.settings, "recorder_default_format", self.recorder_format_choice.GetStringSelection())
        if self.recorder_bitrate_choice.IsShown():
            fallback_bitrate = _safe_get_setting(self.settings, "recorder_default_audio_bitrate", 0)
            _safe_set_setting(
                self.settings,
                "recorder_default_audio_bitrate",
                current_audio_bitrate_bps(self.recorder_bitrate_choice, fallback_bitrate)
            )

    def _save_recorder_quality(self):
        self.settings.set_recorder_enhance_level(ENHANCE_LEVELS[self.recorder_enhance_choice.GetSelection()])
        self.settings.set_recorder_exclusive(self.recorder_exclusive_check.GetValue())

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
        self._refresh_converter_audio_bitrates()

    def _refresh_converter_audio_bitrates(self, preferred_bps=None):
        """قائمة معدلات البت لصيغة المحوّل الافتراضية المختارة الآن."""
        if preferred_bps is None:
            saved_kbps = _safe_get_setting(self.settings, "converter_default_audio_bitrate", 0)
            preferred_bps = current_audio_bitrate_bps(self.converter_audio_bitrate_choice,
                                                      int(saved_kbps or 0) * 1000)
        refresh_audio_bitrate_choice(
            self.converter_audio_bitrate_choice, self.converter_audio_bitrate_note, self.tr,
            self.converter_format_choice.GetStringSelection(),
            self.converter_type_radio.GetSelection() == 1, preferred_bps)
        self._converter_panel.Layout()

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
