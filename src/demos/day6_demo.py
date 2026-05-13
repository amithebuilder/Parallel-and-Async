"""Day 6 demo: JSON / CSV / SQLite storage."""

import asyncio
import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from crawler.storage import JSONStorage, CSVStorage, SQLiteStorage

PAGES = [
    {"url": f"https://example.com/page{i}", "title": f"Page {i}",
     "status_code": 200, "content_type": "text/html",
     "text": f"Content of page {i}", "links": []}
    for i in range(5)
]


async def main():
    with tempfile.TemporaryDirectory() as tmpdir:
        # JSON Lines
        json_path = os.path.join(tmpdir, "out.jsonl")
        store = JSONStorage(json_path)
        await store.save_many(PAGES)
        await store.close()
        lines = open(json_path).readlines()
        print(f"JSON Lines: {len(lines)} records written to {json_path}")

        # CSV
        csv_path = os.path.join(tmpdir, "out.csv")
        store = CSVStorage(csv_path)
        await store.save_many(PAGES)
        await store.close()
        print(f"CSV: {store.count} records written")

        # SQLite
        db_path = os.path.join(tmpdir, "out.db")
        store = SQLiteStorage(db_path, batch_size=3)
        await store.save_many(PAGES)
        await store.close()
        print(f"SQLite: {store.count} records in DB")


if __name__ == "__main__":
    asyncio.run(main())
