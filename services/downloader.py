import os
import re
import requests
import yt_dlp
import instaloader
import time

from playwright.sync_api import sync_playwright


DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ============================================================
# URL HELPERS
# ============================================================

def clean_instagram_url(url):
    """
    Remove unnecessary Instagram URL parameters.
    """
    url = url.strip()

    # Remove query parameters
    url = url.split("?")[0]

    # Remove trailing slash
    url = url.rstrip("/")

    return url


def extract_shortcode(url):
    """
    Extract Instagram shortcode from:
    /p/SHORTCODE/
    /reel/SHORTCODE/
    /reels/SHORTCODE/
    /tv/SHORTCODE/
    """

    match = re.search(
        r"instagram\.com/(?:p|reel|reels|tv)/([^/?]+)",
        url
    )

    if not match:
        return None

    return match.group(1)


def is_instagram_url(url):
    """
    Check whether the URL belongs to Instagram.
    """

    return bool(
        re.search(
            r"https?://(www\.)?instagram\.com/",
            url,
            re.IGNORECASE
        )
    )


# ============================================================
# DOWNLOAD USING YT-DLP
# ============================================================

def _download_with_ytdlp(url):
    """
    Download Instagram video using yt-dlp.

    Returns:
        Path to downloaded file
    """

    shortcode = extract_shortcode(url)

    if not shortcode:
        raise ValueError("Could not extract Instagram shortcode.")

    output_template = os.path.join(
        DOWNLOAD_DIR,
        f"{shortcode}.%(ext)s"
    )

    ydl_opts = {
        "outtmpl": output_template,

        "format": (
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
            "best[ext=mp4]/"
            "best"
        ),

        "merge_output_format": "mp4",

        "quiet": False,
        "no_warnings": False,

        "noplaylist": True,

        # Helps with Instagram
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
        },
    }

    print(f"[Instagram] Trying yt-dlp: {url}")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    # Find downloaded file
    possible_files = []

    for filename in os.listdir(DOWNLOAD_DIR):
        if filename.startswith(shortcode):
            full_path = os.path.join(DOWNLOAD_DIR, filename)

            if os.path.isfile(full_path):
                possible_files.append(full_path)

    if not possible_files:
        raise FileNotFoundError(
            "yt-dlp completed but downloaded file was not found."
        )

    # Prefer mp4
    mp4_files = [
        path for path in possible_files
        if path.lower().endswith(".mp4")
    ]

    if mp4_files:
        return mp4_files[0]

    return possible_files[0]


# ============================================================
# DOWNLOAD SINGLE PHOTO USING INSTALOADER
# ============================================================

def _download_photo_with_instaloader(url):
    """
    Try downloading a single Instagram photo using Instaloader.
    """

    shortcode = extract_shortcode(url)

    if not shortcode:
        raise ValueError("Could not extract Instagram shortcode.")

    print(
        f"[Instagram] Trying Instaloader for photo: {shortcode}"
    )

    loader = instaloader.Instaloader(
        dirname_pattern=DOWNLOAD_DIR,
        filename_pattern="{shortcode}",
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern="",
    )

    try:
        post = instaloader.Post.from_shortcode(
            loader.context,
            shortcode
        )

        loader.download_post(
            post,
            target=shortcode
        )

    except Exception as e:
        print(
            f"[Instagram] Instaloader photo download failed: {e}"
        )
        return None

    # Search for downloaded image
    for filename in os.listdir(DOWNLOAD_DIR):
        if filename.startswith(shortcode):
            full_path = os.path.join(
                DOWNLOAD_DIR,
                filename
            )

            if full_path.lower().endswith(
                (".jpg", ".jpeg", ".png", ".webp")
            ):
                return full_path

    return None


# ============================================================
# DOWNLOAD SINGLE PHOTO USING PLAYWRIGHT
# ============================================================

