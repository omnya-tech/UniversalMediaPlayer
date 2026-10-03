import ctypes
import os
import sys
import wx
import logging

logger = logging.getLogger("omnya")

def _resource_path(*args):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, *args)
    return os.path.join(os.path.abspath(os.path.dirname(__file__)), "..", *args)

class _FocusableAnnouncementLabel(wx.TextCtrl):
    def __init__(self, parent):
        super().__init__(parent, style=wx.TE_READONLY | wx.BORDER_NONE | wx.WANTS_CHARS)
        self.SetBackgroundColour(parent.GetBackgroundColour())
        self.SetForegroundColour(parent.GetForegroundColour())
        self.SetCaret(None)
        self.Bind(wx.EVT_SET_FOCUS, self._on_focus)

    def _on_focus(self, event):
        event.Skip()

class ScreenReaderAnnouncer:
    # استخدام متغيرات على مستوى الكلاس (Singleton) لضمان التحميل لمرة واحدة فقط
    _nvda_dll = None
    _nvda_loaded = False

    def __init__(self, parent_widget=None):
        self.parent_widget = parent_widget
        self._default_focus_target = None
        self._init_nvda()

    @classmethod
    def _init_nvda(cls):
        # التحقق: إذا تم التحميل مسبقاً لا تقم بالتحميل مرة أخرى
        if not cls._nvda_loaded:
            try:
                dll_path = _resource_path("resources", "nvdaControllerClient.dll")
                if os.path.exists(dll_path):
                    cls._nvda_dll = ctypes.windll.LoadLibrary(dll_path)
                    logger.info(f"nvdaControllerClient.dll loaded successfully ({dll_path})")
                else:
                    logger.warning("NVDA DLL not found.")
            except Exception as e:
                logger.warning(f"Error loading NVDA DLL: {e}")
            finally:
                cls._nvda_loaded = True

    def set_default_focus_target(self, target):
        self._default_focus_target = target

    def announce(self, text):
        if not text:
            return
            
        # إصلاح الخطأ المطبعي: الدالة الصحيحة هي nvdaController_testIfRunning وليس testIfIsRunning
        if self._nvda_dll and hasattr(self._nvda_dll, 'nvdaController_testIfRunning'):
            if self._nvda_dll.nvdaController_testIfRunning() == 0:
                self._nvda_dll.nvdaController_speakText(text)
                return

        # بديل قراء الشاشة الآخرين (مثل Narrator) في حال غياب NVDA
        if self._default_focus_target:
            self._default_focus_target.SetValue(text)
            self._default_focus_target.SetFocus()