from pathlib import Path


def get_media_type(file_path: str) -> str:
    """
    Determine the media type from the file extension.
    """

    extension = Path(file_path).suffix.lower()

    video_extensions = {
        ".mp4",
        ".mov",
        ".mkv",
        ".webm",
    }

    image_extensions = {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
    }

    if extension in video_extensions:
        return "video"

    if extension in image_extensions:
        return "photo"

    return "document"