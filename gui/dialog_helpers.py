# -*- coding: utf-8 -*-
"""
مفتاح المسافة "زي الإنتر بالظبط" في حوارات wx.Dialog.

الإنتر بيفعّل الزرار الافتراضي (SetDefault()) في أي wx.Dialog تلقائيًا -
آلية أصلية جاهزة في نظام التشغيل (IsDialogMessage على ويندوز) بدون أي
كود إضافي. المسافة معندهاش نفس السلوك ده جاهز، فمحتاجة ربط صريح.

لازم حذر هنا: المسافة (بعكس الإنتر) لها معنى أصلي مهم جدًا لعناصر تحكم
كتير (تفعيل/إلغاء checkbox، اختيار radio button، تفعيل أي زرار له فوكس
حاليًا، فتح قائمة Choice) - وده أساسي لمستخدمي قارئ الشاشة اللي
البرنامج مصمم لهم من الأساس. فالمسافة هنا بتفعّل الزرار الافتراضي بس
لو مفيش عنصر تفاعلي زي دول واخد الفوكس حاليًا - لو فيه، بتسيب سلوكها
الطبيعي زي ما هو تمامًا (زي ما بالظبط الإنتر بيسيب مربعات النص متعددة
الأسطر تستخدمه لسطر جديد بدل ما يفعّل الزرار الافتراضي).
"""

import wx

# عناصر تحكم المسافة ليها معنى أصلي مهم فيها - لو حد منها واخد الفوكس،
# المسافة بتتسيب لسلوكها الطبيعي بدل ما تتحوّل لتفعيل الزرار الافتراضي
_CONTROLS_WITH_NATIVE_SPACE_MEANING = (
    wx.Button,
    wx.CheckBox,
    wx.RadioButton,
    wx.Choice,
    wx.ListBox,
    wx.Slider,
)


def bind_space_like_enter(dialog: wx.Dialog):
    """تربط EVT_CHAR_HOOK على الحوار عشان مفتاح المسافة يفعّل زرار
    SetDefault() الخاص بيه - بالظبط زي الإنتر - إلا لو الفوكس حاليًا على
    عنصر تحكم من _CONTROLS_WITH_NATIVE_SPACE_MEANING فوق."""

    def _on_char_hook(event):
        if event.GetKeyCode() != wx.WXK_SPACE:
            event.Skip()
            return

        focused = dialog.FindFocus()
        if isinstance(focused, _CONTROLS_WITH_NATIVE_SPACE_MEANING):
            event.Skip()
            return

        default_button = dialog.GetDefaultItem()
        if default_button is None or not default_button.IsShown() or not default_button.IsEnabled():
            event.Skip()
            return

        click_event = wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, default_button.GetId())
        click_event.SetEventObject(default_button)
        wx.PostEvent(default_button.GetEventHandler(), click_event)

    dialog.Bind(wx.EVT_CHAR_HOOK, _on_char_hook)


def bind_escape_closes(window):
    """تربط EVT_CHAR_HOOK على أي نافذة (wx.Dialog أو wx.Frame) عشان
    مفتاح Escape يقفلها - بنفس آلية الضغط على زرار الإغلاق (X) أو
    الاختصار المعتاد Alt+F4 بالظبط: بيستدعي window.Close() اللي بيبعت
    EVT_CLOSE عادي، فأي منطق تنظيف موجود بالفعل في معالج _on_close الخاص
    بالنافذة (زي إيقاف تسجيل شغال، أو إلغاء تحويل ملفات جارٍ) بيتنفّذ
    زي ما هو من غير أي تكرار أو تغيير في السلوك - الاختصار هنا مجرد طريق
    إضافي لنفس الإغلاق العادي، مش سلوك مختلف أو "خروج فجائي".

    بيتجاهل أي مفتاح غير Escape (event.Skip() عشان باقي عناصر التحكم
    تستمر تستخدم مفاتيحها الطبيعية - زي قائمة Choice مفتوحة بتتقفل
    بـ Escape أول مرة من غير ما توصل للنافذة الأساسية أصلًا، وهو سلوك
    نظام التشغيل الطبيعي في الحالة دي)."""

    def _on_char_hook(event):
        if event.GetKeyCode() != wx.WXK_ESCAPE:
            event.Skip()
            return
        window.Close()

    window.Bind(wx.EVT_CHAR_HOOK, _on_char_hook)
