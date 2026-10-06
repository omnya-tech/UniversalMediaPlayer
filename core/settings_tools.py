# -*- coding: utf-8 -*-
"""
إعدادات الأدوات: محول الصيغ، ومسجّل الصوت وإعدادات كل جهاز إدخال على حدة،
ومحرر الوسائط واختصاراته الشبحية.

نُقلت كما هي من core/settings.py.
"""


class ToolsSettingsMixin:
    """إعدادات المحول والمسجّل ومحرر الوسائط."""

    # الحقول المحفوظة لكل جهاز - الصيغة ومعدل البت مش خاصين بالجهاز
    _DEVICE_PROFILE_FIELDS = ("sample_rate", "channels", "bit_depth")

    def get_device_profile(self, device_name: str):
        """تفضيلات جهاز بعينه، أو None لو الجهاز جديد."""
        if not device_name:
            return None
        profiles = self._data.get("recorder_device_profiles") or {}
        stored = profiles.get(device_name)
        if not isinstance(stored, dict):
            return None
        profile = {}
        for field in self._DEVICE_PROFILE_FIELDS:
            if field in stored:
                try:
                    profile[field] = int(stored[field])
                except (TypeError, ValueError):
                    continue
        return profile or None

    def set_device_profile(self, device_name: str, profile: dict):
        """يحفظ تفضيلات جهاز. الجهاز اللي اتفصل بيفضل محفوظ لما يرجع."""
        if not device_name or not isinstance(profile, dict):
            return
        profiles = self._data.get("recorder_device_profiles")
        if not isinstance(profiles, dict):
            profiles = {}
        clean = {}
        for field in self._DEVICE_PROFILE_FIELDS:
            if field in profile:
                try:
                    clean[field] = int(profile[field])
                except (TypeError, ValueError):
                    continue
        if not clean:
            return
        profiles[device_name] = clean
        self._data["recorder_device_profiles"] = profiles
        self.save()

    def forget_device_profile(self, device_name: str):
        profiles = self._data.get("recorder_device_profiles")
        if isinstance(profiles, dict) and device_name in profiles:
            del profiles[device_name]
            self.save()

    # ------------------------------------------------------------------ #
    # محرر الوسائط
    # ------------------------------------------------------------------ #
    _VALID_EDITOR_PROGRESS_STEPS = (0, 10, 25, 50)

    def get_editor_video_precise(self) -> bool:
        """طريقة قص الفيديو التي تبدأ بها النافذة: الدقيق أو السريع."""
        return bool(self._data.get("editor_video_precise", False))

    def set_editor_video_precise(self, precise: bool):
        self._data["editor_video_precise"] = bool(precise)
        self.save()

    def get_editor_progress_step(self) -> int:
        """كل كم في المئة يُعلن التقدم؛ الصفر يعني لا إعلان أثناء العمل."""
        try:
            value = int(self._data.get("editor_progress_step", 25))
        except (TypeError, ValueError):
            return 25
        return value if value in self._VALID_EDITOR_PROGRESS_STEPS else 25

    def set_editor_progress_step(self, step: int):
        self._data["editor_progress_step"] = step if step in self._VALID_EDITOR_PROGRESS_STEPS else 25
        self.save()

    def get_editor_hotkey(self, action: str):
        """(المفاتيح المساعدة، المفتاح) المحفوظان لاختصار شبحي، أو None للافتراضي."""
        value = self._data.get(f"editor_hotkey_{action}")
        if isinstance(value, (list, tuple)) and len(value) == 2 and all(isinstance(v, str) for v in value):
            return tuple(value)
        return None

    def set_editor_hotkeys(self, mapping: dict):
        """يحفظ كل الاختصارات الشبحية مرة واحدة: {الفعل: (المساعدة، المفتاح)}."""
        for action, combo in mapping.items():
            self._data[f"editor_hotkey_{action}"] = list(combo)
        self.save()

    # ------------------------------------------------------------------ #
    # إعدادات محول الصيغ
    # ------------------------------------------------------------------ #
    def get_converter_default_is_video(self) -> bool:
        return bool(self._data.get("converter_default_is_video", False))

    def set_converter_default_is_video(self, is_video: bool):
        self._data["converter_default_is_video"] = bool(is_video)
        self.save()

    def get_converter_default_format(self) -> str:
        return self._data.get("converter_default_format", ".mp3")

    def set_converter_default_format(self, ext: str):
        self._data["converter_default_format"] = ext
        self.save()

    def get_converter_default_video_format(self) -> str:
        return self._data.get("converter_default_video_format", ".mp4")

    def set_converter_default_video_format(self, ext: str):
        self._data["converter_default_video_format"] = ext
        self.save()

    def get_converter_default_audio_format(self) -> str:
        return self._data.get("converter_default_audio_format", ".mp3")

    def set_converter_default_audio_format(self, ext: str):
        self._data["converter_default_audio_format"] = ext
        self.save()

    def get_converter_default_audio_bitrate(self) -> int:
        return int(self._data.get("converter_default_audio_bitrate", 0))

    def set_converter_default_audio_bitrate(self, kbps: int):
        self._data["converter_default_audio_bitrate"] = int(kbps)
        self.save()

    def get_converter_default_video_bitrate(self) -> int:
        return int(self._data.get("converter_default_video_bitrate", 4000))

    def set_converter_default_video_bitrate(self, kbps: int):
        self._data["converter_default_video_bitrate"] = int(kbps)
        self.save()

    def get_converter_custom_video_bitrate(self) -> str:
        return self._data.get("converter_custom_video_bitrate", "")

    def set_converter_custom_video_bitrate(self, bitrate: str):
        self._data["converter_custom_video_bitrate"] = bitrate
        self.save()

    def get_converter_custom_audio_bitrate(self) -> str:
        return self._data.get("converter_custom_audio_bitrate", "192k")

    def set_converter_custom_audio_bitrate(self, bitrate: str):
        self._data["converter_custom_audio_bitrate"] = bitrate
        self.save()

    # ------------------------------------------------------------------ #
    # إعدادات مسجل الصوت
    # ------------------------------------------------------------------ #
    def get_recorder_default_device_name(self) -> str:
        return self._data.get("recorder_default_device_name", "")

    def set_recorder_default_device_name(self, name: str):
        self._data["recorder_default_device_name"] = name
        self.save()

    def get_recorder_default_sample_rate(self) -> int:
        return int(self._data.get("recorder_default_sample_rate", 44100))

    def set_recorder_default_sample_rate(self, rate: int):
        self._data["recorder_default_sample_rate"] = int(rate)
        self.save()

    def get_recorder_default_channels(self) -> int:
        return int(self._data.get("recorder_default_channels", 1))

    def set_recorder_default_channels(self, channels: int):
        self._data["recorder_default_channels"] = int(channels)
        self.save()

    _VALID_BIT_DEPTHS = (16, 24, 32)

    def get_recorder_default_bit_depth(self) -> int:
        try:
            value = int(self._data.get("recorder_default_bit_depth", 16))
        except (TypeError, ValueError):
            return 16
        return value if value in self._VALID_BIT_DEPTHS else 16

    def set_recorder_default_bit_depth(self, bit_depth: int):
        bit_depth = int(bit_depth)
        self._data["recorder_default_bit_depth"] = bit_depth if bit_depth in self._VALID_BIT_DEPTHS else 16
        self.save()

    # تحسين صوت المايكروفون (core/voice_enhance.py) والوضع الحصري لكرت الصوت
    _VALID_ENHANCE_LEVELS = ("off", "clean", "denoise")

    def get_recorder_enhance_level(self) -> str:
        value = self._data.get("recorder_enhance_level", "clean")
        return value if value in self._VALID_ENHANCE_LEVELS else "clean"

    def set_recorder_enhance_level(self, level: str):
        self._data["recorder_enhance_level"] = level if level in self._VALID_ENHANCE_LEVELS else "clean"
        self.save()

    def get_recorder_exclusive(self) -> bool:
        return bool(self._data.get("recorder_exclusive", True))

    def set_recorder_exclusive(self, enabled: bool):
        self._data["recorder_exclusive"] = bool(enabled)
        self.save()

    def get_recorder_default_format(self) -> str:
        return self._data.get("recorder_default_format", ".wav")

    def set_recorder_default_format(self, ext: str):
        self._data["recorder_default_format"] = ext
        self.save()

    def get_recorder_default_audio_bitrate(self) -> int:
        return int(self._data.get("recorder_default_audio_bitrate", 0))

    def set_recorder_default_audio_bitrate(self, bps: int):
        self._data["recorder_default_audio_bitrate"] = int(bps)
        self.save()

    def get_recorder_default_bitrate(self) -> str:
        return self._data.get("recorder_default_bitrate", "192k")

    def set_recorder_default_bitrate(self, bitrate: str):
        self._data["recorder_default_bitrate"] = bitrate
        self.save()
