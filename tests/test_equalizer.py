# -*- coding: utf-8 -*-
"""اختبارات منطق المعادل (core/equalizer.py) وحفظه في الإعدادات."""

from core import equalizer
from core.settings import Settings


def test_cycle_wraps_and_skips_custom_when_not_saved():
    assert equalizer.cycle_mode("off", 1, has_custom=False) == "flat"
    assert equalizer.cycle_mode("off", -1, has_custom=False) == "techno"
    assert equalizer.cycle_mode("techno", 1, has_custom=False) == "off"
    assert equalizer.cycle_mode("techno", 1, has_custom=True) == "custom"
    assert equalizer.cycle_mode("custom", 1, has_custom=True) == "off"
    # نمط غير معروف بيبدأ من أول الدورة بدل ما يتعطل
    assert equalizer.cycle_mode("garbage", 1, has_custom=False) == "flat"


def test_preset_index_matches_libvlc_order():
    assert equalizer.preset_index("flat") == 0
    assert equalizer.preset_index("rock") == 13
    assert equalizer.preset_index("techno") == 17
    assert equalizer.preset_index("off") is None
    assert equalizer.preset_index("custom") is None


def test_normalize_bands_pads_trims_and_clamps():
    assert equalizer.normalize_bands(None) == [0.0] * 10
    assert equalizer.normalize_bands([5, "x", 99, -99]) == [5.0, 0.0, 20.0, -20.0] + [0.0] * 6
    assert len(equalizer.normalize_bands(list(range(15)))) == 10
    assert equalizer.clamp_gain(float("nan")) == 0.0


def test_format_frequency():
    assert [equalizer.format_frequency(f) for f in equalizer.BAND_FREQUENCIES] == [
        "31", "62", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"]


def test_settings_equalizer_roundtrip_and_validation(tmp_path):
    path = str(tmp_path / "settings.json")
    settings = Settings(path=path)
    assert settings.get_equalizer_mode() == "off"
    assert settings.has_equalizer_custom() is False

    settings.set_equalizer_mode("rock")
    settings.set_equalizer_custom(3, [1, 2, 3])
    reloaded = Settings(path=path)
    assert reloaded.get_equalizer_mode() == "rock"
    assert reloaded.get_equalizer_custom() == (3.0, [1.0, 2.0, 3.0] + [0.0] * 7)
    assert reloaded.has_equalizer_custom() is True

    reloaded.set_equalizer_mode("not_a_mode")
    assert reloaded.get_equalizer_mode() == "off"
