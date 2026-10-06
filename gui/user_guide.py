# -*- coding: utf-8 -*-
"""
دليل المستخدم وقائمة الاختصارات، بالعربية والإنجليزية.

الدليل صفحة HTML تُفتح في المتصفح (F1): فهرس بروابط، وكل قسم عنوان
وقائمة نقاط حقيقية، فيتنقل قارئ الشاشة بالعناوين (H) والقوائم (L)
والروابط. والنسختان بالمحتوى نفسه نقطة بنقطة.

قائمة الاختصارات تُعرض في آخر الدليل وتُصدَّر نصًا (Ctrl+Shift+H)، وفيها
ما غيّره المستخدم من مقادير التقديم والاختصارات الشبحية.
"""

import re
from html import escape

from core.version import APP_VERSION

# سطور التقديم بمفاتيحها في القائمة، ونوع كل منها في الإعدادات
_SEEK_LINE_KEYS = {
    "ar": (("normal", "السهم الأيمن / الأيسر"), ("ctrl", "Ctrl + السهم الأيمن / الأيسر"),
           ("shift", "Shift + السهم الأيمن / الأيسر"), ("alt", "Alt + السهم الأيمن / الأيسر"),
           ("ctrl_shift", "Ctrl + Shift + السهم الأيمن / الأيسر")),
    "en": (("normal", "Right / Left Arrow"), ("ctrl", "Ctrl + Right / Left Arrow"),
           ("shift", "Shift + Right / Left Arrow"), ("alt", "Alt + Right / Left Arrow"),
           ("ctrl_shift", "Ctrl + Shift + Right / Left Arrow")),
}

_SEEK_DEFAULTS = {"normal": 10, "ctrl": 60, "shift": 300, "alt": 600, "ctrl_shift": 1800}


def get_shortcuts_list(lang: str = "ar", seek_steps: dict = None, ghost_hotkeys: dict = None) -> list:
    """
    قائمة الاختصارات مصنفة، للعرض في الدليل وللتصدير النصي.

    seek_steps ({النوع: ثوانٍ}) وghost_hotkeys ({الفعل: (المساعدة، المفتاح)})
    يضعان ما ضبطه المستخدم في الخيارات مكان القيم الافتراضية.
    """
    lines = _default_shortcuts_list(lang)
    if seek_steps:
        lines = _apply_seek_steps(lines, lang, seek_steps)
    if ghost_hotkeys:
        lines = _apply_ghost_hotkeys(lines, ghost_hotkeys)
    return lines


