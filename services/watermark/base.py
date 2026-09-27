from abc import ABC, abstractmethod


class WatermarkStyle(ABC):
    """
    Base class for all watermark styles.
    """

    @abstractmethod
    def build_filter(self, username: str) -> str:
        """
        Build and return the FFmpeg filter string
        for this watermark style.
        """
        pass