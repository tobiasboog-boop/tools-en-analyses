"""Genereer OBS webcam-overlay en circulair masker in Notifica-huisstijl.

Maakt twee bestanden aan in assets/:
- webcam-frame.png: Oranje ring overlay (#FBBA00) voor over de webcam
- webcam-mask.png: Circulair masker (wit op zwart) voor OBS Image Mask filter

Gebruik: python create_overlay.py
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ASSETS_DIR = Path(__file__).parent / "assets"
NOTIFICA_ORANGE = "#FBBA00"
FRAME_SIZE = 400        # Totale afmeting in pixels
RING_WIDTH = 18         # Breedte van de oranje ring
SHADOW_BLUR = 8         # Zachte schaduw rondom


def create_webcam_frame():
    """Maak de oranje ring overlay (transparante achtergrond)."""
    size = FRAME_SIZE
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    center = size // 2
    outer_radius = center - SHADOW_BLUR - 2
    inner_radius = outer_radius - RING_WIDTH

    # Teken schaduw (donkerdere ring, geblurd)
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.ellipse(
        [center - outer_radius, center - outer_radius,
         center + outer_radius, center + outer_radius],
        fill=(0, 0, 0, 80)
    )
    # Knip het midden uit de schaduw
    shadow_draw.ellipse(
        [center - inner_radius, center - inner_radius,
         center + inner_radius, center + inner_radius],
        fill=(0, 0, 0, 0)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(SHADOW_BLUR))

    # Combineer schaduw met hoofdafbeelding
    img = Image.alpha_composite(img, shadow)
    draw = ImageDraw.Draw(img)

    # Teken de oranje ring
    draw.ellipse(
        [center - outer_radius, center - outer_radius,
         center + outer_radius, center + outer_radius],
        fill=NOTIFICA_ORANGE
    )
    # Knip het midden uit (transparant)
    draw.ellipse(
        [center - inner_radius, center - inner_radius,
         center + inner_radius, center + inner_radius],
        fill=(0, 0, 0, 0)
    )

    ASSETS_DIR.mkdir(exist_ok=True)
    output_path = ASSETS_DIR / "webcam-frame.png"
    img.save(output_path, "PNG")
    print(f"Webcam frame opgeslagen: {output_path}")
    return output_path


def create_webcam_mask():
    """Maak circulair masker voor OBS Image Mask/Blend filter.

    Wit = zichtbaar, zwart = verborgen.
    """
    size = FRAME_SIZE
    img = Image.new("L", (size, size), 0)  # Zwart (verborgen)
    draw = ImageDraw.Draw(img)

    center = size // 2
    # Masker iets kleiner dan de ring zodat de webcam netjes binnen de ring past
    mask_radius = center - SHADOW_BLUR - 2 - RING_WIDTH

    draw.ellipse(
        [center - mask_radius, center - mask_radius,
         center + mask_radius, center + mask_radius],
        fill=255  # Wit (zichtbaar)
    )

    output_path = ASSETS_DIR / "webcam-mask.png"
    img.save(output_path, "PNG")
    print(f"Webcam masker opgeslagen: {output_path}")
    return output_path


def create_watermark_logo():
    """Maak een Notifica logo watermerk (wit op transparant).

    Tekent het N-mark uit de SVG als polygonen, met 'notifica' tekst eronder.
    """
    from PIL import ImageFont

    # --- SVG coordinaten (viewBox 0 0 1387.2 1387.2) ---
    # N-mark: x 511-896, y 338-779
    # Tekst:  x 251-1157, y 860-1023
    # Totaal: x 251-1157, y 338-1023

    # Werk op hoge resolutie, schaal daarna
    canvas_w, canvas_h = 600, 460
    white = (255, 255, 255, 240)

    # N-mark: schaal 385px SVG-breedte naar 200px, gecentreerd
    nmark_w = 200
    svg_nw, svg_nh = 384.5, 440.4
    ns = nmark_w / svg_nw
    nmark_h = int(svg_nh * ns)
    nx_off = (canvas_w - nmark_w) // 2  # centreer horizontaal
    ny_off = 0

    def n_px(x, y):
        return (int((x - 511.2) * ns + nx_off), int((y - 338.3) * ns + ny_off))

    left_poly = [n_px(703.4, 778.7), n_px(511.2, 778.7),
                 n_px(511.2, 338.3), n_px(703.5, 558.5)]
    right_poly = [n_px(703.4, 338.3), n_px(895.7, 338.3),
                  n_px(895.7, 778.7), n_px(703.4, 558.5)]

    img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    draw.polygon(left_poly, fill=white)
    draw.polygon(right_poly, fill=white)

    # Tekst "notifica" eronder
    text = "notifica"
    # Probeer een geschikt Windows-font (bold, sans-serif)
    font = None
    font_size = 72
    for font_name in [
        "C:/Windows/Fonts/segoeuib.ttf",   # Segoe UI Bold
        "C:/Windows/Fonts/arialbd.ttf",     # Arial Bold
        "C:/Windows/Fonts/calibrib.ttf",    # Calibri Bold
    ]:
        try:
            font = ImageFont.truetype(font_name, font_size)
            break
        except (OSError, IOError):
            continue
    if font is None:
        font = ImageFont.load_default()

    # Meet tekst en centreer onder N-mark
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    tx = (canvas_w - tw) // 2
    ty = nmark_h + 15  # ruimte onder N-mark
    draw.text((tx, ty), text, fill=white, font=font)

    # Crop naar daadwerkelijke inhoud + kleine marge
    content_bbox = img.getbbox()
    if content_bbox:
        margin = 5
        crop_box = (
            max(0, content_bbox[0] - margin),
            max(0, content_bbox[1] - margin),
            min(canvas_w, content_bbox[2] + margin),
            min(canvas_h, content_bbox[3] + margin),
        )
        img = img.crop(crop_box)

    ASSETS_DIR.mkdir(exist_ok=True)
    output_path = ASSETS_DIR / "watermark-logo.png"
    img.save(output_path, "PNG")
    print(f"Watermark logo opgeslagen: {output_path} ({img.size[0]}x{img.size[1]})")
    return output_path


if __name__ == "__main__":
    create_webcam_frame()
    create_webcam_mask()
    create_watermark_logo()
    print("\nAlles gegenereerd!")
