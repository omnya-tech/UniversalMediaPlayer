# -*- coding: utf-8 -*-
import sys
import os
import threading
import time
import ctypes

# socket لا يُستورد هنا: لا تحتاجه إلا نسخة ثانية تراسل الأولى أو خادم
# الاتصال، فاستيراده في أعلى الملف كان يؤخر الإقلاع بلا داعٍ.
# (يُستورد داخل الدوال التي تحتاجه)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import wx
from gui.main_window import MainWindow
from core.logging_setup import configure_logging, install_global_exception_hook
from core.settings import Settings
from i18n.strings import Translator
from gui.theme import apply_app_theme

PORT = 48215
_app_mutex = None
_ipc_server_socket = None


# تجهيز النص البرمجي للإرسال عبر خادم الاتصال المحلي بين النسخ
def prepare_ipc_payload(cmd_type, paths):
    lines = [cmd_type] + [p for p in paths if p]
    return "\n".join(lines)


def _collect_converter_targets(args):
    """
    مسارات المحوّل من سطر الأوامر، أو من ملف قائمة لو الاختيار كبير.

    ويندوز بيرفض أي سطر أوامر فوق 32767 حرفًا، ومجلد فيه تلتمية ملف
    بمسارات عربية بيتخطّى الحد - فالقائمة بتتكتب في ملف مؤقت وبيتمرّر
    مساره بدلها.
    """
    if "--file-list" in args:
        index = args.index("--file-list")
        if index + 1 < len(args):
            list_path = args[index + 1]
            try:
                with open(list_path, "r", encoding="utf-8") as stream:
                    paths = [line.strip() for line in stream if line.strip()]
                return [p for p in paths if os.path.exists(p)]
            except OSError:
                return []
            finally:
                # الملف المؤقت لا يُحتاج بعد القراءة؛ حذفه يمنع تراكم
                # قوائم قديمة في مجلد المؤقتات، وفشل الحذف لا يمنع
                # التحويل.
                try:
                    os.remove(list_path)
                except OSError:
                    pass
        return []
    return [p for p in args if p != "--converter-only" and os.path.exists(p)]


def check_and_send_ipc(payload):
    import socket

    # يكتشف نسخة قيد الإقلاع عبر Windows Mutex، وينتظر خادمها ليرسل إليه
    global _app_mutex
    mutex_name = "UniversalMediaPlayerMutex_48215"
    kernel32 = ctypes.windll.kernel32

    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    already_exists = (kernel32.GetLastError() == 183)

    if already_exists:
        for _ in range(25):
            try:
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                client.settimeout(1.0)
                client.connect(('127.0.0.1', PORT))
                client.sendall(payload.encode('utf-8'))
                # إغلاق جهة الإرسال يُعلم الخادم بنهاية الرسالة، فيقرأها
                # كاملة مهما طالت بدل أن يكتفي بأول دفعة
                # (الرسائل الطويلة كانت تُقطع عند 8 كيلوبايت)
                try:
                    client.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
                client.close()
                return True
            except Exception:
                time.sleep(0.2)
        return True
    else:
        _app_mutex = mutex
        return False


def release_ipc_and_mutex():
    global _ipc_server_socket, _app_mutex
    if _ipc_server_socket:
        try:
            _ipc_server_socket.close()
        except Exception:
            pass
        _ipc_server_socket = None

    if _app_mutex:
        try:
            ctypes.windll.kernel32.CloseHandle(_app_mutex)
        except Exception:
            pass
        _app_mutex = None


