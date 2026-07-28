#!/usr/bin/env python3
"""
generate_rss.py

Reads articles.yaml and produces one RSS file per source in docs/,
plus a combined docs/rss.xml with everything together.

Run automatically by the GitHub Action, but you can also run it
locally with:  python generate_rss.py
"""

import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.dom import minidom

import yaml

ARTICLES_FILE = Path(__file__).parent / "articles.yaml"
OUTPUT_DIR = Path(__file__).parent / "docs"
COMBINED_FILE = OUTPUT_DIR / "rss.xml"


def parse_date(value):
    """Parse a pub_date string, or fall back to now (UTC) if missing/invalid."""
    if value:
        try:
            dt = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"Warning: could not parse date '{value}', using current time instead.")
    return datetime.now(timezone.utc)


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def build_rss(articles, title, link, description):
    """Build an RSS <rss> ElementTree from a list of article dicts."""
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "link").text = link
    ET.SubElement(channel, "description").text = description
    ET.SubElement(channel, "language").text = "en"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(datetime.now(timezone.utc))

    added = 0
    for i, article in enumerate(articles):
        a_title = article.get("title")
        a_link = article.get("link")
        a_description = article.get("description", "")

        if not a_title or not a_link:
            print(f"  Skipping article #{i + 1}: missing required 'title' or 'link'.")
            continue

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = a_title
        ET.SubElement(item, "link").text = a_link
        ET.SubElement(item, "description").text = a_description
        if article.get("category"):
            ET.SubElement(item, "category").text = article["category"]
        guid = ET.SubElement(item, "guid", isPermaLink="true")
        guid.text = a_link
        ET.SubElement(item, "pubDate").text = format_datetime(parse_date(article.get("pub_date")))
        added += 1

    return rss, added


def write_pretty_xml(rss_element, output_file):
    rough_string = ET.tostring(rss_element, encoding="utf-8")
    pretty = minidom.parseString(rough_string).toprettyxml(indent="  ")
    pretty = "\n".join(line for line in pretty.split("\n") if line.strip())
    output_file.write_text(pretty, encoding="utf-8")


def main():
    if not ARTICLES_FILE.exists():
        print(f"Error: {ARTICLES_FILE} not found.")
        sys.exit(1)

    with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    feed_meta = data.get("feed", {})
    base_link = feed_meta.get("link", "https://example.com").rstrip("/")
    articles = data.get("articles", []) or []

    if not articles:
        print("No articles found in articles.yaml — generating an empty combined feed only.")

    OUTPUT_DIR.mkdir(exist_ok=True)

    # --- Group articles by source (slug) ---
    by_slug = {}
    for article in articles:
        slug = article.get("slug") or slugify(article.get("source", "unknown"))
        by_slug.setdefault(slug, {"source": article.get("source", slug), "items": []})
        by_slug[slug]["items"].append(article)

    generated_files = []
    for slug, group in by_slug.items():
        source_name = group["source"]
        rss, added = build_rss(
            group["items"],
            title=f"{source_name} — {feed_meta.get('title', 'Feed')}",
            link=f"{base_link}/rss-{slug}.xml",
            description=f"Latest articles from {source_name}.",
        )
        out_file = OUTPUT_DIR / f"rss-{slug}.xml"
        write_pretty_xml(rss, out_file)
        generated_files.append((slug, source_name, added, out_file.name))
        print(f"Generated {out_file} with {added} article(s).")

    # --- Combined feed with everything ---
    rss, added = build_rss(
        articles,
        title=feed_meta.get("title", "My RSS Feed"),
        link=feed_meta.get("link", "https://example.com"),
        description=feed_meta.get("description", "A daily-updated RSS feed."),
    )
    write_pretty_xml(rss, COMBINED_FILE)
    print(f"Generated {COMBINED_FILE} with {added} article(s) (combined, all sources).")

    # --- Rebuild the landing page with links to every per-source feed ---
    links_html = "\n".join(
        f'    <li><a href="rss-{slug}.xml">{source_name}</a></li>'
        for slug, source_name, _, _ in sorted(generated_files, key=lambda x: x[1])
    )
    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{feed_meta.get('title', 'My RSS Feed')}</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; max-width: 600px; margin: 80px auto; padding: 0 20px; color: #222; }}
    a {{ color: #d2691e; }}
    li {{ margin-bottom: 8px; }}
    code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>📡 {feed_meta.get('title', 'My RSS Feed')}</h1>
  <p>Combined feed (all sources): <a href="rss.xml">rss.xml</a></p>
  <p>Individual feeds by source:</p>
  <ul>
{links_html if links_html else '    <li>(none generated yet)</li>'}
  </ul>
  <p><em>These feeds rebuild automatically every day and whenever new articles are scraped.</em></p>
</body>
</html>
"""
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print(f"Updated {OUTPUT_DIR / 'index.html'} with links to {len(generated_files)} source feed(s).")


if __name__ == "__main__":
    main()
