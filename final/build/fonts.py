"""Embed a TrueType family so bold/italic render identically everywhere (and subscripts etc. work)."""
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
import matplotlib

def register():
    sup = Path("/System/Library/Fonts/Supplemental")
    arial = {"": "Arial.ttf", "-Bold": "Arial Bold.ttf", "-Oblique": "Arial Italic.ttf", "-BoldOblique": "Arial Bold Italic.ttf"}
    if all((sup / f).exists() for f in arial.values()):
        files = {k: str(sup / v) for k, v in arial.items()}
    else:
        d = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
        files = {"": str(d / "DejaVuSans.ttf"), "-Bold": str(d / "DejaVuSans-Bold.ttf"), "-Oblique": str(d / "DejaVuSans-Oblique.ttf"), "-BoldOblique": str(d / "DejaVuSans-BoldOblique.ttf")}
    for suf, f in files.items():
        pdfmetrics.registerFont(TTFont("Body" + suf, f))
    addMapping("Body", 0, 0, "Body"); addMapping("Body", 1, 0, "Body-Bold"); addMapping("Body", 0, 1, "Body-Oblique"); addMapping("Body", 1, 1, "Body-BoldOblique")
register()
