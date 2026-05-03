"""Day 6: Async data storage — JSON, CSV, SQLite."""

import abc
import csv
import io
import json
import logging
from datetime import datetime, timezone

import aiofiles
import aiosqlite

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Abstract base
# ------------------------------------------------------------------

class DataStorage(abc.ABC):
    """Abstract interface for crawl-result storage."""

    @abc.abstractmethod
    async def save(self, data: dict) -> None: ...

    @abc.abstractmethod
    async def save_many(self, items: list[dict]) -> None: ...

    @abc.abstractmethod
    async def close(self) -> None: ...

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()


# ------------------------------------------------------------------
# JSON storage (one JSON-Lines file, one object per line)
# ------------------------------------------------------------------

class JSONStorage(DataStorage):
    """Append crawl results as JSON Lines (one JSON object per line).

    Also supports writing the entire dataset as a pretty-printed JSON array
    via :meth:`export_all`.
    """

    def __init__(self, filepath: str):
        self._filepath = filepath
        self._count = 0

    async def save(self, data: dict) -> None:
        data = self._prepare(data)
        try:
            async with aiofiles.open(self._filepath, "a", encoding="utf-8") as f:
                await f.write(json.dumps(data, ensure_ascii=False) + "\n")
            self._count += 1
        except Exception as exc:
            logger.error("JSONStorage.save failed: %s", exc)

    async def save_many(self, items: list[dict]) -> None:
        lines = []
        for item in items:
            lines.append(json.dumps(self._prepare(item), ensure_ascii=False))
        try:
            async with aiofiles.open(self._filepath, "a", encoding="utf-8") as f:
                await f.write("\n".join(lines) + "\n")
            self._count += len(items)
        except Exception as exc:
            logger.error("JSONStorage.save_many failed: %s", exc)

    async def export_all(self, output_path: str) -> None:
        """Read JSON-Lines file and export as a formatted JSON array."""
        records: list[dict] = []
        try:
            async with aiofiles.open(self._filepath, "r", encoding="utf-8") as f:
                async for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
        except FileNotFoundError:
            pass
        async with aiofiles.open(output_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(records, ensure_ascii=False, indent=2))

    async def close(self) -> None:
        pass

    @property
    def count(self) -> int:
        return self._count

    @staticmethod
    def _prepare(data: dict) -> dict:
        d = dict(data)
        if "crawled_at" not in d:
            d["crawled_at"] = datetime.now(timezone.utc).isoformat()
        return d


# ------------------------------------------------------------------
# CSV storage
# ------------------------------------------------------------------

class CSVStorage(DataStorage):
    """Append crawl results to a CSV file.

    Only scalar fields are written; lists/dicts are serialised as JSON strings.
    """

    FIELDS = [
        "url", "title", "status_code", "content_type",
        "text_length", "links_count", "images_count", "crawled_at",
    ]

    def __init__(self, filepath: str, fields: list[str] | None = None):
        self._filepath = filepath
        self._fields = fields or self.FIELDS
        self._header_written = False
        self._count = 0

    async def save(self, data: dict) -> None:
        row = self._make_row(data)
        try:
            async with aiofiles.open(self._filepath, "a", encoding="utf-8", newline="") as f:
                if not self._header_written:
                    await f.write(self._row_to_csv(self._fields))
                    self._header_written = True
                await f.write(self._row_to_csv([row.get(k, "") for k in self._fields]))
            self._count += 1
        except Exception as exc:
            logger.error("CSVStorage.save failed: %s", exc)

    async def save_many(self, items: list[dict]) -> None:
        buf = io.StringIO()
        writer = csv.writer(buf)
        if not self._header_written:
            writer.writerow(self._fields)
            self._header_written = True
        for item in items:
            row = self._make_row(item)
            writer.writerow([row.get(k, "") for k in self._fields])
        try:
            async with aiofiles.open(self._filepath, "a", encoding="utf-8", newline="") as f:
                await f.write(buf.getvalue())
            self._count += len(items)
        except Exception as exc:
            logger.error("CSVStorage.save_many failed: %s", exc)

    async def close(self) -> None:
        pass

    @property
    def count(self) -> int:
        return self._count

    @staticmethod
    def _make_row(data: dict) -> dict:
        row = dict(data)
        row.setdefault("crawled_at", datetime.now(timezone.utc).isoformat())
        row["text_length"] = len(data.get("text", ""))
        row["links_count"] = len(data.get("links", []))
        row["images_count"] = len(data.get("images", []))
        return row

    @staticmethod
    def _row_to_csv(values: list) -> str:
        buf = io.StringIO()
        csv.writer(buf).writerow(values)
        return buf.getvalue()


# ------------------------------------------------------------------
# SQLite storage
# ------------------------------------------------------------------

class SQLiteStorage(DataStorage):
    """Store crawl results in a SQLite database via aiosqlite."""

    def __init__(self, db_path: str, batch_size: int = 50):
        self._db_path = db_path
        self._batch_size = batch_size
        self._db: aiosqlite.Connection | None = None
        self._buffer: list[dict] = []
        self._count = 0

    async def _ensure_db(self) -> aiosqlite.Connection:
        if self._db is None:
            self._db = await aiosqlite.connect(self._db_path)
            await self._db.execute("""
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE,
                    title TEXT,
                    text TEXT,
                    links TEXT,
                    metadata TEXT,
                    status_code INTEGER,
                    content_type TEXT,
                    crawled_at TEXT
                )
            """)
            await self._db.execute(
                "CREATE INDEX IF NOT EXISTS idx_pages_url ON pages (url)"
            )
            await self._db.commit()
        return self._db

    async def save(self, data: dict) -> None:
        self._buffer.append(data)
        if len(self._buffer) >= self._batch_size:
            await self._flush()

    async def save_many(self, items: list[dict]) -> None:
        self._buffer.extend(items)
        if len(self._buffer) >= self._batch_size:
            await self._flush()

    async def _flush(self) -> None:
        if not self._buffer:
            return
        db = await self._ensure_db()
        rows = []
        for d in self._buffer:
            rows.append((
                d.get("url", ""),
                d.get("title", ""),
                d.get("text", ""),
                json.dumps(d.get("links", []), ensure_ascii=False),
                json.dumps(d.get("metadata", {}), ensure_ascii=False),
                d.get("status_code"),
                d.get("content_type", ""),
                d.get("crawled_at", datetime.now(timezone.utc).isoformat()),
            ))
        try:
            await db.executemany(
                """INSERT OR REPLACE INTO pages
                   (url, title, text, links, metadata, status_code, content_type, crawled_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            await db.commit()
            self._count += len(rows)
            logger.debug("SQLiteStorage flushed %d rows", len(rows))
        except Exception as exc:
            logger.error("SQLiteStorage flush failed: %s", exc)
        finally:
            self._buffer.clear()

    async def close(self) -> None:
        await self._flush()
        if self._db:
            await self._db.close()
            self._db = None

    @property
    def count(self) -> int:
        return self._count + len(self._buffer)  # include items pending flush
