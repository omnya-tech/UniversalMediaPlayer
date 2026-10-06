# -*- coding: utf-8 -*-
"""
اختبارات نافذة مسجّل الصوت بأجهزة ومستوى مايكروفون وهميين: قائمة الأجهزة
وقدراتها، وما يُحفظ لكل جهاز، والصيغة ومعدل البت، وشريط المستوى، والدمج،
والتسجيل والإيقاف، والتنبيهات.
"""

import os
import wave

import numpy as np
import pytest

wx = pytest.importorskip("wx")

from core.audio_devices import AudioDevice
from core.settings import Settings
from i18n.strings import Translator
from tests.gui_support import FakeAnnouncer

USB = AudioDevice("Microphone (USB)", 3, "Windows WASAPI", 192000, 1, 3.0)
LAPTOP = AudioDevice("Microphone Array (Laptop)", 4, "Windows WASAPI", 48000, 2, 3.0)
MIX = AudioDevice("Stereo Mix (Realtek)", 5, "Windows WASAPI", 48000, 2, 3.0)
RATES = {3: (192000, 96000, 48000, 44100), 4: (48000, 44100), 5: (48000, 44100)}


class FakeMicLevel:
    """مستوى مايكروفون وهمي: جهاز USB بمستوى في الجهاز، والمصفوفة بمستوى برمجي."""
    levels = {"Microphone (USB)": [80, True], "Microphone Array (Laptop)": [50, False]}

    def __init__(self, name):
        self.name = name
        self.hardware = self.levels[name][1]

    @classmethod
    def open(cls, name):
        return cls(name) if name in cls.levels else None

    def get(self):
        return self.levels[self.name][0]

    def set(self, percent):
        self.levels[self.name][0] = percent
        return True

    def close(self):
        pass


