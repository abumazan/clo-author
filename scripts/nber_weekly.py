"""
NBER Weekly Paper Fetcher
=========================
Fetches new NBER working papers relevant to:
  - Global value chains (GVC)
  - International trade
  - Production networks
  - International economics

Usage:
    python nber_weekly.py              # fetch this week's papers
    python nber_weekly.py --days 14    # fetch last 14 days
    python nber_weekly.py --download   # also download PDFs (requires NBER access)

Output:
    master_supporting_docs/nber/       # downloaded PDFs
    master_supporting_docs/nber/log/   # weekly CSV logs
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import feedparser
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

KEYWORDS = [
    # GVC core
    "global value chain", "value chain", "value-added export",
    "value added trade", "vertical specialization", "fragmentation",
    "offshoring", "reshoring", "nearshoring", "GVC",
    # Trade
    "international trade", "trade policy", "trade war",
    "tariff", "trade agreement", "comparative advantage",
    "gravity model", "trade cost", "trade barrier",
    "trade liberalization", "trade openness",
    "terms of trade", "trade balance", "trade deficit",
    # Production networks
    "production network", "supply chain", "input-output",
    "intermediate good", "intermediate input",
    "upstream industry", "downstream industry",
    "production linkage", "shock propagation",
    # International economics
    "international economics", "multinational",
    "foreign direct investment", "FDI",
    "exchange rate", "current account",
    "globalization", "deglobalization",
    "open economy", "trade openness",
    # Methods
    "multi-region input-output", "MRIO",
    "inter-country input-output", "ICIO",
    "world input-output", "WIOD",
    "Leontief", "input-output table",
]

NBER_PROGRAMS = [
    "ITI",   # International Trade and Investment
    "IFM",   # International Finance and Macroeconomics
    "DEV",   # Development Economics
    "EFG",   # Economic Fluctuations and Growth
]

NBER_RSS_URL = "https://www.nber.org/rss/new.xml"
NBER_PAPER_BASE = "https://www.nber.org/papers/w{}"
NBER_PDF_BASE = "https://www.nber.org/system/files/working_papers/w{}/w{}.pdf"

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_DIR / "master_supporting_docs" / "nber"
LOG_DIR = OUTPUT_DIR / "log"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (academic research; GVC course)",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def keyword_pattern():
    escaped = [re.escape(kw) for kw in KEYWORDS]
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)

KW_RE = keyword_pattern()


def matches_keywords(title, abstract):
    text = f"{title} {abstract}"
    found = set(m.group().lower() for m in KW_RE.finditer(text))
    return found


def fetch_rss_papers():
    """Fetch papers from the NBER RSS feed."""
    print("Fetching NBER RSS feed...")
    feed = feedparser.parse(NBER_RSS_URL)
    papers = []
    for entry in feed.entries:
        # Extract paper number from link
        m = re.search(r"w(\d+)", entry.get("link", ""))
        paper_id = m.group(1) if m else None
        papers.append({
            "id": paper_id,
            "title": entry.get("title", "").strip(),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", "").strip(),
            "published": entry.get("published", ""),
        })
    print(f"  Found {len(papers)} papers in RSS feed.")
    return papers


def fetch_paper_details(paper_id):
    """Fetch full abstract and program info from the paper page."""
    url = NBER_PAPER_BASE.format(paper_id)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Warning: could not fetch {url}: {e}")
        return {}, []

    soup = BeautifulSoup(resp.text, "html.parser")

    # Abstract
    abstract = ""
    abs_div = soup.find("div", class_="page-header__intro-inner")
    if abs_div:
        abstract = abs_div.get_text(strip=True)

    # Programs
    programs = []
    prog_links = soup.select('a[href*="/programs/"]')
    for a in prog_links:
        href = a.get("href", "")
        code = href.rstrip("/").split("/")[-1].upper()
        if code:
            programs.append(code)

    # Authors
    authors = []
    author_links = soup.select('a[href*="/people/"]')
    for a in author_links:
        name = a.get_text(strip=True)
        if name:
            authors.append(name)

    return {
        "abstract": abstract,
        "authors": authors,
        "programs": programs,
    }, programs


def download_pdf(paper_id, output_dir):
    """Attempt to download the PDF. Requires institutional/NBER access."""
    url = NBER_PDF_BASE.format(paper_id, paper_id)
    out_path = output_dir / f"w{paper_id}.pdf"
    if out_path.exists():
        print(f"  PDF already exists: {out_path.name}")
        return True
    try:
        resp = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        if resp.status_code == 200 and "pdf" in resp.headers.get("content-type", "").lower():
            with open(out_path, "wb") as f:
                for chunk in resp.iter_content(8192):
                    f.write(chunk)
            print(f"  Downloaded: {out_path.name}")
            return True
        else:
            print(f"  PDF not accessible (status {resp.status_code}): w{paper_id}")
            return False
    except requests.RequestException as e:
        print(f"  Download failed for w{paper_id}: {e}")
        return False


def save_log(papers, log_dir):
    """Save a CSV log of matched papers."""
    log_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_path = log_dir / f"nber_{date_str}.csv"

    with open(log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "paper_id", "title", "authors", "programs",
            "matched_keywords", "link", "published",
        ])
        for p in papers:
            writer.writerow([
                p.get("id", ""),
                p.get("title", ""),
                "; ".join(p.get("authors", [])),
                "; ".join(p.get("programs", [])),
                "; ".join(sorted(p.get("matched_keywords", set()))),
                p.get("link", ""),
                p.get("published", ""),
            ])

    print(f"\nLog saved: {log_path}")
    return log_path


def save_summary(papers, log_dir):
    """Save a human-readable markdown summary."""
    date_str = datetime.now().strftime("%Y-%m-%d")
    md_path = log_dir / f"nber_{date_str}.md"

    lines = [f"# NBER Papers — {date_str}\n"]
    lines.append(f"**{len(papers)} relevant papers found**\n")

    for p in papers:
        lines.append(f"### w{p['id']}: {p['title']}")
        if p.get("authors"):
            lines.append(f"**Authors:** {', '.join(p['authors'])}")
        if p.get("programs"):
            lines.append(f"**Programs:** {', '.join(p['programs'])}")
        if p.get("matched_keywords"):
            lines.append(f"**Keywords matched:** {', '.join(sorted(p['matched_keywords']))}")
        lines.append(f"**Link:** {p['link']}")
        if p.get("abstract"):
            lines.append(f"\n> {p['abstract'][:500]}{'...' if len(p.get('abstract',''))>500 else ''}\n")
        lines.append("---\n")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Summary saved: {md_path}")
    return md_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fetch relevant NBER working papers")
    parser.add_argument("--days", type=int, default=7,
                        help="Look back this many days (default: 7)")
    parser.add_argument("--download", action="store_true",
                        help="Also download PDFs (requires NBER/institutional access)")
    parser.add_argument("--all-details", action="store_true",
                        help="Fetch full abstract from each paper page (slower)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Fetch RSS
    papers = fetch_rss_papers()
    if not papers:
        print("No papers found in RSS feed.")
        return

    # 2. Filter by keywords (using RSS summary first)
    matched = []
    for p in papers:
        kw = matches_keywords(p["title"], p["summary"])
        if kw:
            p["matched_keywords"] = kw
            p["abstract"] = p["summary"]
            p["authors"] = []
            p["programs"] = []
            matched.append(p)

    print(f"\n{len(matched)} papers matched keywords from RSS titles/summaries.")

    # 3. Optionally fetch full details for matched papers
    if args.all_details and matched:
        print("\nFetching full details for matched papers...")
        for i, p in enumerate(matched):
            if p["id"]:
                details, programs = fetch_paper_details(p["id"])
                p.update(details)
                # Re-check with full abstract
                kw = matches_keywords(p["title"], p.get("abstract", ""))
                p["matched_keywords"] = kw
                time.sleep(1)  # be polite
                print(f"  [{i+1}/{len(matched)}] w{p['id']}: {p['title'][:60]}...")

    # 4. Filter by NBER programs (if details fetched)
    if args.all_details:
        program_matched = []
        for p in papers:
            if p in matched:
                continue
            if p["id"]:
                details, programs = fetch_paper_details(p["id"])
                if any(prog in NBER_PROGRAMS for prog in programs):
                    p.update(details)
                    p["matched_keywords"] = {"[program match]"}
                    program_matched.append(p)
                time.sleep(1)
        if program_matched:
            print(f"{len(program_matched)} additional papers matched by NBER program.")
            matched.extend(program_matched)

    if not matched:
        print("No relevant papers found this week.")
        return

    # 5. Sort by paper ID (newest first)
    matched.sort(key=lambda p: int(p.get("id", 0) or 0), reverse=True)

    # 6. Display results
    print(f"\n{'='*70}")
    print(f"  RELEVANT NBER WORKING PAPERS ({len(matched)} found)")
    print(f"{'='*70}\n")

    for p in matched:
        print(f"  w{p['id']}: {p['title']}")
        if p.get("matched_keywords"):
            print(f"         Keywords: {', '.join(sorted(p['matched_keywords']))}")
        print(f"         {p['link']}")
        print()

    # 7. Save log and summary
    save_log(matched, LOG_DIR)
    save_summary(matched, LOG_DIR)

    # 8. Download PDFs
    if args.download:
        print("\nDownloading PDFs...")
        for p in matched:
            if p["id"]:
                download_pdf(p["id"], OUTPUT_DIR)

    print("\nDone.")


if __name__ == "__main__":
    main()
