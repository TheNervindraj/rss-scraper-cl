# Auto-Scraped RSS Feed → Power Automate → Dataverse

Scrapes article title, published date, and link from websites that don't
publish their own RSS, republishes them as a real RSS feed, and rebuilds
that feed automatically — so a weekly Power Automate flow can read it and
push new items into Dataverse.

## How it works

```
sources.yaml (your list of sites + link-matching rules)
   → scrape_sources.py   (visits each site, finds articles, extracts
                           title/date/link, writes articles.yaml)
   → generate_rss.py     (turns articles.yaml into docs/rss.xml)
   → GitHub Pages        (publishes rss.xml at a public URL)
   → Power Automate      ("When a feed item is published" trigger,
                           weekly, reads title/link/pubDate/category)
   → Dataverse
```

The whole pipeline runs automatically via GitHub Actions — daily on a
schedule, and instantly whenever you edit `sources.yaml`.

## Current source status

| Source | Category | Status |
|---|---|---|
| MOIT (moit.gov.vn) | Government | Active — static HTML, confirmed scrapable |
| Vietnam Energy Online | Vietnam news | Active — static HTML, confirmed scrapable |
| Halliburton Newsroom | Competitors | Needs review — press release list uses a filterable JS interface; link discovery may return few results until confirmed on a real run |
| Energy Voice | Industry intelligence | Needs review — large paginated site, listing structure not yet confirmed against live HTML |
| PVN (pvn.vn) | Operators | Skipped — homepage returned stale/cached content when inspected, suggesting it's JS-rendered. Simple scraping likely won't work; would need a headless-browser approach or manual entry |

**Important honest note:** I built the scraper's logic (title/date extraction)
against real page content I inspected, and unit-tested that logic locally.
But I don't have live network access to run it against these actual
websites end-to-end before handing it to you. The two "Active" sources are
the ones I'm most confident in; treat the first GitHub Actions run as the
real test. If a source comes back with 0 articles, see "Debugging a source"
below — it's usually a one-line fix in `sources.yaml`, not a rebuild.

## One-time setup

Same as the manual version:
1. Push these files to a new GitHub repo.
2. Settings → Pages → Deploy from branch → `main` / `/docs`.
3. Settings → Actions → General → Workflow permissions → **Read and write**.
4. Update `feed.link` in `articles.yaml` to your real Pages URL (this gets
   preserved automatically on future scrapes).
5. Actions tab → "Build and publish RSS feed" → **Run workflow** to trigger
   the first scrape.
6. Your feed will be live at:
   `https://YOUR-USERNAME.github.io/YOUR-REPO-NAME/rss.xml`

## Debugging a source that returns 0 articles

Open the Action's run log (Actions tab → latest run → "Scrape sources"
step). You'll see one of two messages per source:

- `found 0 candidate link(s)` — the `link_pattern` regex in `sources.yaml`
  didn't match any links on the listing page. Open the site, right-click
  an article headline → Inspect, and check what its actual URL looks like;
  adjust `link_pattern` to match that shape.
- `Failed to fetch ... 403/429` — the site is blocking automated requests.
  This needs a different approach (rotating headers, a delay increase, or
  in stubborn cases a headless browser) — flag it and I'll adjust.

## Adding a new source

Add a block to `sources.yaml`:

```yaml
  - name: "Some New Site"
    category: "Operators"
    list_url: "https://example.com/news"
    link_pattern: 'example\.com/news/[a-z0-9-]+'
    max_articles: 10
    status: active
```

Commit it — the next scheduled run (or your next `workflow_dispatch`) will
pick it up automatically.

## Setting up the Power Automate side

1. **Trigger:** Add an action → search "RSS" → **"When a feed item is
   published"**. Paste your feed URL
   (`https://your-username.github.io/your-repo/rss.xml`). Set the polling
   interval to weekly (or however often you want PA to check — the feed
   itself refreshes daily regardless).
2. **Fields available from the trigger:** Title, Link, Publish Date,
   Summary, and Category (each item's category is included in the feed too,
   in case it's useful as a cross-check against your own category logic).
3. **Map into Dataverse:** Add a "Add a new row" (Dataverse) action, map:
   - Title → Title column
   - Publish Date → your date column
   - Link → your link/URL column
   - (plus your existing Source Name / Category logic)

## Running it locally (optional)

```bash
pip install -r requirements.txt
python scrape_sources.py   # writes articles.yaml
python generate_rss.py     # writes docs/rss.xml
```

## Files in this project

| File | Purpose |
|---|---|
| `sources.yaml` | The websites to scrape + how to recognize their article links — **edit this to add/fix sources** |
| `scrape_sources.py` | Visits each active source, extracts title/date/link, writes `articles.yaml` |
| `articles.yaml` | Auto-generated scrape output (kept in git so you can see history/diffs) |
| `generate_rss.py` | Turns `articles.yaml` into `docs/rss.xml` |
| `docs/rss.xml` | The published feed — this is the URL you give Power Automate |
| `docs/index.html` | Simple landing page linking to the feed |
| `.github/workflows/build-rss.yml` | Automation: runs daily + on every relevant push |
