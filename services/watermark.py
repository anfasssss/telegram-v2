import subprocess
from pathlib import Path


def add_watermark(input_path: str, username: str) -> str:
    """
    Add a simple @username watermark to a video.

    Returns the path of the processed video.
    """

    input_file = Path(input_path)

    # Output file name
    output_file = input_file.with_name(
        f"{input_file.stem}_watermarked.mp4"
    )

    # Make sure username starts with @
    if not username.startswith("@"):
        username = f"@{username}"

    # Windows font path
    font_path = "C\\:/Windows/Fonts/arial.ttf"

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_file),
        "-vf",
        (
            "drawtext="
            f"fontfile='{font_path}':"
            f"text='{username}':"
            "x=20:"
            "y=h-th-20:"
            "fontsize=24:"
            "fontcolor=white:"
            "box=1:"
            "boxcolor=black@0.5:"
            "boxborderw=10"
        ),
        "-c:a",
        "copy",
        str(output_file),
    ]

    try:
        print(f"Adding watermark: {username}")

        subprocess.run(
            command,
            check=True,
        )

        print(f"Watermark complete: {output_file}")

        return str(output_file)

    except subprocess.CalledProcessError as e:
        print(f"FFmpeg watermark error: {e}")
        raise