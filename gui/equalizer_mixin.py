# -*- coding: utf-8 -*-
"""
المعادل الصوتي: نافذة الضبط، والتنقّل بين الأنماط من النافذة الرئيسية.

المنطق النقي (الأنماط والحدود) في core/equalizer.py، والتطبيق الفعلي
في PlayerEngine.set_equalizer. هنا الواجهة بس.
"""

import threading

import wx

from core import equalizer
from gui.dialog_helpers import bind_escape_closes, bind_space_like_enter


def equalizer_mode_name(tr, mode):
    return tr.t(f"eq_mode_{mode}")


class EqualizerDialog(wx.Dialog):
    """
    النمط وعشر شرائح للنطاقات وشريحة للتضخيم المسبق.

    التغيير بيتسمع فورًا (on_preview)، والإلغاء بيرجّع اللي كان. الشرائح
    بأرقام صحيحة بالديسيبل: قارئ الشاشة بينطق قيمة الشريحة كرقم، و"4.8"
    مالهاش معنى زيادة عن "5" في الأذن.
    """

    def __init__(self, parent, tr, mode, custom_values, preset_values, on_preview):
        super().__init__(parent, title=tr.t("eq_dialog_title"),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.tr = tr
        self._preset_values = preset_values
        self._on_preview = on_preview
        self._custom_values = custom_values
        self._modes = equalizer.all_modes(has_custom=True)
        # أثناء ما الكود نفسه بيحرّك الشرائح (اختيار نمط)، الحدث ما
        # يقلبش النمط لـ"مخصص"
        self._updating = False

        panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        preset_row = wx.BoxSizer(wx.HORIZONTAL)
        preset_label = wx.StaticText(panel, label=tr.t("eq_preset_label"))
        self.mode_choice = wx.Choice(panel, choices=[equalizer_mode_name(tr, m) for m in self._modes])
        self.mode_choice.SetName(tr.t("eq_preset_label").rstrip(":"))
        preset_row.Add(preset_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT | wx.LEFT, 6)
        preset_row.Add(self.mode_choice, 1, wx.EXPAND)
        sizer.Add(preset_row, 0, wx.EXPAND | wx.ALL, 10)

        grid = wx.FlexGridSizer(cols=3, vgap=4, hgap=8)
        grid.AddGrowableCol(1)
        self.preamp_slider, self._preamp_value = self._add_slider(panel, grid, tr.t("eq_preamp_label"))
        self.band_sliders = []
        self._band_values = []
        for freq in equalizer.BAND_FREQUENCIES:
            name = tr.t("eq_band_label", freq=equalizer.format_frequency(freq))
            slider, value_label = self._add_slider(panel, grid, name)
            self.band_sliders.append(slider)
            self._band_values.append(value_label)
        sizer.Add(grid, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        hint = wx.StaticText(panel, label=tr.t("eq_hint"))
        hint.Wrap(460)
        sizer.Add(hint, 0, wx.ALL, 10)

        buttons = wx.BoxSizer(wx.HORIZONTAL)
        reset_btn = wx.Button(panel, label=tr.t("eq_btn_reset"))
        ok_btn = wx.Button(panel, wx.ID_OK, label=tr.t("btn_ok_activate"))
        ok_btn.SetDefault()
        cancel_btn = wx.Button(panel, wx.ID_CANCEL, label=tr.t("btn_cancel"))
        buttons.Add(reset_btn, 0, wx.RIGHT, 20)
        buttons.Add(ok_btn, 0, wx.RIGHT, 6)
        buttons.Add(cancel_btn)
        sizer.Add(buttons, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        panel.SetSizer(sizer)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(frame_sizer)
        self.SetMinSize((520, self.GetSize().height))
        self.CenterOnParent()

        self.mode_choice.Bind(wx.EVT_CHOICE, self._on_mode_change)
        reset_btn.Bind(wx.EVT_BUTTON, self._on_reset)
        bind_space_like_enter(self)
        bind_escape_closes(self)

        self._select_mode(mode)
        self.mode_choice.SetFocus()

    def _add_slider(self, panel, grid, name):
        label = wx.StaticText(panel, label=name)
        slider = wx.Slider(panel, value=0, minValue=int(equalizer.MIN_GAIN_DB),
                           maxValue=int(equalizer.MAX_GAIN_DB), size=(260, -1))
        slider.SetName(name)
        slider.SetLineSize(1)
        slider.SetPageSize(3)
        value_label = wx.StaticText(panel, label=self.tr.t("eq_db_value", value=0))
        grid.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
        grid.Add(slider, 1, wx.EXPAND)
        grid.Add(value_label, 0, wx.ALIGN_CENTER_VERTICAL)
        slider.Bind(wx.EVT_SLIDER, self._on_slider)
        return slider, value_label

    # ------------------------------------------------------------------ #

    @property
    def mode(self):
        return self._modes[self.mode_choice.GetSelection()]

    def slider_values(self):
        return (float(self.preamp_slider.GetValue()),
                [float(s.GetValue()) for s in self.band_sliders])

    def _values_for(self, mode):
        if mode == equalizer.MODE_CUSTOM:
            return self._custom_values
        if mode == equalizer.MODE_OFF:
            return None
        return self._preset_values(mode)

    def _show_values(self, values):
        preamp, bands = values if values else (0.0, [0.0] * equalizer.BAND_COUNT)
        self._updating = True
        try:
            for slider, label, value in zip([self.preamp_slider] + self.band_sliders,
                                            [self._preamp_value] + self._band_values,
                                            [preamp] + list(bands)):
                slider.SetValue(int(round(value)))
                label.SetLabel(self.tr.t("eq_db_value", value=int(round(value))))
        finally:
            self._updating = False

    def _set_sliders_enabled(self, enabled):
        for slider in [self.preamp_slider] + self.band_sliders:
            slider.Enable(enabled)

    def _select_mode(self, mode):
        if mode not in self._modes:
            mode = equalizer.MODE_OFF
        self.mode_choice.SetSelection(self._modes.index(mode))
        values = self._values_for(mode)
        self._show_values(values)
        # "مطفي" مالوش قيم تتعدّل: الشرائح بتتقفل بدل ما تتحرك من غير أثر
        self._set_sliders_enabled(mode != equalizer.MODE_OFF)
        self._on_preview(values)

    def _on_mode_change(self, event):
        self._select_mode(self.mode)

    def _on_slider(self, event):
        slider = event.GetEventObject()
        index = ([self.preamp_slider] + self.band_sliders).index(slider)
        label = ([self._preamp_value] + self._band_values)[index]
        label.SetLabel(self.tr.t("eq_db_value", value=slider.GetValue()))
        if self._updating:
            return
        # أي تعديل يدوي بيحوّل النمط لـ"مخصص" بالقيم الحالية
        self._custom_values = self.slider_values()
        self.mode_choice.SetSelection(self._modes.index(equalizer.MODE_CUSTOM))
        self._on_preview(self._custom_values)

    def _on_reset(self, event):
        self._select_mode("flat")
        self.mode_choice.SetFocus()

    def custom_values(self):
        """القيم المخصصة لو اتعدّلت في النافذة (للحفظ)."""
        return self._custom_values


class EqualizerMixin:
    """تشغيل المعادل من النافذة الرئيسية. بيفترض self.engine وself.settings وself.tr."""

    def _equalizer_values_for(self, mode):
        if mode == equalizer.MODE_OFF:
            return None
        if mode == equalizer.MODE_CUSTOM:
            return self.settings.get_equalizer_custom()
        return self.engine.get_equalizer_preset_values(equalizer.preset_index(mode))

    def _restore_equalizer(self):
        """
        بيرجّع المعادل المحفوظ عند فتح البرنامج.

        في خيط خلفي: قيم الأنماط الجاهزة من libvlc، وتحميلها أول مرة
        بياخد ثواني - ما ينفعش يأخّر ظهور النافذة (شوف PlayerEngine.warm_up).
        """
        mode = self.settings.get_equalizer_mode()
        if mode == equalizer.MODE_OFF:
            return

        def worker():
            values = self._equalizer_values_for(mode)
            if values is not None:
                self.engine.set_equalizer(*values)
        threading.Thread(target=worker, daemon=True).start()

    def _apply_equalizer_mode(self, mode, announce=True):
        values = self._equalizer_values_for(mode)
        if values is None:
            self.engine.set_equalizer(None)
            if mode != equalizer.MODE_OFF:
                # VLC مش متاحة: ما نحفظش نمط مش متطبّق فعلًا
                mode = equalizer.MODE_OFF
        else:
            self.engine.set_equalizer(*values)
        self.settings.set_equalizer_mode(mode)
        if announce:
            self._announce(self.tr.t("announce_equalizer_mode", name=equalizer_mode_name(self.tr, mode)),
                           "announce_equalizer")

    def _cycle_equalizer(self, step):
        mode = equalizer.cycle_mode(self.settings.get_equalizer_mode(), step,
                                    has_custom=self.settings.has_equalizer_custom())
        self._apply_equalizer_mode(mode)

    def _on_equalizer(self, event):
        original_mode = self.settings.get_equalizer_mode()

        def preview(values):
            if values is None:
                self.engine.set_equalizer(None)
            else:
                self.engine.set_equalizer(*values)

        def preset_values(mode):
            return self.engine.get_equalizer_preset_values(equalizer.preset_index(mode))

        with EqualizerDialog(self, self.tr, original_mode, self.settings.get_equalizer_custom(),
                             preset_values, preview) as dialog:
            if dialog.ShowModal() == wx.ID_OK:
                if dialog.mode == equalizer.MODE_CUSTOM:
                    self.settings.set_equalizer_custom(*dialog.custom_values())
                self._apply_equalizer_mode(dialog.mode)
            else:
                self._apply_equalizer_mode(original_mode, announce=False)