# خادم محلي في النسخة الأولى يستقبل الوسائط وأوامر التحويل من النسخ الجديدة
def start_ipc_server(window, logger):
    import socket

    def server_thread():
        global _ipc_server_socket
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(('127.0.0.1', PORT))
            server.listen(100)
            _ipc_server_socket = server
        except Exception as e:
            logger.error("Failed to start IPC server: %s", e)
            return

        while True:
            try:
                conn, _ = _ipc_server_socket.accept()
                # القراءة حتى يغلق المرسل جهته: قائمة ملفات طويلة لا تصل
                # في دفعة واحدة.
                # والمهلة تمنع عميلًا معطوبًا من حجز الخادم للأبد.
                # (العميل يرسل ثم يغلق جهة الإرسال؛ انظر check_and_send_ipc)
                conn.settimeout(5.0)
                chunks = []
                try:
                    while True:
                        chunk = conn.recv(65536)
                        if not chunk:
                            break
                        chunks.append(chunk)
                except socket.timeout:
                    pass
                data = b"".join(chunks)

                if data:
                    msg = data.decode('utf-8').strip()
                    lines = msg.split('\n')
                    cmd_type = lines[0] if lines else "OPEN"
                    paths = [l.strip() for l in lines[1:] if l.strip()]

                    if not paths and os.path.exists(msg):
                        cmd_type = "OPEN"
                        paths = [msg]

                    if not window or not isinstance(window, wx.Window) or getattr(window, "IsBeingDeleted", lambda: False)():
                        conn.close()
                        continue

                    # النافذة قد تكون أُغلقت بين الفحص والتنفيذ
                    if cmd_type == "CONVERT" and paths:
                        wx.CallAfter(window.queue_converter_paths, paths)
                    elif cmd_type == "CONVERT_FOLDER" and paths and os.path.isdir(paths[0]):
                        wx.CallAfter(window.open_converter_with_folder, paths[0])
                    elif cmd_type == "USER_GUIDE":
                        wx.CallAfter(window._on_user_guide, None)
                    elif cmd_type == "EXPORT_SHORTCUTS":
                        wx.CallAfter(window._on_export_shortcuts_doc, None)
                    elif cmd_type == "OPEN_MULTI" and paths:
                        wx.CallAfter(window.queue_converter_paths, paths)
                    elif paths:
                        if os.path.isfile(paths[0]):
                            wx.CallAfter(window._open_specific_path, paths[0])
                        elif os.path.isdir(paths[0]):
                            wx.CallAfter(window._open_folder_path, paths[0])


                    try:
                        wx.CallAfter(window.Raise)
                    except Exception:
                        pass
                conn.close()
            except OSError as e:
                # 10038 و10053: المقبس أُغلق عمدًا عند الخروج، فلا خطأ يُسجَّل
                if "10038" in str(e) or "10053" in str(e) or getattr(e, "winerror", None) in (10038, 10053):
                    break
                logger.error("IPC server OS error: %s", e)
                break
            except Exception as e:
                logger.error("IPC server connection closed or error: %s", e)
                break

    t = threading.Thread(target=server_thread, daemon=True)
    t.start()


def apply_interface_direction(app, lang):
    """
    الواجهة العربية من اليمين لليسار.

    كانت كل النوافذ من اليسار لليمين مع نصوص عربية: العنوان على يسار
    خانته، و«...» في الجهة الخطأ، والكلمات الإنجليزية وسط الجمل العربية
    مرتبة ترتيبًا غريبًا. wx يقلب النوافذ حين تكون لغة البرنامج عربية،
    فنضبطها. وتُعاد لغة مكتبة C إلى المحايدة فورًا، فلا تتغير الفاصلة
    العشرية في المكتبات (VLC وFFmpeg) ولا تنسيق الأرقام.

    كائن اللغة يُحفظ في التطبيق: لو حُذف رجعت wx لغتها السابقة.
    """
    if lang != "ar":
        return
    import locale

    app._interface_locale = wx.Locale(wx.LANGUAGE_ARABIC, wx.LOCALE_DONT_LOAD_DEFAULT)
    try:
        locale.setlocale(locale.LC_ALL, "C")
    except locale.Error:
        pass


