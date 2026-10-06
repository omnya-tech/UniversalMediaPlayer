# -*- coding: utf-8 -*-
"""
أدوات مشتركة لنوافذ الخيارات و«حول البرنامج»: قراءة الإعدادات وحفظها بأمان،
ومجموعات العناصر وأسماؤها المنطوقة، وقوائم المقادير.

نُقلت كما هي من gui/dialogs.py.
"""

import logging

import wx

from i18n.plural import count_phrase
from gui import theme


logger = logging.getLogger(__name__)


def _safe_get_setting(settings_obj, key_name, default=True):
    """قراءة آمنة وشاملة لأي عنصر من كائن الإعدادات"""
    getter_name = f"get_{key_name}"
    if hasattr(settings_obj, getter_name) and callable(getattr(settings_obj, getter_name)):
        try:
            return getattr(settings_obj, getter_name)()
        except Exception:
            pass
    if hasattr(settings_obj, "get") and callable(getattr(settings_obj, "get")):
        try:
            val = settings_obj.get(key_name)
            if val is not None:
                return val
        except Exception:
            pass
    if hasattr(settings_obj, "_data") and isinstance(settings_obj._data, dict):
        return settings_obj._data.get(key_name, default)
    return default


def _safe_set_setting(settings_obj, key_name, value):
    """
    حفظ عنصر في الإعدادات، بسلسلة بدائل: setter مخصص -> set() عامة ->
    كتابة مباشرة في _data.

    الصمت بين البدائل مقصود (كل واحدة بتجرّب اللي بعدها). اللي مش مقصود
    هو إن كل البدائل تفشل والمستخدم يفتكر إن الخيار اتحفظ - ده صنف
    "الخيارات ما بتتطبقش" اللي اشتكى منه. فآخر السلسلة بيسجّل.
    """
    setter_name = f"set_{key_name}"
    if hasattr(settings_obj, setter_name) and callable(getattr(settings_obj, setter_name)):
        try:
            getattr(settings_obj, setter_name)(value)
            return
        except Exception:
            logger.warning("فشل %s، بنجرّب set() العامة", setter_name, exc_info=True)
    if hasattr(settings_obj, "set") and callable(getattr(settings_obj, "set")):
        try:
            settings_obj.set(key_name, value)
            return
        except Exception:
            logger.warning("فشلت set(%s)، بنكتب في _data مباشرة", key_name, exc_info=True)
    if hasattr(settings_obj, "_data") and isinstance(settings_obj._data, dict):
        settings_obj._data[key_name] = value
    elif hasattr(settings_obj, "settings") and isinstance(settings_obj.settings, dict):
        settings_obj.settings[key_name] = value
    else:
        # كل البدائل فشلت: لازم يبان في السجل، لأن المستخدم هيفتكر إن
        # الخيار اتحفظ
        logger.error("تعذّر حفظ الخيار %s نهائيًا - القيمة المطلوبة %r", key_name, value)


def _add_group_box(panel: wx.Window, outer_sizer: wx.Sizer, title: str) -> wx.StaticBoxSizer:
    box = wx.StaticBox(panel, label=title)
    box_sizer = wx.StaticBoxSizer(box, wx.VERTICAL)
    outer_sizer.Add(box_sizer, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=10)
    return box_sizer


# الأقسام بعناوين خفيفة لا بإطارات: شوف _add_section.
# ووصف كل عنصر بيروح لاسمه الإمكانيّ ولتلميحه معًا: شوف _describe.
# (المساعدات دي بتستعملها نافذة الخيارات كلها)
# (_add_group_box فاضلة لنافذة "حول")
# الثلاث دوال بترجّع العنصر نفسه عشان الاستدعاء يبقى سطر واحد.
# مثال: _describe(wx.CheckBox(...), name, hint)
# بدل إنشاء ثم ضبط في سطرين.
# والأقسام بتتبني بالترتيب اللي بيتقرا بيه.
# (من فوق لتحت، ومن اليمين للشمال في العربي)


def _describe(control, name: str, description: str = ""):
    """
    يضبط الاسم الإمكانيّ والتلميح على عنصر تحكّم.

    نفس النص بيروح للاتنين عن قصد: قارئ الشاشة بيقراه عند التركيز،
    والمبصر بيشوفه كتلميح عند مرور الفأرة.
    """
    try:
        if name:
            control.SetName(name)
        if description:
            control.SetToolTip(description)
            if hasattr(control, "SetHelpText"):
                control.SetHelpText(description)
    except Exception:
        pass
    return control


def _add_section(panel: wx.Window, sizer: wx.Sizer, title: str) -> wx.BoxSizer:
    """
    عنوان قسم خفيف + حاوية لمحتواه.

    أخف من StaticBox: الإطار المرسوم بيضيف طبقة تجميع زيادة قارئ الشاشة
    بيعلنها عند كل دخول وخروج، وبتتقل التصفّح لما الأقسام تبقى كتير.
    """
    header = wx.StaticText(panel, label=title)
    font = header.GetFont()
    font.SetWeight(wx.FONTWEIGHT_BOLD)
    header.SetFont(font)
    sizer.Add(header, flag=wx.LEFT | wx.RIGHT | wx.TOP, border=12)

    line = wx.StaticLine(panel)
    sizer.Add(line, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=12)

    body = wx.BoxSizer(wx.VERTICAL)
    sizer.Add(body, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, border=18)
    return body


def _add_hint(panel: wx.Window, sizer: wx.Sizer, text: str):
    """سطر شرح صغير تحت الخيار."""
    hint = wx.StaticText(panel, label=text)
    hint.SetForegroundColour(theme.hint_colour())
    font = hint.GetFont()
    font.SetPointSize(max(7, font.GetPointSize() - 1))
    hint.SetFont(font)
    sizer.Add(hint, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=4)
    return hint


def _light(setter, colour):
    """لون ثابت مصمَّم لخلفية فاتحة: يُطبَّق في المظهر الفاتح وحده."""
    if theme.custom_colours_allowed() and not theme.is_dark():
        setter(colour)


# مقادير التقديم: (النوع، مفتاح العنوان، المقادير المتاحة بالثواني)
_SEEK_STEP_ROWS = (
    ("normal", "options_seek_step_normal", (1, 2, 3, 5, 10, 15, 20, 30, 45, 60)),
    ("ctrl", "options_seek_step_ctrl", (15, 20, 30, 45, 60, 90, 120, 180, 300, 600)),
    ("shift", "options_seek_step_shift", (60, 120, 180, 300, 600, 900, 1200, 1800)),
    ("alt", "options_seek_step_alt", (60, 120, 300, 600, 900, 1200, 1800, 2700, 3600)),
    ("ctrl_shift", "options_seek_step_ctrl_shift", (300, 600, 900, 1200, 1800, 2700, 3600, 5400, 7200)),
)


def _seek_amount_text(tr, seconds):
    """«10 ثوانٍ» أو «5 دقائق»: المقدار بوحدته، كما يُقرأ."""
    if seconds >= 60 and seconds % 60 == 0:
        return count_phrase(tr, "count_minutes", seconds // 60)
    return count_phrase(tr, "count_seconds", seconds)


_EDITOR_PROGRESS_STEPS = (10, 25, 50, 0)
