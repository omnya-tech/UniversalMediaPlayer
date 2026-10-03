# -*- coding: utf-8 -*-
import logging
import os
import sys
import threading
import time

logger = logging.getLogger("omnya.engine")

def _locate_bundled_vlc_dir():
    candidates = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(os.path.join(meipass, "resources", "vlc"))
        candidates.append(os.path.join(os.path.dirname(sys.executable), "resources", "vlc"))
    else:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        candidates.append(os.path.join(project_root, "resources", "vlc"))

    for candidate in candidates:
        if os.path.isfile(os.path.join(candidate, "libvlc.dll")):
            return candidate
    return None

def _setup_bundled_libvlc():
    if sys.platform != "win32":
        return
    vlc_dir = _locate_bundled_vlc_dir()
    if vlc_dir is None:
        return
    os.environ["PYTHON_VLC_LIB_PATH"] = os.path.join(vlc_dir, "libvlc.dll")
    os.environ["PYTHON_VLC_MODULE_PATH"] = vlc_dir
    plugins_dir = os.path.join(vlc_dir, "plugins")
    if os.path.isdir(plugins_dir):
        os.environ["VLC_PLUGIN_PATH"] = plugins_dir
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(vlc_dir)
        except OSError:
            pass

# عدد خيوط القراءة المسبقة: أكثر من ذلك لا يسرّع القرص ويزاحم الواجهة
_PLUGIN_PRELOAD_THREADS = 8


