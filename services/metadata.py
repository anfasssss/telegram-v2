import re

import instaloader

from urllib.parse import urlparse

from playwright.sync_api import sync_playwright


def clean_instagram_url(url: str) -> str:
    """
    Remove tracking/query parameters from an Instagram URL.
    """
    parsed = urlparse(url)

    return (
        f"{parsed.scheme}://"
        f"{parsed.netloc}"
        f"{parsed.path}"
    )


def extract_shortcode(url: str) -> str:
    """
    Extract the Instagram post/reel shortcode from a URL.
    """
    match = re.search(
        r"instagram\.com/(?:p|reel|tv)/"
        r"([A-Za-z0-9_-]+)",
        url
    )

    if not match:
        raise ValueError(
            "Invalid Instagram post/reel URL"
        )

    return match.group(1)


def extract_location_with_browser(
    url: str
) -> str | None:
    """
    Try to extract the publicly visible Instagram
    location tag using Playwright.

    Returns None if the location is not publicly
    available.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True
            )

            page = browser.new_page()

            print(
                "🌐 Checking Instagram page for location..."
            )

            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            page.wait_for_timeout(3000)

            location_links = page.locator(
                'a[href*="/explore/locations/"]'
            )

            count = location_links.count()

            print(
                f"📍 Found {count} possible "
                f"location link(s)."
            )

            ignored_locations = [
                "locations",
                "location",
                "explore",
                "search",
            ]

            for i in range(count):
                try:
                    link = location_links.nth(i)

                    href = link.get_attribute(
                        "href"
                    )

                    text = link.inner_text(
                        timeout=1000
                    ).strip()

                    print(
                        f"📍 Candidate {i + 1}: "
                        f"text={text!r}, "
                        f"href={href!r}"
                    )

                    if not href:
                        continue

                    if not re.search(
                        r"/explore/locations/"
                        r"\d+/[^/?]+",
                        href
                    ):
                        continue

                    if text:
                        location = text.strip()

                        if (
                            location.lower()
                            in ignored_locations
                        ):
                            continue

                        print(
                            f"📍 Valid location found: "
                            f"{location}"
                        )

                        browser.close()

                        return location

                except Exception:
                    continue

            browser.close()

            print(
                "📍 No valid publicly accessible "
                "location found."
            )

            return None

    except Exception as e:
        print(
            "⚠️ Browser location extraction failed: "
            f"{type(e).__name__}: {e}"
        )

        return None


def extract_public_metadata_with_browser(
    url: str
) -> dict:
    """
    Extract publicly visible Instagram metadata
    using Playwright.

    This is a fallback when Instaloader cannot
    retrieve the post.
    """

    result = {
        "username": None,
        "caption": "",
        "date": None,
        "hashtags": [],
        "mentions": [],
        "location": None,
    }

    print(
        "🌐 Trying Playwright metadata fallback..."
    )

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page()

        try:
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=60000,
            )

            page.wait_for_timeout(3000)

            # ---------------------------------
            # Username
            # ---------------------------------

            # Try common Instagram profile links.
            profile_links = page.locator(
                'a[href^="/"]'
            )

            count = profile_links.count()

            for i in range(count):
                try:
                    href = profile_links.nth(i).get_attribute(
                        "href"
                    )

                    text = profile_links.nth(i).inner_text(
                        timeout=500
                    ).strip()

                    if not href or not text:
                        continue

                    # Ignore common navigation paths.
                    ignored_paths = {
                        "/",
                        "/explore/",
                        "/accounts/",
                        "/direct/",
                        "/reels/",
                        "/p/",
                    }

                    if href in ignored_paths:
                        continue

                    # A simple public username link.
                    if re.fullmatch(
                        r"/[A-Za-z0-9._]+/?",
                        href
                    ):
                        if (
                            text.lower()
                            not in {
                                "follow",
                                "log in",
                                "sign up",
                            }
                        ):
                            result["username"] = (
                                text.lstrip("@").strip()
                            )
                            break

                except Exception:
                    continue

            # ---------------------------------
            # Open Graph metadata
            # ---------------------------------

            og_title = page.locator(
                'meta[property="og:title"]'
            ).get_attribute("content")

            og_description = page.locator(
                'meta[property="og:description"]'
            ).get_attribute("content")

            description = page.locator(
                'meta[name="description"]'
            ).get_attribute("content")

            # ---------------------------------
            # Username fallback from metadata
            # ---------------------------------

            combined_meta = " ".join(
                value
                for value in [
                    og_title,
                    og_description,
                    description,
                ]
                if value
            )

            if not result["username"]:
                username_match = re.search(
                    r"(?:by|from)\s+"
                    r"@?([A-Za-z0-9._]+)",
                    combined_meta,
                    re.IGNORECASE,
                )

                if username_match:
                    result["username"] = (
                        username_match.group(1)
                    )

            # ---------------------------------
            # Date
            # ---------------------------------

            time_element = page.locator(
                "time[datetime]"
            ).first

            if time_element.count() > 0:
                datetime_value = (
                    time_element.get_attribute(
                        "datetime"
                    )
                )

                if datetime_value:
                    result["date"] = datetime_value

            # ---------------------------------
            # Caption
            # ---------------------------------

            # First try visible article content.
            try:
                article = page.locator(
                    "article"
                ).first

                if article.count() > 0:
                    article_text = article.inner_text(
                        timeout=3000
                    ).strip()

                    if article_text:
                        lines = [
                            line.strip()
                            for line in article_text.splitlines()
                            if line.strip()
                        ]

                        # We only use this as a fallback.
                        # Avoid assigning the whole article
                        # blindly as the caption.
                        if result["username"]:
                            username = (
                                result["username"]
                            )

                            for index, line in enumerate(
                                lines
                            ):
                                if (
                                    line
                                    .lstrip("@")
                                    .strip()
                                    == username
                                ):
                                    following_lines = (
                                        lines[index + 1:]
                                    )

                                    if following_lines:
                                        result["caption"] = (
                                            " ".join(
                                                following_lines
                                            )
                                        )
                                    break

            except Exception:
                pass

            # If no visible caption was found,
            # use the public description as a fallback.
            if not result["caption"]:
                if description:
                    result["caption"] = description.strip()

                elif og_description:
                    result["caption"] = (
                        og_description.strip()
                    )

            # ---------------------------------
            # Hashtags
            # ---------------------------------

            if result["caption"]:
                result["hashtags"] = list(
                    dict.fromkeys(
                        re.findall(
                            r"#([A-Za-z0-9_]+)",
                            result["caption"]
                        )
                    )
                )

                result["mentions"] = list(
                    dict.fromkeys(
                        re.findall(
                            r"@([A-Za-z0-9._]+)",
                            result["caption"]
                        )
                    )
                )

            print(
                "🌐 Playwright metadata fallback "
                "completed."
            )

            return result

        finally:
            browser.close()


def extract_metadata(url: str) -> dict:
    """
    Extract metadata from a public Instagram post/reel.

    Instaloader is used first.

    If Instaloader cannot retrieve the post,
    Playwright is used as a public-page fallback.
    """

    shortcode = extract_shortcode(url)

    clean_url = clean_instagram_url(url)

    # ---------------------------------
    # Try Instaloader first
    # ---------------------------------

    try:
        loader = instaloader.Instaloader(
            download_pictures=False,
            download_videos=False,
            download_video_thumbnails=False,
            download_geotags=False,
            save_metadata=False,
            quiet=True,
        )

        post = instaloader.Post.from_shortcode(
            loader.context,
            shortcode
        )

        print(
            "📍 DEBUG LOCATION:",
            post.location
        )

        if post.location:
            print(
                "📍 DEBUG LOCATION NAME:",
                post.location.name
            )

            print(
                "📍 DEBUG LOCATION ID:",
                post.location.id
            )

        location = None

        # ---------------------------------
        # Location
        # ---------------------------------

        if post.location:
            location = post.location.name

            print(
                f"📍 Location from Instaloader: "
                f"{location}"
            )

        if not location:
            location = (
                extract_location_with_browser(
                    url
                )
            )

        metadata = {
            "username": post.owner_username,
            "caption": post.caption or "",
            "url": clean_url,
            "date": post.date_utc.isoformat(),
            "hashtags": list(
                post.caption_hashtags
            ),
            "mentions": list(
                post.caption_mentions
            ),
            "location": location,
        }

        return metadata

    # ---------------------------------
    # Instaloader failed
    # ---------------------------------

    except Exception as e:

        print(
            "⚠️ Instaloader metadata extraction "
            f"failed: {type(e).__name__}: {e}"
        )

        print(
            "🌐 Falling back to public webpage "
            "metadata..."
        )

        # ---------------------------------
        # Try Playwright fallback
        # ---------------------------------

        try:
            browser_metadata = (
                extract_public_metadata_with_browser(
                    url
                )
            )

            location = (
                browser_metadata.get("location")
            )

            if not location:
                location = (
                    extract_location_with_browser(
                        url
                    )
                )

            username = (
                browser_metadata.get("username")
                or "Unknown"
            )

            return {
                "username": username,
                "caption": (
                    browser_metadata.get(
                        "caption"
                    ) or ""
                ),
                "url": clean_url,
                "date": (
                    browser_metadata.get(
                        "date"
                    )
                ),
                "hashtags": (
                    browser_metadata.get(
                        "hashtags",
                        []
                    )
                ),
                "mentions": (
                    browser_metadata.get(
                        "mentions",
                        []
                    )
                ),
                "location": location,
            }

        except Exception as browser_error:

            print(
                "⚠️ Playwright metadata fallback "
                f"failed: "
                f"{type(browser_error).__name__}: "
                f"{browser_error}"
            )

            # ---------------------------------
            # Last-resort metadata
            # ---------------------------------

            print(
                "⚠️ Returning minimal metadata "
                "instead of failing the download."
            )

            return {
                "username": "Unknown",
                "caption": "",
                "url": clean_url,
                "date": None,
                "hashtags": [],
                "mentions": [],
                "location": None,
            }


if __name__ == "__main__":

    url = input(
        "Enter Instagram URL: "
    ).strip()

    try:
        data = extract_metadata(url)

        print(
            "\n✅ Metadata extracted!\n"
        )

        for key, value in data.items():
            print(
                f"{key}: {value}"
            )

    except Exception as e:

        print(
            "\n❌ Metadata extraction failed."
        )

        print(
            f"Error: {e}"
        )