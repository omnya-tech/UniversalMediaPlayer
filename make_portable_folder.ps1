# سكريبت PowerShell بيجهّز مجلد جاهز فيه:
#  - نسخة كاملة من مجلد Omnya (من dist\ اللي بنته PyInstaller
#    بنسخة "onedir" - يعني Universal Media Player.exe + مجلد _internal بكل مكتباته)
#  - ملف اختصار (.lnk) جاهز يشاور على الـ exe جوه المجلد ده
#
# طريقة التشغيل: من داخل مجلد المشروع (بعد ما بنيت dist\Universal Media Player\
# بأمر pyinstaller omnya_player.spec)
#   powershell -ExecutionPolicy Bypass -File make_portable_folder.ps1

$distFolder = "dist\Universal Media Player"
$outputFolder = "Universal_Media_Player_Portable"

if (-not (Test-Path $distFolder)) {
    Write-Host "خطأ: مجلد $distFolder غير موجود." -ForegroundColor Red
    Write-Host "لازم تبني البرنامج الأول باستخدام: pyinstaller omnya_player.spec" -ForegroundColor Red
    exit 1
}

if (Test-Path $outputFolder) {
    Remove-Item $outputFolder -Recurse -Force
}
Copy-Item $distFolder -Destination $outputFolder -Recurse

$fullOutputFolder = (Resolve-Path $outputFolder).Path
$targetPath = Join-Path $fullOutputFolder "Universal Media Player.exe"

if (-not (Test-Path $targetPath)) {
    Write-Host "خطأ: ملف Universal Media Player.exe مش موجود جوه $distFolder." -ForegroundColor Red
    exit 1
}

$shortcutPath = Join-Path $fullOutputFolder "Universal Media Player.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $targetPath
$Shortcut.WorkingDirectory = $fullOutputFolder
$Shortcut.IconLocation = $targetPath
$Shortcut.Description = "Omnya - مشغل وسائط متاح لقارئات الشاشة"
$Shortcut.Save()

Write-Host ""
Write-Host "تم بنجاح. المجلد الجاهز موجود هنا:" -ForegroundColor Green
Write-Host "  $fullOutputFolder"
Write-Host ""
Write-Host "فيه:"
Write-Host "  - Universal Media Player.exe + مجلد _internal (كل المكتبات المطلوبة وملفات VLC المُضمّنة)"
Write-Host "  - Universal Media Player.lnk  (اختصار جاهز)"
Write-Host ""
Write-Host "علشان تثبت البرنامج:"
Write-Host "  1) نقل المجلد ده كامل (بكل محتوياته) لأي مكان تحب (Program Files مثلاً، أو أي قرص)."
Write-Host "     مهم: خد المجلد كامل، مش الـ exe لوحده."
Write-Host "  2) انسخ ملف الاختصار (Universal Media Player.lnk) بس، ولصقه على سطح المكتب"
Write-Host "     أو في قائمة بدء (اضغط Win+R واكتب shell:programs وحط نسخة منه هناك)."