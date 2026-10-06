# -*- coding: utf-8 -*-
import os
import wx
from core.version import APP_VERSION
from gui.dialog_helpers import bind_escape_closes
from gui.options_helpers import _light
# نافذة الخيارات في ملفها؛ تبقى متاحة من هنا لمن يستوردها كما كان
from gui.options_dialog import OptionsDialog

__all__ = ["AboutDialog", "OptionsDialog"]


class AboutDialog(wx.Dialog):
    def __init__(self, parent, tr, on_open_user_guide=None):
        super().__init__(parent, title=tr.t("menu_about"), style=wx.DEFAULT_DIALOG_STYLE)
        self.tr = tr

        panel = wx.Panel(self)
        _light(panel.SetBackgroundColour, wx.Colour(248, 250, 252))
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- القسم العلوي: الأيقونة والعنوان ---
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        icon_path = os.path.join("resources", "omnya_icon.ico")
        if os.path.exists(icon_path):
            try:
                img = wx.Image(icon_path, wx.BITMAP_TYPE_ANY)
                img = img.Scale(75, 75, wx.IMAGE_QUALITY_HIGH)
                bmp = wx.StaticBitmap(panel, bitmap=wx.Bitmap(img))
                header_sizer.Add(bmp, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
            except Exception:
                pass

        title_sizer = wx.BoxSizer(wx.VERTICAL)
        title_label = wx.StaticText(panel, label=tr.t('app_title'))
        title_font = wx.Font(18, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        title_label.SetFont(title_font)
        _light(title_label.SetForegroundColour, wx.Colour(0, 70, 140))

        # رقم الإصدار بأرقام لاتينية كما في عنوان النافذة والمثبّت: ويندوز
        # يختار شكل الأرقام من الكلمة السابقة («الإصدار») فكتبه «١٫٥٫٠»؛
        # علامة الاتجاه اليساري الخفية (U+200E) قبله تجعله لاتينيًا
        version_label = wx.StaticText(panel, label=tr.t("about_version", version="‎" + APP_VERSION))
        version_font = wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        version_label.SetFont(version_font)
        _light(version_label.SetForegroundColour, wx.Colour(80, 100, 120))

        title_sizer.Add(title_label, 0, wx.BOTTOM, 4)
        title_sizer.Add(version_label, 0, wx.BOTTOM, 0)
        
        header_sizer.Add(title_sizer, 1, wx.ALIGN_CENTER_VERTICAL)
        main_sizer.Add(header_sizer, 0, wx.EXPAND | wx.ALL, 20)

        main_sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        # --- قسم النبذة ---
        intro_label = wx.StaticText(panel, label=tr.t("about_vision_text"))
        intro_label.Wrap(450)
        intro_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        _light(intro_label.SetForegroundColour, wx.Colour(30, 30, 30))
        main_sizer.Add(intro_label, 0, wx.ALL | wx.ALIGN_CENTER_HORIZONTAL, 20)

        # --- قسم الميزات ---
        features_box = wx.StaticBox(panel, label=tr.t("about_features_title"))
        features_box.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        _light(features_box.SetForegroundColour, wx.Colour(0, 70, 140))
        features_sizer = wx.StaticBoxSizer(features_box, wx.VERTICAL)
        
        features_label = wx.StaticText(panel, label=tr.t("about_features_text"))
        features_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        _light(features_label.SetForegroundColour, wx.Colour(50, 50, 50))
        features_sizer.Add(features_label, 0, wx.ALL, 10)
        
        main_sizer.Add(features_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        main_sizer.AddSpacer(10)

        # --- قسم الناشر وحقوق الملكية ---
        pub_sizer = wx.BoxSizer(wx.VERTICAL)
        
        publisher_label = wx.StaticText(panel, label=tr.t("about_publisher"))
        publisher_label.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        _light(publisher_label.SetForegroundColour, wx.Colour(20, 20, 20))
        
        copyright_label = wx.StaticText(panel, label=tr.t("about_copyright"))
        copyright_label.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        _light(copyright_label.SetForegroundColour, wx.Colour(120, 120, 120))
        # بيان الرخصة طويل: يُلف فلا يمدّ النافذة عرضًا
        copyright_label.Wrap(400)

        pub_sizer.Add(publisher_label, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM, 5)
        pub_sizer.Add(copyright_label, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.BOTTOM, 0)

        main_sizer.Add(pub_sizer, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 15)
        main_sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        # --- قسم الأزرار ---
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        if on_open_user_guide is not None:
            guide_btn = wx.Button(panel, label=tr.t("menu_user_guide"), size=(130, 38))
            guide_btn.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            guide_btn.Bind(wx.EVT_BUTTON, lambda event: on_open_user_guide())
            btn_sizer.Add(guide_btn, 0, wx.RIGHT, 15)

        close_btn = wx.Button(panel, wx.ID_OK, label=tr.t("converter_close_button"), size=(100, 38))
        close_btn.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        btn_sizer.Add(close_btn, 0, wx.LEFT, 0)

        main_sizer.Add(btn_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 15)

        panel.SetSizer(main_sizer)
        outer_sizer = wx.BoxSizer(wx.VERTICAL)
        outer_sizer.Add(panel, 1, wx.EXPAND)
        
        self.SetSizerAndFit(outer_sizer)
        self.CenterOnParent()
        
        close_btn.SetFocus()
        close_btn.SetDefault()
        bind_escape_closes(self)

