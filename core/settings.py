# -*- coding: utf-8 -*-
import contextlib
import json
import logging
import os

from core import equalizer
from core.logging_setup import get_app_data_dir, get_documents_dir
from core.streams import is_stream_url
from i18n.strings import STRINGS

logger = logging.getLogger(__name__)

_SETTINGS_FILENAME = "settings.json"
_DEFAULT_MAX_RECENT_FILES = 10
_MIN_MAX_RECENT_FILES = 3
_MAX_MAX_RECENT_FILES = 50
_MAX_REMEMBERED_POSITIONS = 200
_MAX_BOOKMARKS_PER_FILE = 50

_MIN_PLAYBACK_SPEED = 0.5
_MAX_PLAYBACK_SPEED = 2.0
_DEFAULT_PLAYBACK_SPEED = 1.0
_DEFAULT_SLEEP_TIMER_MINUTES = 30


class Settings:
    def __init__(self, path: str = None):
        self._path = path or os.path.join(get_app_data_dir(), _SETTINGS_FILENAME)
        self._backup_path = self._path + ".bak"
        self._autosave_enabled = True
        self._data = {
            "recent_files": [],
            "last_positions": {},
            "volume": 100,
            "language": "ar",
            "auto_resume": True,
            "max_recent_files": _DEFAULT_MAX_RECENT_FILES,
            "enable_folder_navigation": True,
            "enable_completion_sound": True,
            "enable_global_media_keys": True,
            "ui_theme": "standard",
            "on_playback_ended_action": "next_file",

            # إعلانات إمكانية الوصول
            # المفتاح الرئيسي: لو مطفي، مفيش أي إعلان مهما كانت المفاتيح
            # الفرعية. موجود علشان Ctrl+Alt+A يقدر يسكّت البرنامج كله مرة
            # واحدة، والمستخدم يرجّع الإعلانات اللي كان مختارها بالظبط.
            # (الإعلانات اللي بيطلبها المستخدم صراحةً بتتجاوزه)
            "announce_accessibility": True,
            "announce_file_loaded": True,
            "announce_file_info": True,
            "announce_playlist_position": True,
            "announce_resume_position": True,
            "announce_navigation_blocked": True,
            "announce_playback_state": True,
            "announce_buffering": False,
            "announce_volume_changes": True,
            "announce_mute_toggle": True,
            "announce_seek_mode": "enabled",
            # أصغر قفزة بيتعلن عندها الموضع بالثواني. صفر يعني كل قفزة.
            # المستخدم اللي بيضغط سهم العشر ثواني كتير بيتزعج من إعلان
            # كل ضغطة، فيقدر يخلّي الإعلان للقفزات الكبيرة بس.
            "announce_seek_min_seconds": 0,

            "announce_time_status": True,
            "announce_duration_announce": True,
            "announce_remaining_time": True,
            "announce_playback_speed": True,
            "announce_bookmarks": True,
            "announce_sleep_timer": True,
            "announce_settings_import_export": True,
            "announce_fullscreen": True,
            "announce_equalizer": True,
            # "يُذاع الآن" في الراديو كل ما الأغنية/البرنامج يتغيّر
            "announce_stream_title": True,

            "bookmarks": {},
            "file_speeds": {},
            "window_geometry": None,
            "sleep_timer_last_minutes": _DEFAULT_SLEEP_TIMER_MINUTES,

            # المعادل (شوف core/equalizer.py): النمط، وقيم "مخصص"
            "equalizer_mode": equalizer.MODE_OFF,
            "equalizer_custom_preamp": 0.0,
            "equalizer_custom_bands": [0.0] * equalizer.BAND_COUNT,
            # آخر مجلد اتحفظت فيه أو اتفتحت منه قائمة تشغيل
            "playlist_last_folder": "",

            # إعدادات محول الصيغ
            "converter_default_is_video": False,
            "converter_default_format": ".mp3",
            "converter_default_video_format": ".mp4",
            "converter_default_audio_format": ".mp3",
            "converter_custom_video_bitrate": "",
            "converter_custom_audio_bitrate": "192k",
            # صفر = «أعلى جودة متاحة» للصيغة الحالية (شوف HIGHEST_AUDIO_BITRATE)
            "converter_default_audio_bitrate": 0,
            "converter_default_video_bitrate": 4000,
            "converter_output_folder": "",

            # إعدادات مسجل الصوت
            "recorder_default_device_name": "",
            "recorder_default_sample_rate": 44100,
            "recorder_default_channels": 1,
            "recorder_default_bit_depth": 16,
            "recorder_default_format": ".wav",
            # صفر = «أعلى جودة متاحة» للصيغة الحالية
            "recorder_default_audio_bitrate": 0,
            "recorder_default_bitrate": "192k",
            "recorder_output_folder": "",
            # تفضيلات كل جهاز إدخال على حدة، بالاسم: المعدل والقنوات وعمق
            # البت. المستخدم اللي عنده مايك USB وكارت صوت داخلي ما يعيدش
            # الضبط كل ما يبدّل بينهم، وتصحيح إعدادات جهاز ما يبوّظش
            # التاني.
            # {اسم الجهاز: {"sample_rate": ..., "channels": ..., "bit_depth": ...}}
            "recorder_device_profiles": {},
        }
        self.load()

    # ------------------------------------------------------------------ #
    def load(self):
        """
        بيقرأ الإعدادات، ولو الملف الأساسي مشوّه بيقع على النسخة الاحتياطية.

        الملف بيتكتب ذرّيًا (شوف _write_to_disk)، فالتشوّه المفروض ما يحصلش.
        بس ده ما بيمنعش تلف على مستوى القرص، ولا ملف مشوّه اتساب من إصدار
        قديم كان بيكتب مباشرة. الاسترجاع أرخص من ضياع كل إعدادات المستخدم.
        """
        for candidate in (self._path, self._backup_path):
            if not os.path.exists(candidate):
                continue
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
            except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
                logger.warning("تعذّرت قراءة الإعدادات من %s: %s",
                               os.path.basename(candidate), exc)
                continue

            if not isinstance(loaded, dict):
                logger.warning("ملف الإعدادات %s مش قاموس - بيتتجاهل",
                               os.path.basename(candidate))
                continue

            self._data.update(loaded)
            if "announce_seek_mode" not in loaded and "announce_seek_feedback" in loaded:
                self._data["announce_seek_mode"] = (
                    "enabled" if loaded["announce_seek_feedback"] else "disabled"
                )
            # «إيقاف الكمبيوتر» عند نهاية التشغيل اتشال من الخيارات: إيقاف
            # الجهاز من غير ما المستخدم يطلبه صراحةً في اللحظة دي خطر،
            # والمؤقّت بيعمله لمن يريده. القيمة القديمة بترجع للملف التالي
            # بدل ما تفضل مستخبية من غير اختيار مقابل في الواجهة.
            if loaded.get("on_playback_ended_action") == "shutdown":
                self._data["on_playback_ended_action"] = "next_file"
            # 192 كان افتراضيًا قديمًا مش اختيارًا من المستخدم، والافتراضي
            # الجديد «أعلى جودة». المستخدم اللي كان سايبه على حاله بياخد
            # الجديد؛ ومن اختار رقمًا غيره بيفضل رقمه.
            # (192 بالكيلوبت في المحوّل، وبالبت في المسجّل)
            if loaded.get("converter_default_audio_bitrate") == 192:
                self._data["converter_default_audio_bitrate"] = 0
            if loaded.get("recorder_default_audio_bitrate") == 192_000:
                self._data["recorder_default_audio_bitrate"] = 0

            self._purge_dead_keys(loaded)

            if candidate == self._backup_path:
                logger.warning("الإعدادات اتسترجعت من النسخة الاحتياطية")
            return

    # مفاتيح كتبتها نسخ قديمة وما بقاش حد بيقراها
    _DEAD_KEYS = ("seek_mode", "announce_seek")

    def _purge_dead_keys(self, loaded):
        """
        تنظيف بقايا نسخ سابقة من ملف الإعدادات.

        نسخة قديمة من نافذة الخيارات كانت بتحفظ نمط الإعلان بتلات مفاتيح
        وبقيمة "all" مش من ضمن القيم الصالحة، وبتكتبها في القاموس مباشرة
        فما كانتش بتعدّي على التحقق. الغلط ما بانش لأن القارئ بيتحقق تاني،
        بس الملف كان بيتلوّث - وأي كود بيقرا المفتاح مباشرة كان هيلاقي
        قيمة مش في القاموس أصلًا.
        """
        for key in self._DEAD_KEYS:
            self._data.pop(key, None)

        mode = self._data.get("announce_seek_mode")
        if mode is not None and mode not in self._VALID_SEEK_MODES:
            # التحقق هنا مش في القارئ بس: القيمة الغلط لازم تتشال من
            # الملف نفسه أول ما يتحفظ
            logger.info("نمط إعلان غير معروف في الإعدادات (%r) - بيترجّع للمفعّل", mode)
            self._data["announce_seek_mode"] = "enabled"

    def save(self):
        if not self._autosave_enabled:
            return
        self._write_to_disk()

    def _write_to_disk(self):
        """
        كتابة ذرّية: ملف مؤقت -> flush + fsync -> os.replace.

        الكتابة المباشرة بـ open(path, "w") بتفرّغ الملف الأول. انقطاع
        كهرباء أو تعليق في اللحظة دي كان بيسيب JSON مقطوع، يعني ضياع كل
        الإعدادات والعلامات والمواضع المحفوظة. والدالة دي بتتنادى من
        عشرات المواضع (كل إيقاف، كل تغيير ملف، كل إغلاق)، والأجهزة
        الضعيفة أكتر عرضة للتعليق.

        os.replace ذرّية على ويندوز وعلى POSIX: إما الملف القديم كامل
        أو الجديد كامل، مفيش حالة بينهم.
        """
        temp_path = self._path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)

            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            # النسخة الاحتياطية من الملف السليم الحالي قبل استبداله: لو
            # الجديد طلع مشوّه لأي سبب، load بترجع لها.
            # نسخ لا نقل: الملف الأساسي لازم يفضل موجود لحد ما الجديد
            # يحلّ محله.
            if os.path.exists(self._path):
                try:
                    with open(self._path, "rb") as source:
                        payload = source.read()
                    with open(self._backup_path, "wb") as backup:
                        backup.write(payload)
                except OSError:
                    pass

            os.replace(temp_path, self._path)
        except OSError as exc:
            logger.error("فشل حفظ الإعدادات: %s", exc)
            with contextlib.suppress(OSError):
                if os.path.exists(temp_path):
                    os.remove(temp_path)

    @contextlib.contextmanager
    def batch(self):
        previous = self._autosave_enabled
        self._autosave_enabled = False
        try:
            yield self
        finally:
            self._autosave_enabled = previous
            self.save()

    # ------------------------------------------------------------------ #
    # الملفات الأخيرة
    # ------------------------------------------------------------------ #
    def add_recent_file(self, path: str):
        recent = [p for p in self._data["recent_files"] if p != path]
        recent.insert(0, path)
        self._data["recent_files"] = recent[: self.get_max_recent_files()]
        self.save()

    def get_recent_files(self):
        # الروابط مالهاش وجود على القرص، فبتفضل في القائمة دايمًا
        return [p for p in self._data["recent_files"] if is_stream_url(p) or os.path.exists(p)]

    def get_max_recent_files(self) -> int:
        value = int(self._data.get("max_recent_files", _DEFAULT_MAX_RECENT_FILES))
        return max(_MIN_MAX_RECENT_FILES, min(_MAX_MAX_RECENT_FILES, value))

    def set_max_recent_files(self, count: int):
        count = max(_MIN_MAX_RECENT_FILES, min(_MAX_MAX_RECENT_FILES, int(count)))
        self._data["max_recent_files"] = count
        self._data["recent_files"] = self._data.get("recent_files", [])[:count]
        self.save()

    # ------------------------------------------------------------------ #
    # آخر موضع تشغيل لكل ملف
    # ------------------------------------------------------------------ #
    def set_last_position(self, path: str, seconds: float):
        positions = self._data["last_positions"]
        positions[path] = seconds
        if len(positions) > _MAX_REMEMBERED_POSITIONS:
            oldest_key = next(iter(positions))
            positions.pop(oldest_key, None)
        self.save()

    def get_last_position(self, path: str) -> float:
        return float(self._data["last_positions"].get(path, 0.0))

    def clear_last_position(self, path: str):
        self._data["last_positions"].pop(path, None)
        self.save()

    # ------------------------------------------------------------------ #
    # مستوى الصوت
    # ------------------------------------------------------------------ #
    def set_volume(self, percent: int):
        self._data["volume"] = percent
        self.save()

    def get_volume(self) -> int:
        return int(self._data.get("volume", 100))

    # ------------------------------------------------------------------ #
    # خيارات صفحة الإعدادات
    # ------------------------------------------------------------------ #
    def get_language(self) -> str:
        return self._data.get("language", "ar")

    def set_language(self, lang: str):
        self._data["language"] = lang
        self.save()

    def get_auto_resume(self) -> bool:
        return bool(self._data.get("auto_resume", True))

    def set_auto_resume(self, enabled: bool):
        self._data["auto_resume"] = bool(enabled)
        self.save()

    def get_enable_folder_navigation(self) -> bool:
        return bool(self._data.get("enable_folder_navigation", True))

    def set_enable_folder_navigation(self, enabled: bool):
        self._data["enable_folder_navigation"] = bool(enabled)
        self.save()

    def get_enable_completion_sound(self) -> bool:
        return bool(self._data.get("enable_completion_sound", True))

    def set_enable_completion_sound(self, enabled: bool):
        self._data["enable_completion_sound"] = bool(enabled)
        self.save()

    def get_enable_global_media_keys(self) -> bool:
        return bool(self._data.get("enable_global_media_keys", True))

    def set_enable_global_media_keys(self, enabled: bool):
        self._data["enable_global_media_keys"] = bool(enabled)
        self.save()

    _VALID_UI_THEMES = ("standard", "high_contrast", "dark", "light")
    def get_ui_theme(self) -> str:
        value = self._data.get("ui_theme", "dark")
        return value if value in self._VALID_UI_THEMES else "dark"

    def set_ui_theme(self, theme: str):
        self._data["ui_theme"] = theme if theme in self._VALID_UI_THEMES else "dark"
        self.save()

    # «shutdown» اتشال: شوف load
    _VALID_PLAYBACK_ENDED_ACTIONS = ("none", "next_file")

    def get_on_playback_ended_action(self) -> str:
        value = self._data.get("on_playback_ended_action", "next_file")
        return value if value in self._VALID_PLAYBACK_ENDED_ACTIONS else "next_file"

    def set_on_playback_ended_action(self, action: str):
        if action not in self._VALID_PLAYBACK_ENDED_ACTIONS:
            action = "next_file"
        self._data["on_playback_ended_action"] = action
        self.save()

    # ------------------------------------------------------------------ #
    # تخصيص فئات الإعلان الصوتي
    # ------------------------------------------------------------------ #
    def _get_announce_flag(self, key: str) -> bool:
        return bool(self._data.get(key, True))

    def _set_announce_flag(self, key: str, enabled: bool):
        self._data[key] = bool(enabled)
        self.save()

    def get_announce_accessibility(self) -> bool: return self._get_announce_flag("announce_accessibility")
    def set_announce_accessibility(self, enabled: bool): self._set_announce_flag("announce_accessibility", enabled)

    def is_announcement_enabled(self, setting_key: str = None) -> bool:
        """
        هل الإعلان ده مسموح؟ بيفحص المفتاح الرئيسي ثم المفتاح المحدد.

        الطريقة دي بتقرا من _data مباشرة بدل ما تدوّر على get_<key>. القديم
        كان بيتخطّى الفحص بصمت لو الـ getter مش موجود - وده اللي خلّى
        المفتاح الرئيسي بلا أثر لفترة. دلوقتي أي مفتاح جديد بيشتغل من غير
        ما حد يفتكر يضيف له getter.
        """
        if not self._get_announce_flag("announce_accessibility"):
            return False
        if not setting_key:
            return True
        return self._get_announce_flag(setting_key)

    def get_announce_file_loaded(self) -> bool: return self._get_announce_flag("announce_file_loaded")

    def set_announce_file_loaded(self, enabled: bool): self._set_announce_flag("announce_file_loaded", enabled)

    def get_announce_playlist_position(self) -> bool: return self._get_announce_flag("announce_playlist_position")

    def set_announce_playlist_position(self, enabled: bool): self._set_announce_flag("announce_playlist_position", enabled)

    def get_announce_resume_position(self) -> bool: return self._get_announce_flag("announce_resume_position")

    def set_announce_resume_position(self, enabled: bool): self._set_announce_flag("announce_resume_position", enabled)

    def get_announce_navigation_blocked(self) -> bool: return self._get_announce_flag("announce_navigation_blocked")

    def set_announce_navigation_blocked(self, enabled: bool): self._set_announce_flag("announce_navigation_blocked", enabled)

    def get_announce_playback_state(self) -> bool: return self._get_announce_flag("announce_playback_state")

    def set_announce_playback_state(self, enabled: bool): self._set_announce_flag("announce_playback_state", enabled)

    def get_announce_volume_changes(self) -> bool: return self._get_announce_flag("announce_volume_changes")

    def set_announce_volume_changes(self, enabled: bool): self._set_announce_flag("announce_volume_changes", enabled)

    def get_announce_mute_toggle(self) -> bool: return self._get_announce_flag("announce_mute_toggle")

    def set_announce_mute_toggle(self, enabled: bool): self._set_announce_flag("announce_mute_toggle", enabled)

    _VALID_SEEK_MODES = ("disabled", "enabled")
    # صفر، ودقيقة، و5، و10، و30 دقيقة - نفس مقادير القفز في البرنامج
    _VALID_SEEK_MIN_SECONDS = (0, 60, 300, 600, 1800)

    def get_announce_seek_mode(self) -> str:
        value = self._data.get("announce_seek_mode", "enabled")
        return value if value in self._VALID_SEEK_MODES else "enabled"

    def set_announce_seek_mode(self, mode: str):
        self._data["announce_seek_mode"] = mode if mode in self._VALID_SEEK_MODES else "enabled"
        self.save()

    def get_announce_seek_feedback(self) -> bool:
        return self.get_announce_seek_mode() != "disabled"

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

    def get_announce_seek_min_seconds(self) -> int:
        try:
            value = int(self._data.get("announce_seek_min_seconds", 0))
        except (TypeError, ValueError):
            return 0
        return value if value in self._VALID_SEEK_MIN_SECONDS else 0

    def set_announce_seek_min_seconds(self, seconds: int):
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            seconds = 0
        self._data["announce_seek_min_seconds"] = (
            seconds if seconds in self._VALID_SEEK_MIN_SECONDS else 0
        )
        self.save()

    def get_announce_time_status(self) -> bool: return self._get_announce_flag("announce_time_status")

    def set_announce_time_status(self, enabled: bool): self._set_announce_flag("announce_time_status", enabled)

    def get_announce_duration_announce(self) -> bool: return self._get_announce_flag("announce_duration_announce")

    def set_announce_duration_announce(self, enabled: bool): self._set_announce_flag("announce_duration_announce", enabled)

    def get_announce_remaining_time(self) -> bool: return self._get_announce_flag("announce_remaining_time")

    def set_announce_remaining_time(self, enabled: bool): self._set_announce_flag("announce_remaining_time", enabled)

    def get_announce_file_info(self) -> bool: return self._get_announce_flag("announce_file_info")

    def set_announce_file_info(self, enabled: bool): self._set_announce_flag("announce_file_info", enabled)

    def get_announce_buffering(self) -> bool: return bool(self._data.get("announce_buffering", False))

    def set_announce_buffering(self, enabled: bool): self._set_announce_flag("announce_buffering", enabled)

    def get_announce_playback_speed(self) -> bool: return self._get_announce_flag("announce_playback_speed")

    def set_announce_playback_speed(self, enabled: bool): self._set_announce_flag("announce_playback_speed", enabled)

    def get_announce_bookmarks(self) -> bool: return self._get_announce_flag("announce_bookmarks")

    def set_announce_bookmarks(self, enabled: bool): self._set_announce_flag("announce_bookmarks", enabled)

    def get_announce_sleep_timer(self) -> bool: return self._get_announce_flag("announce_sleep_timer")

    def set_announce_sleep_timer(self, enabled: bool): self._set_announce_flag("announce_sleep_timer", enabled)

    def get_announce_settings_import_export(self) -> bool: return self._get_announce_flag("announce_settings_import_export")

    def set_announce_settings_import_export(self, enabled: bool): self._set_announce_flag("announce_settings_import_export", enabled)

    def get_announce_fullscreen(self) -> bool: return self._get_announce_flag("announce_fullscreen")

    def set_announce_fullscreen(self, enabled: bool): self._set_announce_flag("announce_fullscreen", enabled)

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

    def get_recorder_default_bit_depth(self) -> int:
        value = int(self._data.get("recorder_default_bit_depth", 16))
        return 32 if value == 32 else 16

    def set_recorder_default_bit_depth(self, bit_depth: int):
        self._data["recorder_default_bit_depth"] = 32 if int(bit_depth) == 32 else 16
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

    # ------------------------------------------------------------------ #
    # مجلدات الحفظ الافتراضية
    # ------------------------------------------------------------------ #
    def _localized_folder_name(self, translation_key: str) -> str:
        lang_strings = STRINGS.get(self.get_language(), STRINGS["ar"])
        return lang_strings.get(translation_key, translation_key)

    # اسم المجلد الرئيسي ثابت لا يتبع لغة الواجهة: تغيير اللغة كان بيفتح
    # مجلدًا جديدًا ويسيب ملفات المستخدم في القديم
    APP_FOLDER_NAME = "مشغل الوسائط الشامل - Omnya"

    def _default_output_folder(self, translation_key: str) -> str:
        return os.path.join(
            get_documents_dir(),
            self.APP_FOLDER_NAME,
            self._localized_folder_name(translation_key),
        )

    def get_converter_output_folder(self) -> str:
        folder = self._data.get("converter_output_folder")
        if not folder:
            folder = self._default_output_folder("folder_name_converted_files")
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            pass
        return folder

    def set_converter_output_folder(self, folder: str):
        self._data["converter_output_folder"] = folder
        self.save()

    def get_recorder_output_folder(self) -> str:
        folder = self._data.get("recorder_output_folder")
        if not folder:
            folder = self._default_output_folder("folder_name_voice_recordings")
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            pass
        return folder

    def set_recorder_output_folder(self, folder: str):
        self._data["recorder_output_folder"] = folder
        self.save()

    # ------------------------------------------------------------------ #
    # حجم النافذة الرئيسية وموضعها
    # ------------------------------------------------------------------ #
    def get_window_geometry(self):
        """(عرض، ارتفاع، س، ص) أو None لو ما اتحفظش قبل كده."""
        stored = self._data.get("window_geometry")
        if not isinstance(stored, (list, tuple)) or len(stored) != 4:
            return None
        try:
            width, height, x, y = (int(value) for value in stored)
        except (TypeError, ValueError):
            return None
        if width < 200 or height < 150:
            return None
        return width, height, x, y

    def set_window_geometry(self, width, height, x, y):
        self._data["window_geometry"] = [int(width), int(height), int(x), int(y)]
        self.save()

    # ------------------------------------------------------------------ #
    # سرعة التشغيل لكل ملف
    # ------------------------------------------------------------------ #
    def get_file_speed(self, path: str) -> float:
        """
        السرعة المحفوظة للملف ده، أو 1.0 لو مفيش.

        السرعة تفضيل بيخص نوع المحتوى لا البرنامج: كتاب صوتي بسرعة 1.5
        وموسيقى بسرعة عادية، والمستخدم ما يعيدش ضبطها كل مرة.
        """
        speeds = self._data.get("file_speeds", {})
        try:
            value = float(speeds.get(path, 1.0))
        except (TypeError, ValueError):
            return 1.0
        return value if _MIN_PLAYBACK_SPEED <= value <= _MAX_PLAYBACK_SPEED else 1.0

    def set_file_speed(self, path: str, speed: float):
        speeds = self._data.setdefault("file_speeds", {})
        value = max(_MIN_PLAYBACK_SPEED, min(_MAX_PLAYBACK_SPEED, float(speed)))
        if abs(value - 1.0) < 0.01:
            speeds.pop(path, None)
        else:
            speeds[path] = value
        # نفس حد المواضع المحفوظة، والأقدم يتشال الأول
        if len(speeds) > _MAX_REMEMBERED_POSITIONS:
            for key in list(speeds)[: len(speeds) - _MAX_REMEMBERED_POSITIONS]:
                speeds.pop(key, None)
        self.save()

    # ------------------------------------------------------------------ #
    # النقاط المرجعية
    # ------------------------------------------------------------------ #
    def get_bookmark_entries(self, path: str):
        """
        العلامات كقائمة من (الثانية، الاسم).

        الإصدارات الأقدم كانت بتخزّن أرقامًا مجردة، فبنقبل الشكلين -
        علامات المستخدم القديمة ما تضيعش لمجرد إننا ضفنا الأسماء.
        """
        entries = []
        for item in self._data.get("bookmarks", {}).get(path, []):
            if isinstance(item, dict):
                try:
                    entries.append((float(item.get("at", 0.0)), str(item.get("name", ""))))
                except (TypeError, ValueError):
                    continue
            else:
                try:
                    entries.append((float(item), ""))
                except (TypeError, ValueError):
                    continue
        entries.sort(key=lambda entry: entry[0])
        return entries

    def get_bookmark_name(self, path: str, seconds: float) -> str:
        for at, name in self.get_bookmark_entries(path):
            if abs(at - seconds) < 0.5:
                return name
        return ""

    def rename_bookmark(self, path: str, seconds: float, name: str) -> bool:
        bookmarks = self._data.setdefault("bookmarks", {})
        points = bookmarks.get(path, [])
        for index, item in enumerate(points):
            at = item.get("at") if isinstance(item, dict) else item
            try:
                at = float(at)
            except (TypeError, ValueError):
                continue
            if abs(at - seconds) < 0.5:
                points[index] = {"at": at, "name": str(name).strip()}
                self.save()
                return True
        return False

    def get_bookmarks(self, path: str):
        """مواضع العلامات فقط - بيمرّ على get_bookmark_entries فبيقبل الشكلين."""
        return [at for at, _name in self.get_bookmark_entries(path)]

    def add_bookmark(self, path: str, seconds: float, name: str = "") -> bool:
        bookmarks = self._data.setdefault("bookmarks", {})
        points = bookmarks.setdefault(path, [])
        existing_seconds = [at for at, _name in self.get_bookmark_entries(path)]
        if any(abs(existing - seconds) < 0.5 for existing in existing_seconds):
            return False
        points.append({"at": float(seconds), "name": str(name).strip()})
        points.sort(key=lambda item: item["at"] if isinstance(item, dict) else item)
        if len(points) > _MAX_BOOKMARKS_PER_FILE:
            points.pop(0)
        self.save()
        return True

    def clear_bookmarks(self, path: str):
        self._data.get("bookmarks", {}).pop(path, None)
        self.save()

    # ------------------------------------------------------------------ #
    # مؤقت النوم
    # ------------------------------------------------------------------ #
    def get_sleep_timer_last_minutes(self) -> int:
        return int(self._data.get("sleep_timer_last_minutes", _DEFAULT_SLEEP_TIMER_MINUTES))

    def set_sleep_timer_last_minutes(self, minutes: int):
        self._data["sleep_timer_last_minutes"] = max(1, int(minutes))
        self.save()

    # ------------------------------------------------------------------ #
    # المعادل
    # ------------------------------------------------------------------ #
    def get_equalizer_mode(self) -> str:
        mode = self._data.get("equalizer_mode", equalizer.MODE_OFF)
        return mode if equalizer.is_valid_mode(mode) else equalizer.MODE_OFF

    def set_equalizer_mode(self, mode: str):
        self._data["equalizer_mode"] = mode if equalizer.is_valid_mode(mode) else equalizer.MODE_OFF
        self.save()

    def get_equalizer_custom(self):
        """(التضخيم المسبق، [عشر قيم]) - دايمًا صالحة ومحصورة في الحدود."""
        preamp = equalizer.clamp_gain(self._data.get("equalizer_custom_preamp", 0.0))
        bands = equalizer.normalize_bands(self._data.get("equalizer_custom_bands"))
        return preamp, bands

    def set_equalizer_custom(self, preamp, bands):
        self._data["equalizer_custom_preamp"] = equalizer.clamp_gain(preamp)
        self._data["equalizer_custom_bands"] = equalizer.normalize_bands(bands)
        self.save()

    def has_equalizer_custom(self) -> bool:
        """هل فيه قيم مخصصة فعلًا (مش كلها أصفار)؟"""
        preamp, bands = self.get_equalizer_custom()
        return any(bands) or bool(preamp)

    def get_announce_equalizer(self) -> bool: return self._get_announce_flag("announce_equalizer")

    def set_announce_equalizer(self, enabled: bool): self._set_announce_flag("announce_equalizer", enabled)

    def get_announce_stream_title(self) -> bool: return self._get_announce_flag("announce_stream_title")

    def set_announce_stream_title(self, enabled: bool): self._set_announce_flag("announce_stream_title", enabled)

    # ------------------------------------------------------------------ #
    # قوائم التشغيل
    # ------------------------------------------------------------------ #
    def get_playlist_last_folder(self) -> str:
        folder = self._data.get("playlist_last_folder") or ""
        return folder if isinstance(folder, str) and os.path.isdir(folder) else ""

    def set_playlist_last_folder(self, folder: str):
        self._data["playlist_last_folder"] = folder or ""
        self.save()

    # ------------------------------------------------------------------ #
    # تصدير واستيراد
    # ------------------------------------------------------------------ #
    def export_to(self, path: str) -> bool:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            return True
        except OSError:
            return False

    def import_from(self, path: str) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(loaded, dict):
            return False
        self._data.update(loaded)
        self.save()
        return True
