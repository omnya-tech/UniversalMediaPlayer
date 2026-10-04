# -*- coding: utf-8 -*-
import os

from core.streams import is_stream_url

AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".m4a", ".m4b", ".m4p", ".aac", ".ogg", ".wma", 
    ".oga", ".opus", ".aiff", ".aif", ".ape", ".alac", ".amr", ".caf", ".au", 
    ".mid", ".midi", ".ac3", ".eac3", ".dts", ".mka", ".weba", ".tta", ".wv", 
    ".mpc", ".spx", ".dsf", ".dff", ".voc", ".gsm", ".mpa", ".mp2", ".tsa", 
    ".mus", ".ra", ".ram", ".snd", ".tak", ".shn", ".dsd", 
    ".oma", ".qcp", ".xwma", ".mlp", ".thd", ".vqf", ".w64", ".8svx", ".cda", 
    ".dss", ".s3m", ".xm", ".it", ".mod"
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".mpg", ".mpeg",
    ".mpe", ".mp4v", ".m4v", ".3gp", ".3g2", ".3gpp", ".3gp2", ".ts", ".mts", 
    ".m2ts", ".m2t", ".vob", ".ogv", ".ogm", ".rm", ".rmvb", ".asf", ".divx", 
    ".f4v", ".mxf", ".qt", ".wtv", ".y4m", ".nut", ".mas", ".npa", ".swf", 
    ".h264", ".h265", ".hevc", ".vp9", ".av1", ".amv", ".bik", ".csf", ".dav", 
    ".drc", ".ifo", ".m1v", ".m2v", ".nsv", ".roq", ".svi", ".viv", ".vivo", 
    ".xvid", ".yuv", ".dat", ".dv", ".dvr-ms", ".gxf", ".nuv", ".rec", ".xesc"
}

# ملفات القوائم (.m3u و.m3u8 و.pls) مش هنا عن قصد: مش وسائط، وفتحها
# بيحمّل محتواها كقائمة (شوف core/playlist_files.py). لما كانت هنا،
# كانت بتظهر كـ"ملف" وسط أغاني المجلد ويتسلّمها VLC يشغّلها لوحده.
SUPPORTED_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS

def is_video_extension(ext: str) -> bool:
    if not ext:
        return False
    return ext.lower() in VIDEO_EXTENSIONS

def is_audio_extension(ext: str) -> bool:
    if not ext:
        return False
    return ext.lower() in AUDIO_EXTENSIONS

