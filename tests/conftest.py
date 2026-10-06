# -*- coding: utf-8 -*-
"""إعدادات مشتركة لكل الاختبارات."""

import os
import tempfile

import pytest

# مجلد بيانات البرنامج (السجل والإعدادات) في مجلد مؤقت، وقبل أي استيراد من
# core: السجل يُفتح عند استيراد الوحدات. كانت الاختبارات تكتب في سجل
# المستخدم الحقيقي، فيختلط تشغيلها بتشغيله في التقرير التشخيصي
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="omnya_tests_")


@pytest.fixture(autouse=True)
def _documents_in_temp(tmp_path_factory, monkeypatch):
    """
    مجلد المستندات في مجلد مؤقت لكل اختبار.

    الإعدادات تصنع مجلدات الحفظ في المستندات أول ما تُطلب؛ اختبارات قديمة
    كانت تصنعها في مستندات المستخدم الحقيقية.
    """
    # مجلد مستقل لا داخل tmp_path: بعض الاختبارات تعدّ محتويات tmp_path
    documents = tmp_path_factory.mktemp("Documents")
    monkeypatch.setattr("core.settings.get_documents_dir", lambda: str(documents))
    return documents


@pytest.fixture(scope="session")
def wx_app():
    """تطبيق wx واحد لكل اختبارات الواجهة."""
    wx = pytest.importorskip("wx")
    app = wx.App(False)
    yield app
    # النوافذ العليا تُحذف فعلًا في وقت الخمول: بلا ذلك يشكو wx عند الخروج
    # من «صنف ما زالت له نوافذ مفتوحة»
    for window in wx.GetTopLevelWindows():
        window.Destroy()
    from tests.gui_support import pump
    pump(0.2)


@pytest.fixture
def app_data(tmp_path_factory, monkeypatch):
    """مجلد بيانات خاص بالاختبار: إعدادات جديدة لا ترث ما تركه غيره."""
    folder = tmp_path_factory.mktemp("AppData")
    monkeypatch.setenv("APPDATA", str(folder))
    return folder


@pytest.fixture
def make_main_window(wx_app, app_data, monkeypatch):
    """
    النافذة الرئيسية الحقيقية بمحرك وهمي ومعلن يسجّل.

    الاختصارات العامة (مفاتيح الوسائط والاختصارات الشبحية) لا تُسجَّل في
    ويندوز: تسجيلها كان سيحجز تركيبات على جهاز من يشغّل الاختبارات.
    """
    import gui.main_window as main_window_module
    from tests.gui_support import FakeAnnouncer, FakeEngine

    monkeypatch.setattr(main_window_module, "PlayerEngine", FakeEngine)
    monkeypatch.setattr(main_window_module, "ScreenReaderAnnouncer", FakeAnnouncer)
    monkeypatch.setattr(main_window_module.MainWindow, "RegisterHotKey",
                        lambda self, *args: True, raising=False)
    monkeypatch.setattr(main_window_module.MainWindow, "UnregisterHotKey",
                        lambda self, *args: True, raising=False)
    # مؤقت النوم يستطيع إطفاء الجهاز فعلًا: لا يُنفَّذ في أي اختبار
    shutdowns = []
    monkeypatch.setattr(main_window_module.MainWindow, "_shutdown_computer",
                        lambda self: shutdowns.append(True))
    windows = []

    def make(lang="ar"):
        window = main_window_module.MainWindow(lang)
        windows.append(window)
        return window

    yield make
    for window in windows:
        for timer_name in ("_ui_timer", "_manual_announce_timer", "_sleep_timer", "_hold_seek_timer"):
            timer = getattr(window, timer_name, None)
            if timer is not None:
                timer.Stop()
        window.Destroy()
    wx_app.Yield(True)


@pytest.fixture
def main_window(make_main_window):
    return make_main_window("ar")
