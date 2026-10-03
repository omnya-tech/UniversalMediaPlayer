import logging
import os
import sys
import threading

def get_app_data_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.path.expanduser("~/.local/share")
    path = os.path.join(base, "Omnya")
    if not os.path.isdir(path):
        _migrate_legacy_app_data_dir(base, path)
    os.makedirs(path, exist_ok=True)
    return path

def _migrate_legacy_app_data_dir(base: str, new_path: str):
    legacy_path = os.path.join(base, "OmniaPlayer")
    if os.path.isdir(legacy_path):
        try:
            os.rename(legacy_path, new_path)
        except OSError:
            return
        old_log = os.path.join(new_path, "omnia_player.log")
        new_log = os.path.join(new_path, "omnya.log")
        if os.path.isfile(old_log) and not os.path.isfile(new_log):
            try:
                os.rename(old_log, new_log)
            except OSError:
                pass

def get_documents_dir() -> str:
    candidate = os.path.join(os.path.expanduser("~"), "Documents")
    if os.path.isdir(candidate):
        return candidate
    return os.path.expanduser("~")

_app_data_dir = get_app_data_dir

MAX_LOG_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 3


def rotate_log_if_needed(log_path: str, max_bytes: int = MAX_LOG_BYTES,
                         backup_count: int = LOG_BACKUP_COUNT) -> bool:
    """
    بيدوّر ملف السجل مرة واحدة عند بدء التشغيل لو كبر عن الحد.

    ليه مش RotatingFileHandler؟ لأن استيراد logging.handlers بيجرّ معاه
    socket وpickle وqueue (علشان handlers الشبكة والبريد اللي إحنا مش
    مستعملينهم خالص) - 28 مللي ثانية على كل إقلاع مقابل صنف واحد.
    logging.FileHandler موجودة في logging نفسها ببلاش.

    الفرق في السلوك: التدوير بيحصل عند التشغيل لا في نص الجلسة. لمشغّل
    وسائط ده كفاية - أسوأ حالة إن جلسة طويلة جدًا تعدّي الحد شوية،
    وبتترتّب أول مرة جاية.

    بيرجّع True لو دوّر فعلًا.
    """
    try:
        if not os.path.isfile(log_path) or os.path.getsize(log_path) < max_bytes:
            return False
    except OSError:
        return False

    # الأقدم يُحذف، والباقي يتزحزح رقمًا: .2 إلى .3 ثم .1 إلى .2، والحالي
    # يصبح .1
    try:
        oldest = f"{log_path}.{backup_count}"
        if os.path.isfile(oldest):
            os.remove(oldest)
        for index in range(backup_count - 1, 0, -1):
            source = f"{log_path}.{index}"
            if os.path.isfile(source): os.replace(source, f"{log_path}.{index + 1}")
        os.replace(log_path, f"{log_path}.1")
        return True
    except OSError:
        # ملف مقفول من نسخة أخرى من البرنامج: نكمل الكتابة في الملف
        # الحالي، والتدوير يحصل في تشغيل لاحق
        return False

def configure_logging(level=logging.INFO) -> logging.Logger:
    logger = logging.getLogger("omnya")
    logger.setLevel(level)

    if logger.handlers:
        return logger

    log_path = os.path.join(_app_data_dir(), "omnya.log")
    rotate_log_if_needed(log_path)
    file_handler = logging.FileHandler(log_path, encoding="utf-8", delay=True)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

def install_global_exception_hook(logger: logging.Logger):
    def _hook(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Unexpected unhandled exception", exc_info=(exc_type, exc_value, exc_traceback))
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    def _thread_hook(args):
        logger.critical(
            "Unexpected unhandled exception in thread: %s",
            args.thread.name if args.thread else "?",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = _hook
    threading.excepthook = _thread_hook

def log_file_path() -> str:
    return os.path.join(_app_data_dir(), "omnya.log")