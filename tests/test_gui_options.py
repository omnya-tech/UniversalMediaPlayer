# -*- coding: utf-8 -*-
"""
اختبارات نافذة الخيارات و«حول البرنامج»: كل خيار يُحفظ ويعود كما هو،
والتنقل بين التبويبات، ورفض الاختصار الشبحي المكرر.
"""

import pytest

wx = pytest.importorskip("wx")

from core.audio_devices import AudioDevice
from core.settings import Settings
from i18n.strings import Translator

FAKE_DEVICES = [
    AudioDevice("Microphone (USB)", 3, "Windows WASAPI", 48000, 1, 3.0),
    AudioDevice("Stereo Mix (Realtek)", 4, "Windows WASAPI", 48000, 2, 3.0),
]


@pytest.fixture
def open_options(wx_app, app_data, monkeypatch):
    """يفتح نافذة الخيارات على إعدادات جديدة، بأجهزة إدخال وهمية ثابتة."""
    import gui.options_tabs_mixin as tabs_module
    from gui.dialogs import OptionsDialog

    monkeypatch.setattr(tabs_module, "group_devices", lambda: list(FAKE_DEVICES))
    boxes = []
    monkeypatch.setattr(wx, "MessageBox", lambda *args, **kwargs: boxes.append(args[0]))
    dialogs = []

    def open_(settings=None, lang="ar"):
        settings = settings or Settings()
        dialog = OptionsDialog(None, Translator(lang), settings)
        dialog.ensure_all_tabs_built()
        dialog.boxes = boxes
        dialogs.append(dialog)
        return dialog, settings

    yield open_
    for dialog in dialogs:
        dialog.Destroy()


def _pick_other(choice):
    """يختار عنصرًا غير المختار حاليًا، ويرجّع رقمه."""
    index = (choice.GetSelection() + 1) % choice.GetCount()
    choice.SetSelection(index)
    return index


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_all_six_tabs_build(open_options, lang):
    dialog, _settings = open_options(lang=lang)
    assert dialog.notebook.GetPageCount() == 6


def test_every_changed_option_is_saved_and_shown_again(open_options):
    dialog, settings = open_options()
    picked = {}

    # عام
    picked["theme"] = _pick_other(dialog.theme_choice)
    picked["ended"] = _pick_other(dialog.on_playback_ended_choice)
    for checkbox in (dialog.auto_resume_checkbox, dialog.folder_navigation_checkbox,
                     dialog.enable_completion_sound_checkbox, dialog.enable_media_keys_checkbox):
        checkbox.SetValue(not checkbox.GetValue())
    picked["general_checks"] = [c.GetValue() for c in (
        dialog.auto_resume_checkbox, dialog.folder_navigation_checkbox,
        dialog.enable_completion_sound_checkbox, dialog.enable_media_keys_checkbox)]
    # التشغيل والتنقل
    picked["seek"] = {kind: _pick_other(choice) for kind, (choice, _a) in dialog.seek_step_choices.items()}
    picked["seek_min"] = _pick_other(dialog.seek_min_choice)
    # إمكانية الوصول: كل إعلان بعكس قيمته
    for _attr, _key, checkbox in dialog._announce_checkboxes:
        checkbox.SetValue(not checkbox.GetValue())
    picked["announce"] = {key: checkbox.GetValue() for _a, key, checkbox in dialog._announce_checkboxes}
    # المسجّل
    dialog.recorder_device_choice.SetStringSelection("Microphone (USB)")
    picked["rec_rate"] = _pick_other(dialog.recorder_rate_choice)
    picked["rec_channels"] = _pick_other(dialog.recorder_channels_choice)
    picked["rec_bits"] = _pick_other(dialog.recorder_bit_depth_choice)
    picked["rec_enhance"] = _pick_other(dialog.recorder_enhance_choice)
    dialog.recorder_exclusive_check.SetValue(not dialog.recorder_exclusive_check.GetValue())
    picked["rec_exclusive"] = dialog.recorder_exclusive_check.GetValue()
    # محرر الوسائط
    picked["editor_mode"] = _pick_other(dialog.editor_video_mode_choice)
    picked["editor_progress"] = _pick_other(dialog.editor_progress_choice)

    assert dialog.apply_to_settings() is False      # اللغة لم تتغير

    again, _ = open_options(settings)
    assert again.theme_choice.GetSelection() == picked["theme"]
    assert again.on_playback_ended_choice.GetSelection() == picked["ended"]
    assert [c.GetValue() for c in (again.auto_resume_checkbox, again.folder_navigation_checkbox,
                                    again.enable_completion_sound_checkbox,
                                    again.enable_media_keys_checkbox)] == picked["general_checks"]
    assert {k: c.GetSelection() for k, (c, _a) in again.seek_step_choices.items()} == picked["seek"]
    assert again.seek_min_choice.GetSelection() == picked["seek_min"]
    assert {key: c.GetValue() for _a, key, c in again._announce_checkboxes} == picked["announce"]
    assert again.recorder_device_choice.GetStringSelection() == "Microphone (USB)"
    assert again.recorder_rate_choice.GetSelection() == picked["rec_rate"]
    assert again.recorder_channels_choice.GetSelection() == picked["rec_channels"]
    assert again.recorder_bit_depth_choice.GetSelection() == picked["rec_bits"]
    assert again.recorder_enhance_choice.GetSelection() == picked["rec_enhance"]
    assert again.recorder_exclusive_check.GetValue() == picked["rec_exclusive"]
    assert again.editor_video_mode_choice.GetSelection() == picked["editor_mode"]
    assert again.editor_progress_choice.GetSelection() == picked["editor_progress"]


