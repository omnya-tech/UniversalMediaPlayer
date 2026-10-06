# تراخيص المكوّنات الخارجية

برنامج «مشغل الوسائط الشامل» (Universal Media Player) برنامج حر مرخّص تحت
**GNU GPL الإصدار الثالث** (انظر `LICENSE`): لك أن تستعمله وتنسخه وتعدّله
وتوزّعه بشروط الرخصة، وهو يُقدَّم **بلا أي ضمان**.

هذا الملف يسرد المكوّنات الخارجية التي تُوزَّع داخل النسخة التنفيذية
وتراخيصها. نصوص التراخيص في مجلد `licenses` بجانب البرنامج:

- `LICENSE` — GPL v3 (رخصة البرنامج، وتغطي كذلك ما رُخّص تحت GPL v2 «أو أي إصدار لاحق»)
- `licenses/LGPL-3.0.txt` و`licenses/LGPL-2.1.txt` — للمكتبات تحت LGPL
- `licenses/Apache-2.0.txt` — لمكتبة opencore-amr
- `licenses/NVDA-LICENSE-NOTICE.md` — بيان مكتبة NVDA
- `licenses/<الحزمة>/` — ملفات الترخيص كما وردت في حزم بايثون نفسها (تُنسخ عند البناء)

## مكتبات بايثون ومكتبات النظام

| المكوّن | الترخيص | المصدر |
|---|---|---|
| Python | PSF License | <https://www.python.org/> |
| wxPython وwxWidgets | wxWindows Library Licence | <https://wxpython.org/> |
| python-vlc | LGPL v2.1 أو لاحق | <https://github.com/oaubert/python-vlc> |
| libVLC (libvlc.dll وlibvlccore.dll والإضافات) | LGPL v2.1 أو لاحق (بعض الإضافات GPL v2 أو لاحق) | <https://code.videolan.org/videolan/vlc> |
| PyAV | BSD-3-Clause | <https://github.com/PyAV-Org/PyAV> |
| sounddevice | MIT | <https://github.com/spatialaudio/python-sounddevice> |
| PortAudio (libportaudio64bit.dll داخل sounddevice) | MIT | <https://www.portaudio.com/> |
| numpy | BSD-3-Clause مع مكوّنات 0BSD وMIT وZlib وCC0 | <https://numpy.org/> |
| cffi | MIT-0 | <https://github.com/python-cffi/cffi> |
| pycparser | BSD-3-Clause | <https://github.com/eliben/pycparser> |
| nvdaControllerClient.dll (NVDA) | GPL v2 أو لاحق، مع استثناءين | <https://github.com/nvaccess/nvda> |

من PortAudio تُشحن نسخة ويندوز 64 بت وحدها. النسخ التي فيها دعم ASIO (برخصة
Steinberg مستقلة) ونسخ الأنظمة الأخرى تُستبعد عند البناء (`omnya_player.spec`)،
والبرنامج لا يستعمل ASIO.

## FFmpeg والمكتبات المضمَّنة مع PyAV

PyAV يحمل نسخته من FFmpeg ومكتبات الترميز في مجلد `av.libs`. FFmpeg نفسه مبني
تحت **LGPL v3 أو لاحق** (`--enable-version3`، متحقَّق منه من إعدادات البناء
داخل PyAV 18.1). ومعه:

| المكتبة | الاستعمال في البرنامج | الترخيص |
|---|---|---|
| FFmpeg (avcodec وavformat وavfilter وavutil وswresample وswscale وavdevice) | فك الترميز والتحويل والقص وفلاتر تحسين الصوت | LGPL v3 أو لاحق |
| x264 (libx264) | ترميز فيديو H.264 | **GPL v2 أو لاحق** |
| x265 (libx265) | ترميز فيديو H.265 | **GPL v2 أو لاحق** |
| LAME (libmp3lame) | ترميز MP3 | LGPL v2 أو لاحق |
| opencore-amr (amrnb وamrwb) | صيغة AMR | Apache 2.0 |
| Opus (libopus) | صيغة Opus | BSD-3-Clause |
| libvpx | صيغتا VP8 وVP9 | BSD-3-Clause |
| dav1d | فك ترميز AV1 | BSD-2-Clause |
| SVT-AV1 | ترميز AV1 | BSD-3-Clause-Clear مع رخصة براءات AOMedia |
| libwebp وlibsharpyuv | صيغة WebP | BSD-3-Clause |
| libvpl | تسريع Intel | MIT |
| zlib | الضغط | zlib |
| libiconv | ترميز النصوص | LGPL v2.1 أو لاحق |
| مكتبات تشغيل GCC (libgcc وlibstdc++) | تشغيل المكتبات المبنية بـ GCC | GPL v3 مع استثناء مكتبة تشغيل GCC |
| winpthreads | الخيوط | MIT وZPL 2.1 |

وجود x264 وx265 (GPL) داخل التوزيعة يجعل مجموعها خاضعًا لـ GPL، وهذا متوافق
لأن البرنامج نفسه GPL v3. ومصدر هذه البنية كلها: <https://github.com/PyAV-Org/pyav-ffmpeg>
ومصادر كل مكتبة في الروابط الرسمية لمشاريعها.

## التوافق مع GPL v3

كل ما سبق متوافق مع GPL v3:

- رخص GPL v2 «أو أي إصدار لاحق» وLGPL «أو أي إصدار لاحق» تُؤخذ بإصدارها
  الثالث.
- Apache 2.0 متوافقة مع GPL v3 (لا مع v2، ولهذا لا يُرخَّص البرنامج تحت v2).
- رخص BSD وMIT وzlib وPSF وwxWindows متساهلة وتسمح بالدمج.

## التزامات التوزيع

من يوزّع البرنامج (المثبِّت أو النسخة المحمولة) عليه:

1. شحن `LICENSE` وهذا الملف ومجلد `licenses` معه. البناء يضعها بجانب
   البرنامج تلقائيًا، فتصل للمثبِّت والنسخة المحمولة.
2. إتاحة **مصدر البرنامج** ومصادر المكوّنات تحت GPL وLGPL لمن يطلبها، أو ذكر
   روابطها في صفحة التنزيل. روابط المصادر في الجداول أعلاه.

## مكتبة NVDA

`resources/nvdaControllerClient.dll` جزء من مشروع NVDA، مرخّص تحت
**GNU GPL الإصدار الثاني أو أي إصدار لاحق**، مع استثناءين يوسّعان الرخصة ولا
يضيّقانها. عبارة **«أو أي إصدار لاحق»** هي التي تتيح دمجها مع برنامج تحت
GPL v3. بيانها في `resources/NVDA-LICENSE-NOTICE.md`، ويُنسخ إلى `licenses`
عند البناء.

البرنامج يعمل بدونها: `accessibility/announcer.py` يتجاوزها عند غيابها ويعلن
النصوص عبر حقل مخفي يقرؤه أي قارئ شاشة (مثل Narrator).

## VLC

ملفات VLC **مستثناة من المستودع** في `.gitignore` (حوالي 137 ميجا). تُنزَّل
بـ `download_vlc.ps1` من الموقع الرسمي قبل البناء.

## أدوات تُستخدم في البناء فقط (لا تُوزَّع)

| الأداة | الترخيص | ملاحظة |
|---|---|---|
| PyInstaller | GPL v2+ مع استثناء خاص | الاستثناء يسمح صراحةً بتوزيع الناتج تحت أي ترخيص |
| Inno Setup | رخصة Inno Setup | يبني المُثبِّت فقط |

## الأيقونة والخلفية

`resources/omnya_icon.*` و`resources/background.jpg` من إنتاج المشروع نفسه،
وتخضع لرخصة البرنامج.