def _download_photo_from_webpage(url):
    """
    Browser fallback for Instagram photos.

    Finds the largest visible rendered image on the page
    instead of relying only on og:image.
    """

    shortcode = extract_shortcode(url)

    if not shortcode:
        raise ValueError("Could not extract Instagram shortcode.")

    output_path = os.path.join(
        DOWNLOAD_DIR,
        f"{shortcode}.jpg"
    )

    print("[Instagram] Trying browser photo download...")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1280,
                "height": 1000
            },
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            )
        )

        try:
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            page.wait_for_timeout(5000)

            # Collect visible large images
            images = page.locator("img")

            candidates = []

            count = images.count()

            for i in range(count):

                image = images.nth(i)

                try:
                    if not image.is_visible():
                        continue

                    box = image.bounding_box()

                    if not box:
                        continue

                    width = box["width"]
                    height = box["height"]

                    if width < 300 or height < 300:
                        continue

                    src = image.get_attribute("src")

                    if not src:
                        continue

                    candidates.append(
                        {
                            "image": image,
                            "src": src,
                            "width": width,
                            "height": height,
                            "area": width * height,
                        }
                    )

                except Exception:
                    continue

            if not candidates:
                raise RuntimeError(
                    "No suitable Instagram image found."
                )

            # Largest rendered image
            candidates.sort(
                key=lambda item: item["area"],
                reverse=True
            )

            selected = candidates[0]

            print(
                "[Instagram] Selected image: "
                f"{selected['width']}x{selected['height']}"
            )

            image_url = selected["src"]

            response = requests.get(
                image_url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/140.0.0.0 Safari/537.36"
                    )
                },
                timeout=60
            )

            response.raise_for_status()

            with open(output_path, "wb") as f:
                f.write(response.content)

            print(
                f"[Instagram] Saved photo: {output_path}"
            )

            return output_path

        finally:
            browser.close()


# ============================================================
# CAROUSEL IMAGE DOWNLOAD
# ============================================================

