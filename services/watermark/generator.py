from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def draw_instagram_icon(draw, x, y, size):
    """
    Draw a simple Instagram-style camera icon.
    """

    # Outer rounded square
    draw.rounded_rectangle(
        (x, y, x + size, y + size),
        radius=size // 4,
        outline=(255, 255, 255, 255),
        width=max(2, size // 12),
    )

    # Camera lens
    lens_size = int(size * 0.35)
    lens_x = x + (size - lens_size) // 2
    lens_y = y + (size - lens_size) // 2

    draw.ellipse(
        (
            lens_x,
            lens_y,
            lens_x + lens_size,
            lens_y + lens_size,
        ),
        outline=(255, 255, 255, 255),
        width=max(2, size // 12),
    )

    # Small camera dot
    dot_size = max(3, size // 10)

    draw.ellipse(
        (
            x + int(size * 0.68),
            y + int(size * 0.22),
            x + int(size * 0.68) + dot_size,
            y + int(size * 0.22) + dot_size,
        ),
        fill=(255, 255, 255, 255),
    )

def create_glass_watermark(
    username: str,
    video_height: int,
    output_path: str,
) -> str:
    """
    Create a transparent PNG watermark with a glass-style background.
    """

    # Make sure username starts with @
    if not username.startswith("@"):
        username = f"@{username}"

    # Scale everything based on video height
    font_size = max(20, int(video_height * 0.035))
    padding_x = max(20, int(video_height * 0.02))
    padding_y = max(12, int(video_height * 0.012))
    border_radius = max(15, int(video_height * 0.015))

    # Use Arial on Windows, DejaVu Sans in Docker/Linux
    if Path("C:/Windows/Fonts/arial.ttf").exists():
        font_path = "C:/Windows/Fonts/arial.ttf"
    else:
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    font = ImageFont.truetype(
        font_path,
        font_size,
    )

    # Temporary image to measure text
    temp_image = Image.new("RGBA", (10, 10))
    temp_draw = ImageDraw.Draw(temp_image)

    bbox = temp_draw.textbbox(
        (0, 0),
        username,
        font=font,
    )

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Extra space reserved for Instagram icon later
    icon_space = font_size + padding_x

    width = text_width + icon_space + (padding_x * 2)
    height = text_height + (padding_y * 2)

    # Create transparent watermark
    watermark = Image.new(
        "RGBA",
        (width, height),
        (0, 0, 0, 0),
    )

    draw = ImageDraw.Draw(watermark)

    # Semi-transparent glass background
    draw.rounded_rectangle(
        (0, 0, width, height),
        radius=border_radius,
        fill=(30, 30, 30, 120),
        outline=(255, 255, 255, 80),
        width=2,
    )
     
    # Draw Instagram-style icon
    icon_size = font_size
    icon_x = padding_x
    icon_y = (height - icon_size) // 2
    
    draw_instagram_icon(
        draw,
        icon_x,
        icon_y,
        icon_size,
    ) 
     
    
    # Draw username
    text_x = padding_x + icon_space
    text_y = padding_y - bbox[1]

    draw.text(
        (text_x, text_y),
        username,
        font=font,
        fill=(255, 255, 255, 255),
    )

    # Save PNG
    output_file = Path(output_path)

    watermark.save(
        output_file,
        "PNG",
    )

    return str(output_file)