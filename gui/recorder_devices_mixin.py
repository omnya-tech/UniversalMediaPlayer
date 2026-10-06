# -*- coding: utf-8 -*-
"""
نافذة المسجّل: قائمة الأجهزة وقدراتها، ومستوى المايكروفون في ويندوز، والجهاز
الثاني للدمج، واختيارات الجودة والتحسين والصيغة وما يُحفظ منها لكل جهاز.

نُقلت كما هي من gui/audio_recorder_dialog.py.
"""

import os

import wx

from core.audio_recorder import SUPPORTED_BIT_DEPTHS, get_default_input_device
from core.audio_devices import group_devices, recommended_profile, supported_rates, looks_like_system_audio
from core.mic_level import MicLevel
from core.voice_enhance import DEFAULT_ENHANCE_LEVEL, ENHANCE_LEVELS
from gui.audio_bitrate_widget import current_audio_bitrate_bps, refresh_audio_bitrate_choice
from core.logging_setup import configure_logging

_logger = configure_logging()


class RecorderDevicesMixin:
    """الأجهزة وإعدادات التسجيل في نافذة المسجّل."""

    def _on_toggle_dual_input(self, event):
        is_enabled = self.chk_dual_input.IsChecked()
        self.secondary_device_choice.Enable(is_enabled)
        self.lbl_dev_sec.Enable(is_enabled)
        if not is_enabled:
            return

        # التركيز بينتقل لقائمة الجهاز الثاني ويتقال عدد الخيارات: المستخدم
        # الكفيف ما كانش بيعرف إن فيه قائمة اتفعّلت أصلًا، ولا إن فيها
        # اختيار تلقائي.
        # (الاختيار التلقائي: صوت النظام لو موجود)
        self._prefer_system_audio_as_secondary()
        self.secondary_device_choice.SetFocus()
        if self.announcer:
            count = self.secondary_device_choice.GetCount()
            chosen = self.secondary_device_choice.GetStringSelection()
            try:
                self.announcer.announce(
                    self.tr.t("recorder_dual_ready", count=count, device=chosen)
                )
            except Exception:
                pass

    def _prefer_system_audio_as_secondary(self):
        """
        يختار مصدر صوت النظام لو موجود.

        أشهر استعمال للدمج هو صوتك مع صوت البرنامج، فالستيريو ميكس هو
        المقصود في الغالب. الافتراضي القديم كان "تاني جهاز في القائمة"
        وده اختيار عشوائي - ممكن يطلع مايك تاني.
        """
        devices = getattr(self, "_audio_devices", None)
        if not devices:
            return

        primary = self.device_choice.GetSelection()
        for position, device in enumerate(devices):
            if position == primary:
                continue
            if looks_like_system_audio(device.name):
                self.secondary_device_choice.SetSelection(position)
                return

        # بلا صوت نظام: أي جهاز غير الأساسي
        for position in range(len(devices)):
            if position != primary:
                self.secondary_device_choice.SetSelection(position)
                return

    def _populate_devices(self):
        """
        قائمة بالأجهزة الحقيقية لا بمداخل النظام.

        ويندوز بيعرض نفس المايك أربع مرات (مرة لكل واجهة صوت)، فالقائمة
        كانت بتوصل لعشرين مدخل لأربع أجهزة. group_devices بتلمّهم وتختار
        أفضل واجهة لكل جهاز.
        """
        try:
            self._audio_devices = group_devices()
        except Exception as exc:
            _logger.exception("تعذّر مسح أجهزة الإدخال")
            wx.MessageBox(str(exc), self.tr.t("recorder_dialog_title"), wx.ICON_WARNING)
            self._audio_devices = []

        devices = [(d.index, d.name) for d in self._audio_devices]
        self._devices = devices
        default_device = get_default_input_device()
        saved_device_name = self.settings.get_recorder_default_device_name() if self.settings is not None else ""
        default_selection = 0
        names = [d.name for d in self._audio_devices]
        self.device_choice.Set(names)
        self.secondary_device_choice.Set(names)
        for position, device in enumerate(self._audio_devices):
            if saved_device_name:
                if device.name == saved_device_name:
                    default_selection = position
            elif device.index == default_device:
                default_selection = position

        if devices:
            self.device_choice.SetSelection(default_selection)
            sec_sel = 1 if len(devices) > 1 else 0
            self.secondary_device_choice.SetSelection(sec_sel)

    def _on_capabilities_changed(self, event):
        self._refresh_capabilities()
        self._refresh_mic_level()

    def _refresh_mic_level(self):
        """يربط الشريط بمستوى الجهاز المختار في ويندوز، أو يعطّله لو مش متاح."""
        if self._mic_level is not None:
            self._mic_level.close()
            self._mic_level = None
        selection = self.device_choice.GetSelection()
        devices = getattr(self, "_audio_devices", None) or []
        if 0 <= selection < len(devices):
            try:
                self._mic_level = MicLevel.open(devices[selection].name)
            except Exception:
                _logger.exception("تعذّر فتح مستوى المايكروفون في ويندوز")

        level = self._mic_level.get() if self._mic_level is not None else None
        available = level is not None
        for control in (self.mic_level_label, self.mic_level_slider, self.mic_level_value):
            control.Enable(available)
        if available:
            self._show_mic_level(level)
            note = "" if self._mic_level.hardware else self.tr.t("recorder_mic_level_software")
        else:
            self.mic_level_value.SetLabel("")
            note = self.tr.t("recorder_mic_level_unavailable") if devices else ""
        self.mic_level_note.SetLabel(note)
        self.mic_level_note.Wrap(500)
        self.mic_level_note.Show(bool(note))
        self.Layout()

    def _show_mic_level(self, level):
        self.mic_level_slider.SetValue(level)
        self.mic_level_value.SetLabel(self.tr.t("recorder_mic_level_value", level=level))

    def _on_mic_level_change(self, event):
        level = self.mic_level_slider.GetValue()
        if self._mic_level is None or not self._mic_level.set(level):
            # الجهاز اتفصل: الشريط يرجع يعكس الحقيقة
            self._refresh_mic_level()
            return
        self.mic_level_value.SetLabel(self.tr.t("recorder_mic_level_value", level=level))

    def _on_activate(self, event):
        if event.GetActive() and self._mic_level is not None:
            level = self._mic_level.get()
            if level is None:
                self._refresh_mic_level()
            elif level != self.mic_level_slider.GetValue():
                self._show_mic_level(level)
        event.Skip()

    def _on_device_setting_changed(self, event):
        self._remember_device_profile()
        event.Skip()

    def _apply_channel_limit(self):
        """الستيريو متاح فقط لجهاز له قناتان أو أكثر."""
        devices = getattr(self, "_audio_devices", None) or []
        selection = self.device_choice.GetSelection()
        if 0 <= selection < len(devices):
            self.channels_choice.Enable(devices[selection].max_channels >= 2)

    def _refresh_capabilities(self):
        """
        يضبط الإعدادات على ما يناسب الجهاز المختار.

        الترتيب: تفضيلات المستخدم المحفوظة لهذا الجهاز بالذات أولًا، وإلا
        الإعداد المقترَح من قدرات الجهاز نفسه. كل جهاز له ذاكرته: مايك
        192 كيلوهرتز وسمّاعة بلوتوث 16 ما بيتشاركوش نفس الإعداد.
        """
        if not getattr(self, "_audio_devices", None):
            self.channels_choice.Clear()
            self.rate_choice.Clear()
            return

        selection = max(0, self.device_choice.GetSelection())
        if selection >= len(self._audio_devices):
            selection = 0
        device = self._audio_devices[selection]

        working_rates = supported_rates(device.index, 1, device.native_rate)
        if not working_rates:
            working_rates = supported_rates(device.index, 2, device.native_rate)
        if not working_rates:
            working_rates = (device.native_rate,) if device.native_rate else (44100,)

        profile = None
        if self.settings is not None:
            profile = self.settings.get_device_profile(device.name)
        if not profile:
            profile = recommended_profile(device, working_rates)

        max_channels = max(1, device.max_channels)
        self.channels_choice.Set([
            self.tr.t("recorder_channels_mono"),
            self.tr.t("recorder_channels_stereo"),
        ])
        self.channels_choice.Enable(max_channels >= 2)
        wanted_channels = min(int(profile.get("channels", 1)), max_channels)
        self.channels_choice.SetSelection(1 if wanted_channels == 2 else 0)

        # «48000 هرتز» لا «Hz 48000»: الوحدة اللاتينية كانت تنقلب أمام الرقم في
        # الواجهة العربية، وقارئ الشاشة ينطقها حرفين. الرقم أولًا فيُقرأ بـsplit
        self.rate_choice.Set([self.tr.t("sample_rate_value", rate=rate) for rate in working_rates])
        wanted_rate = int(profile.get("sample_rate", working_rates[0]))
        self.rate_choice.SetSelection(
            working_rates.index(wanted_rate) if wanted_rate in working_rates else 0
        )

        # عمق البت بيتضبط هنا كمان لو القائمة موجودة: الدالة دي بتتنادى
        # مرة أثناء بناء الواجهة قبل ما قائمة العمق تتعمل.
        # (والتغيير اليدوي بعد كده بيتحفظ للجهاز)
        # شوف _remember_device_profile.
        if hasattr(self, "bit_depth_choice"):
            self._select_bit_depth(int(profile.get("bit_depth", 16)))

        self._update_rate_headroom_note(working_rates)
        self._announce_device_profile(device, working_rates)

    def _update_rate_headroom_note(self, working_rates):
        """
        يبيّن إن الجهاز يقدر على أعلى من المختار.

        من غير السطر ده، صاحب مايك 192 كيلوهرتز يشوف 48 مختارة فيفتكر إن
        البرنامج مش شايف جهازه - والحقيقة إننا سقّفناه عن قصد.
        """
        note = getattr(self, "rate_headroom_note", None)
        if note is None:
            return
        # (الملاحظة بتتعمل في _build_ui بعد أول نداء للدالة دي)
        try:
            selected = int(self.rate_choice.GetStringSelection().split()[0])
        except (ValueError, IndexError, AttributeError):
            note.Hide()
            return

        ceiling = max(working_rates) if working_rates else selected
        if ceiling > selected:
            note.SetLabel(self.tr.t("recorder_rate_headroom_note", rate=ceiling))
            note.Wrap(520)
            note.Show()
        else:
            note.Hide()

    def _announce_device_profile(self, device, rates):
        """
        ينطق للمستخدم إيه اللي اتضبط له تلقائيًا.

        المستخدم الكفيف مش هيلاحظ إن القوائم اتغيّرت لوحدها، فلازم
        يتقال له - وإلا يفتكر إن إعداده القديم لسه شغّال.
        """
        if not getattr(self, "_devices_announced", None):
            self._devices_announced = set()
        if device.name in self._devices_announced:
            return
        self._devices_announced.add(device.name)

        rate = self.rate_choice.GetStringSelection() or ""
        channels = self.channels_choice.GetStringSelection() or ""
        message = self.tr.t(
            "recorder_device_configured",
            device=device.name, rate=rate, channels=channels,
        )
        try:
            self.announcer.announce(message)
        except Exception:
            pass

    def _remember_device_profile(self):
        """يحفظ اختيار المستخدم لهذا الجهاز بالذات."""
        if self.settings is None or not getattr(self, "_audio_devices", None):
            return
        selection = self.device_choice.GetSelection()
        if selection < 0 or selection >= len(self._audio_devices):
            return
        device = self._audio_devices[selection]

        try:
            rate = int(self.rate_choice.GetStringSelection().split()[0])
        except (ValueError, IndexError, AttributeError):
            return

        self.settings.set_device_profile(device.name, {
            "sample_rate": rate,
            "channels": 1 if self.channels_choice.GetSelection() == 0 else 2,
            "bit_depth": self._selected_bit_depth(),
        })

    def _select_bit_depth(self, depth):
        self.bit_depth_choice.SetSelection(
            SUPPORTED_BIT_DEPTHS.index(depth) if depth in SUPPORTED_BIT_DEPTHS else 0)

    def _selected_bit_depth(self):
        index = self.bit_depth_choice.GetSelection()
        return SUPPORTED_BIT_DEPTHS[index] if index != wx.NOT_FOUND else 16

    def _selected_enhance_level(self):
        index = self.enhance_choice.GetSelection()
        return ENHANCE_LEVELS[index] if index != wx.NOT_FOUND else DEFAULT_ENHANCE_LEVEL

    def _on_enhance_change(self, event):
        if self.settings is not None:
            self.settings.set_recorder_enhance_level(self._selected_enhance_level())

    def _on_exclusive_change(self, event):
        if self.settings is not None:
            self.settings.set_recorder_exclusive(self.exclusive_check.GetValue())

    def _on_format_change(self, event):
        target_ext = self.format_choice.GetStringSelection() or ".wav"
        if self._output_path_is_default:
            base, _old_ext = os.path.splitext(self._output_path)
            self._output_path = base + target_ext
            self.output_path_label.SetLabel(self._output_path)
            self.output_path_label.SetToolTip(self._output_path)

        fallback_bps = (
            self.settings.get_recorder_default_audio_bitrate() if self.settings is not None else 0
        )
        preferred_bps = current_audio_bitrate_bps(self.bitrate_choice, fallback_bps)
        refresh_audio_bitrate_choice(
            self.bitrate_choice, self.bitrate_lossless_note, self.tr, target_ext, False, preferred_bps
        )
        self.Layout()

    def _get_audio_bitrate(self) -> int:
        if not self.bitrate_choice.IsShown():
            return 0
        fallback_bps = (
            self.settings.get_recorder_default_audio_bitrate() if self.settings is not None else 0
        )
        return current_audio_bitrate_bps(self.bitrate_choice, fallback_bps)
