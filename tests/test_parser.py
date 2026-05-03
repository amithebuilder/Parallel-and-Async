"""Tests for Day 2: HTMLParser."""

import pytest
from crawler.parser import HTMLParser

SAMPLE_HTML = """\
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
    <meta name="description" content="A test page">
    <meta name="keywords" content="test, parser">
</head>
<body>
    <h1>Main Heading</h1>
    <h2>Sub Heading</h2>
    <p>Some text content.</p>
    <a href="/page1">Page 1</a>
    <a href="https://external.com/link">External</a>
    <a href="javascript:void(0)">JS Link</a>
    <img src="/images/logo.png" alt="Logo">
    <img src="https://cdn.example.com/photo.jpg" alt="Photo">
    <table>
        <tr><th>Name</th><th>Value</th></tr>
        <tr><td>A</td><td>1</td></tr>
    </table>
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
    </ul>
    <ol>
        <li>First</li>
        <li>Second</li>
    </ol>
</body>
</html>
"""

BASE_URL = "https://example.com"


@pytest.fixture
def parser():
    return HTMLParser()


@pytest.mark.asyncio
async def test_parse_html(parser):
    data = await parser.parse_html(SAMPLE_HTML, BASE_URL)
    assert data["url"] == BASE_URL
    assert data["title"] == "Test Page"
    assert "Some text content" in data["text"]


@pytest.mark.asyncio
async def test_extract_links(parser):
    data = await parser.parse_html(SAMPLE_HTML, BASE_URL)
    links = data["links"]
    # Relative link converted to absolute
    assert "https://example.com/page1" in links
    # External link present
    assert "https://external.com/link" in links
    # javascript: link filtered out
    assert not any("javascript" in l for l in links)


@pytest.mark.asyncio
async def test_extract_metadata(parser):
    data = await parser.parse_html(SAMPLE_HTML, BASE_URL)
    meta = data["metadata"]
    assert meta["title"] == "Test Page"
    assert meta["description"] == "A test page"
    assert meta["keywords"] == "test, parser"


@pytest.mark.asyncio
async def test_extract_images(parser):
    data = await parser.parse_html(SAMPLE_HTML, BASE_URL)
    images = data["images"]
    assert len(images) == 2
    assert images[0]["src"] == "https://example.com/images/logo.png"
    assert images[0]["alt"] == "Logo"


@pytest.mark.asyncio
async def test_extract_headings(parser):
    data = await parser.parse_html(SAMPLE_HTML, BASE_URL)
    headings = data["headings"]
    assert len(headings) == 2
    assert headings[0] == {"level": 1, "text": "Main Heading"}
    assert headings[1] == {"level": 2, "text": "Sub Heading"}


@pytest.mark.asyncio
async def test_extract_tables(parser):
    data = await parser.parse_html(SAMPLE_HTML, BASE_URL)
    tables = data["tables"]
    assert len(tables) == 1
    assert tables[0][0] == ["Name", "Value"]
    assert tables[0][1] == ["A", "1"]


@pytest.mark.asyncio
async def test_extract_lists(parser):
    data = await parser.parse_html(SAMPLE_HTML, BASE_URL)
    lists = data["lists"]
    assert len(lists) == 2
    assert lists[0]["type"] == "ul"
    assert lists[0]["items"] == ["Item 1", "Item 2"]
    assert lists[1]["type"] == "ol"


@pytest.mark.asyncio
async def test_broken_html(parser):
    broken = "<html><body><p>Unclosed<div>Nested badly"
    data = await parser.parse_html(broken, "https://test.com")
    assert data["url"] == "https://test.com"
    assert "Unclosed" in data["text"]
    assert "parse_error" not in data


@pytest.mark.asyncio
async def test_empty_html(parser):
    data = await parser.parse_html("", "https://test.com")
    assert data["title"] == ""
    assert data["links"] == []
