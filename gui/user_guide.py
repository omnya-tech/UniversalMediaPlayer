# -*- coding: utf-8 -*-
"""
وحدة دليل المستخدم وقائمة الاختصارات لمشغل الوسائط الشامل.
تضم الدليل التوثيقي الكامل والشامل مع استخلاص منسق ومصنف للاختصارات باللغتين العربية والإنجليزية.
"""


def get_shortcuts_list(lang: str = "ar") -> list:
    """
    إرجاع قائمة مرتبة ومصنفة بمهنية عالية باختصارات المشغل، 
    تُستخدم للعرض أو عند التوليد والتصدير النصي لضمان أعلى مستويات التنسيق والوضوح.
    """
    if lang == "ar":
        return [
            "=== التحكم والتشغيل الأساسي ===",
            "تشغيل / إيقاف مؤقت: مسافة (Space)",
            "إيقاف التشغيل الكامل والإعادة للبداية: Ctrl + Space",
            "كتم / إلغاء كتم الصوت: حرف M",
            "رفع / خفض مستوى الصوت (بنسبة 5%): السهم العلوي / السفلي",
            "رفع / خفض مستوى الصوت السريع (بنسبة 20%): Ctrl + السهم العلوي / السفلي",
            "",
            "=== التقديم والإرجاع التكيّفي ===",
            "تقديم / إرجاع بـ 10 ثوانٍ: السهم الأيمن / الأيسر",
            "تقديم / إرجاع بدقيقة واحدة (60 ثانية): Ctrl + السهم الأيمن / الأيسر",
            "تقديم / إرجاع بـ 5 دقائق: Shift + السهم الأيمن / الأيسر",
            "تقديم / إرجاع بـ 10 دقائق: Alt + السهم الأيمن / الأيسر",
            "تقديم / إرجاع بـ 30 دقيقة: Ctrl + Shift + السهم الأيمن / الأيسر",
            "القفز المباشر لنسبة مئوية من الملف (10% إلى 90%): أرقام لوحة الأرقام الجانبية (Numpad 1 إلى 9)",
            "القفز لبداية الملف تمامًا: Numpad 0 أو Home",
            "القفز لنهاية الملف (آخر 5 ثوانٍ): End",
            "تحديد أصغر قفزة يُعلَن عندها الموضع (دقيقة أو 5 أو 10 أو 30): من الخيارات، تبويب إمكانية الوصول",
            "",
            "=== التحكم بالسرعة والعلامات المرجعية ===",
            "زيادة / تقليل سرعة التشغيل (بمقدار 0.25x): Alt + السهم العلوي / السفلي",
            "إعادة سرعة التشغيل للوضع الطبيعي (1.0x): Alt + Numpad 0",
            "إضافة نقطة محفوظة (علامة مرجعية): Ctrl + B",
            "الانتقال إلى وقت محدد: Ctrl + G",
            "تسمية أقرب علامة مرجعية: Ctrl + Alt + B",
            "الانتقال للنقطة المحفوظة التالية: F2",
            "الانتقال للنقطة المحفوظة السابقة: Shift + F2",
            "حذف كل النقاط المحفوظة للملف الحالي: Ctrl + Shift + B",
            "",
            "=== إعلانات الوقت وإمكانية الوصول ===",
            "إعلان الوقت الحالي والمتبقي والكامل معًا: حرف T",
            "إعلان الوقت المتبقي فقط: حرف R",
            "إعلان مدة الملف الكلية فقط: حرف E",
            "تفعيل / تعطيل إعلانات النطق لقارئ الشاشة: Ctrl + Alt + A",
            "",
            "=== التنقل في المجلد والعرض ===",
            "الملف التالي في المجلد: Page Down",
            "الملف السابق في المجلد: Page Up",
            "تبديل وضع ملء الشاشة للفيديو: F11 أو Escape",
            "",
            "=== الروابط وقوائم التشغيل ===",
            "فتح رابط (راديو أو بث مباشر أو ملف على الإنترنت): Ctrl + U",
            "إعلان ما يُذاع الآن في الراديو: حرف N",
            "نافذة قائمة التشغيل (إضافة وحذف وترتيب): Ctrl + L",
            "حفظ قائمة التشغيل الحالية كملف M3U8: Ctrl + S",
            "داخل نافذة القائمة: Enter للتشغيل، Delete للحذف، Alt + السهم العلوي / السفلي للتحريك",
            "",
            "=== المعادل الصوتي ===",
            "فتح نافذة المعادل الصوتي: Ctrl + E",
            "نمط المعادل التالي / السابق: حرف Q / Shift + Q",
            "",
            "=== الأدوات والنوافذ العامة ===",
            "فتح نافذة مسجل الصوت: Ctrl + Shift + R",
            "فتح نافذة محرر الوسائط: Ctrl + Shift + X",
            "بدء / إيقاف التسجيل الصوتي المباشر: Ctrl + R",
            "إعلان مستوى الصوت أثناء التسجيل (داخل نافذة المسجّل): Ctrl + L",
            "فتح نافذة محول الصيغ: من قائمة أدوات (Tools Menu)",
            "فتح خيارات البرنامج والتفضيلات: Ctrl + Shift + P",
            "التنقل بين تبويبات نافذة الخيارات: Ctrl + Tab، أو Ctrl + 1 إلى Ctrl + 5",
            "فتح ملف وسائط جديد: Ctrl + O",
            "فتح مجلد وسائط كامل: Ctrl + Shift + O",
            "تصدير دليل الاختصارات كمستند نصي: Ctrl + Shift + H",
            "حفظ تقرير تشخيصي على سطح المكتب (بلا معلومات شخصية): Ctrl + Shift + D",
            "الخروج الكامل من البرنامج: Ctrl + Q",
        ]
    else:
        return [
            "=== Basic Playback & Controls ===",
            "Play / Pause: Space",
            "Full Stop & Rewind to Start: Ctrl + Space",
            "Mute / Unmute: M",
            "Volume Up / Down (5%): Up / Down Arrow",
            "Quick Volume Up / Down (20%): Ctrl + Up / Down Arrow",
            "",
            "=== Adaptive Seeking ===",
            "Seek 10 Seconds: Right / Left Arrow",
            "Seek 1 Minute (60s): Ctrl + Right / Left Arrow",
            "Seek 5 Minutes: Shift + Right / Left Arrow",
            "Seek 10 Minutes: Alt + Right / Left Arrow",
            "Seek 30 Minutes: Ctrl + Shift + Right / Left Arrow",
            "Jump to Duration Percentage (10% - 90%): Numpad 1 to 9",
            "Jump to Start of File: Numpad 0 or Home",
            "Jump to End of File (last 5s): End",
            "Set the smallest jump that announces the position (1, 5, 10 or 30 minutes): Options, Accessibility tab",
            "",
            "=== Speed Control & Bookmarks ===",
            "Increase / Decrease Speed (by 0.25x): Alt + Up / Down Arrow",
            "Reset Playback Speed (1.0x): Alt + Numpad 0",
            "Add Bookmark: Ctrl + B",
            "Go to a specific time: Ctrl + G",
            "Name the nearest bookmark: Ctrl + Alt + B",
            "Next Bookmark: F2",
            "Previous Bookmark: Shift + F2",
            "Clear Bookmarks for Current File: Ctrl + Shift + B",
            "",
            "=== Time Announcements & Accessibility ===",
            "Announce Time Status (Current, Remaining, Total): T",
            "Announce Remaining Time Only: R",
            "Announce Total Duration Only: E",
            "Toggle Screen Reader Speech Announcements: Ctrl + Alt + A",
            "",
            "=== Folder Navigation & Display ===",
            "Next File in Folder: Page Down",
            "Previous File in Folder: Page Up",
            "Toggle Video Fullscreen: F11 or Escape",
            "",
            "=== Links & Playlists ===",
            "Open URL (radio, live stream, or online file): Ctrl + U",
            "Announce radio now-playing: N",
            "Playlist window (add, remove, reorder): Ctrl + L",
            "Save the current playlist as M3U8: Ctrl + S",
            "Inside the Playlist window: Enter plays, Delete removes, Alt + Up / Down Arrow moves",
            "",
            "=== Equalizer ===",
            "Open the Equalizer window: Ctrl + E",
            "Next / Previous equalizer preset: Q / Shift + Q",
            "",
            "=== Tools & Windows ===",
            "Open Audio Recorder Window: Ctrl + Shift + R",
            "Open Media Editor Window: Ctrl + Shift + X",
            "Start / Stop Quick Recording Immediately: Ctrl + R",
            "Open Format Converter Window: From Tools Menu",
            "Open Program Options: Ctrl + Shift + P",
            "Open Media File: Ctrl + O",
            "Open Media Folder: Ctrl + Shift + O",
            "Export Shortcuts Guide as Text: Ctrl + Shift + H",
            "Announce recording level (inside the Recorder window): Ctrl + L",
            "Switch Options tabs: Ctrl + Tab, or Ctrl + 1 to Ctrl + 5",
            "Save a diagnostic report to the Desktop (no personal data): Ctrl + Shift + D",
            "Exit Application: Ctrl + Q",
        ]


