from playwright.async_api import async_playwright


async def extract_top_comment(url: str) -> dict | None:
    """
    Attempt to extract a publicly accessible Instagram comment.

    Returns:
        {
            "username": "...",
            "text": "...",
            "likes": 0
        }

    Returns None if comments are unavailable or extraction fails.
    """

    try:
        async with async_playwright() as p:

            browser = await p.chromium.launch(
                headless=True
            )

            page = await browser.new_page(
                viewport={
                    "width": 1280,
                    "height": 720
                }
            )

            print("🌐 Opening Instagram post...")

            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            # Allow dynamically loaded content some time.
            await page.wait_for_timeout(5000)

            print("📄 Page title:", await page.title())
            print("🔗 Current URL:", page.url)

            # -------------------------------------------------
            # Check whether Instagram is asking for login
            # -------------------------------------------------

            login_wall = page.get_by_text(
                "Log in",
                exact=True
            )

            if await login_wall.count() > 0:
                print(
                    "🔒 Instagram login wall detected. "
                    "Comments unavailable."
                )
                await browser.close()
                return None

            # -------------------------------------------------
            # Look for comment containers
            # -------------------------------------------------

            print("💬 Looking for comments...")

            comments = page.locator(
                "article ul li"
            )

            count = await comments.count()

            print(
                f"📝 Found {count} possible comment elements."
            )

            if count == 0:
                print("⚠️ No comments found.")
                await browser.close()
                return None

            # -------------------------------------------------
            # Inspect possible comments
            # -------------------------------------------------

            for i in range(min(count, 30)):

                comment = comments.nth(i)

                try:
                    text = (
                        await comment.inner_text(
                            timeout=1500
                        )
                    ).strip()

                except Exception:
                    continue

                if len(text) < 5:
                    continue

                lines = [
                    line.strip()
                    for line in text.splitlines()
                    if line.strip()
                ]

                if not lines:
                    continue

                print(
                    f"🔎 Possible comment: {lines}"
                )

                # -------------------------------------------------
                # Try to determine username
                # -------------------------------------------------

                username = ""

                links = comment.locator("a")

                link_count = await links.count()

                for j in range(link_count):

                    try:
                        href = await links.nth(j).get_attribute(
                            "href"
                        )

                        if href and "/".encode().decode() in href:
                            parts = [
                                part
                                for part in href.split("/")
                                if part
                            ]

                            if parts:
                                username = parts[-1]
                                break

                    except Exception:
                        continue

                # -------------------------------------------------
                # Try to find like count
                # -------------------------------------------------

                likes = None

                like_text = comment.get_by_text(
                    "likes",
                    exact=False
                )

                if await like_text.count() > 0:

                    try:
                        like_content = await like_text.first.inner_text()

                        digits = "".join(
                            character
                            for character in like_content
                            if character.isdigit()
                        )

                        if digits:
                            likes = int(digits)

                    except Exception:
                        pass

                # -------------------------------------------------
                # Clean comment text
                # -------------------------------------------------

                comment_text = text

                # Remove username from beginning if detected.
                if username:
                    comment_text = comment_text.replace(
                        username,
                        "",
                        1
                    ).strip()

                if len(comment_text) < 5:
                    continue

                print(
                    f"⭐ Comment found:"
                    f" username={username},"
                    f" likes={likes},"
                    f" text={comment_text}"
                )

                await browser.close()

                return {
                    "username": username,
                    "text": comment_text,
                    "likes": likes,
                }

            print("⚠️ No usable comment found.")

            await browser.close()

            return None

    except Exception as e:

        print(
            "⚠️ Comment extraction failed: "
            f"{type(e).__name__}: {e}"
        )

        # IMPORTANT:
        # Comment extraction is optional.
        # Never break the main download process.
        return None