def _amount_text(lang, seconds):
    from i18n.plural import count_phrase
    from i18n.strings import Translator

    tr = Translator(lang)
    if seconds >= 60 and seconds % 60 == 0:
        return count_phrase(tr, "count_minutes", seconds // 60)
    return count_phrase(tr, "count_seconds", seconds)


def _apply_seek_steps(lines, lang, seek_steps):
    keys = _SEEK_LINE_KEYS["ar" if lang == "ar" else "en"]
    result = []
    for line in lines:
        for kind, key_text in keys:
            if line.endswith(": " + key_text) and kind in seek_steps:
                amount = _amount_text(lang, seek_steps[kind])
                line = (f"تقديم / إرجاع بـ {amount}: {key_text}" if lang == "ar"
                        else f"Seek {amount}: {key_text}")
                break
        result.append(line)
    return result


def _apply_ghost_hotkeys(lines, ghost_hotkeys):
    from gui.editor_hotkeys import DEFAULT_HOTKEYS, combo_text

    replacements = {}
    for action, default in DEFAULT_HOTKEYS:
        if action in ghost_hotkeys:
            replacements[": " + combo_text(default).replace("+", " + ")] = \
                ": " + combo_text(ghost_hotkeys[action]).replace("+", " + ")
    result = []
    for line in lines:
        for old, new in replacements.items():
            if line.endswith(old):
                line = line[: -len(old)] + new
                break
        result.append(line)
    return result


def _default_shortcuts_list(lang: str) -> list:
    """
    الاختصارات بأقسامها: سطر «=== القسم ===» ثم «الوصف: المفاتيح».

    سطور التقديم والاختصارات الشبحية تبقى بصيغتها هذه بالضبط:
    _apply_seek_steps و_apply_ghost_hotkeys يعرفانها من آخرها.
    """
    if lang == "ar":
        return [
            "=== التشغيل الأساسي ===",
            "تشغيل / إيقاف مؤقت: مسافة (Space)",
            "إيقاف التشغيل الكامل والإعادة للبداية: Ctrl + Space",
            "كتم / إلغاء كتم الصوت: حرف M",
            "رفع / خفض مستوى الصوت (بنسبة 5%): السهم العلوي / السفلي",
            "رفع / خفض مستوى الصوت السريع (بنسبة 20%): Ctrl + السهم العلوي / السفلي",
            "تبديل وضع ملء الشاشة للفيديو: F11 أو Escape",
            "",
            "=== التقديم والإرجاع ===",
            "تقديم / إرجاع بـ 10 ثوانٍ: السهم الأيمن / الأيسر",
            "تقديم / إرجاع بدقيقة واحدة (60 ثانية): Ctrl + السهم الأيمن / الأيسر",
            "تقديم / إرجاع بـ 5 دقائق: Shift + السهم الأيمن / الأيسر",
            "تقديم / إرجاع بـ 10 دقائق: Alt + السهم الأيمن / الأيسر",
            "تقديم / إرجاع بـ 30 دقيقة: Ctrl + Shift + السهم الأيمن / الأيسر",
            "القفز المباشر لنسبة من الملف (10% إلى 90%): Numpad 1 إلى 9",
            "القفز لبداية الملف: Numpad 0 أو Home",
            "القفز لنهاية الملف (آخر 5 ثوانٍ): End",
            "الانتقال إلى وقت محدد: Ctrl + G",
            "",
            "=== السرعة والعلامات المرجعية ===",
            "زيادة / تقليل سرعة التشغيل (بمقدار 0.25x): Alt + السهم العلوي / السفلي",
            "إعادة السرعة للوضع الطبيعي (1.0x): Alt + Numpad 0",
            "إضافة علامة مرجعية عند الموضع الحالي: Ctrl + B",
            "تسمية أقرب علامة مرجعية: Ctrl + Alt + B",
            "العلامة التالية: F2",
            "العلامة السابقة: Shift + F2",
            "حذف كل علامات الملف الحالي: Ctrl + Shift + B",
            "",
            "=== إعلانات الوقت وقارئ الشاشة ===",
            "الوقت الحالي والمتبقي والكامل معًا: حرف T",
            "الوقت المتبقي فقط: حرف R",
            "مدة الملف الكاملة فقط: حرف E",
            "ما يُذاع الآن في الراديو: حرف N",
            "إيقاف كل الإعلانات وإعادتها: Ctrl + Alt + A",
            "",
            "=== الملفات والمجلدات وقوائم التشغيل ===",
            "فتح ملف وسائط: Ctrl + O",
            "فتح مجلد وسائط كامل: Ctrl + Shift + O",
            "فتح رابط (راديو أو بث مباشر أو ملف على الإنترنت): Ctrl + U",
            "الملف التالي في المجلد أو القائمة: Page Down",
            "الملف السابق في المجلد أو القائمة: Page Up",
            "نافذة قائمة التشغيل (إضافة وحذف وترتيب): Ctrl + L",
            "حفظ قائمة التشغيل الحالية كملف M3U8: Ctrl + S",
            "داخل نافذة القائمة: Enter للتشغيل، Delete للحذف، Alt + السهم العلوي / السفلي للتحريك",
            "",
            "=== المعادل الصوتي ===",
            "فتح نافذة المعادل الصوتي: Ctrl + E",
            "نمط المعادل التالي / السابق: حرف Q / Shift + Q",
            "",
            "=== مسجّل الصوت ===",
            "فتح نافذة مسجّل الصوت: Ctrl + Shift + R",
            "بدء التسجيل فورًا من النافذة الرئيسية أو نافذة المسجّل، ثم إيقافه وحفظه: Ctrl + R",
            "سماع مستوى الصوت أثناء التسجيل (داخل نافذة المسجّل): Ctrl + L",
            "شريط «مستوى المايكروفون» في نافذة المسجّل: الأسهم درجة واحدة، وPage Up / Page Down عشر درجات، ويعمل أثناء التسجيل أيضًا",
            "",
            "=== محرر الوسائط ===",
            "فتح نافذة محرر الوسائط: Ctrl + Shift + X",
            "",
            "=== الاختصارات الشبحية لمحرر الوسائط (تعمل من أي مكان) ===",
            "تشغيل الاختصارات الشبحية وإيقافها: Ctrl + Alt + Shift + G",
            "فتح محرر الوسائط: Ctrl + Alt + Shift + O",
            "تحديد نقطة القص عند الموضع الحالي: Ctrl + Alt + Shift + S",
            "تحديد بداية مقطع عند الموضع الحالي: Ctrl + Alt + Shift + B",
            "تحديد نهاية المقطع وإضافته: Ctrl + Alt + Shift + E",
            "التراجع عن آخر مقطع أو بداية: Ctrl + Alt + Shift + Z",
            "إضافة الملف الحالي إلى قائمة «قص عدة ملفات»: Ctrl + Alt + Shift + L",
            "إضافة الملف الحالي إلى قائمة الدمج: Ctrl + Alt + Shift + M",
            "الإعلان عما حُدِّد في المحرر: Ctrl + Alt + Shift + I",
            "بدء العمل: Ctrl + Alt + Shift + Enter",
            "إلغاء العمل الجاري: Ctrl + Alt + Shift + C",
            "",
            "=== الخيارات والمساعدة ===",
            "فتح الخيارات: Ctrl + Shift + P",
            "التنقل بين تبويبات الخيارات: Ctrl + Tab، أو Ctrl + 1 إلى Ctrl + 6",
            "فتح محول الصيغ: من قائمة «أدوات»",
            "مؤقت النوم وتصدير الإعدادات واستيرادها: من قائمة «أدوات»",
            "دليل الاستخدام: F1",
            "تصدير دليل الاختصارات كمستند نصي: Ctrl + Shift + H",
            "حفظ تقرير تشخيصي على سطح المكتب (بلا معلومات شخصية): Ctrl + Shift + D",
            "الخروج من البرنامج: Ctrl + Q",
        ]
    return [
        "=== Basic Playback ===",
        "Play / Pause: Space",
        "Stop and return to the start: Ctrl + Space",
        "Mute / Unmute: M",
        "Volume up / down (5%): Up / Down Arrow",
        "Fast volume up / down (20%): Ctrl + Up / Down Arrow",
        "Toggle video fullscreen: F11 or Escape",
        "",
        "=== Seeking ===",
        "Seek 10 Seconds: Right / Left Arrow",
        "Seek 1 Minute (60s): Ctrl + Right / Left Arrow",
        "Seek 5 Minutes: Shift + Right / Left Arrow",
        "Seek 10 Minutes: Alt + Right / Left Arrow",
        "Seek 30 Minutes: Ctrl + Shift + Right / Left Arrow",
        "Jump to a percentage of the file (10% to 90%): Numpad 1 to 9",
        "Jump to the start of the file: Numpad 0 or Home",
        "Jump to the end of the file (last 5 seconds): End",
        "Go to a specific time: Ctrl + G",
        "",
        "=== Speed & Bookmarks ===",
        "Increase / decrease speed (by 0.25x): Alt + Up / Down Arrow",
        "Reset speed (1.0x): Alt + Numpad 0",
        "Add a bookmark at the current position: Ctrl + B",
        "Name the nearest bookmark: Ctrl + Alt + B",
        "Next bookmark: F2",
        "Previous bookmark: Shift + F2",
        "Clear all bookmarks of the current file: Ctrl + Shift + B",
        "",
        "=== Time & Screen Reader Announcements ===",
        "Current, remaining and total time together: T",
        "Remaining time only: R",
        "Total duration only: E",
        "Radio now playing: N",
        "Turn all announcements off and on: Ctrl + Alt + A",
        "",
        "=== Files, Folders & Playlists ===",
        "Open a media file: Ctrl + O",
        "Open a whole media folder: Ctrl + Shift + O",
        "Open a link (radio, live stream or online file): Ctrl + U",
        "Next file in the folder or playlist: Page Down",
        "Previous file in the folder or playlist: Page Up",
        "Playlist window (add, remove, reorder): Ctrl + L",
        "Save the current playlist as M3U8: Ctrl + S",
        "Inside the Playlist window: Enter plays, Delete removes, Alt + Up / Down Arrow moves",
        "",
        "=== Equalizer ===",
        "Open the Equalizer window: Ctrl + E",
        "Next / previous equalizer preset: Q / Shift + Q",
        "",
        "=== Audio Recorder ===",
        "Open the Audio Recorder window: Ctrl + Shift + R",
        "Start recording right away from the main or Recorder window, then stop and save: Ctrl + R",
        "Hear the level while recording (inside the Recorder window): Ctrl + L",
        "Microphone level slider in the Recorder window: arrows move one step, Page Up / Page Down ten steps; works while recording too",
        "",
        "=== Media Editor ===",
        "Open the Media Editor window: Ctrl + Shift + X",
        "",
        "=== Media Editor Ghost Shortcuts (work from anywhere) ===",
        "Turn ghost shortcuts on or off: Ctrl + Alt + Shift + G",
        "Open the Media Editor: Ctrl + Alt + Shift + O",
        "Set the split point at the current position: Ctrl + Alt + Shift + S",
        "Set a part start at the current position: Ctrl + Alt + Shift + B",
        "Set the part end and add the part: Ctrl + Alt + Shift + E",
        "Undo the last part or start: Ctrl + Alt + Shift + Z",
        "Add the current file to the “Split several files” list: Ctrl + Alt + Shift + L",
        "Add the current file to the merge list: Ctrl + Alt + Shift + M",
        "Announce what is set in the editor: Ctrl + Alt + Shift + I",
        "Start the work: Ctrl + Alt + Shift + Enter",
        "Cancel the running work: Ctrl + Alt + Shift + C",
        "",
        "=== Options & Help ===",
        "Open Options: Ctrl + Shift + P",
        "Switch Options tabs: Ctrl + Tab, or Ctrl + 1 to Ctrl + 6",
        "Open the Format Converter: from the Tools menu",
        "Sleep timer, export and import settings: from the Tools menu",
        "User guide: F1",
        "Export the shortcuts guide as text: Ctrl + Shift + H",
        "Save a diagnostic report to the Desktop (no personal data): Ctrl + Shift + D",
        "Exit the program: Ctrl + Q",
    ]


def _k(keys):
    """
    مفاتيح داخل النص: كل مفتاح في <kbd> والعلامة + بينها.

    الاختصار كله من اليسار لليمين: في الصفحة العربية كانت المفاتيح تُرتَّب
    من اليمين فيظهر Ctrl+Shift+X كأنه X+Shift+Ctrl.
    """
    joined = "+".join(f"<kbd>{escape(part.strip())}</kbd>" for part in keys.split("+"))
    return f'<span class="combo" dir="ltr">{joined}</span>'


def _sections(lang, steps):
    """
    أقسام الدليل: (معرّف، عنوان، [نقاط]). النقطة نص HTML، وقد تبدأ بعنوان
    فرعي بين <b>.

    steps: مقادير التقديم الحالية بالثواني، ليطابق الدليل ما ضبطه المستخدم.
    """
    amount = {kind: _amount_text(lang, seconds) for kind, seconds in steps.items()}
    k = _k

    if lang == "ar":
        return [
            ("new", "ما الجديد في الإصدار " + APP_VERSION, [
                f"<b>محرر الوسائط:</b> قص الصوت والفيديو ودمجهما داخل البرنامج، مع اختصارات «شبحية» تعمل وأنت تسمع في المشغّل ({k('Ctrl+Shift+X')}).",
                f"<b>الراديو والبث المباشر:</b> افتح أي رابط بـ {k('Ctrl+U')}، ويُعلَن اسم ما يُذاع الآن كلما تغيّر.",
                f"<b>قوائم تشغيل محفوظة:</b> ابنِ قائمتك ورتّبها بـ {k('Ctrl+L')} واحفظها بـ {k('Ctrl+S')}.",
                f"<b>المعادل الصوتي:</b> 18 نمطًا جاهزًا تتنقل بينها بـ {k('Q')}، وعشرة نطاقات تضبطها بنفسك ({k('Ctrl+E')}).",
                "<b>مسجّل أنقى:</b> شريط لمستوى المايكروفون داخل المسجّل، وتقليل ضوضاء يعمل فعلًا مع أي مايكروفون، ووضع حصري يعمل مع مايكروفونات USB، ودمج المايكروفون وصوت الجهاز بلا انقطاع.",
                "<b>محول أذكى:</b> «أعلى جودة» لا يضخّم الملف بلا فائدة، والصيغ التي كانت تفشل بمعدلات عيّنة عالية صارت تنجح.",
                "<b>مظهر داكن حقيقي</b> للبرنامج كله، وواجهة عربية من اليمين إلى اليسار.",
                "<b>مقادير تقديم تختارها بنفسك</b> لكل مفتاح مساعد، ومجلدات حفظ ثابتة ومرتبة في المستندات.",
            ]),
            ("start", "البداية", [
                f"<b>فتح الملفات:</b> {k('Ctrl+O')} لملف، و{k('Ctrl+Shift+O')} لمجلد كامل، و{k('Ctrl+U')} لرابط. وقائمة «ملف» فيها «الملفات الأخيرة».",
                "<b>من مستكشف ويندوز:</b> انقر بزر الفأرة الأيمن على ملف صوت أو فيديو فتجد «تشغيل» و«تحويل» بالبرنامج، وعلى مجلد فتجد «تحويل» لكل ما فيه. ويظهر البرنامج كذلك في «فتح باستخدام».",
                "<b>الاستئناف:</b> يتذكر البرنامج أين توقفت في كل ملف، ويكمل من عنده عند فتحه مرة أخرى، ويتذكر سرعة التشغيل لكل ملف على حدة.",
                "<b>التنقل في المجلد:</b> فتح ملف يُحضر بقية ملفات مجلده، فتنتقل بينها بـ " + k("Page Down") + " و" + k("Page Up") + ". ومن الخيارات تختار ما يحدث عند انتهاء الملف: لا شيء، أو الانتقال إلى التالي.",
                "<b>مفاتيح الوسائط:</b> أزرار التشغيل والإيقاف والتالي والسابق في لوحة المفاتيح تعمل مع البرنامج حتى وهو في الخلفية، ويمكن إطفاؤها من الخيارات.",
            ]),
            ("playback", "التشغيل والتنقل داخل الملف", [
                f"<b>التشغيل:</b> {k('Space')} للتشغيل والإيقاف المؤقت، و{k('Ctrl+Space')} للإيقاف والعودة إلى البداية، و{k('M')} للكتم.",
                f"<b>الصوت:</b> الأسهم لأعلى ولأسفل بخطوة 5%، ومع {k('Ctrl')} بخطوة 20%.",
                f"<b>التقديم والإرجاع:</b> الأسهم يمينًا ويسارًا بـ {amount['normal']}، ومع {k('Ctrl')} بـ {amount['ctrl']}، ومع {k('Shift')} بـ {amount['shift']}، ومع {k('Alt')} بـ {amount['alt']}، ومع {k('Ctrl+Shift')} بـ {amount['ctrl_shift']}. كل مقدار منها تغيّره من الخيارات، تبويب «التشغيل والتنقل».",
                f"<b>القفز المباشر:</b> أرقام لوحة الأرقام من 1 إلى 9 تقفز إلى 10% حتى 90% من الملف، و{k('Numpad 0')} أو {k('Home')} إلى البداية، و{k('End')} إلى آخر خمس ثوانٍ.",
                f"<b>الذهاب إلى وقت محدد:</b> {k('Ctrl+G')} ثم اكتب الوقت: <code>90</code> أو <code>1:30</code> أو <code>1:02:03</code>. إن كان بعد نهاية الملف يخبرك بدل أن ينتقل إلى مكان خاطئ.",
                f"<b>السرعة:</b> {k('Alt')} مع السهم لأعلى أو لأسفل يغيّرها بمقدار 0.25×، و{k('Alt+Numpad 0')} يعيدها طبيعية، دون أن تتغير نبرة الصوت.",
                f"<b>ملء الشاشة:</b> {k('F11')} للفيديو، و{k('Escape')} للخروج منه.",
            ]),
            ("announce", "الإعلانات الصوتية والوقت", [
                f"<b>الوقت عند الطلب:</b> {k('T')} للوقت الحالي والمتبقي والكامل معًا، و{k('R')} للمتبقي فقط، و{k('E')} لمدة الملف كاملة.",
                f"<b>المفتاح الرئيسي:</b> {k('Ctrl+Alt+A')} يوقف كل إعلانات البرنامج فورًا ويعيدها.",
                "<b>إعلان لكل شيء على حدة:</b> تبويب «إمكانية الوصول» في الخيارات فيه صندوق اختيار لكل إعلان: اسم الملف وترتيبه في القائمة، والاستئناف، وحالة التشغيل، والصوت والكتم، والسرعة، والعلامات، ومؤقت النوم، ونمط المعادل، وما يُذاع في الراديو، وغيرها. فعّل ما ينفعك وأسكت الباقي.",
                "<b>إعلانات التقديم بلا ثرثرة:</b> اختر أصغر قفزة يُعلَن عندها الموضع الجديد (كل القفزات، أو من دقيقة أو 5 أو 10 أو 30 دقيقة فأكثر). أرقام لوحة الأرقام والذهاب إلى وقت محدد تُعلَن دائمًا.",
                "<b>معلومات الملف:</b> يمكن أن يعلن البرنامج صيغة الملف وجودته ومدته عند فتحه، وحالة التحميل إن احتاج الملف وقتًا.",
            ]),
            ("bookmarks", "العلامات المرجعية", [
                f"<b>ضع علامة</b> عند أي موضع بـ {k('Ctrl+B')}، وتنقّل بين العلامات بـ {k('F2')} و{k('Shift+F2')}، واحذف علامات الملف كلها بـ {k('Ctrl+Shift+B')}.",
                f"<b>سمِّ العلامة</b> بـ {k('Ctrl+Alt+B')}، فتسمع «بداية الفصل الثالث» بدل «علامة عند 12 دقيقة». اترك الاسم فارغًا لإزالته.",
                "<b>العلامات أداة للمحرر أيضًا:</b> في محرر الوسائط تختار الأوقات «من العلامات» بدل كتابتها، وانظر قسم المحرر.",
            ]),
            ("streams", "الراديو والروابط وقوائم التشغيل", [
                f"<b>الروابط:</b> {k('Ctrl+U')} يفتح خانة الرابط، وإن كنت نسخت رابطًا تجده مكتوبًا فيها. يشغّل الراديو والبث المباشر والملفات على الإنترنت، ويعيد الاتصال وحده إن انقطع البث.",
                f"<b>ما يُذاع الآن:</b> في المحطات التي ترسل اسم الأغنية أو البرنامج يُعلَن الاسم كلما تغيّر، و{k('N')} يعيده متى شئت.",
                f"<b>قائمة التشغيل:</b> {k('Ctrl+L')} يفتح القائمة الحالية: أضف ملفات أو مجلدات أو روابط محطات، واحذف بـ {k('Delete')}، ورتّب بـ {k('Alt')} مع الأسهم، وشغّل بـ {k('Enter')}.",
                f"<b>حفظ القوائم:</b> {k('Ctrl+S')} يحفظها بصيغة M3U8 التي تفتحها معظم المشغلات. إن كانت الملفات داخل مجلد القائمة تبقى صالحة لو نقلت المجلد كله. وأي قائمة M3U أو M3U8 أو PLS تُفتح مثل أي ملف بـ {k('Ctrl+O')}.",
            ]),
            ("eq", "المعادل الصوتي", [
                f"<b>الأنماط الجاهزة:</b> {k('Q')} و{k('Shift+Q')} يتنقلان بين 18 نمطًا (منها «سماعات الرأس» و«جهير كامل» و«قاعة كبيرة») ويُنطق اسم كل نمط.",
                f"<b>الضبط اليدوي:</b> {k('Ctrl+E')} يفتح نافذة فيها التضخيم المسبق وعشرة نطاقات تعدّلها بالأسهم وتسمع النتيجة فورًا. تعديل أي نطاق يجعل النمط «مخصص»، و«إلغاء» يعيد ما كان قبل فتح النافذة.",
                "<b>يبقى محفوظًا:</b> اختيارك يسري على كل الملفات ويبقى بعد إغلاق البرنامج.",
            ]),
            ("recorder", "مسجّل الصوت", [
                f"<b>الفتح والتسجيل السريع:</b> {k('Ctrl+Shift+R')} يفتح نافذة المسجّل. و{k('Ctrl+R')} من النافذة الرئيسية أو نافذة المسجّل يبدأ التسجيل فورًا بآخر إعداداتك، والضغطة الثانية توقفه وتحفظه. إن أغلقت النافذة والتسجيل جارٍ تختفي ويستمر التسجيل في الخلفية.",
                "<b>قائمة أجهزة نظيفة:</b> كل مايكروفون يظهر مرة واحدة باسم مفهوم، ويختار له البرنامج أفضل طريقة اتصال وإعداداته المناسبة، ولكل جهاز إعداداته المحفوظة على حدة.",
                f"<b>مستوى المايكروفون:</b> شريط «مستوى المايكروفون» تحت اختيار الجهاز هو نفسه مستوى المايكروفون في إعدادات الصوت في ويندوز. التشوّه يحدث داخل المايكروفون قبل أن يصل الصوت للبرنامج، فخفض هذا المستوى هو العلاج الحقيقي. حرّكه بالأسهم درجة درجة، أو بـ {k('Page Up')} و{k('Page Down')} عشر درجات، ويمكنك تغييره أثناء التسجيل. ابدأ من نحو 70%. وإن كان الجهاز لا يسمح بالتحكم في مستواه يتعطل الشريط ويظهر تحته السبب.",
                "<b>اختبار المايكروفون:</b> زر يسجّل عشر ثوانٍ ثم يخبرك نصًّا يقرؤه قارئ الشاشة: هل المستوى جيد أم مرتفع أم منخفض أم لا يصل صوت أصلًا، ومعه خطوات الإصلاح.",
                f"<b>المستوى أثناء التسجيل:</b> {k('Ctrl+L')} ينطق المستوى الحالي وأعلى قمة، وعند الطلب فقط حتى لا يتسجّل صوت قارئ الشاشة في الملف. وإن ارتفع المستوى حتى التشوّه يظهر تنبيه في النافذة، ويخبرك البرنامج عند الحفظ بعدد المواضع المتأثرة.",
                "<b>تحسين صوت المايكروفون:</b> «بلا معالجة» يحفظ الصوت كما خرج من كرت الصوت. «تنقية» تزيل الطنين المنخفض (اهتزاز المكتب ومروحة الجهاز ولمس المايكروفون) وتمنع قص القمم دون أن تمس الكلام. «تنقية وتقليل الضوضاء الثابتة» تخفض معها الوشيش والتكييف والمروحة وطنين الكهرباء: يقيس البرنامج ضوضاء مايكروفونك وغرفتك بنفسه أثناء التسجيل، فيخفضها نحو أربع مرات في سكتات الكلام دون أن يصير الصوت معدنيًا. التحسين للمايكروفون وحده، ولا يمس صوت الجهاز.",
                "<b>الوضع الحصري (وصول مباشر لكرت الصوت):</b> يأخذ البرنامج الصوت من الكرت مباشرة دون معالجة ويندوز، فلا تحسينات خفية ولا خلط مع برامج أخرى، لكن لا يستعمل برنامج آخر المايكروفون أثناء التسجيل. بعض المايكروفونات لا تقبله إلا بدقتها الأصلية (192000 مثلًا)، فيلتقط البرنامج بها ويحوّل الصوت إلى الدقة التي اخترتها، ويبقى الملف بحجمه المعتاد. وإن رفض الكرت الوضع الحصري تمامًا يخبرك البرنامج ويسجّل بالوضع العادي.",
                "<b>صوتك مع صوت الجهاز:</b> فعّل «دمج جهاز إدخال ثانٍ» فيختار البرنامج صوت النظام (الستيريو ميكس) تلقائيًا. يُدمج المصدران عيّنة بعيّنة ويوازن البرنامج مستواهما، فلا يضيع صوتك تحت الموسيقى ولا تحدث انقطاعات.",
                "<b>الجودة والصيغة:</b> معدل العيّنة (48000 كافية لكل ما تسمعه الأذن)، وأحادي أو ستيريو، وعمق 16 أو 24 أو 32 بت، والصيغة: WAV بلا ضغط، أو MP3 وM4A وغيرهما ملفات أصغر بكثير تُكتب مباشرة أثناء التسجيل. «معدل البت» يبدأ عند «أعلى جودة متاحة» ويعرف سقف كل صيغة.",
            ]),
            ("editor", "محرر الوسائط", [
                f"<b>أربع عمليات</b> من قائمة «أدوات» أو {k('Ctrl+Shift+X')}: «قص ملف» إلى جزأين، و«قص عدة ملفات» عند الوقت نفسه دفعة واحدة، و«مقاطع من ملف» تُضم بالترتيب في ملف واحد، و«دمج ملفات» بالترتيب الذي تختاره.",
                "<b>بلا فقد في الجودة:</b> الناتج بصيغة الأصل نفسها، والصوت يُنسخ كما هو دون إعادة ترميز. ملفات الصوت المختلفة الصيغ تُدمج بإعادة ترميزها، أما ملفات الفيديو المدموجة فيجب أن تتطابق في الصيغة والمقاس، وإلا يخبرك المحرر بالسبب.",
                "<b>طريقتان للفيديو:</b> «سريع بنفس الجودة» يبدأ القص من أقرب إطار مفتاحي (صورة كاملة كل بضع ثوانٍ) ويخبرك أين قص بالضبط، و«دقيق بالثانية» يقص عند الوقت المطلوب لكنه أبطأ.",
                "<b>الأوقات بلا كتابة:</b> زر «الموضع الحالي» يأخذ الوقت من المشغّل وأنت تسمع. أو ضع علامة بـ " + k("Ctrl+B") + " عند كل موضع، ثم اختر الوقت «من العلامات»، أو اضغط «مقاطع من العلامات» فتصير كل علامتين متتاليتين بداية مقطع ونهايته. وتقبل خانة الوقت أجزاء الثانية مثل <code>1:30.5</code>.",
                f"<b>الاختصارات الشبحية:</b> تعمل من أي مكان والمشغّل في المقدمة أو الخلفية: حدد نقطة القص وبداية المقطع ونهايته، وأضف الملف الحالي إلى قوائم القص والدمج، واسمع ما حُدِّد، وابدأ العمل أو ألغِه، دون أن تفتح نافذة المحرر. تشغيلها وإيقافها بـ {k('Ctrl+Alt+Shift+G')} أو من قائمة «أدوات»، وكلها في آخر هذا الدليل. وإغلاق المحرر يخفيه فقط، فلا يضيع ما حددته.",
                "<b>إعدادات المحرر:</b> تبويب «محرر الوسائط» في الخيارات: طريقة قص الفيديو الافتراضية، وإعلان التقدم كل كم بالمئة، وتغيير أي اختصار شبحي (ويرفض البرنامج الاختصار المكرر).",
            ]),
            ("converter", "محول الصيغ", [
                "<b>الفتح:</b> من قائمة «أدوات»، أو بزر الفأرة الأيمن على ملف أو مجلد في مستكشف ويندوز. يحوّل ملفًا أو مجلدًا كاملًا دفعة واحدة، ويعلن تقدم كل ملف ونتيجته.",
                "<b>معلومات المصدر الحقيقية:</b> الترميز والدقة ومعدل البت الفعلي ومعدل العيّنة والقنوات، لتعرف ما تحوّله قبل أن تبدأ.",
                "<b>أعلى جودة بذكاء:</b> «أعلى جودة متاحة» تعرف سقف كل صيغة (320 كيلوبت لـ MP3، و640 لـ AC3، و256 لـ Opus أحادي)، ولا تتجاوز جودة المصدر المضغوط فلا يكبر الملف بلا فائدة. وإن اخترت رقمًا فوق ما تحتمله الصيغة نزل البرنامج إلى أقصاها بدل أن يفشل التحويل، وكذلك معدلات العيّنة غير المدعومة.",
                "<b>إعدادات متقدمة:</b> للصوت معدل العيّنة والقنوات، وللفيديو جودة ثابتة (CRF) أو معدل بت ثابت، والدقة ومعدل الإطارات. وقيمها الافتراضية في تبويب «المحول» في الخيارات.",
            ]),
            ("folders", "أين تُحفظ ملفاتك", [
                "في «المستندات» مجلد باسم البرنامج، وفيه: «التسجيلات» و«الملفات المحولة» و«محرر الوسائط» بداخله «صوت» و«فيديو».",
                "تُسمّى المجلدات مرة واحدة بلغة البرنامج عند أول تشغيل ولا تتغير بعد ذلك، وإن كان الاسم مأخوذًا يُضاف إليه رقم. ومجلدات الإصدارات السابقة تُضم إليها تلقائيًا.",
                "عند حفظ تسجيل يخبرك البرنامج بمدته والمكان الذي حُفظ فيه.",
            ]),
            ("options", "الخيارات والتخصيص", [
                f"<b>الخيارات</b> بـ {k('Ctrl+Shift+P')}، وفيها ستة تبويبات تتنقل بينها بـ {k('Ctrl+Tab')} أو {k('Ctrl+1')} إلى {k('Ctrl+6')}: «عام» و«التشغيل والتنقل» و«إمكانية الوصول» و«المحول» و«المسجّل» و«محرر الوسائط».",
                "<b>المظهر:</b> «يتبع ويندوز» أو «فاتح» أو «داكن». الداكن يشمل القوائم وشريط العنوان والنوافذ كلها، ويسري بعد إعادة فتح البرنامج. وفي وضع التباين العالي يستعمل البرنامج ألوان ويندوز دائمًا.",
                "<b>اللغة:</b> العربية بواجهة من اليمين إلى اليسار، أو الإنجليزية. تسري بعد إعادة التشغيل.",
                "<b>أشياء أخرى في «عام»:</b> عدد الملفات الأخيرة، ونغمة هادئة عند انتهاء التحويل أو التسجيل، ومفاتيح الوسائط، وزرّا «البرامج الافتراضية» و«خصوصية المايكروفون» في ويندوز.",
                "<b>مؤقت النوم:</b> من قائمة «أدوات»: يوقف التشغيل بعد عدد من الدقائق، أو عند نهاية الملف الحالي. اختر صفرًا لإلغائه.",
                "<b>نقل إعداداتك:</b> «تصدير الإعدادات» و«استيراد الإعدادات» من قائمة «أدوات»، لجهاز جديد أو نسخة احتياطية.",
                "<b>النافذة كما تركتها:</b> حجمها وموضعها يُحفظان بين المرات.",
            ]),
            ("help", "عند مواجهة مشكلة", [
                f"<b>تقرير تشخيصي:</b> {k('Ctrl+Shift+D')} يحفظ على سطح المكتب ملفًا نصيًا فيه معلومات النظام وسجل البرنامج، و<b>بلا أي معلومات شخصية</b>: لا اسم جهازك ولا اسم المستخدم ولا مسارات ملفاتك، فيمكنك نشره في مجموعة عامة دون قلق.",
                "<b>تفاصيل اختبار المايكروفون:</b> في نتيجة الاختبار زر «نسخ التفاصيل التقنية» ينسخ سطرًا واحدًا خاليًا من أي بيانات تعرّفك، جاهزًا للصق في رسالة الدعم.",
                "<b>المايكروفون لا يصل صوته:</b> تأكد من السماح للتطبيقات باستعمال المايكروفون، وزر «خصوصية المايكروفون» في تبويب «عام» يفتح الإعداد مباشرة. وإن كان برنامج آخر يمسك المايكروفون في الوضع الحصري أغلقه وحاول مرة أخرى.",
            ]),
            ("license", "الترخيص", [
                "البرنامج حر تحت رخصة GNU GPL الإصدار الثالث: لك أن تستعمله وتنسخه وتعدّله وتوزّعه بشروطها، وهو بلا أي ضمان.",
                "نص الرخصة وتراخيص المكتبات المضمَّنة في ملفي LICENSE وTHIRD-PARTY.md ومجلد licenses بجانب البرنامج.",
            ]),
        ]

    return [
        ("new", "What's New in Version " + APP_VERSION, [
            f"<b>Media Editor:</b> cut and merge audio and video inside the program, with “ghost” shortcuts that work while you listen in the player ({k('Ctrl+Shift+X')}).",
            f"<b>Radio and live streams:</b> open any link with {k('Ctrl+U')}, and what is playing now is announced whenever it changes.",
            f"<b>Saved playlists:</b> build and reorder your list with {k('Ctrl+L')} and save it with {k('Ctrl+S')}.",
            f"<b>Equalizer:</b> 18 presets you cycle with {k('Q')}, and ten bands you adjust yourself ({k('Ctrl+E')}).",
            "<b>Cleaner recordings:</b> a microphone level slider inside the recorder, noise reduction that really works with any microphone, exclusive mode that works with USB microphones, and microphone plus system audio mixed without dropouts.",
            "<b>Smarter converter:</b> “Highest quality” no longer inflates files for nothing, and formats that failed at high sample rates now succeed.",
            "<b>A real dark mode</b> for the whole program, and a right-to-left Arabic interface.",
            "<b>Seek amounts you choose</b> for each modifier key, and fixed, tidy output folders in Documents.",
        ]),
        ("start", "Getting Started", [
            f"<b>Opening files:</b> {k('Ctrl+O')} for a file, {k('Ctrl+Shift+O')} for a whole folder, {k('Ctrl+U')} for a link. The File menu has “Recent Files”.",
            "<b>From Windows Explorer:</b> right-click an audio or video file for “Play” and “Convert” with the program, or a folder to convert everything in it. The program also appears in “Open with”.",
            "<b>Resume:</b> the program remembers where you stopped in each file and continues from there when you open it again, and it remembers the playback speed of each file separately.",
            "<b>Folder navigation:</b> opening a file brings in the rest of its folder, so you move between them with " + k("Page Down") + " and " + k("Page Up") + ". In Options you choose what happens when a file ends: nothing, or go to the next one.",
            "<b>Media keys:</b> the play, stop, next and previous keys on your keyboard work with the program even in the background; you can turn this off in Options.",
        ]),
        ("playback", "Playback and Moving Within a File", [
            f"<b>Playback:</b> {k('Space')} plays and pauses, {k('Ctrl+Space')} stops and returns to the start, {k('M')} mutes.",
            f"<b>Volume:</b> Up and Down Arrow in 5% steps, with {k('Ctrl')} in 20% steps.",
            f"<b>Seeking:</b> Right and Left Arrow by {amount['normal']}, with {k('Ctrl')} by {amount['ctrl']}, with {k('Shift')} by {amount['shift']}, with {k('Alt')} by {amount['alt']}, with {k('Ctrl+Shift')} by {amount['ctrl_shift']}. Each amount can be changed in Options, “Playback & Navigation” tab.",
            f"<b>Direct jumps:</b> Numpad 1 to 9 jump to 10% through 90% of the file, {k('Numpad 0')} or {k('Home')} to the start, {k('End')} to the last five seconds.",
            f"<b>Go to a time:</b> {k('Ctrl+G')}, then type the time: <code>90</code>, <code>1:30</code> or <code>1:02:03</code>. If it is past the end of the file you are told instead of being taken to the wrong place.",
            f"<b>Speed:</b> {k('Alt')} with Up or Down Arrow changes it by 0.25×, and {k('Alt+Numpad 0')} resets it, without changing the pitch.",
            f"<b>Fullscreen:</b> {k('F11')} for video, {k('Escape')} to leave it.",
        ]),
        ("announce", "Spoken Announcements and Time", [
            f"<b>Time on demand:</b> {k('T')} for current, remaining and total time together, {k('R')} for remaining only, {k('E')} for the full duration.",
            f"<b>Master switch:</b> {k('Ctrl+Alt+A')} silences all of the program's announcements at once and brings them back.",
            "<b>One setting per announcement:</b> the Accessibility tab in Options has a checkbox for each announcement: file name and playlist position, resume, playback state, volume and mute, speed, bookmarks, sleep timer, equalizer preset, radio now playing and more. Keep what helps you and silence the rest.",
            "<b>Seeking without chatter:</b> choose the smallest jump whose new position is announced (every jump, or from 1, 5, 10 or 30 minutes up). Numpad jumps and Go to time are always announced.",
            "<b>File information:</b> the program can announce a file's format, quality and duration when it opens, and the loading state if a file takes time.",
        ]),
        ("bookmarks", "Bookmarks", [
            f"<b>Add a bookmark</b> anywhere with {k('Ctrl+B')}, move between bookmarks with {k('F2')} and {k('Shift+F2')}, and clear a file's bookmarks with {k('Ctrl+Shift+B')}.",
            f"<b>Name a bookmark</b> with {k('Ctrl+Alt+B')}, so you hear “Start of chapter three” instead of “Bookmark at 12 minutes”. Leave the name empty to remove it.",
            "<b>Bookmarks also drive the editor:</b> in the Media Editor you pick times “From Bookmarks” instead of typing them; see the editor section.",
        ]),
        ("streams", "Radio, Links and Playlists", [
            f"<b>Links:</b> {k('Ctrl+U')} opens the link box, already filled in if you copied a link. It plays radio, live streams and online files, and reconnects by itself if the stream drops.",
            f"<b>Now playing:</b> on stations that send the song or show name, it is announced whenever it changes, and {k('N')} repeats it any time.",
            f"<b>Playlist:</b> {k('Ctrl+L')} opens the current list: add files, folders or station links, remove with {k('Delete')}, reorder with {k('Alt')} and the arrows, play with {k('Enter')}.",
            f"<b>Saving playlists:</b> {k('Ctrl+S')} saves as M3U8, which most players open. If the files are inside the playlist's folder, the list keeps working when you move the whole folder. Any M3U, M3U8 or PLS list opens like a file with {k('Ctrl+O')}.",
        ]),
        ("eq", "Equalizer", [
            f"<b>Presets:</b> {k('Q')} and {k('Shift+Q')} cycle 18 presets (including “Headphones”, “Full Bass” and “Large Hall”) and speak each name.",
            f"<b>Manual adjustment:</b> {k('Ctrl+E')} opens a window with preamp and ten bands you adjust with the arrows and hear immediately. Changing any band makes the preset “Custom”, and “Cancel” restores what you had before opening the window.",
            "<b>It stays:</b> your choice applies to every file and is kept after closing the program.",
        ]),
        ("recorder", "Audio Recorder", [
            f"<b>Opening and quick recording:</b> {k('Ctrl+Shift+R')} opens the recorder. {k('Ctrl+R')} from the main or Recorder window starts recording right away with your last settings, and pressing it again stops and saves. If you close the window while recording, it hides and the recording continues in the background.",
            "<b>A clean device list:</b> each microphone appears once with a readable name; the program picks the best connection and settings for it, and each device keeps its own saved settings.",
            f"<b>Microphone level:</b> the “Microphone level” slider under the device choice is the same microphone level as in Windows sound settings. Distortion happens inside the microphone before the sound reaches the program, so lowering this level is the real cure. Move it one step with the arrows, or ten with {k('Page Up')} and {k('Page Down')}; you can change it while recording. Start around 70%. If a device doesn't allow its level to be changed, the slider is disabled and the reason is shown under it.",
            "<b>Microphone test:</b> a button that records ten seconds and then tells you, in text your screen reader reads, whether the level is good, too high, too low or silent, with steps to fix it.",
            f"<b>Level while recording:</b> {k('Ctrl+L')} speaks the current level and highest peak, only on request so the screen reader's voice isn't recorded into the file. If the level gets high enough to distort, a warning appears in the window, and when saving you are told how many spots were affected.",
            "<b>Microphone enhancement:</b> “None” keeps the sound exactly as the sound card gives it. “Clean up” removes low hum (desk bumps, computer fans, handling noise) and prevents clipped peaks without touching speech. “Clean up and reduce steady noise” also lowers hiss, air conditioning, fans and electrical hum: the program measures your own microphone and room while recording and lowers the noise about four times in the pauses, without making the voice sound metallic. Enhancement applies to the microphone only, never to system audio.",
            "<b>Exclusive mode (direct access to the sound card):</b> the program takes the sound straight from the card, skipping Windows processing, so there are no hidden effects and no mixing with other programs, but no other program can use the microphone while recording. Some microphones only accept it at their native rate (192000, for example); the program captures at that rate and converts to the one you chose, so the file keeps its usual size. If the card refuses exclusive mode entirely, you are told and recording uses the normal mode.",
            "<b>Your voice with system audio:</b> turn on “Merge a second input device” and the program picks system audio (Stereo Mix) automatically. The two sources are mixed sample by sample and their levels balanced, so your voice doesn't disappear under the music and there are no dropouts.",
            "<b>Quality and format:</b> sample rate (48000 covers everything the ear hears), mono or stereo, 16, 24 or 32 bit, and the format: uncompressed WAV, or much smaller MP3, M4A and others written directly while recording. “Bitrate” starts at “Highest available quality”, which knows each format's ceiling.",
        ]),
        ("editor", "Media Editor", [
            f"<b>Four tasks</b> from the Tools menu or {k('Ctrl+Shift+X')}: “Split a file” in two, “Split several files” at the same time in one go, “Parts of a file” joined in order into one file, and “Merge files” in the order you choose.",
            "<b>No quality loss:</b> the result keeps the source format, and audio is copied as is without re-encoding. Audio files of different formats are merged by re-encoding them; merged video files must share the same format and size, otherwise the editor tells you why.",
            "<b>Two modes for video:</b> “Fast, same quality” starts the cut at the nearest keyframe (a full picture every few seconds) and tells you exactly where it cut; “Exact to the second” cuts at the requested time but is slower.",
            "<b>Times without typing:</b> the “Current Position” button takes the time from the player while you listen. Or press " + k("Ctrl+B") + " at each spot, then pick a time “From Bookmarks”, or press “Parts from Bookmarks” so every two bookmarks in a row become a part's start and end. Time boxes accept fractions of a second, like <code>1:30.5</code>.",
            f"<b>Ghost shortcuts:</b> they work from anywhere, with the player in front or in the background: set the split point and a part's start and end, add the current file to the split and merge lists, hear what is set, and start or cancel the work, without opening the editor window. Turn them on or off with {k('Ctrl+Alt+Shift+G')} or from the Tools menu; they are all listed at the end of this guide. Closing the editor only hides it, so nothing you set is lost.",
            "<b>Editor settings:</b> the Media Editor tab in Options: the default video cut mode, progress announcements every few percent, and changing any ghost shortcut (duplicates are refused).",
        ]),
        ("converter", "Format Converter", [
            "<b>Opening:</b> from the Tools menu, or by right-clicking a file or folder in Windows Explorer. It converts a file or a whole folder in one go, announcing each file's progress and result.",
            "<b>Real source information:</b> codec, resolution, actual bitrate, sample rate and channels, so you know what you are converting before you start.",
            "<b>Highest quality, wisely:</b> “Highest available quality” knows each format's ceiling (320 kbps for MP3, 640 for AC3, 256 for mono Opus) and doesn't exceed the quality of a compressed source, so files don't grow for nothing. If you pick a number above what a format allows, the program uses its maximum instead of failing, and the same goes for unsupported sample rates.",
            "<b>Advanced settings:</b> sample rate and channels for audio; constant quality (CRF) or constant bitrate, resolution and frame rate for video. Their defaults are in the Converter tab in Options.",
        ]),
        ("folders", "Where Your Files Are Saved", [
            "In Documents, a folder named after the program containing “Recordings”, “Converted Files” and “Media Editor” with “Audio” and “Video” inside.",
            "The folders are named once, in the program's language, the first time it runs and never renamed afterwards; if a name is taken, a number is added. Folders from previous versions are merged into them automatically.",
            "When a recording is saved, the program tells you its length and where it was saved.",
        ]),
        ("options", "Options and Customization", [
            f"<b>Options</b> with {k('Ctrl+Shift+P')}, with six tabs you switch with {k('Ctrl+Tab')} or {k('Ctrl+1')} to {k('Ctrl+6')}: General, Playback & Navigation, Accessibility, Converter, Recorder and Media Editor.",
            "<b>Appearance:</b> Follow Windows, Light or Dark. Dark covers menus, title bars and every window, and takes effect after reopening the program. In high contrast mode the program always uses Windows' colours.",
            "<b>Language:</b> Arabic with a right-to-left interface, or English. Takes effect after a restart.",
            "<b>More in General:</b> number of recent files, a gentle chime when a conversion or recording finishes, media keys, and buttons for Windows' Default Apps and Microphone Privacy settings.",
            "<b>Sleep timer:</b> from the Tools menu: stops playback after a number of minutes, or at the end of the current file. Choose zero to cancel it.",
            "<b>Moving your settings:</b> “Export Settings” and “Import Settings” in the Tools menu, for a new computer or a backup.",
            "<b>The window as you left it:</b> its size and position are kept between sessions.",
        ]),
        ("help", "When Something Goes Wrong", [
            f"<b>Diagnostic report:</b> {k('Ctrl+Shift+D')} saves a text file to your Desktop with system information and the program log, with <b>no personal information</b>: no computer name, user name or file paths, so you can post it in a public group without worry.",
            "<b>Microphone test details:</b> the test result has a “Copy technical details” button that copies a single line free of anything that identifies you, ready to paste into a support message.",
            "<b>No sound from the microphone:</b> make sure apps are allowed to use the microphone; the “Microphone Privacy” button in the General tab opens that setting directly. If another program holds the microphone in exclusive mode, close it and try again.",
        ]),
        ("license", "License", [
            "The program is free software under the GNU GPL version 3: you may use, copy, modify and distribute it under its terms, and it comes with no warranty.",
            "The license text and the licenses of the bundled libraries are in LICENSE, THIRD-PARTY.md and the licenses folder next to the program.",
        ]),
    ]


# تسلسل مفاتيح لاتيني داخل سطر عربي: «Ctrl + Tab» و«Numpad 1» و«F11»
_KEY_RUN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 +./]*[A-Za-z0-9]|[A-Za-z0-9]")


