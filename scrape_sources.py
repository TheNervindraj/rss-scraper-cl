#!/usr/bin/env python3
"""
scrape_sources.py

Reads sources.yaml, visits each "active" site, discovers article links,
then visits each article to extract title + published date from page
metadata (falls back to visible text patterns where needed).

Writes results into articles.yaml (same format the manual-entry version
uses), which generate_rss.py then turns into docs/rss.xml.

Run locally with:  python scrape_sources.py
"""

import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import yaml
from bs4 import BeautifulSoup

SOURCES_FILE = Path(__file__).parent / "sources.yaml"
ARTICLES_FILE = Path(__file__).parent / "articles.yaml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
REQUEST_TIMEOUT = 20
DELAY_BETWEEN_REQUESTS = 1.5  # be polite to source servers
MAX_ARTICLE_AGE_DAYS = 90     # skip anything older than ~3 months
TOP_N_PER_SOURCE = 3          # keep only the N most recent per source

# Vietnamese weekday-date pattern, e.g. "Thứ 4, 22/07/2026"
VN_DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def fetch(url):
    """GET a URL, return BeautifulSoup or None on failure."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except requests.RequestException as e:
        print(f"    ! Failed to fetch {url}: {e}")
        return None


def discover_links(list_url, link_pattern, max_articles):
    """Find article links on a listing page matching link_pattern."""
    soup = fetch(list_url)
    if soup is None:
        return []

    pattern = re.compile(link_pattern)
    seen = set()
    links = []

    for a in soup.find_all("a", href=True):
        href = urljoin(list_url, a["href"])
        if href in seen:
            continue
        if pattern.search(href):
            seen.add(href)
            links.append(href)
        if len(links) >= max_articles:
            break

    return links


def extract_title(soup, fallback_url):
    """Try meta tags first, then <h1>, then <title>."""
    for attrs in (
        {"property": "og:title"},
        {"name": "twitter:title"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            return tag["content"].strip()

    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)

    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)

    return fallback_url


def extract_date(soup):
    """Try common published-date meta tags, then fall back to a
    dd/mm/yyyy pattern found in the visible page text."""
    for attrs in (
        {"property": "article:published_time"},
        {"name": "publish-date"},
        {"name": "pubdate"},
        {"name": "date"},
        {"itemprop": "datePublished"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            raw = tag["content"].strip()
            for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
                try:
                    dt = datetime.strptime(raw[:19], fmt.replace("%z", ""))
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue

    # Fallback: search visible text for a dd/mm/yyyy pattern
    text = soup.get_text(" ", strip=True)
    match = VN_DATE_RE.search(text)
    if match:
        day, month, year = match.groups()
        try:
            dt = datetime(int(year), int(month), int(day))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    return None  # unknown — generate_rss.py will fall back to "now"


def scrape_source(source):
    name = source["name"]
    print(f"\n[{name}] discovering article links on {source['list_url']} ...")
    links = discover_links(source["list_url"], source["link_pattern"], source["max_articles"])
    print(f"  found {len(links)} candidate link(s)")

    if not links:
        print(f"  ! No links matched link_pattern for '{name}'. "
              f"The pattern likely needs adjusting in sources.yaml — "
              f"see README for how to debug this.")
        return []

    articles = []
    for link in links:
        soup = fetch(link)
        time.sleep(DELAY_BETWEEN_REQUESTS)
        if soup is None:
            continue

        title = extract_title(soup, link)
        pub_date = extract_date(soup)

        if pub_date is None:
            print(f"    - skipped (no date found, can't verify age): {title[:60]}")
            continue

        article_dt = datetime.strptime(pub_date, "%Y-%m-%d %H:%M:%S")
        cutoff = datetime.now() - timedelta(days=MAX_ARTICLE_AGE_DAYS)
        if article_dt < cutoff:
            print(f"    - skipped (older than {MAX_ARTICLE_AGE_DAYS} days, "
                  f"{pub_date}): {title[:60]}")
            continue

        articles.append({
            "title": title,
            "link": link,
            "description": f"Source: {name} | Category: {source.get('category', '')}",
            "pub_date": pub_date,
            "source": name,
            "category": source.get("category", ""),
        })
        print(f"    - {title[:70]}{'...' if len(title) > 70 else ''}"
              f"  ({pub_date or 'date unknown'})")

    articles.sort(key=lambda a: a["pub_date"], reverse=True)
    if len(articles) > TOP_N_PER_SOURCE:
        print(f"  keeping the {TOP_N_PER_SOURCE} most recent "
              f"(discarding {len(articles) - TOP_N_PER_SOURCE} older match(es))")
    articles = articles[:TOP_N_PER_SOURCE]

    return articles


def main():
    if not SOURCES_FILE.exists():
        print(f"Error: {SOURCES_FILE} not found.")
        sys.exit(1)

    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    all_articles = []
    skipped = []

    for source in config.get("sources", []):
        if source.get("status") != "active":
            skipped.append(source["name"])
            continue
        all_articles.extend(scrape_source(source))

    if skipped:
        print(f"\nSkipped (status != active): {', '.join(skipped)}")

    # Preserve existing feed metadata if articles.yaml already exists
    feed_meta = {
        "title": "Oil & Gas Industry Watch",
        "link": "https://yourusername.github.io/your-repo-name/",
        "description": "Auto-scraped articles across government, operator, "
                        "competitor, and industry-intelligence sources.",
    }
    if ARTICLES_FILE.exists():
        with open(ARTICLES_FILE, "r", encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}
        if existing.get("feed"):
            feed_meta = existing["feed"]

    output = {"feed": feed_meta, "articles": all_articles}

    with open(ARTICLES_FILE, "w", encoding="utf-8") as f:
        yaml.dump(output, f, allow_unicode=True, sort_keys=False, width=100)

    print(f"\nWrote {len(all_articles)} article(s) total to {ARTICLES_FILE}")


if __name__ == "__main__":
    main()
