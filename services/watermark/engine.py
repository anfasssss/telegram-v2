import subprocess
from pathlib import Path

from .generator import create_glass_watermark


def get_video_height(video_path: str) -> int:
    """
    Get the height of a video using FFprobe.
    """

    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=height",
        "-of",
        "csv=p=0",
        video_path,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
    )

    return int(result.stdout.strip())


def add_watermark(
    input_path: str,
    username: str,
    style: str = "glass",
) -> str:
    """
    Add a watermark to a video.

    Returns the path of the processed video.
    """

    input_file = Path(input_path)

    if not input_file.exists():
        raise FileNotFoundError(
            f"Video not found: {input_file}"
        )

    if style != "glass":
        raise ValueError(
            f"Unsupported watermark style: {style}"
        )

    # Output video path
    output_file = input_file.with_name(
        f"{input_file.stem}_watermarked.mp4"
    )

    # Temporary watermark image path
    watermark_file = input_file.with_name(
        f"{input_file.stem}_watermark.png"
    )

    try:
        print("📐 Reading video resolution...")

        video_height = get_video_height(
            str(input_file)
        )

        print(
            f"📏 Video height: {video_height}px"
        )

        print("🧊 Creating glass watermark...")

        create_glass_watermark(
            username=username,
            video_height=video_height,
            output_path=str(watermark_file),
        )

        print("🎬 Overlaying watermark on video...")

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_file),
            "-i",
            str(watermark_file),
            "-filter_complex",
            (
                "[0:v][1:v]"
                "overlay=20:H-h-20"
            ),
            "-c:a",
            "copy",
            str(output_file),
        ]

        subprocess.run(
            command,
            check=True,
        )

        print(
            f"✅ Watermark complete: {output_file}"
        )

        return str(output_file)

    except Exception as e:

        print(
            f"❌ Watermark processing error: {e}"
        )

        raise

    finally:

        # Delete temporary PNG watermark
        if watermark_file.exists():
            watermark_file.unlink()

            print(
                f"🗑️ Deleted temporary watermark: "
                f"{watermark_file}"
            )