def _keys_html(keys):
    """
    خانة المفاتيح في جدول الاختصارات.

    مفاتيح وحدها: <kbd> واحد من اليسار لليمين. ومعها كلام عربي («أو»
    و«إلى» و«من قائمة أدوات»): الكلام بخطه العادي من اليمين، وكل تسلسل
    مفاتيح في <kbd> وحده؛ بخط الأكواد كانت الحروف العربية مفكّكة.
    """
    if not any("؀" <= ch <= "ۿ" for ch in keys):
        return f'<kbd dir="ltr">{escape(keys)}</kbd>'
    parts, last = [], 0
    for match in _KEY_RUN.finditer(keys):
        parts.append(escape(keys[last:match.start()]))
        parts.append(f'<kbd dir="ltr">{escape(match.group())}</kbd>')
        last = match.end()
    parts.append(escape(keys[last:]))
    return f'<span class="mixed-keys" dir="rtl">{"".join(parts)}</span>'


def _shortcuts_html(lines):
    """قائمة الاختصارات: عنوان فرعي لكل قسم، وجدول مفتاح لكل سطر."""
    html = []
    open_list = False
    for line in lines:
        if not line:
            continue
        if line.startswith("==="):
            if open_list:
                html.append("</ul>")
            html.append(f"<h3>{escape(line.strip('= ').strip())}</h3>")
            html.append('<ul class="keys">')
            open_list = True
            continue
        if not open_list:
            html.append('<ul class="keys">')
            open_list = True
        if ":" in line:
            desc, keys = line.split(":", 1)
            html.append(f"<li><span>{escape(desc.strip())}</span> {_keys_html(keys.strip())}</li>")
        else:
            html.append(f"<li>{escape(line)}</li>")
    if open_list:
        html.append("</ul>")
    return "\n".join(html)


