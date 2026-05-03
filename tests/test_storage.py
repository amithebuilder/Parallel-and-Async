"""Tests for Day 6: JSONStorage, CSVStorage, SQLiteStorage."""

import json
import os
import pytest
import aiosqlite
from crawler.storage import JSONStorage, CSVStorage, SQLiteStorage

SAMPLE_DATA = {
    "url": "https://example.com",
    "title": "Example",
    "text": "Hello world",
    "links": ["https://example.com/a", "https://example.com/b"],
    "metadata": {"description": "test"},
    "images": [],
    "status_code": 200,
    "content_type": "text/html",
}


@pytest.fixture
def tmp_dir(tmp_path):
    return str(tmp_path)


@pytest.mark.asyncio
async def test_json_storage_save(tmp_dir):
    path = os.path.join(tmp_dir, "test.jsonl")
    async with JSONStorage(path) as storage:
        await storage.save(SAMPLE_DATA)
        await storage.save(SAMPLE_DATA)
        assert storage.count == 2

    # Verify file
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 2
    data = json.loads(lines[0])
    assert data["url"] == "https://example.com"
    assert "crawled_at" in data


@pytest.mark.asyncio
async def test_json_storage_export_all(tmp_dir):
    jsonl_path = os.path.join(tmp_dir, "test.jsonl")
    export_path = os.path.join(tmp_dir, "export.json")

    async with JSONStorage(jsonl_path) as storage:
        await storage.save(SAMPLE_DATA)
        await storage.save(SAMPLE_DATA)
        await storage.export_all(export_path)

    with open(export_path, encoding="utf-8") as f:
        arr = json.load(f)
    assert len(arr) == 2


@pytest.mark.asyncio
async def test_csv_storage_save(tmp_dir):
    path = os.path.join(tmp_dir, "test.csv")
    async with CSVStorage(path) as storage:
        await storage.save(SAMPLE_DATA)
        assert storage.count == 1

    with open(path, encoding="utf-8") as f:
        lines = f.readlines()
    assert len(lines) == 2  # header + 1 row
    assert "url" in lines[0]  # header


@pytest.mark.asyncio
async def test_csv_storage_save_many(tmp_dir):
    path = os.path.join(tmp_dir, "test.csv")
    async with CSVStorage(path) as storage:
        await storage.save_many([SAMPLE_DATA, SAMPLE_DATA, SAMPLE_DATA])
        assert storage.count == 3


@pytest.mark.asyncio
async def test_sqlite_storage(tmp_dir):
    path = os.path.join(tmp_dir, "test.db")
    data2 = {**SAMPLE_DATA, "url": "https://example.com/page2", "title": "Page 2"}
    async with SQLiteStorage(path, batch_size=2) as storage:
        await storage.save(SAMPLE_DATA)
        await storage.save(data2)
        # batch_size=2, so flush should have happened
        assert storage.count == 2

    # Verify DB contents
    async with aiosqlite.connect(path) as db:
        async with db.execute("SELECT COUNT(*) FROM pages") as cur:
            (count,) = await cur.fetchone()
        assert count == 2

        async with db.execute("SELECT url, title FROM pages ORDER BY url LIMIT 1") as cur:
            row = await cur.fetchone()
        assert row[0] == "https://example.com"
        assert row[1] == "Example"


@pytest.mark.asyncio
async def test_sqlite_storage_flush_on_close(tmp_dir):
    path = os.path.join(tmp_dir, "test.db")
    async with SQLiteStorage(path, batch_size=100) as storage:
        await storage.save(SAMPLE_DATA)  # won't flush yet (batch_size=100)

    # But close() should have flushed
    async with aiosqlite.connect(path) as db:
        async with db.execute("SELECT COUNT(*) FROM pages") as cur:
            (count,) = await cur.fetchone()
        assert count == 1