def build_user_guide_html(tr, seek_kwargs: dict = None) -> str:
    """
    إنشاء مستند HTML توثيقي عصري وراقي لعرض دليل الاستخدام الشامل والمنظم داخل المتصفح.
    """
    lang = getattr(tr, "lang", "ar")
    is_ar = (lang == "ar")
    
    app_name = tr.t("app_title")
    title = f"{tr.t('menu_user_guide')} — {app_name}"
    dir_attr = "rtl" if is_ar else "ltr"
    
    if is_ar:
        intro_title = f"مرحبًا بك في {app_name}"
        intro_body = (
            "تم تصميم هذا البرنامج خصيصًا ليقدم تجربة استماع ومشاهدة فريدة تجمع بين قوة الأداء وسهولة الاستخدام، مع عناية "
            "فائقة بتوفير إتاحة كاملة لمستخدمي قارئات الشاشة لتتمكن من التحكم في كافة وظائف البرنامج بسلاسة تامة عبر لوحة "
            "المفاتيح دون الحاجة لاستخدام الفأرة، مع الحفاظ التام على صفاء ونبرة الصوت الأصلية أثناء التحكم بالسرعة."
        )

        sec1_title = "1. الأساسيات والتحكم بالتشغيل"
        sec1_body = (
            "• <b>التشغيل والإيقاف:</b> شغّل الوسائط أو أوقفها مؤقتًا بمفتاح <code>Space</code>، أو أوقفها نهائيًا وارجع "
            "للبداية بـ <code>Ctrl+Space</code>. الإيقاف يستجيب فورًا حتى مع ملفات الفيديو الكبيرة.\n"
            "• <b>التنقل السريع (التقديم والإرجاع):</b> اختر مقدار القفزة بمفتاح مساعد:\n"
            "  - السهم الأيمن والأيسر: 10 ثوانٍ.\n"
            "  - مع <code>Ctrl</code>: دقيقة كاملة.\n"
            "  - مع <code>Shift</code>: 5 دقائق.\n"
            "  - مع <code>Alt</code>: 10 دقائق.\n"
            "  - مع <code>Ctrl+Shift</code>: 30 دقيقة.\n"
            "  - أرقام لوحة الأرقام الجانبية (Numpad من 1 إلى 9): قفز مباشر إلى نسبة من الملف (من 10% إلى 90%).\n"
            "  ويمكنك من تبويب إمكانية الوصول اختيار أصغر قفزة يُعلَن عندها الموضع (دقيقة أو 5 أو 10 أو 30 دقيقة)، فلا "
            "يتحول الضغط المتكرر على سهم العشر ثوانٍ إلى ثرثرة.\n"
            "  والتقديم صار أسرع بكثير في هذا الإصدار: الصوت يعود فور وصولك للموضع الجديد بدل فترة صمت محسوسة بعد كل ضغطة.\n"
            "• <b>التحكم بالسرعة:</b> <code>Alt</code> مع السهم لأعلى أو لأسفل يغيّر السرعة بمقدار 0.25×، "
            "و<code>Alt+Numpad 0</code> يعيدها إلى الوضع الطبيعي — دون أن تتغير نبرة الصوت.\n"
            "• <b>الفتح أسرع:</b> صار البرنامج يفتح أسرع بفارق ملحوظ عند أول تشغيل بعد تشغيل الجهاز."
        )

        sec2_title = "2. الصيغ المدعومة"
        sec2_body = (
            "يشغّل البرنامج <b>أكثر من 120 صيغة</b> صوت وفيديو، ويحوّل بينها بـ<b>86 صيغة</b> مخرجات، دون الحاجة إلى تثبيت "
            "أي حزم ترميز خارجية:\n"
            "\n"
            "<b>🎵 الصيغ الصوتية:</b>\n"
            "الصيغ اليومية المعروفة مثل MP3 وWAV وAAC وFLAC، والصيغ عديمة الفقد عالية الجودة (Lossless)، وصيغ المسارح "
            "المنزلية، وملفات الموسيقى القديمة.\n"
            "\n"
            "<b>🎬 صيغ الفيديو:</b>\n"
            "من الملفات القياسية إلى صيغ الضغط الحديثة، مرورًا بملفات البث التلفزيوني وأقراص السينما، ووصولًا إلى صيغ "
            "كاميرات المراقبة وملفات الإنتاج الاحترافي."
        )

        sec3_title = "3. التنقل بين الملفات والعلامات المرجعية"
        sec3_body = (
            "• <b>التنقل داخل المجلد:</b> عند فتح أي ملف، انتقل إلى الملف التالي أو السابق في المجلد نفسه بمفتاحَي "
            "<code>Page Down</code> و<code>Page Up</code>.\n"
            "• <b>حفظ الموضع تلقائيًا:</b> يتذكر البرنامج أين توقفت في كل ملف، ويستأنف من عنده عند إعادة فتحه.\n"
            "• <b>العلامات المرجعية:</b> ضع علامة عند أي موضع بـ <code>Ctrl+B</code>، وتنقّل بينها بـ <code>F2</code> "
            "و<code>Shift+F2</code>.\n"
            "• <b>تسمية العلامات:</b> بدل أن تسمع «العلامة عند 12 دقيقة»، سمِّها بـ <code>Ctrl+Alt+B</code> فتسمع «انتقلت "
            "إلى بداية الفصل الثالث». اترك الاسم فارغًا لإزالته.\n"
            "• <b>الذهاب إلى وقت محدد:</b> بـ <code>Ctrl+G</code> اكتب الوقت مباشرة — <code>90</code> أو <code>1:30</code> "
            "أو <code>1:02:03</code>. إن كان الوقت بعد نهاية الملف يخبرك بذلك بدل أن ينتقل لمكان خاطئ."
        )

        sec4_title = "4. أدوات التحويل والتسجيل"
        sec4_body = (
            "• <b>محول الصيغ:</b> حوّل ملفات الصوت والفيديو من قائمة السياق (زر الفأرة الأيمن) أو من قائمة أدوات، مع دعم "
            "المجلدات الكاملة وتنظيم الملفات الناتجة تلقائيًا.\n"
            "• <b>مسجّل الصوت:</b> يسجّل من المايكروفون أو من صوت النظام، ويبدأ ويتوقف بـ <code>Ctrl+R</code>.\n"
            "• <b>محرر الوسائط:</b> لقص ملفات الصوت والفيديو ودمجها، من قائمة أدوات أو بـ <code>Ctrl+Shift+X</code>. اقسم ملفًا لجزأين، أو اقسم عدة ملفات "
            "عند نفس الوقت دفعة واحدة، أو خذ مقاطع متفرقة من ملف طويل وضمها في ملف واحد، أو ادمج ملفات بالترتيب الذي "
            "تختاره. الناتج بنفس صيغة الأصل، وزر «الموضع الحالي» يأخذ الوقت من المشغّل وأنت تسمع فلا تحتاج لكتابته. "
            "وللفيديو طريقتان: «سريع بنفس الجودة» يبدأ القص من أقرب إطار مفتاحي (صورة كاملة كل بضع ثوانٍ)، "
            "و«دقيق بالثانية» يقص عند الوقت بالضبط لكنه أبطأ. والفيديوهات المدموجة يجب أن تكون بنفس الصيغة والمقاس. "
            "وأسهل طريقة: ضع علامة بـ <code>Ctrl+B</code> عند كل موضع وأنت تسمع، ثم في المحرر اختر الوقت «من العلامات»، "
            "أو اضغط «مقاطع من العلامات» فتصير كل علامتين بداية مقطع ونهايته.\n"
            "• <b>اختبار المايكروفون قبل التسجيل:</b> زر داخل نافذة المسجّل يسجّل عشر ثوانٍ ثم يخبرك <b>نصًّا مقروءًا "
            "لقارئ الشاشة</b> هل المستوى ممتاز أم مرتفع أم منخفض أم لا يصل صوت أصلًا، مع خطوات الإصلاح. هذا يغنيك عن مؤشّر "
            "المستوى المرئي الذي لا يفيد من لا يرى.\n"
            "• <b>سماع المستوى أثناء التسجيل:</b> اضغط <code>Ctrl+L</code> في أي لحظة أثناء التسجيل ليُنطق لك المستوى "
            "الحالي وأعلى قمة وصلت إليها.\n"
            "• <b>تنبيه تشوّه الصوت:</b> إذا كان مستوى المايكروفون مرتفعًا لدرجة تُفسد التسجيل، يخبرك البرنامج عند الحفظ "
            "ويرشدك إلى خفضه — بدل أن تكتشف الخشونة بعد فوات الأوان.\n"
            "• <b>قائمة أجهزة نظيفة:</b> يجمع البرنامج المداخل التي تعود لجهاز واحد في سطر واحد باسم مفهوم، بدل أن يظهر "
            "المايكروفون الواحد أربع مرات، ويختار له أفضل طريقة اتصال بنفسه. ولكل جهاز إعداداته المحفوظة على حدة، فتصحيحك "
            "لمايكروفون لا يفسد إعدادات غيره.\n"
            "• <b>جودة مطابقة لجهازك:</b> يختار المسجّل تلقائيًا معدل العينة الأصلي لمايكروفونك، فلا يحدث تحويل زائد يضرّ "
            "بنقاء الصوت.\n"
            "• <b>أعلى جودة لكل صيغة:</b> خانة «معدل البت» في المسجّل والمحوّل تبدأ عند «أعلى جودة متاحة»، وهي تعرف سقف كل "
            "صيغة على حدة: 320 كيلوبت للـ MP3، و640 للـ AC3، و256 للـ Opus أحادي القناة. اختر رقمًا بنفسك متى شئت — وإن "
            "اخترت رقمًا فوق ما تحتمله الصيغة نزل البرنامج إلى أقصاها بدل أن يفشل التحويل ويتركك بلا ملف."
        )

        sec5_title = "5. إمكانية الوصول والتخصيص"
        sec5_body = (
            (
                "• <b>تحكّم منفصل في كل إعلان:</b> تبويب «إمكانية الوصول» في نافذة الخيارات يعطيك صندوق اختيار مستقلًا لكل نوع "
                "إعلان: اسم الملف، ترتيبه في القائمة، الاستئناف، حالة التشغيل، الصوت، السرعة، العلامات، مؤقت النوم وغيرها. "
                "فعّل ما ينفعك وأسكت الباقي.\n"
                "• <b>مفتاح رئيسي:</b> <code>Ctrl+Alt+A</code> يوقف كل الإعلانات فورًا ويعيدها، وله مربّع في أعلى التبويب "
                "يُظهر لك حالته.\n"
                "• <b>تنقّل سريع في نافذة الخيارات:</b> <code>Ctrl+Tab</code> للتبويب التالي، و<code>Ctrl+1</code> إلى "
                "<code>Ctrl+5</code> للانتقال المباشر.\n"
                "• <b>حفظ حجم النافذة وموضعها:</b> تفتح النافذة كما تركتها في المرة السابقة.\n"
                "• <b>سرعة محفوظة لكل ملف:</b> إذا كنت تسمع كتابًا صوتيًا بسرعة 1.5×، يتذكرها البرنامج لهذا الملف وحده دون أن "
                "يؤثر على غيره."
            )
        )

        sec6_title = "6. عند مواجهة مشكلة"
        sec6_body = (
            (
                "• <b>تقرير تشخيصي جاهز للإرسال:</b> اضغط <code>Ctrl+Shift+D</code> فيُحفظ على سطح المكتب ملف نصي يحتوي "
                "معلومات النظام وسجل البرنامج.\n"
                "• <b>آمن للنشر:</b> التقرير <b>لا يحتوي على أي معلومات شخصية</b> — لا اسم جهازك ولا اسم المستخدم ولا مسارات "
                "ملفاتك. يمكنك إرفاقه في مجموعة عامة دون قلق.\n"
                "• <b>تفاصيل اختبار المايكروفون:</b> نتيجة الاختبار فيها زر «نسخ التفاصيل التقنية» ينسخ سطرًا واحدًا خاليًا "
                "كذلك من أي بيانات تعرّفك، جاهزًا للصق في رسالة الدعم."
            )
        )

        sec_new_title = "7. الراديو وقوائم التشغيل والمعادل الصوتي"
        sec_new_body = (
            "• <b>تشغيل الروابط:</b> <code>Ctrl+U</code> يفتح خانة الرابط — وإن كنت نسخت رابطًا قبلها تجده مكتوبًا. "
            "يشغّل الراديو والبث المباشر والملفات على الإنترنت، ويعيد الاتصال تلقائيًا إذا انقطع البث.\n"
            "• <b>ما يُذاع الآن:</b> في محطات الراديو التي ترسل اسم الأغنية أو البرنامج، يُعلَن الاسم كلما تغيّر، "
            "و<code>N</code> يعيده لك في أي وقت.\n"
            "• <b>قوائم تشغيل خاصة بك:</b> <code>Ctrl+L</code> يفتح القائمة الحالية: أضف ملفات من أي مجلد أو روابط "
            "محطات، واحذف بـ <code>Delete</code>، ورتّب بـ <code>Alt</code> مع الأسهم، ثم احفظها بـ <code>Ctrl+S</code>. "
            "تُحفظ بصيغة M3U8 التي تفتحها معظم المشغلات، وإن كانت الملفات داخل مجلد القائمة تبقى القائمة صالحة إذا نقلت "
            "المجلد كله. افتح أي قائمة (M3U أو M3U8 أو PLS) مثل أي ملف بـ <code>Ctrl+O</code>.\n"
            "• <b>المعادل الصوتي:</b> <code>Q</code> و<code>Shift+Q</code> يتنقلان بين 18 نمطًا جاهزًا (منها «سماعات الرأس» "
            "و«جهير كامل» و«قاعة كبيرة») ويُنطق اسم كل نمط. <code>Ctrl+E</code> يفتح نافذة فيها عشرة نطاقات تعدّلها "
            "بالأسهم وتسمع النتيجة فورًا، ويبقى اختيارك محفوظًا لكل الملفات."
        )

        sec7_title = "8. دليل اختصارات لوحة المفاتيح الشامل"
    else:
        intro_title = f"Welcome to {app_name}"
        intro_body = (
            "Designed to provide a unique listening and viewing experience combining high performance and ease of use, "
            "with complete accessibility for screen reader users to control all features smoothly via keyboard shortcuts "
            "without needing a mouse, while preserving original audio pitch during speed adjustments."
        )

        sec1_title = "1. Basics & Playback Controls"
        sec1_body = (
            "• <b>Play & Pause:</b> Use <code>Space</code> to play/pause, or <code>Ctrl+Space</code> to stop completely and return to the start.\n"
            "• <b>Adaptive Navigation:</b> Jump through timeline flexibly using arrows, modifier keys, or Numpad keys for percentage jumping.\n"
            "• <b>Speed Control:</b> Adjust playback speed precisely without affecting natural audio pitch."
        )

        sec2_title = "2. Supported Formats Arsenal (Over 120 Formats)"
        sec2_body = (
            "The program plays <b>over 120 audio and video formats</b> and converts between them with <b>86 output "
            "formats</b>, without requiring any external codecs:\n"
            "\n"
            "<b>🎵 Audio Formats:</b> Covers standard everyday formats, lossless high-definition audio, home theater "
            "formats, and legacy/tracker music files.\n"
            "\n"
            "<b>🎬 Video Formats:</b> Supports standard formats, modern high-compression encodings, broadcast streams, and "
            "professional surveillance or production files."
        )

        sec3_title = "3. Folder Navigation & Bookmarks"
        sec3_body = (
            "• <b>Folder Navigation:</b> Move smoothly between files in the same folder using <code>Page Down</code> and <code>Page Up</code>.\n"
            "• <b>Bookmarks:</b> Automatically remembers your last playback position and allows marking custom spots for quick access."
        )

        sec4_title = "4. Conversion & Recording Tools"
        sec4_body = (
            "• <b>Format Converter:</b> Easily convert audio and video files using the direct context menu option or tools "
            "window, supporting batch folder organization.\n"
            "• <b>Audio Recorder:</b> Built-in tool for high-quality audio recording, started and stopped with "
            "<code>Ctrl+R</code>.\n"
            "• <b>Media Editor:</b> cuts and merges audio and video files, from the Tools menu or <code>Ctrl+Shift+X</code>. Split a file in two, split "
            "several files at the same time in one go, take scattered parts of a long file into one file, or merge files "
            "in the order you choose. The result keeps the original format, and the «Current Position» "
            "button takes the time from the player while you listen. Video has two modes: «Fast, same quality» "
            "starts the cut at the nearest keyframe (a full picture every few seconds), and «Exact to the second» "
            "cuts at the exact time but is slower. Merged videos must share the same format and size. "
            "Easiest way: press <code>Ctrl+B</code> at each spot while listening, then in the editor pick a time "
            "«From Bookmarks», or press «Parts from Bookmarks» so every two bookmarks become a part's start and end.\n"
            "• <b>Microphone test:</b> records ten seconds and tells you <b>in text your screen reader can read</b> "
            "whether the level is good, too high, too low, or silent — along with how to fix it.\n"
            "• <b>Hear your level while recording:</b> press <code>Ctrl+L</code> at any time during a recording.\n"
            "• <b>Distortion warning:</b> if the microphone level is high enough to spoil the recording, you are told when "
            "saving.\n"
            "• <b>Matches your hardware:</b> the recorder picks your microphone's native sample rate automatically."
        )

        sec5_title = "5. Accessibility & Customization"
        sec5_body = (
            (
                "• <b>Per-announcement control:</b> the Accessibility tab gives every announcement type its own checkbox — "
                "file name, playlist position, resume, playback state, volume, speed, bookmarks, sleep timer and more.\n"
                "• <b>Enable or silence everything at once</b> with two buttons at the top of the tab.\n"
                "• <b>Master switch:</b> <code>Ctrl+Alt+A</code> stops all announcements instantly and brings them back.\n"
                "• <b>Choose the smallest jump worth announcing</b> — every jump, or only a minute, 5, 10 or 30 minutes and "
                "above.\n"
                "• <b>Fast tab navigation</b> in Options: <code>Ctrl+Tab</code>, or <code>Ctrl+1</code> to "
                "<code>Ctrl+5</code>.\n"
                "• <b>Window size and position are remembered</b> between sessions.\n"
                "• <b>Per-file playback speed</b> is remembered separately for each file."
            )
        )

        sec6_title = "6. When Something Goes Wrong"
        sec6_body = (
            (
                "• <b>Diagnostic report:</b> press <code>Ctrl+Shift+D</code> to save a text report to your Desktop.\n"
                "• <b>Safe to share:</b> it contains <b>no personal information</b> — no computer name, user name, or file "
                "paths — so you can post it in a public group.\n"
                "• <b>Microphone test details</b> can be copied as a single line that is likewise free of identifying data."
            )
        )

        sec_new_title = "7. Radio, Playlists & Equalizer"
        sec_new_body = (
            "• <b>Play links:</b> <code>Ctrl+U</code> opens the URL box — a link you copied beforehand is already filled "
            "in. Plays radio, live streams and online files, and reconnects automatically if the stream drops.\n"
            "• <b>Now playing:</b> on radio stations that send the song or show name, it is announced whenever it "
            "changes, and <code>N</code> repeats it any time.\n"
            "• <b>Your own playlists:</b> <code>Ctrl+L</code> opens the current playlist: add files from any folder or "
            "station links, remove with <code>Delete</code>, reorder with <code>Alt</code> and the arrows, then save with "
            "<code>Ctrl+S</code> as M3U8, which most players open. Open any M3U, M3U8 or PLS playlist with "
            "<code>Ctrl+O</code>.\n"
            "• <b>Equalizer:</b> <code>Q</code> and <code>Shift+Q</code> cycle 18 presets and speak each name. "
            "<code>Ctrl+E</code> opens a window with ten bands you adjust with the arrows and hear immediately; your "
            "choice is kept for all files."
        )

        sec7_title = "8. Complete Keyboard Shortcuts Map"

    raw_shortcuts = get_shortcuts_list(lang)
    formatted_shortcuts_html = []
    
    for line in raw_shortcuts:
        if not line:
            formatted_shortcuts_html.append("<br>")
        elif line.startswith("==="):
            clean_head = line.replace("===", "").strip()
            formatted_shortcuts_html.append(f"</ul><h3>{clean_head}</h3><ul>")
        else:
            if ":" in line:
                desc, key = line.split(":", 1)
                formatted_shortcuts_html.append(f"<li><b>{desc.strip()}:</b> <kbd>{key.strip()}</kbd></li>")
            else:
                formatted_shortcuts_html.append(f"<li>{line}</li>")

    shortcuts_block = "\n".join(formatted_shortcuts_html)

    return f"""<!DOCTYPE html>
<html lang="{lang}" dir="{dir_attr}">
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        :root {{
            --primary: #1a5276;
            --accent: #2980b9;
            --bg: #f4f6f9;
            --card-bg: #ffffff;
            --text-main: #2c3e50;
            --text-muted: #566573;
            --border: #e5e8e8;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 40px 20px;
            background-color: var(--bg);
            color: var(--text-main);
            line-height: 1.8;
        }}
        .container {{
            max-width: 960px;
            margin: 0 auto;
            background: var(--card-bg);
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.06);
        }}
        h1 {{
            color: var(--primary);
            border-bottom: 3px solid var(--accent);
            padding-bottom: 14px;
            margin-top: 0;
            font-size: 28px;
            font-weight: 700;
        }}
        h2 {{
            color: var(--primary);
            margin-top: 35px;
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
            font-size: 21px;
        }}
        h3 {{
            color: var(--accent);
            margin-top: 25px;
            margin-bottom: 10px;
            font-size: 17px;
        }}
        p {{
            font-size: 16px;
            color: var(--text-main);
            white-space: pre-line;
            margin-bottom: 18px;
        }}
        ul {{
            background: #fdfefe;
            padding: 20px 35px;
            border-radius: 8px;
            border: 1px solid var(--border);
            list-style-type: none;
            margin-top: 10px;
        }}
        li {{
            margin-bottom: 10px;
            font-size: 15px;
            border-bottom: 1px dashed #f0f3f4;
            padding-bottom: 6px;
        }}
        li:last-child {{
            border-bottom: none;
        }}
        kbd {{
            background-color: #ebf5fb;
            border: 1px solid #aed6f1;
            border-radius: 4px;
            box-shadow: 0 1px 1px rgba(0,0,0,0.1);
            color: #1b4f72;
            display: inline-block;
            font-family: Consolas, 'Courier New', monospace;
            font-size: 14px;
            font-weight: 600;
            padding: 2px 7px;
        }}
        .section-card {{
            background-color: #fafbfc;
            border-right: 5px solid var(--accent);
            padding: 20px 25px;
            margin: 25px 0;
            border-radius: 6px;
            border: 1px solid var(--border);
            border-right-width: 5px;
        }}
        [dir="ltr"] .section-card {{
            border-right-width: 1px;
            border-left: 5px solid var(--accent);
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        
        <div class="section-card">
            <h2>{intro_title}</h2>
            <p>{intro_body}</p>
        </div>

        <h2>{sec1_title}</h2>
        <p>{sec1_body}</p>

        <h2>{sec2_title}</h2>
        <p>{sec2_body}</p>

        <h2>{sec3_title}</h2>
        <p>{sec3_body}</p>

        <h2>{sec4_title}</h2>
        <p>{sec4_body}</p>

        <h2>{sec5_title}</h2>
        <p>{sec5_body}</p>

        <h2>{sec6_title}</h2>
        <p>{sec6_body}</p>

        <h2>{sec_new_title}</h2>
        <p>{sec_new_body}</p>

        <h2>{sec7_title}</h2>
        {shortcuts_block}
    </div>
</body>
</html>"""