def _download_carousel_with_browser(url):
    """
    Download Instagram carousel items using Playwright.

    Instagram keeps several carousel images in the DOM at the same
    time. The active image is identified by its x-position.

    The carousel DOM can be completely rebuilt during navigation,
    especially near the final items. Therefore, the carousel
    container is re-discovered whenever necessary.
    """

    shortcode = extract_shortcode(url)

    if not shortcode:
        raise ValueError(
            "Could not extract Instagram shortcode."
        )

    downloaded_files = []

    print(
        "[Instagram] Starting browser carousel download..."
    )

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1280,
                "height": 1000
            },
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            )
        )

        try:

            # ==================================================
            # OPEN INSTAGRAM POST
            # ==================================================

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000
            )

            page.wait_for_timeout(6000)

            # ==================================================
            # FIND CAROUSEL CONTAINER
            # ==================================================

            def get_carousel_container():

                try:

                    next_button = page.locator(
                        'button[aria-label="Next"]'
                    ).first

                    if next_button.count() == 0:
                        return None

                    return next_button.locator("..")

                except Exception:
                    return None

            # ==================================================
            # DEBUG IMAGES
            # ==================================================

            def debug_carousel_images():

                container = get_carousel_container()

                if not container:

                    print(
                        "[Instagram] Carousel container "
                        "not available."
                    )

                    return

                images = container.locator("img")

                count = images.count()

                print(
                    f"[Instagram] Carousel has "
                    f"{count} image element(s)"
                )

                for i in range(count):

                    image = images.nth(i)

                    try:

                        visible = image.is_visible()

                        box = image.bounding_box()

                        src = image.get_attribute(
                            "src"
                        )

                        print(
                            f"[Instagram] Image {i}: "
                            f"visible={visible}, "
                            f"box={box}"
                        )

                        if src:

                            print(
                                f"[Instagram] Image {i} src:"
                            )

                            print(
                                src[:250]
                            )

                    except Exception as e:

                        print(
                            f"[Instagram] Could not inspect "
                            f"image {i}: {e}"
                        )

            # ==================================================
            # GET ACTIVE IMAGE
            # ==================================================

            def get_active_image():

                container = get_carousel_container()

                if not container:
                    return None

                images = container.locator(
                    "img"
                )

                count = images.count()

                candidates = []

                for i in range(count):

                    image = images.nth(i)

                    try:

                        if not image.is_visible():
                            continue

                        box = image.bounding_box()

                        if not box:
                            continue

                        width = box["width"]
                        height = box["height"]
                        x = box["x"]

                        # Ignore small/unrelated images
                        if width < 300 or height < 300:
                            continue

                        src = image.get_attribute(
                            "src"
                        )

                        if not src:
                            continue

                        candidates.append(
                            {
                                "locator": image,
                                "src": src,
                                "width": width,
                                "height": height,
                                "x": x,
                                "index": i
                            }
                        )

                    except Exception:
                        continue

                if not candidates:
                    return None

                # Current image is the first large image
                # whose left edge is inside the viewport.
                visible_candidates = [
                    item
                    for item in candidates
                    if item["x"] >= 0
                ]

                if not visible_candidates:
                    return None

                visible_candidates.sort(
                    key=lambda item: item["x"]
                )

                active = visible_candidates[0]

                print(
                    "[Instagram] Active image selected: "
                    f"index={active['index']}, "
                    f"x={active['x']}"
                )

                return active

            # ==================================================
            # FIND NEXT BUTTON
            # ==================================================

            next_button = page.locator(
                'button[aria-label="Next"]'
            ).first

            print(
                f"[Instagram] Next button count: "
                f"{next_button.count()}"
            )

            if next_button.count() == 0:

                raise RuntimeError(
                    "Instagram carousel Next button not found."
                )

            print(
                "[Instagram] Next button outerHTML:"
            )

            try:

                print(
                    next_button.evaluate(
                        "(el) => el.outerHTML"
                    )
                )

            except Exception:
                pass

            # ==================================================
            # INITIAL DEBUG
            # ==================================================

            print(
                "\n========== INITIAL CAROUSEL =========="
            )

            debug_carousel_images()

            print(
                "======================================"
            )

            # ==================================================
            # GET FIRST IMAGE
            # ==================================================

            current_image = None

            for attempt in range(30):

                current_image = get_active_image()

                if current_image:
                    break

                page.wait_for_timeout(
                    300
                )

            if not current_image:

                raise RuntimeError(
                    "Could not detect first carousel image."
                )

            current_url = current_image["src"]

            print(
                "[Instagram] First carousel image detected."
            )

            print(
                "[Instagram] Current image index:",
                current_image["index"]
            )

            print(
                "[Instagram] Current image x:",
                current_image["x"]
            )

            print(
                "[Instagram] Current image URL:"
            )

            print(
                current_url
            )

            # ==================================================
            # DOWNLOAD IMAGE
            # ==================================================

            def download_image(
                image_url,
                index
            ):

                output_path = os.path.join(
                    DOWNLOAD_DIR,
                    f"{shortcode}_{index}.jpg"
                )

                print(
                    f"[Instagram] Downloading "
                    f"carousel image {index}..."
                )

                response = requests.get(
                    image_url,
                    headers={
                        "User-Agent": (
                            "Mozilla/5.0 "
                            "(Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 "
                            "(KHTML, like Gecko) "
                            "Chrome/140.0.0.0 "
                            "Safari/537.36"
                        )
                    },
                    timeout=60
                )

                response.raise_for_status()

                with open(
                    output_path,
                    "wb"
                ) as f:

                    f.write(
                        response.content
                    )

                print(
                    f"[Instagram] Saved carousel image: "
                    f"{output_path}"
                )

                return output_path

            output_path = download_image(
                current_url,
                1
            )

            downloaded_files.append(
                output_path
            )

            seen_urls = {
                current_url
            }

            # ==================================================
            # CAROUSEL LOOP
            # ==================================================

            for item_number in range(2, 21):

                print(
                    "\n-------------------------------------------"
                )

                print(
                    f"[Instagram] Moving to carousel "
                    f"item {item_number}..."
                )

                # ------------------------------------------------
                # Re-find Next button every time
                # ------------------------------------------------

                next_button = page.locator(
                    'button[aria-label="Next"]'
                ).first

                if next_button.count() == 0:

                    print(
                        "[Instagram] Next button no longer "
                        "exists. Carousel finished."
                    )

                    break

                # ------------------------------------------------
                # Get current active image
                # ------------------------------------------------

                old_image = get_active_image()

                if not old_image:

                    print(
                        "[Instagram] Could not identify "
                        "current carousel image."
                    )

                    break

                old_url = old_image["src"]

                print(
                    "[Instagram] Before navigation:"
                )

                print(
                    f"index={old_image['index']}, "
                    f"x={old_image['x']}"
                )
                
                # ------------------------------------------------
                # Check whether the next image is already loaded
                # ------------------------------------------------
                
                next_image_url = None
                
                try:
                    container = get_carousel_container()
                    
                    if container:
                        images = container.locator("img")

                        count = images.count()

                        right_candidates = []

                        for i in range(count):
                            image = images.nth(i)
                            
                            try:
                                if not image.is_visible():
                                    continue
                                
                                box = image.bounding_box()
                                
                                if not box:
                                    continue
                                
                                width = box["width"]
                                height = box["height"]
                                x = box["x"]
                                
                                if width < 300 or height < 300:
                                    continue
                                if x <= old_image["x"] + 100:
                                    continue
                                
                                src = image.get_attribute("src")
                                if not src:
                                    continue
                                if src in seen_urls:
                                    continue
                                
                                right_candidates.append(
                                    {
                                        "src": src,
                                        "x": x
                                    }
                                )
                                
                            except Exception:
                                continue
                            
                        if right_candidates:
                            right_candidates.sort(
                                key=lambda item: item["x"]
                            )
                            next_image_url = right_candidates[0]["src"]
                            
                            print(
                                "[Instagram] Next image already "
                                "present in DOM."
                            )
                            
                            print(
                                "[Instagram] Next image URL:"
                            )
                            
                            print(
                                next_image_url
                            )
                            
                except Exception as e:
                    print(
                        "[Instagram] Could not inspect "
                        f"preloaded next image: {e}"
                    )

        
                # ------------------------------------------------
                # Click Next
                # ------------------------------------------------

                clicked = False

                try:

                    next_button.evaluate(
                        "(button) => button.click()"
                    )

                    clicked = True

                    print(
                        "[Instagram] Next button "
                        "triggered with JS click."
                    )

                except Exception as e:

                    print(
                        "[Instagram] JS click failed:",
                        e
                    )

                # ------------------------------------------------
                # Fallback click
                # ------------------------------------------------

                if not clicked:

                    try:

                        next_button.click(
                            force=True,
                            timeout=5000
                        )

                        clicked = True

                        print(
                            "[Instagram] Next button "
                            "triggered with force click."
                        )

                    except Exception as e:

                        print(
                            "[Instagram] Force click failed:",
                            e
                        )

                if not clicked:
                    break

                # ==================================================
                # WAIT FOR NEW ACTIVE IMAGE
                # ==================================================

                

                print(
                    "[Instagram] Waiting for new "
                    "carousel image..."
                )
                new_image = None
                
                # ------------------------------------------------
                # If the next image was already preloaded,
                # use it directly.
                # ------------------------------------------------
                
                if next_image_url and next_image_url not in seen_urls:
                    print(
                        "[Instagram] Using preloaded next image."
                    )
                    
                    new_image = {
                        "src": next_image_url,      
                        "index": -1,
                        "x": 232
                    }
                    
                else:   
                    # ------------------------------------------------
                    # Otherwise wait for carousel navigation
                    # ------------------------------------------------
                    
                    for attempt in range(60):
                        time.sleep(0.3)
                        
                        try:
                            candidate = get_active_image()
                            
                            if candidate:
                                candidate_url = candidate["src"]
                                
                                if (
                                    candidate_url != old_url
                                    and candidate_url not in seen_urls
                                ):
                                    
                                    new_image = candidate
                                    break
                                
                        except Exception:
                            pass
                    if not new_image:
                        print(
                            "[Instagram] Could not detect a new "
                            "carousel image after waiting."
                        )
                        
                        break

                # Give Instagram a moment to start rebuilding.
                page.wait_for_timeout(300)

                for attempt in range(60):

                    candidate = get_active_image()

                    # Instagram may completely rebuild the
                    # carousel DOM. In that case, wait and
                    # rediscover the container on the next loop.
                    if not candidate:

                        if attempt % 5 == 0:

                            print(
                                "[Instagram] Carousel images "
                                "temporarily unavailable..."
                            )

                        page.wait_for_timeout(
                            300
                        )

                        continue

                    candidate_url = candidate["src"]

                    # A genuinely new image URL means that
                    # navigation succeeded.
                    if (
                        candidate_url != old_url
                        and candidate_url not in seen_urls
                    ):

                        new_image = candidate

                        print(
                            "[Instagram] Active image changed "
                            f"after {(attempt + 1) * 0.3:.1f}s."
                        )

                        break

                    page.wait_for_timeout(
                        300
                    )

                # ==================================================
                # DEBUG AFTER NAVIGATION
                # ==================================================

                print(
                    "\n[Instagram] Images after Next:"
                )

                debug_carousel_images()

                # ==================================================
                # FAILED TO FIND NEW IMAGE
                # ==================================================

                if not new_image:

                    print(
                        "[Instagram] Could not detect a new "
                        "carousel image after waiting."
                    )

                    print(
                        "[Instagram] Previous image URL:"
                    )

                    print(
                        old_url[:300]
                    )

                    break

                # ==================================================
                # NEW IMAGE
                # ==================================================

                new_url = new_image["src"]

                print(
                    "[Instagram] New active image:"
                )

                print(
                    f"index={new_image['index']}, "
                    f"x={new_image['x']}"
                )

                print(
                    "[Instagram] New image URL:"
                )

                print(
                    new_url
                )

                # ==================================================
                # DOWNLOAD
                # ==================================================

                output_path = download_image(
                    new_url,
                    item_number
                )

                downloaded_files.append(
                    output_path
                )

                seen_urls.add(
                    new_url
                )

            # ==================================================
            # COMPLETE
            # ==================================================

            print(
                "\n=========================================="
            )

            print(
                "[Instagram] Carousel browser download "
                f"complete: {len(downloaded_files)} item(s)"
            )

            print(
                "=========================================="
            )

            return downloaded_files

        finally:

            browser.close()


