# ==========================================
# سكريبت البناء الشامل لبرنامج Omnya
# ==========================================

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "      بدء عملية بناء وتجهيز Omnya         " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. التحقق من وجود ملف الـ Spec
if (-not (Test-Path "omnya_player.spec")) {
    Write-Host "خطأ: ملف omnya_player.spec غير موجود في مجلد المشروع." -ForegroundColor Red
    exit 1
}

# 2. بناء المشروع باستخدام PyInstaller وملف الـ Spec
Write-Host "[1/2] جاري بناء التطبيق باستخدام PyInstaller..." -ForegroundColor Yellow
pyinstaller omnya_player.spec

if ($LASTEXITCODE -ne 0) {
    Write-Host "خطأ: فشلت عملية البناء بواسطة PyInstaller." -ForegroundColor Red
    exit 1
}

# 3. تشغيل سكريبت تجهيز المجلد المحمول (Portable)
if (Test-Path "make_portable_folder.ps1") {
    Write-Host "[2/2] جاري تجهيز المجلد المحمول والاختصارات..." -ForegroundColor Yellow
    powershell -ExecutionPolicy Bypass -File make_portable_folder.ps1
} else {
    Write-Host "تحذير: تم البناء بنجاح في مجلد dist\Universal Media Player، ولكن ملف make_portable_folder.ps1 غير موجود." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "تمت عملية البناء والتجهيز بنجاح تام!" -ForegroundColor Green