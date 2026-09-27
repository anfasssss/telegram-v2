import shutil


def check_ffmpeg():
    """
    Check whether FFmpeg is available.
    """

    return shutil.which("ffmpeg") is not None

def check_ytdlp():
    """
    Check whether yt-dlp is available.
    """

    return shutil.which("yt-dlp") is not None

def check_instaloader():
    """
    Check whether Instaloader is available.
    """

    try:
        import instaloader

        return True

    except Exception:
        return False
    
def check_playwright():
    """
    Check whether Playwright Chromium can launch.
    """

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()

        return True

    except Exception as e:
        print(
            f"❌ Playwright check failed: {e}"
        )
        return False