class Playlist:
    def __init__(self):
        self._files = []
        self._current_index = -1

    def load_folder_of(self, file_path: str):
        """
        يحمّل ملفات المجلد كقائمة تشغيل، والملف المطلوب هو الحالي.

        القائمة بتحتوي على الملف المطلوب **دايمًا** حتى لو امتداده مش في
        القائمة المدعومة أو المجلد مش مقروء. من غير كده كانت بتفضل فاضية،
        فـ current بترجّع None بينما فيه ملف شغّال فعلًا - وده كان بيضطر
        المستدعي لاحتياطي "playlist.current or path" عشان يشتغل.
        """
        if not file_path:
            self.clear()
            return

        folder = os.path.dirname(file_path)
        try:
            entries = sorted(os.listdir(folder), key=str.lower)
        except OSError:
            entries = []

        supported_files = [
            os.path.join(folder, name)
            for name in entries
            if os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS
        ]

        norm_target = os.path.normpath(file_path).lower()
        index = next(
            (i for i, path in enumerate(supported_files)
             if os.path.normpath(path).lower() == norm_target),
            -1,
        )
        if index == -1:
            # الملف خارج القائمة المدعومة أو المجلد غير مقروء: قائمة من ملف واحد
            self._files = [file_path]
            self._current_index = 0
            return
        self._files = supported_files
        self._current_index = index

    def load_custom_list(self, file_paths, initial_path=None):
        """
        تحميل قائمة مخصصة بالترتيب (ألبوم، أو قائمة محفوظة) مع بدء
        التشغيل من الملف المحدد.

        الروابط بتتقبل زي ما هي (مالهاش وجود على القرص)، والملفات لازم
        تكون موجودة ومدعومة.
        """
        valid_files = [f for f in file_paths if self._is_playable_entry(f)]
        if not valid_files:
            self.clear()
            return False

        self._files = valid_files
        self._current_index = 0
        if initial_path:
            found = self.index_of(initial_path)
            if found != -1:
                self._current_index = found
        return True

    @staticmethod
    def _is_playable_entry(entry) -> bool:
        if is_stream_url(entry):
            return True
        return os.path.isfile(entry) and os.path.splitext(entry)[1].lower() in SUPPORTED_EXTENSIONS

    def load_single(self, entry: str):
        """قائمة من عنصر واحد - لرابط بث مثلًا، مالوش مجلد يتقري."""
        self._files = [entry]
        self._current_index = 0

    # ------------------------------------------------------------------ #
    # تعديل القائمة (نافذة قائمة التشغيل)

    @property
    def entries(self):
        """نسخة من العناصر - التعديل بيتم من الدوال تحت بس."""
        return list(self._files)

    @property
    def current_index(self) -> int:
        return self._current_index

    @staticmethod
    def _same_entry(a, b) -> bool:
        if is_stream_url(a) or is_stream_url(b):
            return a == b
        return os.path.normpath(a).lower() == os.path.normpath(b).lower()

    def index_of(self, entry) -> int:
        return next((i for i, item in enumerate(self._files) if self._same_entry(item, entry)), -1)

    def add(self, entries):
        """يضيف في الآخر ويرجّع عدد اللي اتضاف فعلًا (الصالح بس)."""
        added = [e for e in entries if self._is_playable_entry(e)]
        self._files.extend(added)
        return len(added)

    def remove(self, index: int) -> bool:
        """
        يشيل عنصر. لو كان هو الحالي، الحالي بيرجع خطوة لورا عشان
        "التالي" يجيب العنصر اللي خد مكانه بدل ما يتخطاه.
        """
        if not 0 <= index < len(self._files):
            return False
        del self._files[index]
        if index <= self._current_index:
            self._current_index -= 1
        if not self._files:
            self._current_index = -1
        return True

    def move(self, index: int, step: int) -> int:
        """يحرّك عنصر خطوة لفوق أو لتحت، ويرجّع مكانه الجديد (أو -1)."""
        target = index + step
        if not (0 <= index < len(self._files) and 0 <= target < len(self._files)):
            return -1
        self._files[index], self._files[target] = self._files[target], self._files[index]
        # الحالي بيتبع العنصر نفسه، مش مكانه
        if self._current_index == index:
            self._current_index = target
        elif self._current_index == target:
            self._current_index = index
        return target

    def select(self, index: int):
        """يخلّي العنصر ده هو الحالي ويرجّعه (أو None)."""
        if 0 <= index < len(self._files):
            self._current_index = index
            return self._files[index]
        return None

    def clear(self):
        self._files = []
        self._current_index = -1

    @property
    def current(self) -> str:
        if 0 <= self._current_index < len(self._files):
            return self._files[self._current_index]
        return None

    @property
    def current_position(self) -> int:
        return self._current_index + 1 if self._current_index >= 0 else 0

    def has_next(self) -> bool:
        # -1 مع قائمة مش فاضية: الحالي اتشال وهو أول عنصر (شوف remove)
        return bool(self._files) and -1 <= self._current_index < len(self._files) - 1

    def has_previous(self) -> bool:
        return self._current_index > 0

    def next(self) -> str:
        if self.has_next():
            self._current_index += 1
            return self.current
        return None

    def previous(self) -> str:
        if self.has_previous():
            self._current_index -= 1
            return self.current
        return None

    def __len__(self):
        return len(self._files)