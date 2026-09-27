import sqlite3
from pathlib import Path


DATABASE_PATH = Path("data/bot.db")


def get_connection():
    """
    Create and return a SQLite database connection.
    """

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():
    """
    Create the required database tables.
    """

    connection = get_connection()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                instagram_url TEXT NOT NULL,
                media_type TEXT,
                creator_username TEXT,
                status TEXT NOT NULL,
                error_message TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT
            )
            """
        )

        connection.commit()

        print("🗄️ Database initialized.")

    finally:
        connection.close()
        
        
def create_download(
    user_id: int | None,
    username: str | None,
    instagram_url: str,
):
    """
    Create a new download record.

    Returns the database record ID.
    """

    connection = get_connection()

    try:
        cursor = connection.execute(
            """
            INSERT INTO downloads (
                user_id,
                username,
                instagram_url,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, datetime('now'))
            """,
            (
                user_id,
                username,
                instagram_url,
                "queued",
            ),
        )

        connection.commit()

        return cursor.lastrowid

    finally:
        connection.close()


def update_download_status(
    download_id: int,
    status: str,
    media_type: str | None = None,
    creator_username: str | None = None,
    error_message: str | None = None,
):
    """
    Update the status and information of a download.
    """

    connection = get_connection()

    try:
        connection.execute(
            """
            UPDATE downloads
            SET
                status = ?,
                media_type = COALESCE(?, media_type),
                creator_username = COALESCE(?, creator_username),
                error_message = ?,
                completed_at = CASE
                    WHEN ? IN ('completed', 'failed')
                    THEN datetime('now')
                    ELSE completed_at
                END
            WHERE id = ?
            """,
            (
                status,
                media_type,
                creator_username,
                error_message,
                status,
                download_id,
            ),
        )

        connection.commit()

    finally:
        connection.close()
        
        
def get_download(download_id: int):
    """
    Get a single download record by ID.
    """

    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT *
            FROM downloads
            WHERE id = ?
            """,
            (download_id,),
        ).fetchone()

        return dict(row) if row else None

    finally:
        connection.close()
        
        
def get_user_downloads(
    user_id: int,
    limit: int = 10
):
    """
    Get recent downloads for a Telegram user.
    """

    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM downloads
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                user_id,
                limit,
            ),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()
        
        
def get_download_stats():
    """
    Get overall download statistics.
    """

    connection = get_connection()

    try:
        total = connection.execute(
            """
            SELECT COUNT(*)
            FROM downloads
            """
        ).fetchone()[0]

        completed = connection.execute(
            """
            SELECT COUNT(*)
            FROM downloads
            WHERE status = 'completed'
            """
        ).fetchone()[0]

        failed = connection.execute(
            """
            SELECT COUNT(*)
            FROM downloads
            WHERE status = 'failed'
            """
        ).fetchone()[0]

        videos = connection.execute(
            """
            SELECT COUNT(*)
            FROM downloads
            WHERE media_type = 'video'
            """
        ).fetchone()[0]

        photos = connection.execute(
            """
            SELECT COUNT(*)
            FROM downloads
            WHERE media_type = 'photo'
            """
        ).fetchone()[0]

        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "videos": videos,
            "photos": photos,
        }

    finally:
        connection.close()
        

def check_database():
    """
    Check whether the SQLite database is accessible.
    """

    connection = get_connection()

    try:
        connection.execute(
            "SELECT 1"
        )

        return True

    except Exception as e:
        print(
            f"❌ Database check failed: {e}"
        )
        return False

    finally:
        connection.close()