class FakeRecorder:
    """بديل AudioRecorder: يكتب ملف WAV قصيرًا ويعيد ما طُلب منه."""

    def __init__(self):
        self.is_recording = False
        self.is_paused = False
        self.exclusive_requested = False
        self.used_exclusive = False
        self.last_recording_had_no_audio = False
        self.had_clipping = False
        self.clip_events = 0
        self.started_with = None

    def start(self, device_index, sample_rate, channels, path, **kwargs):
        self.started_with = dict(device=device_index, rate=sample_rate, channels=channels, **kwargs)
        self.exclusive_requested = kwargs.get("exclusive", False)
        self.path = path
        self.is_recording = True

    def stop(self):
        with wave.open(self.path, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(48000)
            handle.writeframes(np.zeros(4800, dtype="<i2").tobytes())
        self.is_recording = False
        return self.path, 65.0

    def get_elapsed_seconds(self):
        return 0.0


@pytest.fixture
def open_recorder(wx_app, app_data, tmp_path, monkeypatch):
    import gui.audio_recorder_dialog as dialog_module
    import gui.recorder_devices_mixin as devices_module

    monkeypatch.setattr(devices_module, "group_devices", lambda: [LAPTOP, MIX, USB])
    monkeypatch.setattr(devices_module, "supported_rates", lambda index, channels, native=None: RATES[index])
    monkeypatch.setattr(devices_module, "get_default_input_device", lambda: USB.index)
    monkeypatch.setattr(devices_module, "MicLevel", FakeMicLevel)
    monkeypatch.setattr(dialog_module, "play_completion_chime", lambda: None)
    monkeypatch.setattr(dialog_module, "play_error_chime", lambda: None)
    boxes = []
    monkeypatch.setattr(wx, "MessageBox", lambda *args, **kwargs: boxes.append(args[0]))
    FakeMicLevel.levels = {"Microphone (USB)": [80, True], "Microphone Array (Laptop)": [50, False]}
    dialogs = []

    def open_(lang="ar", settings=None):
        settings = settings or Settings()
        dialog = dialog_module.AudioRecorderDialog(None, Translator(lang), FakeAnnouncer(), settings)
        dialog.recorder = FakeRecorder()
        dialog._output_path = str(tmp_path / f"recording{len(dialogs)}.wav")
        dialog.boxes = boxes
        dialogs.append(dialog)
        return dialog

    yield open_
    for dialog in dialogs:
        dialog._ui_timer.Stop()
        dialog.Destroy()


def _select_device(dialog, device):
    dialog.device_choice.SetStringSelection(device.name)
    dialog._on_capabilities_changed(None)


def test_devices_are_listed_and_the_default_is_selected(open_recorder):
    dialog = open_recorder()
    assert dialog.device_choice.GetStrings() == [LAPTOP.name, MIX.name, USB.name]
    assert dialog.device_choice.GetStringSelection() == USB.name


@pytest.mark.parametrize("lang, unit", [("ar", "هرتز"), ("en", "Hz")])
def test_rates_follow_the_device_and_read_number_first(open_recorder, lang, unit):
    dialog = open_recorder(lang)
    _select_device(dialog, USB)
    assert dialog.rate_choice.GetStrings() == [f"{rate} {unit}" for rate in RATES[USB.index]]
    _select_device(dialog, LAPTOP)
    assert [int(label.split()[0]) for label in dialog.rate_choice.GetStrings()] == list(RATES[LAPTOP.index])


def test_mono_device_disables_the_stereo_choice(open_recorder):
    dialog = open_recorder()
    _select_device(dialog, USB)
    assert not dialog.channels_choice.IsEnabled()
    assert dialog.channels_choice.GetSelection() == 0
    _select_device(dialog, LAPTOP)
    assert dialog.channels_choice.IsEnabled()


def test_each_device_keeps_its_own_settings(open_recorder):
    dialog = open_recorder()
    _select_device(dialog, USB)
    dialog.rate_choice.SetSelection(1)                      # 96000
    dialog._select_bit_depth(24)
    dialog._on_device_setting_changed(wx.CommandEvent())
    _select_device(dialog, LAPTOP)
    dialog.rate_choice.SetSelection(1)                      # 44100
    dialog._on_device_setting_changed(wx.CommandEvent())

    _select_device(dialog, USB)
    assert dialog.rate_choice.GetStringSelection().split()[0] == "96000"
    assert dialog._selected_bit_depth() == 24
    _select_device(dialog, LAPTOP)
    assert dialog.rate_choice.GetStringSelection().split()[0] == "44100"


def test_lossless_format_hides_the_bitrate(open_recorder):
    dialog = open_recorder()
    dialog.format_choice.SetStringSelection(".mp3")
    dialog._on_format_change(None)
    assert dialog.bitrate_choice.IsEnabled() and dialog.bitrate_choice.GetCount() > 0
    assert dialog._output_path.endswith(".mp3")
    dialog.format_choice.SetStringSelection(".wav")
    dialog._on_format_change(None)
    assert not dialog.bitrate_choice.IsEnabled() or not dialog.bitrate_choice.IsShown()
    assert dialog._output_path.endswith(".wav")


def test_mic_level_slider_follows_the_selected_device(open_recorder):
    dialog = open_recorder()
    tr = dialog.tr
    _select_device(dialog, USB)
    assert dialog.mic_level_slider.IsEnabled()
    assert dialog.mic_level_slider.GetValue() == 80
    assert not dialog.mic_level_note.IsShown()

    dialog.mic_level_slider.SetValue(65)
    dialog._on_mic_level_change(None)
    assert FakeMicLevel.levels[USB.name][0] == 65
    assert dialog.mic_level_value.GetLabel() == tr.t("recorder_mic_level_value", level=65)

    _select_device(dialog, LAPTOP)                          # مستوى برمجي فقط
    assert dialog.mic_level_slider.GetValue() == 50
    assert dialog.mic_level_note.GetLabel() == tr.t("recorder_mic_level_software")

    _select_device(dialog, MIX)                             # لا يسمح ويندوز بمستواه
    assert not dialog.mic_level_slider.IsEnabled()
    assert dialog.mic_level_note.GetLabel() == tr.t("recorder_mic_level_unavailable")


def test_level_changed_in_windows_shows_when_the_window_is_activated(open_recorder):
    dialog = open_recorder()
    _select_device(dialog, USB)
    FakeMicLevel.levels[USB.name][0] = 40
    event = wx.ActivateEvent(wx.wxEVT_ACTIVATE, True)
    dialog._on_activate(event)
    assert dialog.mic_level_slider.GetValue() == 40


def test_dual_input_picks_system_audio_and_says_so(open_recorder):
    dialog = open_recorder()
    dialog.chk_dual_input.SetValue(True)
    dialog._on_toggle_dual_input(None)
    assert dialog.secondary_device_choice.IsEnabled()
    assert dialog.secondary_device_choice.GetStringSelection() == MIX.name
    assert dialog.announcer.last() == dialog.tr.t(
        "recorder_dual_ready", count=3, device=MIX.name)


def test_exclusive_and_enhancement_choices_are_saved_at_once(open_recorder):
    dialog = open_recorder()
    dialog.exclusive_check.SetValue(False)
    dialog._on_exclusive_change(None)
    dialog.enhance_choice.SetSelection(2)
    dialog._on_enhance_change(None)
    assert dialog.settings.get_recorder_exclusive() is False
    assert dialog.settings.get_recorder_enhance_level() == "denoise"


def test_record_and_stop(open_recorder):
    dialog = open_recorder()
    _select_device(dialog, USB)
    dialog.exclusive_check.SetValue(True)
    dialog.start_recording()
    recorder = dialog.recorder
    assert recorder.started_with["device"] == USB.index
    assert recorder.started_with["rate"] == int(dialog.rate_choice.GetStringSelection().split()[0])
    assert recorder.started_with["exclusive"] is True
    for control in (dialog.device_choice, dialog.rate_choice, dialog.format_choice, dialog.exclusive_check):
        assert not control.IsEnabled()
    assert dialog.stop_button.IsEnabled() and not dialog.record_button.IsEnabled()
    # الكرت رفض الوضع الحصري: يُقال مع بدء التسجيل
    assert dialog.announcer.last() == (dialog.tr.t("recorder_announce_started") + ". "
                                       + dialog.tr.t("recorder_exclusive_fallback"))

    dialog.stop_and_save()
    assert os.path.exists(dialog._output_path)
    assert dialog.announcer.last().startswith(dialog.tr.t(
        "recorder_announce_saved", duration="01:05", path=dialog._output_path).split("،")[0])
    assert dialog.record_button.IsEnabled() and not dialog.stop_button.IsEnabled()
    assert dialog.rate_choice.IsEnabled()
    # جهاز أحادي: الستيريو يبقى معطّلًا بعد التسجيل كما كان قبله
    assert not dialog.channels_choice.IsEnabled()


def test_level_key_when_not_recording(open_recorder):
    dialog = open_recorder()
    dialog._on_announce_level(None)
    assert dialog.announcer.last() == dialog.tr.t("recorder_level_not_recording")


def test_clipping_warning_shows_while_recording_and_clears(open_recorder):
    dialog = open_recorder()
    dialog.recorder.is_recording = True
    dialog._show_clipping_warning()
    assert dialog.clipping_warning.IsShown()
    # النص ملفوف على عرض النافذة: الكلمات نفسها بأسطر
    assert dialog.clipping_warning.GetLabel().replace("\n", " ") == dialog.tr.t("recorder_clipping_live_warning")
    dialog._reset_clipping_warning()
    assert not dialog.clipping_warning.IsShown()


@pytest.mark.parametrize("seconds, text", [(0, "00:00"), (65, "01:05"), (3725, "01:02:05")])
def test_elapsed_time_format(seconds, text):
    from gui.recorder_widgets import _format_elapsed
    assert _format_elapsed(seconds) == text
