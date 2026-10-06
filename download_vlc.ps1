# سكريبت PowerShell بيحمّل نسخة VLC المحمولة (zip) تلقائيًا من الموقع
# الرسمي get.videolan.org، ويجهّز مجلد resources\vlc\ بالملفات المطلوبة
# (libvlc.dll، libvlccore.dll، مجلد plugins\) عشان تتضمّن مع البرنامج
# في النسخة النهائية - فالمستخدم النهائي منيحتاجش يثبّت VLC بنفسه خالص
# (راجعي التعليق أعلى core/engine.py وقسم "تضمين مكتبة VLC" في
# README.md لتفاصيل الآلية اللي بتستخدم المجلد ده وقت التشغيل والبناء).
#
# ملحوظة: السكريبت ده محتاج اتصال إنترنت وقت التشغيل فقط (مرة واحدة
# وقت التجهيز/البناء عندك إنتي كمطوّرة) - النسخة النهائية اللي بتوصل
# للمستخدم مش محتاجة أي اتصال إنترنت أو تثبيت.
#
# طريقة التشغيل: من داخل مجلد المشروع
#   powershell -ExecutionPolicy Bypass -File download_vlc.ps1
#
# لو السكريبت فشل لأي سبب (مثلًا الموقع غيّر شكل صفحة التحميل)، لسه
# ممكن تعملي الخطوة يدويًا: حمّلي "VLC (zip)" من
# https://www.videolan.org/vlc/ بنفسك، وانسخي منها libvlc.dll،
# libvlccore.dll، ومجلد plugins\ كامل لمجلد resources\vlc\.

# ⚠️ دعم ويندوز 7: البرنامج مبني على استهداف ويندوز 7 SP1 فما فوق، وده
# بيعتمد على إن نسخة VLC المُضمَّنة تكون من فرع 3.0.x (آخر فرع من VLC
# بيدعم ويندوز 7 رسميًا - فرع 4.0 لما يخرج نهائيًا متوقّع يرفع الحد
# الأدنى). عشان كده السكريبت ده بيسحب نسخة مثبَّتة (pinned) بالتحديد من
# فرع 3.0.x، مش "آخر نسخة" (last) اللي ممكن تبقى يوم من الأيام 4.0 وتكسر
# التوافق مع ويندوز 7 من غير أي تحذير. لو عايز ترفّع الرقم (مثلًا نسخة
# 3.0.x أحدث)، راجعي صفحة الإصدار على videolan.org الأول وتأكدي إن
# ويندوز 7 لسه مذكور ضمن "OS Versions" المدعومة قبل ما تغيّري $vlcVersion.
$vlcVersion = "3.0.23"
$ErrorActionPreference = "Stop"

$indexUrl = "https://get.videolan.org/vlc/$vlcVersion/win64/"
$destVlcDir = Join-Path $PSScriptRoot "resources\vlc"
$tempZip = Join-Path $env:TEMP "vlc_portable_download.zip"
$tempExtract = Join-Path $env:TEMP "vlc_portable_extract"

Write-Host "بدوّر على نسخة VLC المحمولة المثبَّتة ($vlcVersion، 64-bit) من $indexUrl ..." -ForegroundColor Cyan

try {
    $response = Invoke-WebRequest -Uri $indexUrl -UseBasicParsing
} catch {
    Write-Host "خطأ: تعذّر الاتصال بـ $indexUrl. تأكدي من اتصال الإنترنت." -ForegroundColor Red
    exit 1
}

$zipLink = $response.Links | Where-Object { $_.href -match '^vlc-.*-win64\.zip$' } | Select-Object -First 1
if (-not $zipLink) {
    Write-Host "خطأ: مالقتش رابط ملف .zip في صفحة التحميل. ممكن الموقع يكون غيّر شكله." -ForegroundColor Red
    Write-Host "افتحي $indexUrl يدويًا، حمّلي ملف win64.zip، وحطي محتوياته المطلوبة في resources\vlc\ (شوفي README.md)." -ForegroundColor Yellow
    exit 1
}

$zipFileName = $zipLink.href
$downloadUrl = $indexUrl + $zipFileName

Write-Host "هحمّل: $downloadUrl" -ForegroundColor Cyan
Invoke-WebRequest -Uri $downloadUrl -OutFile $tempZip -UseBasicParsing

Write-Host "بفك الضغط..." -ForegroundColor Cyan
if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
Expand-Archive -Path $tempZip -DestinationPath $tempExtract -Force

$vlcSourceDir = Get-ChildItem -Path $tempExtract -Directory | Select-Object -First 1
if (-not $vlcSourceDir) {
    Write-Host "خطأ: مالقتش مجلد VLC جوه الأرشيف بعد فك الضغط." -ForegroundColor Red
    exit 1
}

$requiredFiles = @("libvlc.dll", "libvlccore.dll")
foreach ($f in $requiredFiles) {
    if (-not (Test-Path (Join-Path $vlcSourceDir.FullName $f))) {
        Write-Host "خطأ: الملف $f مش موجود جوه الأرشيف المحمّل." -ForegroundColor Red
        exit 1
    }
}
if (-not (Test-Path (Join-Path $vlcSourceDir.FullName "plugins"))) {
    Write-Host "خطأ: مجلد plugins مش موجود جوه الأرشيف المحمّل." -ForegroundColor Red
    exit 1
}

if (Test-Path $destVlcDir) { Remove-Item $destVlcDir -Recurse -Force }
New-Item -ItemType Directory -Path $destVlcDir -Force | Out-Null

Copy-Item (Join-Path $vlcSourceDir.FullName "libvlc.dll") $destVlcDir
Copy-Item (Join-Path $vlcSourceDir.FullName "libvlccore.dll") $destVlcDir
Copy-Item (Join-Path $vlcSourceDir.FullName "plugins") $destVlcDir -Recurse

Remove-Item $tempZip -Force -ErrorAction SilentlyContinue
Remove-Item $tempExtract -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "تم بنجاح! اتجهّز resources\vlc\ بالملفات المطلوبة:" -ForegroundColor Green
Write-Host "  - libvlc.dll"
Write-Host "  - libvlccore.dll"
Write-Host "  - plugins\"
Write-Host ""
Write-Host "دلوقتي البرنامج (core/engine.py) هيلاقي النسخة المُضمَّنة دي" -ForegroundColor Green
Write-Host "تلقائيًا وقت التشغيل، وملف omnia_player.spec هيضمّها في" -ForegroundColor Green
Write-Host "التوزيعة النهائية لما تبنيها بـ PyInstaller - المستخدم" -ForegroundColor Green
Write-Host "النهائي مش هيحتاج يثبّت VLC خالص." -ForegroundColor Green
