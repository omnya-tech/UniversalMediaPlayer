# -*- coding: utf-8 -*-
import contextlib
import json
import logging
import os
import threading

from core import equalizer
from core.logging_setup import get_app_data_dir, get_documents_dir
from core.streams import is_stream_url
from i18n.strings import STRINGS
from core.settings_announcements import AnnouncementSettingsMixin
from core.settings_tools import ToolsSettingsMixin
from core.settings_media import MediaSettingsMixin
from core.settings_media import _DEFAULT_SLEEP_TIMER_MINUTES, _MAX_REMEMBERED_POSITIONS

logger = logging.getLogger(__name__)

_SETTINGS_FILENAME = "settings.json"
_DEFAULT_MAX_RECENT_FILES = 10
_MIN_MAX_RECENT_FILES = 3
_MAX_MAX_RECENT_FILES = 50
_DEFAULT_PLAYBACK_SPEED = 1.0
# حسم المجلدات مرة واحدة حتى لو طُلبت من خيطين معًا (خيط النقل عند البدء والواجهة)
_OUTPUT_FOLDERS_LOCK = threading.Lock()


class Settings(MediaSettingsMixin, ToolsSettingsMixin, AnnouncementSettingsMixin):
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
            # اختصارات محرر الوسائط العامة (gui/editor_hotkeys.py)
            "enable_editor_hotkeys": True,
            "ui_theme": "system",
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

    def get_enable_editor_hotkeys(self) -> bool:
        return bool(self._data.get("enable_editor_hotkeys", True))

    def set_enable_editor_hotkeys(self, enabled: bool):
        self._data["enable_editor_hotkeys"] = bool(enabled)
        self.save()

    # يتبع ويندوز، أو فاتح، أو داكن (gui/theme.py). القيم القديمة: «standard»
    # كان يُعرض فاتحًا، و«high_contrast» صار تلقائيًا (البرنامج يحترم تباين
    # ويندوز العالي في كل مظهر)، فكلاهما يصير «يتبع ويندوز»
    _VALID_UI_THEMES = ("system", "light", "dark")
    _LEGACY_UI_THEMES = {"standard": "system", "high_contrast": "system"}

    def get_ui_theme(self) -> str:
        value = self._data.get("ui_theme", "system")
        value = self._LEGACY_UI_THEMES.get(value, value)
        return value if value in self._VALID_UI_THEMES else "system"

    def set_ui_theme(self, theme: str):
        self._data["ui_theme"] = theme if theme in self._VALID_UI_THEMES else "system"
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
    # مقدار التقديم والإرجاع لكل نوع (الأسهم وحدها، ومع Ctrl وShift وAlt
    # وCtrl+Shift)، بالثواني دائمًا؛ الواجهة تعرض بعضها بالدقائق
    # ------------------------------------------------------------------ #
    SEEK_STEP_DEFAULTS = {"normal": 10, "ctrl": 60, "shift": 300, "alt": 600, "ctrl_shift": 1800}
    # (أقل قيمة، أكبر قيمة) بالثواني
    SEEK_STEP_LIMITS = {"normal": (1, 600), "ctrl": (1, 3600), "shift": (60, 7200),
                        "alt": (60, 7200), "ctrl_shift": (60, 14400)}

    def get_seek_step(self, kind: str) -> int:
        default = self.SEEK_STEP_DEFAULTS[kind]
        low, high = self.SEEK_STEP_LIMITS[kind]
        try:
            value = int(self._data.get(f"seek_step_{kind}", default))
        except (TypeError, ValueError):
            return default
        return value if low <= value <= high else default

    def set_seek_step(self, kind: str, seconds: int):
        low, high = self.SEEK_STEP_LIMITS[kind]
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            seconds = self.SEEK_STEP_DEFAULTS[kind]
        self._data[f"seek_step_{kind}"] = max(low, min(high, seconds))
        self.save()

    # ------------------------------------------------------------------ #
    # مجلدات الحفظ الافتراضية
    # ------------------------------------------------------------------ #
    # المجلدات بلغة البرنامج وقت إنشائها أول مرة، ثم تُحفظ ولا تتغير أبدًا
    # (output_folders في الإعدادات). تغيير الاسم مع كل تغيير للغة كان سيكسر
    # العلامات ومواضع الاستكمال وقوائم التشغيل المحفوظة (مساراتها كاملة)،
    # ويفشل في منتصفه لو ملف مفتوح؛ وتبعيتها للغة في الإصدارات السابقة
    # صنعت نسخًا مكررة («تسجيلات صوتية» و«Voice Recordings»)
    OUTPUT_FOLDER_NAMES = {
        "ar": {
            "root": "مشغل الوسائط الشامل - Omnya",
            "recordings": ("التسجيلات",),
            "converted": ("الملفات المحولة",),
            "editor_audio": ("محرر الوسائط", "صوت"),
            "editor_video": ("محرر الوسائط", "فيديو"),
        },
        "en": {
            "root": "Universal Media Player",
            "recordings": ("Recordings",),
            "converted": ("Converted Files",),
            "editor_audio": ("Media Editor", "Audio"),
            "editor_video": ("Media Editor", "Video"),
        },
    }
    OUTPUT_KINDS = ("recordings", "converted", "editor_audio", "editor_video")

    # المجلد الرئيسي للإصدارات السابقة: من وُجد عنده يكمل فيه كما هو
    LEGACY_APP_FOLDER = "مشغل الوسائط الشامل - Omnya"
    # مجلدات الإصدارات السابقة الفرعية؛ ما فيها يُنقل للجديدة مرة واحدة
    LEGACY_OUTPUT_FOLDERS = {
        "recordings": ("تسجيلات صوتية", "Voice Recordings"),
        "converted": ("ملفات محوّلة", "Converted Files"),
    }
    # مجلدات رئيسية صنعها المحوّل بالخطأ في إصدارات سابقة (بلا «- Omnya»)
    STRAY_APP_FOLDERS = ("مشغل الوسائط الشامل", "Universal Media Player")

    def _known_folder_names(self):
        names = set()
        for table in self.OUTPUT_FOLDER_NAMES.values():
            for kind in self.OUTPUT_KINDS:
                names.update(table[kind])
        for legacy in self.LEGACY_OUTPUT_FOLDERS.values():
            names.update(legacy)
        return names

    def _is_our_folder(self, path):
        """
        مجلد صنعه البرنامج: كل ما فيه مجلدات بأسماء مجلداته.

        «Universal Media Player» في المستندات قد يكون مجلدًا للمستخدم لا
        علاقة له بالبرنامج (على جهاز التطوير هو مجلد المشروع نفسه)؛ فيه
        أي شيء آخر يعني أنه ليس لنا، فلا يُمس ويأخذ مجلدنا رقمًا.
        """
        try:
            entries = os.listdir(path)
        except OSError:
            return False
        known = self._known_folder_names()
        return all(name in known and os.path.isdir(os.path.join(path, name)) for name in entries)

    def resolve_output_folders(self) -> dict:
        """
        المجلد الرئيسي وأسماء الفرعية، تُحسم أول مرة وتُحفظ.

        بلغة البرنامج ساعتها. من عنده مجلد الإصدارات السابقة يكمل فيه. ولو
        الاسم مأخوذ بمجلد ليس للبرنامج يُضاف رقم: «Universal Media Player 1».
        """
        with _OUTPUT_FOLDERS_LOCK:
            stored = self._data.get("output_folders")
            if isinstance(stored, dict) and isinstance(stored.get("root"), str) and all(
                    isinstance(stored.get(kind), list) and stored[kind] for kind in self.OUTPUT_KINDS):
                return stored

            names = self.OUTPUT_FOLDER_NAMES["en" if self.get_language() == "en" else "ar"]
            documents = get_documents_dir()
            legacy = os.path.join(documents, self.LEGACY_APP_FOLDER)
            if os.path.isdir(legacy):
                root = legacy
            else:
                base = os.path.join(documents, names["root"])
                root, number = base, 1
                while os.path.exists(root) and not self._is_our_folder(root):
                    root = f"{base} {number}"
                    number += 1
            resolved = {"root": root}
            resolved.update({kind: list(names[kind]) for kind in self.OUTPUT_KINDS})
            self._data["output_folders"] = resolved
            self.save()
            return resolved

    def _default_output_folder(self, kind: str) -> str:
        resolved = self.resolve_output_folders()
        return os.path.join(resolved["root"], *resolved[kind])

    def _legacy_roots(self):
        """المجلدات الرئيسية التي قد تحوي مجلدات الإصدارات السابقة."""
        documents = get_documents_dir()
        roots = [os.path.join(documents, self.LEGACY_APP_FOLDER)]
        for name in self.STRAY_APP_FOLDERS:
            path = os.path.join(documents, name)
            if os.path.isdir(path) and self._is_our_folder(path):
                roots.append(path)
        return roots

    def _is_legacy_default(self, folder: str, kind: str) -> bool:
        """مجلد محفوظ هو افتراضي قديم لا اختيار من المستخدم."""
        wanted = os.path.normcase(os.path.normpath(folder))
        return any(wanted == os.path.normcase(os.path.normpath(os.path.join(root, name)))
                   for root in self._legacy_roots()
                   for name in self.LEGACY_OUTPUT_FOLDERS.get(kind, ()))

    def _output_folder(self, setting_key: str, kind: str) -> str:
        folder = self._data.get(setting_key)
        if not folder or self._is_legacy_default(folder, kind):
            folder = self._default_output_folder(kind)
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            pass
        return folder

    def get_editor_output_folder(self, is_video: bool) -> str:
        """مجلد محرر الوسائط: «صوت» أو «فيديو» حسب الملف."""
        folder = self._default_output_folder("editor_video" if is_video else "editor_audio")
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError:
            pass
        return folder

    def migrate_legacy_output_folders(self) -> int:
        """
        ينقل ما في مجلدات الإصدارات السابقة إلى المجلدات الحالية، مرة واحدة.

        الملف لا يُكتب فوق ملف بنفس الاسم: يأخذ رقمًا. والمجلد القديم
        يُحذف فقط لو فرغ تمامًا، وكذلك المجلد الرئيسي الذي صنعه المحوّل
        بالخطأ. يرجع عدد ما نُقل.
        """
        current_root = os.path.normcase(os.path.normpath(self.resolve_output_folders()["root"]))
        moved = 0
        roots = self._legacy_roots()
        for kind, names in self.LEGACY_OUTPUT_FOLDERS.items():
            target = self._default_output_folder(kind)
            for root in roots:
                for name in names:
                    old = os.path.join(root, name)
                    if not os.path.isdir(old) or os.path.normcase(os.path.normpath(old)) == \
                            os.path.normcase(os.path.normpath(target)):
                        continue
                    try:
                        os.makedirs(target, exist_ok=True)
                        for entry in os.listdir(old):
                            destination = os.path.join(target, entry)
                            base, ext = os.path.splitext(entry)
                            counter = 2
                            while os.path.exists(destination):
                                destination = os.path.join(target, f"{base} ({counter}){ext}")
                                counter += 1
                            os.replace(os.path.join(old, entry), destination)
                            moved += 1
                        os.rmdir(old)
                    except OSError:
                        # ملف مفتوح في برنامج آخر مثلًا: يبقى، وتُعاد المحاولة
                        # في المرة القادمة
                        continue
        for root in roots:
            if os.path.normcase(os.path.normpath(root)) == current_root:
                continue
            try:
                if not os.listdir(root):
                    os.rmdir(root)
            except OSError:
                pass
        return moved

    def get_converter_output_folder(self) -> str:
        return self._output_folder("converter_output_folder", "converted")

    def set_converter_output_folder(self, folder: str):
        self._data["converter_output_folder"] = folder
        self.save()

    def get_recorder_output_folder(self) -> str:
        return self._output_folder("recorder_output_folder", "recordings")

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


def default_output_folder(kind: str) -> str:
    """مسار مجلد حفظ من إعدادات المستخدم: recordings أو converted أو editor_audio أو editor_video."""
    return Settings()._default_output_folder(kind)
