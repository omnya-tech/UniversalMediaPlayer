# -*- mode: python ; coding: utf-8 -*-
#
# ملف إعدادات PyInstaller جاهز - نسخة "onedir" (مجلد كامل فيه الـ exe
# ومكتباته منفصلين، بدون ضغط في ملف واحد). ده بيخلي بدء التشغيل أسرع من
# نسخة "onefile" لإنه مفيش فك ضغط لمجلد مؤقت في كل مرة تشغيل.
#
# استخدمه بالأمر:
#   pyinstaller omnya_player.spec
#
# الناتج هيكون مجلد كامل في dist\Universal Media Player\ (فيه Universal Media Player.exe +
# مجلد _internal بكل المكتبات). لازم تنقل المجلد كله مع بعض لو عايز
# تشغّل البرنامج من مكان تاني، مش الـ exe لوحده.

import os as _os
import sys as _sys

# السطر ده هو اللي بيحل مشكلة VSVersionInfo:
from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo, FixedFileInfo, StringFileInfo, 
    StringTable, StringStruct, VarFileInfo, VarStruct
)

_vlc_resources_dir = _os.path.join('resources', 'vlc')
_vlc_required_files = ['libvlc.dll', 'libvlccore.dll']

_vlc_missing = [
    _f for _f in _vlc_required_files
    if not _os.path.isfile(_os.path.join(_vlc_resources_dir, _f))
]
_vlc_plugins_dir = _os.path.join(_vlc_resources_dir, 'plugins')
if not _os.path.isdir(_vlc_plugins_dir) or not _os.listdir(_vlc_plugins_dir):
    _vlc_missing.append('plugins/')

if _vlc_missing:
    raise SystemExit(
        "resources/vlc/ ناقصة أو غير موجودة (الناقص: " + ", ".join(_vlc_missing) + "). "
        "البناء اتوقف عمدًا عشان مانشحنش نسخة للمستخدم النهائي من غير VLC مُضمَّنة "
        "(وإلا هيتطلب منه هو يثبّت VLC بنفسه). شغّلي download_vlc.ps1 الأول ثم "
        "أعيدي المحاولة."
    )

_resources_dir = 'resources'
_all_datas = []
if _os.path.isdir(_resources_dir):
    for _root, _dirs, _files in _os.walk(_resources_dir):
        for _f in _files:
            _src = _os.path.join(_root, _f)
            _dest = _os.path.relpath(_root, '.')
            _all_datas.append((_src, _dest))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=_all_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

_upx_exclude = [
    'libportaudio64bit.dll',
    'libportaudio32bit.dll',
    'libvlc.dll',
    'libvlccore.dll',
]

# -------------------------------------------------------------------------
# إضافة كائن معلومات الإصدار (Version Info)
# يعزز موثوقية الملف التنفيذي لدى مكافحات الفيروسات ونظام الويندوز
# -------------------------------------------------------------------------
version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(1, 4, 0, 0),
        prodvers=(1, 4, 0, 0),
        mask=0x3f,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0)
    ),
    kids=[
        StringFileInfo(
            [
                StringTable(
                    '040904B0',
                    [
                        StringStruct('CompanyName', 'Omnya'),
                        StringStruct('FileDescription', 'Universal Media Player'),
                        StringStruct('FileVersion', '1.4.0'),
                        StringStruct('LegalCopyright', '© 2026 Omnya'),
                        StringStruct('OriginalFilename', 'Universal Media Player.exe'),
                        StringStruct('ProductName', 'Universal Media Player'),
                        StringStruct('ProductVersion', '1.4.0')
                    ]
                )
            ]
        ),
        VarFileInfo([VarStruct('Translation', [1033, 1200])])
    ]
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Universal Media Player',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=_upx_exclude,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon='resources/omnya_icon.ico',
    version=version_info,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=_upx_exclude,
    name='Universal Media Player',
)