# ============================================================
# DETECT POST TYPE
# ============================================================

def _detect_post_type(url):
    """
    Try to determine whether an Instagram post is:
        video
        photo
        carousel
    """

    shortcode = extract_shortcode(url)

    if not shortcode:
        return "unknown"

    print(
        f"[Instagram] Detecting post type: {shortcode}"
    )

    # --------------------------------------------------------
    # Try Instaloader metadata
    # --------------------------------------------------------

    try:

        loader = instaloader.Instaloader()

        post = instaloader.Post.from_shortcode(
            loader.context,
            shortcode
        )

        if post.typename == "GraphSidecar":
            print(
                "[Instagram] Detected carousel."
            )

            return "carousel"

        if post.is_video:
            print(
                "[Instagram] Detected video."
            )

            return "video"

        print(
            "[Instagram] Detected photo."
        )

        return "photo"

    except Exception as e:

        print(
            "[Instagram] Instaloader type detection "
            f"failed: {e}"
        )

    return "unknown"


# ============================================================
# MAIN INSTAGRAM DOWNLOADER
# ============================================================

def download_instagram(url):
    """
    Main Instagram downloader.

    Returns:

    Video/photo:
        str -> file path

    Carousel:
        list[str] -> list of image paths
    """

    if not is_instagram_url(url):
        raise ValueError(
            "URL is not an Instagram URL."
        )

    url = clean_instagram_url(url)

    shortcode = extract_shortcode(url)

    if not shortcode:
        raise ValueError(
            "Could not extract Instagram shortcode."
        )

    print(
        "\n=========================================="
    )

    print(
        f"[Instagram] Processing: {url}"
    )

    print(
        f"[Instagram] Shortcode: {shortcode}"
    )

    print(
        "=========================================="
    )

    # --------------------------------------------------------
    # Detect post type
    # --------------------------------------------------------

    post_type = _detect_post_type(url)

    # --------------------------------------------------------
    # CAROUSEL
    # --------------------------------------------------------

    if post_type == "carousel":

        print(
            "[Instagram] Attempting carousel download..."
        )

        files = _download_carousel_with_browser(
            url
        )

        if files:

            return files

        raise RuntimeError(
            "Could not download Instagram carousel."
        )

    # --------------------------------------------------------
    # VIDEO
    # --------------------------------------------------------

    if post_type == "video":

        return _download_with_ytdlp(
            url
        )

    # --------------------------------------------------------
    # PHOTO
    # --------------------------------------------------------

    if post_type == "photo":

        # First try Instaloader
        photo_path = (
            _download_photo_with_instaloader(
                url
            )
        )

        if photo_path:

            return photo_path

        # Browser fallback
        photo_path = (
            _download_photo_from_webpage(
                url
            )
        )

        if photo_path:

            return photo_path

        raise RuntimeError(
            "Could not download Instagram photo."
        )

    # --------------------------------------------------------
    # UNKNOWN TYPE
    # --------------------------------------------------------

    print(
        "[Instagram] Post type unknown. "
        "Trying yt-dlp..."
    )

    try:

        return _download_with_ytdlp(
            url
        )

    except Exception as ytdlp_error:

        print(
            "[Instagram] yt-dlp failed:",
            ytdlp_error
        )

    print(
        "[Instagram] Trying browser photo fallback..."
    )

    photo_path = (
        _download_photo_from_webpage(
            url
        )
    )

    if photo_path:

        return photo_path

    raise RuntimeError(
        "Unable to download Instagram content."
    )
    
if __name__ == "__main__":
    test_url = input("Enter Instagram URL: ").strip()

    try:
        result = download_instagram(test_url)

        print("\n========== RESULT ==========")

        if isinstance(result, list):
            print(f"Downloaded {len(result)} files:")

            for file_path in result:
                print(file_path)

        else:
            print("Downloaded file:")
            print(result)

        print("============================")

    except Exception as e:
        print("\n========== ERROR ==========")
        print(e)
        print("===========================")