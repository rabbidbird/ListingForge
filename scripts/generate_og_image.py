"""Generate the deterministic SellerDrafts social preview asset."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from core.config import PROJECT_ROOT

OUTPUT = PROJECT_ROOT / "static" / "og.png"
FAVICON = PROJECT_ROOT / "static" / "favicon.ico"


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        (Path("C:/Windows/Fonts/segoeuib.ttf") if bold else Path("C:/Windows/Fonts/segoeui.ttf")),
        Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def generate(output: Path = OUTPUT) -> None:
    image = Image.new("RGB", (1200, 630), "#08111f")
    draw = ImageDraw.Draw(image)
    draw.ellipse((-140, -260, 640, 520), fill="#152a48")
    draw.rounded_rectangle((82, 76, 154, 148), radius=22, fill="#f4b860")
    draw.text((105, 84), "S", font=_font(42, bold=True), fill="#172238")
    draw.text((177, 88), "SellerDrafts", font=_font(36, bold=True), fill="#f8fafc")
    draw.text(
        (82, 214),
        "Etsy listing drafts that\nstay inside the facts",
        font=_font(58, bold=True),
        fill="#f8fafc",
        spacing=12,
    )
    draw.rounded_rectangle(
        (82, 470, 825, 540), radius=18, fill="#16273d", outline="#f4b860", width=3
    )
    draw.text(
        (108, 489),
        "DRAFT — verify before publishing",
        font=_font(26, bold=True),
        fill="#ffffff",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, format="PNG", optimize=True)
    icon = Image.new("RGB", (64, 64), "#f4b860")
    icon_draw = ImageDraw.Draw(icon)
    icon_draw.text((17, 6), "S", font=_font(42, bold=True), fill="#172238")
    icon.save(FAVICON, format="ICO", sizes=[(16, 16), (32, 32), (64, 64)])


if __name__ == "__main__":
    generate()