def test_changing_the_language_asks_for_a_restart(open_options):
    dialog, settings = open_options()
    dialog.language_choice.SetSelection(1)
    assert dialog.apply_to_settings() is True
    assert settings.get_language() == "en"


def test_master_announcement_switch_greys_out_the_others(open_options):
    dialog, _settings = open_options()
    dialog.toggle_accessibility_checkbox.SetValue(False)
    dialog._update_accessibility_ui_state()
    assert not any(checkbox.IsEnabled() for _a, _k, checkbox in dialog._announce_checkboxes)
    dialog.toggle_accessibility_checkbox.SetValue(True)
    dialog._update_accessibility_ui_state()
    assert all(checkbox.IsEnabled() for _a, _k, checkbox in dialog._announce_checkboxes)


def test_tab_keys_jump_and_wrap(open_options):
    dialog, _settings = open_options()
    dialog._go_to_tab(5)                       # Ctrl+6
    assert dialog.notebook.GetSelection() == 5
    dialog._cycle_tab(1)                       # Ctrl+Tab من الأخير يرجع للأول
    assert dialog.notebook.GetSelection() == 0
    dialog._cycle_tab(-1)                      # Ctrl+Shift+Tab من الأول للأخير
    assert dialog.notebook.GetSelection() == 5
    dialog._go_to_tab(9)                       # رقم بلا تبويب: لا شيء
    assert dialog.notebook.GetSelection() == 5


def test_duplicate_ghost_shortcut_is_refused_until_fixed(open_options):
    dialog, settings = open_options()
    choices = dialog.editor_hotkey_choices
    (open_mods, open_key), (split_mods, split_key) = choices["open"], choices["split"]
    split_mods.SetSelection(open_mods.GetSelection())
    split_key.SetSelection(open_key.GetSelection())

    event = wx.CommandEvent(wx.wxEVT_BUTTON)
    dialog._on_save_clicked(event)
    assert not event.GetSkipped()              # الحفظ متوقف
    assert dialog.notebook.GetSelection() == dialog.EDITOR_TAB
    assert dialog.boxes, "رسالة تشرح التعارض"

    split_key.SetSelection((split_key.GetSelection() + 1) % split_key.GetCount())
    event = wx.CommandEvent(wx.wxEVT_BUTTON)
    dialog._on_save_clicked(event)
    assert event.GetSkipped()


def test_reset_seek_steps_restores_the_defaults(open_options):
    dialog, settings = open_options()
    for _kind, (choice, _amounts) in dialog.seek_step_choices.items():
        _pick_other(choice)
    dialog._on_reset_seek_steps(None)
    dialog.apply_to_settings()
    assert {kind: settings.get_seek_step(kind) for kind in settings.SEEK_STEP_DEFAULTS} == \
        settings.SEEK_STEP_DEFAULTS


@pytest.mark.parametrize("lang", ["ar", "en"])
def test_about_dialog_builds(wx_app, lang):
    from gui.dialogs import AboutDialog
    dialog = AboutDialog(None, Translator(lang))
    try:
        assert Translator(lang).t("menu_about") in dialog.GetTitle()
    finally:
        dialog.Destroy()