def build_user_guide_html(tr, seek_kwargs: dict = None, shortcuts_kwargs: dict = None) -> str:
    """
    صفحة الدليل كاملة.

    seek_kwargs بقي للتوافق مع من يناديها؛ مقادير التقديم تؤخذ من
    shortcuts_kwargs["seek_steps"] (ما ضبطه المستخدم)، وإلا فالافتراضية.
    """
    lang = "ar" if getattr(tr, "lang", "ar") == "ar" else "en"
    is_ar = lang == "ar"
    shortcuts_kwargs = shortcuts_kwargs or {}
    steps = dict(_SEEK_DEFAULTS)
    steps.update(shortcuts_kwargs.get("seek_steps") or {})

    app_name = tr.t("app_title")
    title = f"{tr.t('menu_user_guide')} — {app_name}"
    sections = _sections(lang, steps)
    shortcuts_id = "shortcuts"
    shortcuts_title = "خريطة اختصارات لوحة المفاتيح" if is_ar else "Keyboard Shortcuts Map"
    toc_title = "المحتويات" if is_ar else "Contents"
    version_label = (f"الإصدار {APP_VERSION}" if is_ar else f"Version {APP_VERSION}")
    intro = (
        f"{escape(app_name)} مشغّل صوت وفيديو صُمّم ليُستعمل كله من لوحة المفاتيح ومع قارئ الشاشة، "
        "ومعه مسجّل صوت ومحول صيغ ومحرر للقص والدمج. كل ما يُرى في البرنامج يُسمع أيضًا، وكل ما يُسمع "
        "تتحكم في متى يُقال. في هذا الدليل كل ميزة واختصار، والعناوين تساعدك على التنقل بمفتاح H في قارئ الشاشة."
        if is_ar else
        f"{escape(app_name)} is an audio and video player built to be used entirely from the keyboard and with a "
        "screen reader, with an audio recorder, a format converter and an editor for cutting and merging. "
        "Everything you can see in the program can also be heard, and you decide when it is said. This guide covers "
        "every feature and shortcut; headings let you move around with H in your screen reader."
    )

    toc = "\n".join(
        f'<li><a href="#{sid}">{escape(stitle)}</a></li>' for sid, stitle, _items in sections
    ) + f'\n<li><a href="#{shortcuts_id}">{escape(shortcuts_title)}</a></li>'

    body = []
    for sid, stitle, items in sections:
        css = ' class="whats-new"' if sid == "new" else ""
        body.append(f'<section id="{sid}"{css}>')
        body.append(f"<h2>{escape(stitle)}</h2>")
        body.append("<ul>")
        body.extend(f"<li>{item}</li>" for item in items)
        body.append("</ul>")
        body.append("</section>")

    raw_shortcuts = get_shortcuts_list(lang, **shortcuts_kwargs)

    return f"""<!DOCTYPE html>
<html lang="{lang}" dir="{'rtl' if is_ar else 'ltr'}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>
    :root {{
        --bg: #f3f5f8;
        --card: #ffffff;
        --text: #1f2933;
        --muted: #52606d;
        --accent: #1f6fb2;
        --accent-soft: #e6f0fa;
        --border: #dde3ea;
        --kbd-bg: #eef3f8;
        --kbd-border: #b8c6d6;
        --new-bg: #f0f7ef;
        --new-border: #3d8b40;
    }}
    @media (prefers-color-scheme: dark) {{
        :root {{
            --bg: #15181d;
            --card: #1e232a;
            --text: #e4e8ee;
            --muted: #a3adb9;
            --accent: #6fb3f2;
            --accent-soft: #23303d;
            --border: #333b45;
            --kbd-bg: #29313b;
            --kbd-border: #4a5665;
            --new-bg: #1f2c22;
            --new-border: #6cc070;
        }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
        margin: 0;
        padding: 32px 16px;
        background: var(--bg);
        color: var(--text);
        font-family: 'Segoe UI', Tahoma, Arial, sans-serif;
        font-size: 16px;
        line-height: 1.85;
    }}
    main {{
        max-width: 920px;
        margin: 0 auto;
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 36px 40px;
    }}
    header {{ border-bottom: 3px solid var(--accent); margin-bottom: 24px; padding-bottom: 12px; }}
    h1 {{ margin: 0; font-size: 28px; color: var(--accent); }}
    .version {{ color: var(--muted); margin: 4px 0 0; }}
    .intro {{ font-size: 17px; }}
    nav {{ background: var(--accent-soft); border-radius: 8px; padding: 14px 22px; margin: 24px 0; }}
    nav h2 {{ margin: 0 0 6px; font-size: 18px; border: none; padding: 0; }}
    nav ol {{ margin: 0; padding-inline-start: 22px; columns: 2; column-gap: 32px; }}
    nav a {{ color: var(--accent); text-decoration: none; }}
    nav a:hover, nav a:focus {{ text-decoration: underline; }}
    h2 {{
        font-size: 21px;
        margin: 36px 0 10px;
        padding-bottom: 6px;
        border-bottom: 1px solid var(--border);
        color: var(--accent);
    }}
    h3 {{ font-size: 17px; margin: 22px 0 6px; color: var(--text); }}
    section ul {{ padding-inline-start: 22px; margin: 0; }}
    section li {{ margin-bottom: 10px; }}
    .whats-new {{
        background: var(--new-bg);
        border-inline-start: 5px solid var(--new-border);
        border-radius: 8px;
        padding: 4px 22px 10px;
    }}
    .whats-new h2 {{ border: none; color: var(--new-border); }}
    ul.keys {{ list-style: none; padding: 0; margin: 0; border: 1px solid var(--border); border-radius: 8px; }}
    ul.keys li {{
        display: flex;
        justify-content: space-between;
        gap: 16px;
        padding: 8px 14px;
        margin: 0;
        border-bottom: 1px solid var(--border);
    }}
    ul.keys li:last-child {{ border-bottom: none; }}
    kbd {{
        background: var(--kbd-bg);
        border: 1px solid var(--kbd-border);
        border-radius: 4px;
        padding: 1px 7px;
        font-family: Consolas, 'Courier New', monospace;
        font-size: 14px;
        white-space: nowrap;
        direction: ltr;
        unicode-bidi: isolate;
    }}
    .combo {{ unicode-bidi: isolate; white-space: nowrap; }}
    ul.keys kbd {{ white-space: normal; text-align: end; }}
    .mixed-keys {{ text-align: end; }}
    .mixed-keys kbd {{ white-space: nowrap; }}
    code {{ font-family: Consolas, monospace; direction: ltr; unicode-bidi: isolate; }}
    @media (max-width: 640px) {{
        main {{ padding: 22px 18px; }}
        nav ol {{ columns: 1; }}
        ul.keys li {{ flex-direction: column; gap: 2px; }}
    }}
</style>
</head>
<body>
<main>
<header>
    <h1>{escape(title)}</h1>
    <p class="version">{escape(version_label)}</p>
</header>
<p class="intro">{intro}</p>
<nav aria-labelledby="toc-title">
    <h2 id="toc-title">{toc_title}</h2>
    <ol>
{toc}
    </ol>
</nav>
{chr(10).join(body)}
<section id="{shortcuts_id}">
<h2>{escape(shortcuts_title)}</h2>
{_shortcuts_html(raw_shortcuts)}
</section>
</main>
</body>
</html>"""
