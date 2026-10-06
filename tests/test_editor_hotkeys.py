# -*- coding: utf-8 -*-
"""الاختصارات الشبحية لمحرر الوسائط (gui/editor_hotkeys.py) وإعداداتها."""

import pytest

wx = pytest.importorskip("wx")

from gui.editor_hotkeys import (  # noqa: E402
    ACTIONS,
    DEFAULT_HOTKEYS,
    combo_text,
    current_hotkeys,
    find_duplicates,
    hotkeys_help_text,
)
from i18n.strings import STRINGS, Translator  # noqa: E402


class _Settings:
    def __init__(self, saved=None):
        self.saved = saved or {}

    def get_editor_hotkey(self, action):
        return self.saved.get(action)


def test_default_shortcuts_are_all_different():
    assert find_duplicates(dict(DEFAULT_HOTKEYS)) == []


def test_every_shortcut_is_described_in_both_languages():
    for action in ACTIONS:
        assert f"ghost_action_{action}" in STRINGS["ar"]
        assert f"ghost_action_{action}" in STRINGS["en"]


def test_saved_shortcut_replaces_the_default():
    mapping = current_hotkeys(_Settings({"split": ("ctrl+alt", "F5")}))
    assert combo_text(mapping["split"]) == "Ctrl+Alt+F5"
    assert combo_text(mapping["start"]) == "Ctrl+Alt+Shift+B"


def test_broken_saved_shortcut_falls_back_to_the_default():
    # إعدادات قديمة أو معدّلة يدويًا لا توقف الاختصار
    mapping = current_hotkeys(_Settings({"split": ("hyper", "?")}))
    assert mapping["split"] == dict(DEFAULT_HOTKEYS)["split"]


def test_duplicates_are_found():
    mapping = dict(DEFAULT_HOTKEYS)
    mapping["merge"] = mapping["split"]
    assert find_duplicates(mapping) == [("split", "merge")]


def test_help_lists_the_current_keys():
    mapping = current_hotkeys(_Settings({"toggle": ("ctrl+shift", "F9")}))
    first_line = hotkeys_help_text(Translator("ar"), mapping).splitlines()[0]
    assert first_line.startswith("Ctrl+Shift+F9")


def test_seek_steps_are_saved_and_kept_in_range(tmp_path, monkeypatch):
    from core import settings as settings_module

    monkeypatch.setattr(settings_module, "get_app_data_dir", lambda: str(tmp_path), raising=False)
    settings = settings_module.Settings.__new__(settings_module.Settings)
    settings._data = {}
    settings.save = lambda: None
    assert settings.get_seek_step("normal") == 10
    settings.set_seek_step("normal", 15)
    assert settings.get_seek_step("normal") == 15
    settings.set_seek_step("ctrl_shift", 10 ** 6)
    assert settings.get_seek_step("ctrl_shift") == settings.SEEK_STEP_LIMITS["ctrl_shift"][1]
    settings._data["seek_step_alt"] = "كلام"
    assert settings.get_seek_step("alt") == 600