def main():
    logger = configure_logging()
    install_global_exception_hook(logger)

    settings = Settings()
    lang = settings.get_language()
    tr = Translator(lang)

    args = sys.argv[1:]

    # تسخين المحرك: المثبّت يشغّل البرنامج بهذا الخيار مرة بعد التثبيت،
    # فيقرأ ويندوز مكتبات VLC من القرص ويحفظها في ذاكرته المؤقتة.
    # أول فتح حقيقي بعدها يكون أسرع بفارق ملحوظ، خصوصًا على الأقراص
    # الميكانيكية.
    # يخرج فورًا بلا أي نافذة.
    # (ولا يحجز القفل ولا يفتح خادم الاتصال)
    # انظر omnya_player_installer.iss
    if "--warmup" in args:
        try:
            from core.engine import PlayerEngine
            # الاستيراد هنا لا في أعلى الملف: الخيار ده بس اللي يحتاجه
            engine = PlayerEngine()
            engine._ensure_player()
            engine.release()
        except Exception as exc:
            logger.warning("تسخين المحرك فشل: %s", exc)
        sys.exit(0)

    # المحوّل في عملية مستقلة: لا يجمّد المشغّل ولا يتأثر بقفل النسخة الواحدة
    # (انظر ToolsMixin._launch_standalone_converter)
    if "--converter-only" in args:
        app = wx.App(False)
        apply_interface_direction(app, lang)
        apply_app_theme(app, settings.get_ui_theme())
        from gui.converter_dialog import ConverterDialog
        from accessibility.announcer import ScreenReaderAnnouncer

        target_paths = _collect_converter_targets(args)

        conv_window = ConverterDialog(None, tr, None, settings, initial_files=target_paths)
        conv_window.announcer = ScreenReaderAnnouncer(conv_window)
        conv_window.Show()
        app.MainLoop()
        sys.exit(0)

    # تحليل وسائط سطر الأوامر لتفهم أوامر التثبيت (Inno Setup)
    cmd_type = "OPEN"
    target_paths = []

    if args:
        if args[0] == "--convert" and len(args) >= 2:
            cmd_type = "CONVERT"
            target_paths = [p for p in args[1:] if os.path.exists(p)]
        elif args[0] == "--convert-folder" and len(args) >= 2:
            cmd_type = "CONVERT_FOLDER"
            target_paths = [p for p in args[1:] if os.path.isdir(p)]
        elif args[0] == "--user-guide":
            cmd_type = "USER_GUIDE"
        elif args[0] == "--export-shortcuts":
            cmd_type = "EXPORT_SHORTCUTS"
        else:
            existing_paths = [p for p in args if os.path.exists(p)]
            if len(existing_paths) > 1:
                cmd_type = "OPEN_MULTI"
                target_paths = existing_paths
            elif len(existing_paths) == 1:
                cmd_type = "OPEN"
                target_paths = existing_paths

    if target_paths or cmd_type in ("USER_GUIDE", "EXPORT_SHORTCUTS"):
        payload = prepare_ipc_payload(cmd_type, target_paths)
        if check_and_send_ipc(payload):
            sys.exit(0)
    else:
        if check_and_send_ipc("OPEN\n"):
            sys.exit(0)

    app = wx.App(False)
    apply_interface_direction(app, lang)
    # قبل أي نافذة: الوضع الداكن في ويندوز لا يُفعَّل بعد إنشائها
    apply_app_theme(app, settings.get_ui_theme())

    # المجلدات القديمة (أسماء تتبع اللغة) تُضم للمجلدات الثلاثة الثابتة،
    # في خيط جانبي فلا يتأخر ظهور النافذة
    # (شوف Settings.migrate_legacy_output_folders)
    def _migrate_folders():
        try:
            moved = settings.migrate_legacy_output_folders()
            if moved:
                logger.info("نُقل %d عنصرًا من مجلدات الحفظ القديمة", moved)
        except Exception:
            logger.exception("تعذّر نقل مجلدات الحفظ القديمة")

    # الأسماء تُحسم هنا في الخيط الرئيسي (أول مرة فقط، بلغة البرنامج)، فلا
    # يكتب خيطان ملف الإعدادات معًا
    try:
        settings.resolve_output_folders()
    except Exception:
        logger.exception("تعذّر تحديد مجلدات الحفظ")
    threading.Thread(target=_migrate_folders, daemon=True).start()

    window = MainWindow()
    window.ipc_cleanup_callback = release_ipc_and_mutex
    window.Show()

    start_ipc_server(window, logger)

    if cmd_type == "USER_GUIDE":
        wx.CallAfter(window._on_user_guide, None)
    elif cmd_type == "EXPORT_SHORTCUTS":
        wx.CallAfter(window._on_export_shortcuts_doc, None)
    elif target_paths:
        # «تحويل» من قائمة السياق يمر بالطابور: ويندوز يشغّل نسخة لكل
        # ملف محدد، والطابور يجمعها في محوّل واحد
        # (انظر ToolsMixin.queue_converter_paths)
        if cmd_type == "CONVERT":
            wx.CallAfter(window.queue_converter_paths, target_paths)
        elif cmd_type == "CONVERT_FOLDER" and os.path.isdir(target_paths[0]):
            wx.CallAfter(window.open_converter_with_folder, target_paths[0])
        elif cmd_type == "OPEN_MULTI":
            wx.CallAfter(window.queue_converter_paths, target_paths)
        elif cmd_type == "OPEN":
            if os.path.isfile(target_paths[0]):
                wx.CallAfter(window._open_specific_path, target_paths[0])
            elif os.path.isdir(target_paths[0]):
                wx.CallAfter(window._open_folder_path, target_paths[0])

    app.MainLoop()


if __name__ == "__main__":
    main()
