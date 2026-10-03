# -*- coding: utf-8 -*-
import os

AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".m4a", ".m4b", ".m4p", ".aac", ".ogg", ".wma", 
    ".oga", ".opus", ".aiff", ".aif", ".ape", ".alac", ".amr", ".caf", ".au", 
    ".mid", ".midi", ".ac3", ".eac3", ".dts", ".mka", ".weba", ".tta", ".wv", 
    ".mpc", ".spx", ".dsf", ".dff", ".voc", ".gsm", ".mpa", ".mp2", ".tsa", 
    ".mus", ".m3u", ".m3u8", ".ra", ".ram", ".snd", ".tak", ".shn", ".dsd", 
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
        """تحميل قائمة ملفات مخصصة (ألبوم) بالترتيب مع بدء التشغيل من الملف المحدد"""
        valid_files = [
            f for f in file_paths 
            if os.path.isfile(f) and os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
        ]
        if not valid_files:
            self.clear()
            return False

        self._files = valid_files
        if initial_path:
            norm_target = os.path.normpath(initial_path).lower()
            try:
                self._current_index = next(
                    i for i, path in enumerate(self._files)
                    if os.path.normpath(path).lower() == norm_target
                )
            except StopIteration:
                self._current_index = 0
        else:
            self._current_index = 0
        return True

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
        return 0 <= self._current_index < len(self._files) - 1

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