#!/usr/bin/env python3
"""
generate_rss.py

Reads articles.yaml and produces docs/rss.xml.
Run automatically by the GitHub Action, but you can also run it
locally with:  python generate_rss.py
"""

import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.dom import minidom

import yaml

ARTICLES_FILE = Path(__file__).parent / "articles.yaml"
OUTPUT_DIR = Path(__file__).parent / "docs"
OUTPUT_FILE = OUTPUT_DIR / "rss.xml"


def parse_date(value):
    """Parse a pub_date string, or fall back to now (UTC) if missing/invalid."""
    if value:
        try:
            dt = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"Warning: could not parse date '{value}', using current time instead.")
    return datetime.now(timezone.utc)


def main():
    if not ARTICLES_FILE.exists():
        print(f"Error: {ARTICLES_FILE} not found.")
        sys.exit(1)

    with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    feed_meta = data.get("feed", {})
    articles = data.get("articles", []) or []

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = feed_meta.get("title", "My RSS Feed")
    ET.SubElement(channel, "link").text = feed_meta.get("link", "https://example.com")
    ET.SubElement(channel, "description").text = feed_meta.get("description", "A daily-updated RSS feed.")
    ET.SubElement(channel, "language").text = "en"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(datetime.now(timezone.utc))

    if not articles:
        print("No articles found in articles.yaml — generating an empty feed.")

    added = 0
    for i, article in enumerate(articles):
        title = article.get("title")
        link = article.get("link")
        description = article.get("description", "")

        if not title or not link:
            print(f"Skipping article #{i + 1}: missing required 'title' or 'link'.")
            continue

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text = link
        ET.SubElement(item, "description").text = description
        if article.get("category"):
            ET.SubElement(item, "category").text = article["category"]
        guid = ET.SubElement(item, "guid", isPermaLink="true")
        guid.text = link
        ET.SubElement(item, "pubDate").text = format_datetime(parse_date(article.get("pub_date")))
        added += 1

    OUTPUT_DIR.mkdir(exist_ok=True)
    rough_string = ET.tostring(rss, encoding="utf-8")
    pretty = minidom.parseString(rough_string).toprettyxml(indent="  ")
    # Drop blank lines minidom tends to introduce
    pretty = "\n".join(line for line in pretty.split("\n") if line.strip())
    OUTPUT_FILE.write_text(pretty, encoding="utf-8")

    print(f"Generated {OUTPUT_FILE} with {added} article(s).")


if __name__ == "__main__":
    main()
