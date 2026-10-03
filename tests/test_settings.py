# -*- coding: utf-8 -*-
"""اختبارات لحفظ واسترجاع إعدادات المستخدم (core/settings.py)."""

import json
import os

import pytest

from core.settings import Settings


def test_announce_seek_mode_default_and_roundtrip(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    settings = Settings(path=settings_path)
    assert settings.get_announce_seek_mode() == "enabled"
    assert settings.get_announce_seek_interval_seconds() == 5

    settings.set_announce_seek_mode("enabled_interval")
    settings.set_announce_seek_interval_seconds(30)

    reloaded = Settings(path=settings_path)
    assert reloaded.get_announce_seek_mode() == "enabled_interval"
    assert reloaded.get_announce_seek_interval_seconds() == 30
    assert reloaded.get_announce_seek_feedback() is True

    reloaded.set_announce_seek_mode("disabled")
    assert reloaded.get_announce_seek_feedback() is False


def test_announce_seek_mode_rejects_invalid_values(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    settings = Settings(path=settings_path)
    settings.set_announce_seek_interval_seconds(999)
    assert settings.get_announce_seek_interval_seconds() == 5
    settings.set_announce_seek_mode("not_a_real_mode")
    assert settings.get_announce_seek_mode() == "enabled"


def test_announce_seek_mode_migrates_from_old_boolean_flag(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump({"announce_seek_feedback": False}, f)
    settings = Settings(path=settings_path)
    assert settings.get_announce_seek_mode() == "disabled"

    settings_path2 = str(tmp_path / "settings2.json")
    with open(settings_path2, "w", encoding="utf-8") as f:
        json.dump({"announce_seek_feedback": True}, f)
    settings2 = Settings(path=settings_path2)
    assert settings2.get_announce_seek_mode() == "enabled"


def test_settings_created_fresh_when_no_file_exists(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    settings = Settings(path=settings_path)
    assert settings.get_recent_files() == []
    assert settings.get_volume() == 100


def test_recent_files_ordering_and_dedup(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    settings = Settings(path=settings_path)

    settings.add_recent_file("a.mp3")
    settings.add_recent_file("b.mp3")
    settings.add_recent_file("a.mp3")  # لازم يترفع لأول القايمة تاني مش يتكرر

    raw = settings._data["recent_files"]
    assert raw == ["a.mp3", "b.mp3"]


def test_recent_files_respects_max_limit(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    settings = Settings(path=settings_path)
    for i in range(15):
        settings.add_recent_file(f"file_{i}.mp3")
    assert len(settings._data["recent_files"]) == 10  # _MAX_RECENT_FILES


def test_last_position_persists_across_instances(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    settings = Settings(path=settings_path)
    settings.set_last_position("/media/lecture.mp3", 123.5)

    # instance جديدة لازم تقرا نفس القيمة من الملف
    reloaded = Settings(path=settings_path)
    assert reloaded.get_last_position("/media/lecture.mp3") == 123.5


def test_last_position_default_is_zero(tmp_path):
    settings = Settings(path=str(tmp_path / "settings.json"))
    assert settings.get_last_position("/never/opened.mp3") == 0.0


def test_corrupted_settings_file_falls_back_to_defaults(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("{ this is not valid json", encoding="utf-8")
    settings = Settings(path=str(settings_path))
    # المفروض يبدأ بإعدادات افتراضية بدل ما يطلع استثناء ويكسر البرنامج
    assert settings.get_recent_files() == []
    assert settings.get_volume() == 100


def test_volume_roundtrip(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    settings = Settings(path=settings_path)
    settings.set_volume(65)
    reloaded = Settings(path=settings_path)
    assert reloaded.get_volume() == 65


def test_language_default_and_roundtrip(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    settings = Settings(path=settings_path)
    assert settings.get_language() == "ar"
    settings.set_language("en")
    reloaded = Settings(path=settings_path)
    assert reloaded.get_language() == "en"


def test_auto_resume_default_and_roundtrip(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    settings = Settings(path=settings_path)
    assert settings.get_auto_resume() is True
    settings.set_auto_resume(False)
    reloaded = Settings(path=settings_path)
    assert reloaded.get_auto_resume() is False


def test_max_recent_files_configurable_and_clamped(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    settings = Settings(path=settings_path)
    assert settings.get_max_recent_files() == 10

    settings.set_max_recent_files(5)
    for i in range(15):
        settings.add_recent_file(f"file_{i}.mp3")
    assert len(settings._data["recent_files"]) == 5

    # قيم خارج الحدود لازم تتقصّ (clamp) بدل ما تتقبل زي ما هي
    settings.set_max_recent_files(1000)
    assert settings.get_max_recent_files() == 50
    settings.set_max_recent_files(0)
    assert settings.get_max_recent_files() == 3


def test_batch_defers_write_until_block_exits(tmp_path):
    """set_* جوه كتلة batch() المفروض ما تكتبش الملف على القرص فورًا؛
    الكتابة الفعلية تحصل مرة واحدة بس عند الخروج من الكتلة."""
    settings_path = tmp_path / "settings.json"
    settings = Settings(path=str(settings_path))
    settings.set_volume(1)  # كتابة أولى فورية (خارج أي batch) لإنشاء الملف

    with settings.batch():
        settings.set_volume(42)
        settings.set_language("en")
        # لسه جوه الكتلة: القيمة القديمة (1) هي اللي المفروض على القرص
        # لحد دلوقتي، مش القيمة الجديدة (42)
        on_disk = json.loads(settings_path.read_text(encoding="utf-8"))
        assert on_disk["volume"] == 1

    # بعد الخروج من الكتلة: كتابة واحدة فعلية بكل القيم المجمّعة
    on_disk = json.loads(settings_path.read_text(encoding="utf-8"))
    assert on_disk["volume"] == 42
    assert on_disk["language"] == "en"


def test_batch_still_saves_when_exception_raised_inside(tmp_path):
    """حتى لو حصل استثناء جوه كتلة batch()، لازم القيم اللي اتعدّلت قبل
    الاستثناء تتحفظ على القرص وقت الخروج (finally)، مش تضيع بصمت."""
    settings_path = tmp_path / "settings.json"
    settings = Settings(path=str(settings_path))

    with pytest.raises(ValueError):
        with settings.batch():
            settings.set_volume(77)
            raise ValueError("خطأ تجريبي")

    on_disk = json.loads(settings_path.read_text(encoding="utf-8"))
    assert on_disk["volume"] == 77


def test_default_output_folders_are_nested_under_one_app_folder_and_follow_language(tmp_path):
    settings_path = str(tmp_path / "settings.json")
    settings = Settings(path=settings_path)

    ar_converter = settings.get_converter_output_folder()
    ar_recorder = settings.get_recorder_output_folder()
    assert os.path.join("مشغل الوسائط الشامل - Omnya", "ملفات محوّلة") in ar_converter
    assert os.path.join("مشغل الوسائط الشامل - Omnya", "تسجيلات صوتية") in ar_recorder
    # المجلدين لازم يكونوا جوه نفس المجلد الأب (مشغل الوسائط الشامل -
    # Omnya)، مش منفصلين مباشرة في المستندات زي قبل كده
    assert os.path.dirname(ar_converter) == os.path.dirname(ar_recorder)

    settings.set_language("en")
    en_converter = settings.get_converter_output_folder()
    en_recorder = settings.get_recorder_output_folder()
    assert os.path.join("مشغل الوسائط الشامل - Omnya", "Converted Files") in en_converter
    assert os.path.join("مشغل الوسائط الشامل - Omnya", "Voice Recordings") in en_recorder


def test_custom_output_folder_overrides_language_based_default(tmp_path):
    """لو المستخدم اختار مجلد بنفسه، لازم يفضل هو المستخدم دايمًا -
    تغيير اللغة بعد كده ما يلغيش الاختيار اليدوي."""
    settings_path = str(tmp_path / "settings.json")
    settings = Settings(path=settings_path)
    custom = str(tmp_path / "my_custom_folder")
    settings.set_converter_output_folder(custom)
    assert settings.get_converter_output_folder() == custom
    settings.set_language("en")
    assert settings.get_converter_output_folder() == custom
    settings_path = str(tmp_path / "settings.json")
    settings = Settings(path=settings_path)
    assert settings.get_recorder_default_audio_bitrate() == 192_000

    settings.set_recorder_default_audio_bitrate(320_000)
    reloaded = Settings(path=settings_path)
    assert reloaded.get_recorder_default_audio_bitrate() == 320_000
    settings_path = str(tmp_path / "settings.json")
    settings = Settings(path=settings_path)
    assert settings.get_recorder_default_bit_depth() == 16

    settings.set_recorder_default_bit_depth(32)
    reloaded = Settings(path=settings_path)
    assert reloaded.get_recorder_default_bit_depth() == 32

    # أي قيمة غير 16/32 لازم ترجع لـ 16 (القيمة القياسية) بدل قبولها
    # كما هي أو التعطل
    settings.set_recorder_default_bit_depth(24)
    assert settings.get_recorder_default_bit_depth() == 16
