# -*- coding: utf-8 -*-
"""اختبارات core.mic_level: مستوى المايكروفون في ويندوز."""

import sys

import pytest

from core.mic_level import MicLevel

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="ويندوز فقط")


def test_unknown_device_has_no_level():
    """جهاز مش موجود: None، والواجهة تعطّل الشريط بدل ما تقع."""
    assert MicLevel.open("No Such Microphone 12345") is None
    assert MicLevel.open("") is None


def test_level_round_trip_on_a_real_microphone():
    """أول مايك متاح: القراءة بين 0 و100، والكتابة ترجع كما هي بالضبط."""
    from core.audio_devices import group_devices

    level = None
    for device in group_devices():
        level = MicLevel.open(device.name)
        if level is not None:
            break
    if level is None:
        pytest.skip("لا يوجد مايكروفون يسمح ويندوز بضبط مستواه")
    try:
        original = level.get()
        assert 0 <= original <= 100
        target = 40 if original != 40 else 60
        assert level.set(target)
        assert level.get() == target
    finally:
        level.set(original)
        level.close()