def _lower_current_thread_priority():
    """
    ينزّل أولوية الخيط الحالي تحت العادي.

    خيوط القراءة بتتنافس مع الخيط اللي بيبني النافذة على أربع أنوية.
    من غير ده، التسخين - وهو تحسين خلفي - بيأخّر الحاجة اللي المستخدم
    قاعد يستناها فعلًا.

    بيفشل بهدوء على غير ويندوز أو لو النداء مرفوض: الأولوية تحسين لا شرط.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes

        THREAD_PRIORITY_BELOW_NORMAL = -1
        kernel32 = ctypes.windll.kernel32
        # الأنواع صريحة: المقبض الافتراضي int بـ32 بت، والمقبض الوهمي
        # للخيط الحالي (-2) بيتقصّ على ويندوز 64 بت.
        # (بلا ده النداء بيرجّع خطأ ولا بيغيّر حاجة)
        kernel32.GetCurrentThread.restype = wintypes.HANDLE
        kernel32.SetThreadPriority.argtypes = [wintypes.HANDLE, ctypes.c_int]
        kernel32.SetThreadPriority.restype = wintypes.BOOL

        kernel32.SetThreadPriority(kernel32.GetCurrentThread(),
                                   THREAD_PRIORITY_BELOW_NORMAL)
    except Exception:
        pass


def _read_file(path, limit=None):
    # يقرأ الملف (أو أول limit بايت منه) ويرمي المحتوى؛ المقصود الكاش لا البيانات
    try:
        with open(path, "rb") as handle:
            size = 0
            while limit is None or size < limit:
                chunk = handle.read(1 << 20 if limit is None else min(1 << 20, limit - size))
                if not chunk:
                    break
                size += len(chunk)
            return size
    except OSError:
        return 0


def _preload_plugin_files(plugins_dir):
    """
    يقرأ ملفات إضافات VLC بالتوازي عشان تدخل كاش نظام الملفات.

    السبب: libvlc بيفحص الإضافات **متسلسلة** عند التهيئة، وكل ملف
    بيتفتح بيمر على الحماية اللحظية في ديفندر. سجل مستخدم وصل 13 ثانية،
    والتفصيل أثبت إن تحميل libvlc.dll نفسها 237 مللي ثانية بس والباقي
    كله في فحص الإضافات. وبيتكرر كل ما البرنامج يتفتح بعد خمول طويل،
    لأن ويندوز بيطلّع الملفات من الكاش فيرجع ديفندر يشوفها من أول وجديد.
    نفس الجلسة بعد دقيقة: 417 مللي ثانية.

    وكاش VLC نفسه مش هو المشكلة: --reset-plugins-cache فرقه في حدود
    الضوضاء، يعني الملفات بتتقري على أي حال.

    القراءة المتوازية بتخلي ديفندر يفحص أكتر من ملف في نفس الوقت بدل
    ما يقف على واحد واحد ورا libvlc.

    وبنقرا دايمًا، بلا محاولة نخمّن الكاش دافي ولا بارد.

    كانت فيه نسخة بتقيس عيّنة الأول وتسيب لو الكاش دافي. فشلت عند
    مستخدم: حكمت "دافي" والتهيئة بعدها خدت 22 ثانية. السبب إن ملف
    العيّنة (libavcodec) بيتقري كتير فبيفضل في الكاش، بينما مئات
    الملفات التانية بردت.

    والمقايضة أصلًا كانت مقلوبة: القراءة الزيادة لما الكاش دافي بتكلّف
    نص ثانية **في الخيط الخلفي** - المستخدم ما بيحسّش بيها لأن الواجهة
    ظهرت خلاص. والقراءة الناقصة لما يكون بارد بتكلّفه عشرين ثانية
    واقف مستني. نص ثانية مخفية أرخص من احتمال عشرين ثانية ظاهرة.
    """
    from concurrent.futures import ThreadPoolExecutor

    files = []
    for root, _dirs, names in os.walk(plugins_dir):
        for name in names:
            if name.endswith(".dll"):
                files.append(os.path.join(root, name))
    if not files:
        return 0

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=_PLUGIN_PRELOAD_THREADS,
                            initializer=_lower_current_thread_priority) as pool:
        total = sum(pool.map(_read_file, files))
    elapsed = time.perf_counter() - started
    speed = (total / (1 << 20)) / elapsed if elapsed > 0 else 0
    logger.info("قراءة مسبقة لإضافات VLC: %d ملف، %.0f ميجا في %.0f م.ث (%.0f ميجا/ث)",
                len(files), total / (1 << 20), elapsed * 1000, speed)
    return len(files)


# vlc تُحمَّل عند أول احتياج لا عند الاستيراد: استيرادها وحده كان ياخد
# ثواني قبل ما النافذة تظهر. شوف _load_vlc.
vlc = None
_HAS_VLC = None


def _load_vlc() -> bool:
    """يحمّل vlc عند أول احتياج. يرجّع هل هي متاحة."""
    global vlc, _HAS_VLC
    if _HAS_VLC is not None:
        return _HAS_VLC
    _setup_bundled_libvlc()
    try:
        import vlc as _vlc_module
        vlc = _vlc_module
        _HAS_VLC = True
    except ImportError:
        _HAS_VLC = False
    return _HAS_VLC

class PlaybackState:
    STOPPED = "stopped"
    LOADING = "loading"
    PLAYING = "playing"
    PAUSED = "paused"
    ENDED = "ended"
    ERROR = "error"

class PlayerEngine:
    _PARSE_TIMEOUT_MS = 3000

    # كتم الصوت حوالين القفزة: libvlc بيطلّع كسرة صوت من الموضع القديم
    # قبل ما يوصل للجديد. الكتم بيتشال أول ما الموضع يتحرك فعلًا
    # (شوف _unmute_when_settled)، بحد أدنى يمنع الكسرة وحد أقصى يمنع
    # إن الصوت يفضل مكتوم لو الموضع ما اتحركش.
    #
    # القيم القديمة كانت ثابتة 150 مللي ثانية - صمت مسموع بعد كل ضغطة
    # سهم، والمستخدم اللي بيقدّم كتير بيسمع البرنامج "بيقطّع".
    # القياس: الموضع الجديد بيوصل في أقل من 30 مللي ثانية في الغالب.
    #
    # بالمللي ثانية.
    # (الحد الأقصى للملفات البطيئة على الشبكة)
    # (والأدنى للسرعات العالية)
    _SEEK_MUTE_MIN_MS = 12
    _SEEK_MUTE_MAX_MS = 60

    # محاولات تهيئة libvlc قبل الاستسلام: فشل عابر (ملف إضافة مقفول من
    # برنامج حماية مثلًا) بيتحل بمحاولة تانية، لكن فشل دائم ما ينفعش
    # يتكرر مع كل ملف ويأخّر كل فتح.
    #
    # (الرسالة بتتعرض مرة لكل محاولة)
    _MAX_INIT_ATTEMPTS = 3

    # فيه فتح شغّال دلوقتي؟ الواجهة بتسأل عشان ما تعتبرش "متوقف" أثناء
    # التحميل حالة نهاية ملف.
    # متعرّف في الصنف كمان عشان أي نسخة اتعملت بطريقة غير معتادة
    # (اختبارات مثلًا) يكون عندها القيمة.
    _is_opening = False

    def __init__(self, on_video_frame=None, on_state_change=None, on_error=None, tr=None):
        self.on_video_frame = on_video_frame
        self.on_state_change = on_state_change
        self.on_error = on_error
        self.tr = tr

        self._video_hwnd = None
        self._state = PlaybackState.STOPPED
        self._muted = False
        self._instance = None
        self._player = None
        self._media = None
        self._has_video_cached = False
        self._real_bit_rate = None
        self._pending_seek_target = None
        self._pending_playing_seek = None
        self._seek_lock = threading.Lock()
        self._stop_lock = threading.Lock()

        # نافذة الكتم بعد القفزة: الصوت يرجع بعد الحد الأدنى لو الموضع
        # وصل، وبعد الحد الأقصى في كل الأحوال
        self._unmute_floor = 0.0
        self._unmute_deadline = 0.0
        self._unmute_timer = None

        # المدة المعروفة آخر مرة: libvlc بترجّع صفرًا لحظات أثناء
        # القفز وتغيير الملف، والواجهة كانت بتعرض "00:00" وتعلنها.
        # (شوف duration)
        self._duration_cache = 0.0

        # الصوت والسرعة محفوظين هنا لأن المشغّل نفسه بيتعمل متأخر:
        # أي ضبط قبل وجوده كان بيضيع.
        self._volume = 1.0
        self._speed = 1.0
        self._init_attempts = 0
        self._init_error = None
        self._init_lock = threading.Lock()
        self._play_requested_at = None
        self._is_opening = False

    def _message(self, key, fallback, **kwargs):
        """نص مترجَم لو المترجِم متاح، وإلا النص العربي الاحتياطي."""
        if self.tr is not None:
            try:
                return self.tr.t(key, **kwargs)
            except Exception:
                pass
        return fallback.format(**kwargs) if kwargs else fallback

    def _report_init_failure(self, message):
        """
        يوصّل فشل التهيئة للمستخدم.

        كل مسارات الفشل في _ensure_player كانت بترجّع False بلا كلمة،
        و open بترجّع False فوقها بلا كلمة كمان - فالمستخدم يشوف الواجهة
        مفتوحة، بلا صوت ولا بيانات ولا سبب.
        """
        logger.error("%s", message)
        if self.on_error:
            self.on_error(message)

    def release(self):
        """يسيب موارد libvlc. للاستعمال الصامت (--warmup) اللي بيخرج فورًا."""
        player, instance = self._player, self._instance
        self._player = self._instance = self._media = None
        for handle in (player, instance):
            if handle is None:
                continue
            try:
                handle.release()
            except Exception:
                pass

    @property
    def is_ready(self) -> bool:
        """هل المحرك جاهز دلوقتي، من غير ما ننتظر تجهيزه."""
        # من غير قفل: قراءة مؤشر واحد ذرّية، والإجابة تقريبية بطبيعتها
        return self._player is not None

    def warm_up(self):
        """
        يبدأ تهيئة المشغّل في الخلفية.

        التأجيل لأول ملف خلّى الواجهة تظهر بسرعة، لكنه نقل الانتظار
        لأول فتح: المستخدم يشوف النافذة جاهزة ويستنى الملف. الخيط ده
        بيدفع التكلفة وقت ما المستخدم بيدوّر على ملفه أصلًا، فالاتنين
        بيبقوا سريعين.

        آمن لو الفتح سبقه: _ensure_player متزامنة بقفل.
        """
        logger.info("بدء تجهيز المحرك في الخلفية")
        worker = threading.Thread(target=self._warm_up_worker, daemon=True)
        worker.start()

    def _warm_up_worker(self):
        """
        القراءة المسبقة ثم التهيئة، في نفس الخيط.

        الترتيب مقصود: القراءة المتوازية بتحطّ الملفات في كاش النظام،
        وبعدها فحص libvlc المتسلسل بيلاقيها جاهزة. العكس مالوش معنى.

        والخيط كله بأولوية أقل من العادي: بناء النافذة شغل المستخدم
        قاعد يستناه، والتسخين لأ.
        """
        _lower_current_thread_priority()
        try:
            # المسار بيتضبط في _setup_bundled_libvlc، اللي بتتنادى من
            # _load_vlc - يعني ممكن لسه ما اتنادتش
            plugins_dir = os.environ.get("VLC_PLUGIN_PATH")
            if not plugins_dir:
                _setup_bundled_libvlc()
                plugins_dir = os.environ.get("VLC_PLUGIN_PATH")
            if plugins_dir and os.path.isdir(plugins_dir):
                _preload_plugin_files(plugins_dir)
        except Exception as exc:
            # تحسين لا شرط: لو فشلت القراءة، التهيئة بتكمّل عادي
            logger.warning("القراءة المسبقة للإضافات فشلت: %s", exc)

        self._ensure_player()

    def _ensure_player(self) -> bool:
        """
        بيعمل نسخة VLC عند أول احتياج فعلي.

        مؤجّل عن قصد: vlc.Instance بتاخد ~90 مللي ثانية (بتهيّئ libvlc
        وتفحص الإضافات)، وكانت بتتدفع أثناء بناء النافذة الرئيسية فتأخّر
        ظهورها. أول فتح لملف بيحصل في خيط خلفي أصلاً (شوف _load_and_play
        في gui/main_window.py)، فالتكلفة دي بقت برّه خيط الواجهة تمامًا -
        و warm_up بتدفعها قبل ما المستخدم يطلب ملف.

        القفل ضروري: warm_up والفتح ممكن يتلاقوا، ومن غيره بيتعمل
        نسختين VLC والتانية بتدهس الأولى.
        """
        if self._player is not None:
            return True

        with self._init_lock:
            if self._player is not None:
                return True
            return self._create_player()

    def _create_player(self) -> bool:
        """التهيئة الفعلية. بتتنادى تحت القفل وحدها."""
        started = time.perf_counter()

        # تحميل libvlc نفسها منفصل عن إنشاء النسخة، عشان السجل يقول
        # أنهي جزء هو البطيء
        load_started = time.perf_counter()

        # بعد المحاولات المسموحة ما بنحاولش تاني: كل محاولة فاشلة
        # بتاخد ثواني، وتكرارها مع كل ملف بيجمّد البرنامج.
        # والرسالة بتوصل للمستخدم بدل الصمت.
        if not _load_vlc():
            self._report_init_failure(self._message(
                "engine_err_vlc_missing", "تعذّر تحميل مشغّل الوسائط (libvlc). أعد تثبيت البرنامج."))
            return False

        if self._init_attempts >= self._MAX_INIT_ATTEMPTS:
            self._report_init_failure(self._init_error or self._message(
                "engine_err_player_unavailable", "مشغّل الوسائط غير متاح."))
            return False
        self._init_attempts += 1
        load_ms = (time.perf_counter() - load_started) * 1000
        instance_started = time.perf_counter()

        try:
            self._instance = vlc.Instance(
                "--quiet",
                "--no-video-title-show",
                "--avcodec-hw=any",
                "--no-sub-autodetect-file",
                "--no-stats",
                "--no-osd",
                "--demux=any",
                "--input-fast-seek",
                # الملفات المحلية مش محتاجة 300 مللي ثانية تخزين مؤقت
                # (القيمة الافتراضية): كل قفزة كانت بتستنى المخزن يتملي
                # قبل ما الصوت يرجع.
                # 200 كفاية لأقراص الشبكة البطيئة، وأسرع بشكل محسوس
                # في التقديم المتكرر.
                "--file-caching=200",
            )
            self._player = self._instance.media_player_new()
        except Exception as exc:
            self._instance = None
            self._player = None
            # الرسالة بتتحفظ عشان المحاولات اللي بعد الحد تعرض السبب
            # الحقيقي بدل رسالة عامة
            self._init_error = self._message(
                "engine_err_player_init", "تعذّر تجهيز مشغّل الوسائط: {error}", error=exc)
            self._report_init_failure(self._init_error)
            return False

        self._init_error = None

        self._attach_events()
        self._apply_audio_settings()
        if self._video_hwnd is not None:
            self.set_video_widget_handle(self._video_hwnd)

        logger.info(
            "تجهيز محرك VLC %.0f م.ث [تحميل المكتبة %.0f، إنشاء النسخة %.0f]",
            (time.perf_counter() - started) * 1000,
            load_ms,
            (time.perf_counter() - instance_started) * 1000,
        )
        return True

    def _apply_audio_settings(self):
        """
        يطبّق الصوت والكتم والسرعة المخزّنين على المشغّل.

        بيتنادى مرتين عن قصد: عند إنشاء المشغّل، وتاني بعد set_media -
        لأن libvlc بيتجاهل audio_set_volume قبل ما يبقى فيه وسائط مضبوطة،
        فالمستوى كان بيرجع 100% مهما كان المحفوظ في الإعدادات.
        """
        if self._player is None:
            return
        try:
            self._player.audio_set_volume(int(round(self._volume * 100)))
            self._player.audio_set_mute(self._muted)
            self._player.set_rate(self._speed)
        except Exception:
            # فشل الضبط مش سبب يوقف التشغيل: الملف يشتغل بالقيم
            # الافتراضية أحسن من إنه ما يشتغلش.
            # بس لازم يتسجّل، لأن الصوت اللي بيرجع 100% فجأة
            # شكوى مستخدم حقيقية.
            logger.exception("فشل تطبيق إعدادات الصوت على المشغّل")

    def _attach_events(self):
        events = self._player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerPlaying, self._on_vlc_playing)
        events.event_attach(vlc.EventType.MediaPlayerPaused, self._on_vlc_paused)
        events.event_attach(vlc.EventType.MediaPlayerStopped, self._on_vlc_stopped)
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_vlc_end_reached)
        events.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._on_vlc_error)
        events.event_attach(vlc.EventType.MediaPlayerBuffering, self._on_vlc_buffering)
        events.event_attach(vlc.EventType.MediaPlayerTimeChanged, self._on_vlc_time_changed)

    def _set_state(self, state):
        self._state = state
        if self.on_state_change:
            self.on_state_change(state)

    def _ensure_audio_track_active(self):
        if self._player is None:
            return
        try:
            current_track = self._player.audio_get_track()
            if current_track in (-1, 0):
                tracks = self._player.audio_get_track_description()
                if tracks:
                    for track_id, track_name in tracks:
                        if track_id > 0:
                            self._player.audio_set_track(track_id)
                            break
        except Exception as exc:
            logger.debug(f"Audio track auto-selection failed: {exc}")

    def _on_vlc_playing(self, event):
        requested = getattr(self, "_play_requested_at", None)
        if requested is not None:
            self._play_requested_at = None
            logger.info("بدء الإخراج الصوتي %.0f م.ث بعد الطلب",
                        (time.perf_counter() - requested) * 1000)
        self._set_state(PlaybackState.PLAYING)
        self._ensure_audio_track_active()
        if self._pending_playing_seek is not None:
            target = self._pending_playing_seek
            self._pending_playing_seek = None
            threading.Thread(target=self.seek, args=(target,), daemon=True).start()

    def _on_vlc_paused(self, event):
        self._set_state(PlaybackState.PAUSED)

    def _on_vlc_stopped(self, event):
        self._set_state(PlaybackState.STOPPED)

    def _on_vlc_end_reached(self, event):
        self._set_state(PlaybackState.ENDED)

    def _on_vlc_buffering(self, event):
        if self._state not in (PlaybackState.PLAYING, PlaybackState.PAUSED):
            self._set_state(PlaybackState.LOADING)

    def _on_vlc_time_changed(self, event):
        if self._pending_seek_target is None or self._player is None:
            return
        current_ms = self._player.get_time()
        if current_ms is None or current_ms < 0:
            return
        if abs(current_ms - self._pending_seek_target * 1000) < 400:
            self._pending_seek_target = None

    def _on_vlc_error(self, event):
        self._set_state(PlaybackState.ERROR)
        if self.on_error:
            self.on_error("Playback error occurred in VLC")

    def set_video_widget_handle(self, handle: int):
        self._video_hwnd = handle
        if self._player is None:
            return
        if sys.platform == "win32":
            self._player.set_hwnd(handle)
        elif sys.platform == "darwin":
            self._player.set_nsobject(handle)
        else:
            self._player.set_xwindow(handle)

    def _parse_media_bounded(self, media) -> bool:
        media.parse_with_options(vlc.MediaParseFlag.local, self._PARSE_TIMEOUT_MS)
        deadline = time.monotonic() + (self._PARSE_TIMEOUT_MS / 1000.0) + 0.5
        while time.monotonic() < deadline:
            status = media.get_parsed_status()
            if status in (
                vlc.MediaParsedStatus.done,
                vlc.MediaParsedStatus.failed,
                vlc.MediaParsedStatus.timeout,
            ):
                return status == vlc.MediaParsedStatus.done
            time.sleep(0.02)
        return False

    def open(self, path: str) -> bool:
        # كل مرحلة بتتقاس وبتتسجّل في سطر واحد: شكوى "الفتح بطيء" من
        # مستخدم ما كانش ليها أي أثر في السجل، فما كانش فيه طريقة نعرف
        # أنهي جزء هو البطيء.
        marks = {}
        started = time.perf_counter()

        if not self._ensure_player():
            return False
        marks["تجهيز المحرك"] = time.perf_counter() - started

        # الواجهة بتسأل عن المدة طول الوقت (مؤقّت التحديث، وإعلانات
        # الموضع). أثناء الفتح libvlc بترجّع طول الملف القديم أو صفر،
        # والمخزَّن بيتصفّر هنا - فالسؤال وقتها كان بيخزّن طول الملف
        # القديم للملف الجديد.
        #
        # العلامة دي بتخلّي duration ترجّع صفر لحد ما الفتح يخلص.
        # (والـ try/finally بيضمن إنها ما تفضلش مرفوعة لو حصل استثناء)
        self._is_opening = True
        try:
            return self._open_locked(path, marks, started)
        finally:
            # حتى لو الفتح فشل: العلامة المرفوعة كانت هتخلّي المدة صفر
            # للأبد
            self._is_opening = False

    def _open_locked(self, path, marks, started):
        stage = time.perf_counter()
        self._stop_now()
        marks["إيقاف السابق"] = time.perf_counter() - stage
        self._duration_cache = 0.0

        # الملف المحذوف أو على قرص اتفصل: libvlc بتقبله ثم تفشل بصمت،
        # فالمستخدم يسمع سكوت. الفحص هنا بيدّي رسالة واضحة.
        # (الروابط مستثناة: مالهاش وجود على القرص)
        if "://" not in path and not os.path.exists(path):
            if self.on_error:
                self.on_error(f"الملف غير موجود: {path}")
            return False

        try:
            stage = time.perf_counter()
            media = self._instance.media_new(path)
            parsed_ok = self._parse_media_bounded(media)
            marks["تحليل الملف"] = time.perf_counter() - stage
        except Exception as exc:
            if self.on_error:
                self.on_error(str(exc))
            return False

        # ملف تالف أو مش وسائط أصلًا: التحليل بيفشل، والتشغيل بعده
        # كان بيعدّي بصمت. (الروابط ممكن تفشل في التحليل وتشتغل عادي،
        # فمستثناة)
        if not parsed_ok and "://" not in path:
            if self.on_error:
                self.on_error(f"تعذّر قراءة الملف: {path}")
            return False
        self._media = media
        stage = time.perf_counter()
        self._has_video_cached = self._detect_has_video(media)
        self._real_bit_rate = self._probe_real_bit_rate(path, media.get_duration())
        marks["قراءة الخصائص"] = time.perf_counter() - stage

        stage = time.perf_counter()
        self._player.set_media(media)
        self._apply_audio_settings()
        if self._video_hwnd is not None:
            self.set_video_widget_handle(self._video_hwnd)
        marks["تسليم المشغّل"] = time.perf_counter() - stage

        total = time.perf_counter() - started
        logger.info(
            "فتح الملف %.0f م.ث [%s]",
            total * 1000,
            "، ".join(f"{name} {value * 1000:.0f}" for name, value in marks.items()),
        )
        return True

    @staticmethod
    def _probe_real_bit_rate(path, duration_ms):
        """
        معدل البت من حجم الملف ومدته.

        كان بينادي probe_media_info، وهي بتستورد PyAV - يعني 63 ميجا من
        مكتبات FFmpeg بتتحمّل من القرص عند أول فتح ملف، عشان رقم واحد
        بيتقال في الإعلان الصوتي وبس. ده كان بيخلي أول ملف ياخد ثواني
        بينما الواجهة ظاهرة من زمان، وأسوأ ما يكون على قرص بارد أو مع
        مضاد فيروسات بيفحص الملفات.

        الحساب هنا فوري وبلا أي مكتبة. وهو كمان أصدق مع الترميز متغيّر
        المعدل (VBR): بيقيس اللي في الملف فعلًا، لا الرقم الاسمي المكتوب
        في الترويسة.
        """
        if not duration_ms or duration_ms <= 0:
            return None
        try:
            size = os.path.getsize(path)
        except OSError:
            return None
        if size <= 0:
            return None
        return int(size * 8 / (duration_ms / 1000.0))

    @staticmethod
    def _detect_has_video(media) -> bool:
        try:
            tracks = media.tracks_get()
        except Exception:
            return False
        if not tracks:
            return False
        return any(getattr(track, "type", None) == vlc.TrackType.video for track in tracks)

    def play(self):
        if self._player is not None:
            # بيتسجّل وقت الطلب عشان _on_vlc_playing تقيس الفرق: ده اللي
            # المستخدم بيحس بيه فعلًا (من الضغطة لحد ما يسمع)، مش وقت
            # الفتح بس
            self._play_requested_at = time.perf_counter()
            self._player.play()

    def pause(self):
        if self._player is not None:
            self._player.set_pause(1)

    def resume(self):
        if self._player is not None:
            self._player.set_pause(0)

    def toggle_play_pause(self):
        if self._state == PlaybackState.PLAYING:
            self.pause()
        else:
            self.play()

    def stop(self):
        """
        إيقاف سريع الاستجابة.

        libvlc 3 مافيهاش stop_async، و player.stop() بتحجب ~1.3 ثانية وهي
        بتنهي خيوط فك الترميز - وده تجمّد محسوس لمستخدم دايس زرار الإيقاف.
        الحالة بتتحدث فورًا والإيقاف الفعلي بيكمّل في الخلفية.
        """
        self._pending_seek_target = None
        self._set_state(PlaybackState.STOPPED)

        player = self._player
        if player is None:
            return
        threading.Thread(
            target=self._stop_player_blocking, args=(player,), daemon=True
        ).start()

    def _stop_player_blocking(self, player):
        # القفل بيمنع إيقافين متزامنين على نفس المشغّل
        with self._stop_lock:
            try:
                player.stop()
            except Exception:
                pass

    def _stop_now(self):
        """إيقاف متزامن - للاستخدام الداخلي قبل تحميل وسائط جديدة."""
        self._pending_seek_target = None
        self._set_state(PlaybackState.STOPPED)
        if self._player is not None:
            with self._stop_lock:
                try:
                    self._player.stop()
                except Exception:
                    pass

    def seek(self, seconds: float):
        if self._player is None:
            return
        duration = self.duration
        clamped = max(0.0, min(seconds, duration)) if duration else max(0.0, seconds)
        self._pending_seek_target = clamped

        with self._seek_lock:
            try:
                self._player.audio_set_mute(True)
            except Exception:
                pass

            self._player.set_time(int(clamped * 1000))

            # خيط واحد بيراقب: الضغطات المتتابعة بتمدّ النافذة بس، بدل
            # ما كل ضغطة تعمل خيط يفك الكتم في وقت مختلف
            # (وده كان بيطلّع كسرات صوت بين الضغطات)
            now = time.monotonic()
            self._unmute_floor = now + self._SEEK_MUTE_MIN_MS / 1000.0
            self._unmute_deadline = now + self._SEEK_MUTE_MAX_MS / 1000.0
            if self._unmute_timer is None or not self._unmute_timer.is_alive():
                self._unmute_timer = threading.Thread(
                    target=self._unmute_when_settled, daemon=True
                )
                self._unmute_timer.start()

    def _seek_has_landed(self) -> bool:
        """هل وصل التشغيل للموضع المطلوب؟"""
        target = self._pending_seek_target
        if target is None:
            return True
        try:
            current_ms = self._player.get_time()
        except Exception:
            return True
        if current_ms is None or current_ms < 0:
            return False
        return abs(current_ms / 1000.0 - target) < 0.5

    def _unmute_when_settled(self):
        """
        يفك الكتم أول ما القفزة توصل - مرة واحدة مهما تتابعت الضغطات.

        بنستطلع get_time بأنفسنا بدل ما نستنى حدث TimeChanged: الحدث ده
        بيجي من VLC كل ~250 مللي ثانية، فالاعتماد عليه كان بيخلّي الصمت
        أطول من الثابت القديم بدل ما يقصّره.
        """
        # الحد الأقصى بيتقرأ كل لفّة: الضغطات المتتابعة بتمدّه
        while True:
            now = time.monotonic()
            if now >= self._unmute_deadline:
                break
            if now >= self._unmute_floor and self._seek_has_landed():
                break
            time.sleep(0.002)

        try:
            if self._player is not None:
                self._player.audio_set_mute(self._muted)
        except Exception:
            pass

    def play_and_seek(self, seconds: float):
        if self._player is None:
            return
        self._pending_playing_seek = seconds
        if self._state in (PlaybackState.ENDED, PlaybackState.STOPPED):
            self._player.stop()
            if self._media is not None:
                self._player.set_media(self._media)
        self._player.play()

    def get_current_position(self) -> float:
        if self._player is None:
            return 0.0
        if self._state == PlaybackState.STOPPED:
            return 0.0
        t = self._player.get_time()
        return max(0.0, t / 1000.0) if t is not None and t >= 0 else 0.0

    def get_effective_position(self) -> float:
        if self._pending_seek_target is not None:
            return self._pending_seek_target
        return self.get_current_position()

    @property
    def duration(self) -> float:
        """
        طول المقطع بالثواني.

        مخزَّن: get_length نداء فعلي لـ libvlc، والواجهة بتسأل عنه في كل
        ضغطة سهم (للقصّ، ولشريط الموضع، وللوقت المتبقي) وكل 150 م.ث في
        مؤقّت التحديث. القيمة ثابتة بعد ما VLC يقرأ الملف، فبنقرأها لحد
        ما تيجي صالحة وبعدين نرجّع المخزَّن.
        """
        if self._player is None:
            return 0.0
        if self._duration_cache > 0.0:
            return self._duration_cache

        # أثناء الفتح المشغّل لسه شايل الملف القديم؛ قراءته هنا كانت
        # بتخزّن طوله للملف الجديد (شوف open)
        if self._is_opening:
            return 0.0

        length = self._player.get_length()
        # قبل ما التشغيل يبدأ get_length بترجّع صفر حتى لو الملف
        # اتحلّل خلاص. المدة موجودة في الوسائط نفسها من التحليل، فبناخدها
        # منها - من غيرها أي قفزة قبل التشغيل (End أو أرقام النم باد)
        # كانت بتلاقي المدة صفر.
        if (not length or length <= 0) and self._media is not None:
            try:
                length = self._media.get_duration()
            except Exception:
                length = 0

        if length and length > 0:
            self._duration_cache = length / 1000.0
        return self._duration_cache

    @property
    def state(self):
        return self._state

    @property
    def has_video(self) -> bool:
        return self._has_video_cached

    def get_media_info(self):
        if self._media is None:
            return None
        return {"duration": self.duration, "bit_rate": self._real_bit_rate}

    def set_volume(self, volume_0_to_1: float):
        self._volume = max(0.0, min(1.0, float(volume_0_to_1)))
        if self._player is not None:
            self._player.audio_set_volume(int(round(self._volume * 100)))

    def set_muted(self, muted: bool):
        self._muted = bool(muted)
        if self._player is not None:
            self._player.audio_set_mute(self._muted)

    @property
    def is_muted(self) -> bool:
        return self._muted

    def set_speed(self, factor: float):
        self._speed = max(0.5, min(2.0, float(factor)))
        if self._player is not None:
            self._player.set_rate(self._speed)

    @property
    def speed(self) -> float:
        # القيمة المحفوظة لو المشغّل لسه ما اتعملش
        if self._player is not None:
            rate = self._player.get_rate()
            if rate and rate > 0:
                return rate
        return self._speed
