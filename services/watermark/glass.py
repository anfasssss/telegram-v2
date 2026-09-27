from .base import WatermarkStyle


class GlassWatermark(WatermarkStyle):
    """
    Glass-style watermark for Instagram videos.
    """

    def build_filter(self, username: str) -> str:
        """
        Build the FFmpeg drawtext filter.

        The size and position are based on the
        video resolution.
        """

        if not username.startswith("@"):
            username = f"@{username}"

        font_path = "C\\:/Windows/Fonts/arial.ttf"

        return (
            "drawtext="
            f"fontfile='{font_path}':"
            f"text='{username}':"
            "x=w*0.03:"
            "y=h-th-h*0.03:"
            "fontsize=h*0.035:"
            "fontcolor=white:"
            "box=1:"
            "boxcolor=black@0.35:"
            "boxborderw=12"
        )