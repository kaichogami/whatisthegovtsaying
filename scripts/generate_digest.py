#!/usr/bin/env python3
"""Generate daily (and weekly) digests of government press releases using LLM summarization.

Data source: world-news API (govtintelbot.com)
Output: SQLite DB consumed by the Astro static site builder.

Usage:
    python scripts/generate_digest.py                  # yesterday only
    python scripts/generate_digest.py --backfill 21    # last 21 days
    BACKFILL_DAYS=21 python scripts/generate_digest.py # same via env
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from openai import OpenAI

# --- Configuration ---
API_URL = os.environ.get("WORLD_NEWS_API_URL", "http://127.0.0.1:8000")
API_KEY = os.environ.get("WORLD_NEWS_API_KEY", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")
DB_PATH = os.environ.get("DIGEST_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "digests.db"))
BACKFILL_DAYS = int(os.environ.get("BACKFILL_DAYS", "90"))
PRUNE_DAYS = 90

COUNTRY_NAMES = {
    "AE": "UAE", "AR": "Argentina", "AU": "Australia", "BR": "Brazil",
    "CA": "Canada", "CH": "Switzerland", "CN": "China", "DE": "Germany",
    "ES": "Spain", "EU": "European Union", "FR": "France", "GB": "United Kingdom",
    "ID": "Indonesia", "IE": "Ireland", "IN": "India", "IT": "Italy",
    "JP": "Japan", "KR": "South Korea", "NG": "Nigeria", "NL": "Netherlands",
    "NZ": "New Zealand", "QA": "Qatar", "RU": "Russia", "SG": "Singapore",
    "TH": "Thailand", "TW": "Taiwan", "UN": "United Nations", "US": "United States",
    "VN": "Vietnam", "WHO": "WHO", "ZA": "South Africa",
}

COUNTRIES = sorted(COUNTRY_NAMES.keys())

STYLE_RULES = """Writing rules (follow strictly):
- Write like a sharp newsroom editor, not an AI assistant.
- Use markdown: **bold** key facts, names, numbers. Use *italic* for quotes or emphasis.
- HARD LIMIT: 200-300 characters total. Be ruthlessly concise.
- Never use long dashes or em dashes. Use commas or periods.
- Never count releases or statements. Never say "issued" or "announced X statements".
- Never use: notably, delve, comprehensive, robust, furthermore, landscape, paradigm, pivotal, streamline, underscores, leveraging.
- No filler. Every word must earn its place.
- If content is in a foreign language, summarize in English."""

WEEKLY_STYLE = """Writing rules (follow strictly):
- Write like a sharp newsroom editor, not an AI assistant.
- Use markdown freely: **bold** key facts, *italic* for emphasis or quotes.
- Use bullet lists, tables, blockquotes, and horizontal rules where they help readability.
- HARD LIMIT: 500 characters max for each section.
- Never use long dashes or em dashes. Use commas or periods.
- Never count releases or statements.
- Never use: notably, delve, comprehensive, robust, furthermore, landscape, paradigm, pivotal, streamline, underscores, leveraging.
- If content is in a foreign language, summarize in English."""


# --- Database ---

def init_db(db_path):
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS daily_digest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,
            global_title TEXT NOT NULL DEFAULT '',
            global_summary TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS country_digest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            daily_digest_id INTEGER NOT NULL REFERENCES daily_digest(id),
            country_code TEXT NOT NULL,
            country_name TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS release_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country_digest_id INTEGER NOT NULL REFERENCES country_digest(id),
            release_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            summary TEXT NOT NULL,
            original_url TEXT NOT NULL,
            ministry TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS weekly_digest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start TEXT NOT NULL,
            week_end TEXT UNIQUE NOT NULL,
            global_title TEXT NOT NULL DEFAULT '',
            global_summary TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS weekly_country_digest (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            weekly_digest_id INTEGER NOT NULL REFERENCES weekly_digest(id),
            country_code TEXT NOT NULL,
            country_name TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    return conn


def digest_exists(conn, date):
    return conn.execute("SELECT 1 FROM daily_digest WHERE date = ?", (date,)).fetchone() is not None


def prune_old_digests(conn, keep_days):
    """Delete digests older than keep_days from today."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=keep_days)).strftime("%Y-%m-%d")
    print(f"\nPruning digests older than {cutoff}...")

    old_dailies = conn.execute("SELECT id FROM daily_digest WHERE date < ?", (cutoff,)).fetchall()
    if not old_dailies:
        print("  Nothing to prune.")
        return

    daily_ids = [r[0] for r in old_dailies]
    placeholders = ",".join("?" * len(daily_ids))

    # Delete release_summary rows via country_digest
    country_ids = [
        r[0] for r in conn.execute(
            f"SELECT id FROM country_digest WHERE daily_digest_id IN ({placeholders})", daily_ids
        ).fetchall()
    ]
    if country_ids:
        cp = ",".join("?" * len(country_ids))
        conn.execute(f"DELETE FROM release_summary WHERE country_digest_id IN ({cp})", country_ids)

    conn.execute(f"DELETE FROM country_digest WHERE daily_digest_id IN ({placeholders})", daily_ids)
    conn.execute(f"DELETE FROM daily_digest WHERE id IN ({placeholders})", daily_ids)

    # Prune old weekly digests too
    old_weeklies = conn.execute("SELECT id FROM weekly_digest WHERE week_end < ?", (cutoff,)).fetchall()
    if old_weeklies:
        weekly_ids = [r[0] for r in old_weeklies]
        wp = ",".join("?" * len(weekly_ids))
        conn.execute(f"DELETE FROM weekly_country_digest WHERE weekly_digest_id IN ({wp})", weekly_ids)
        conn.execute(f"DELETE FROM weekly_digest WHERE id IN ({wp})", weekly_ids)

    conn.commit()
    print(f"  Pruned {len(daily_ids)} daily + {len(old_weeklies)} weekly digests.")


# --- API ---

def fetch_releases_for_country(country, date):
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    params = {"country": country, "date_from": date, "date_to": date, "per_page": "100", "fields": "brief"}
    try:
        resp = requests.get(f"{API_URL}/v1/releases", params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
    except requests.RequestException as e:
        print(f"  Warning: Failed to fetch releases for {country}: {e}")
        return []


def fetch_releases_batch(release_ids):
    """Fetch multiple releases by ID in one request (max 50)."""
    if not release_ids:
        return {}
    headers = {}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
    headers["Content-Type"] = "application/json"
    result = {}
    # Chunk into batches of 50
    for i in range(0, len(release_ids), 50):
        chunk = release_ids[i:i + 50]
        try:
            resp = requests.post(
                f"{API_URL}/v1/releases/batch",
                json={"ids": chunk},
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()
            for r in resp.json():
                result[r["id"]] = r
        except requests.RequestException as e:
            print(f"  Warning: Batch fetch failed for {len(chunk)} IDs: {e}")
    return result


# --- LLM ---

def create_llm_client():
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)


def llm_chat(client, system_prompt, user_prompt):
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=OPENROUTER_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            if attempt < 2:
                print(f"    LLM retry ({e})")
                time.sleep(2 ** attempt)
            else:
                raise


def filter_releases(client, releases, country_name):
    if len(releases) <= 5:
        return releases

    listing = "\n".join(
        f"- ID:{r['id']} | {r.get('ministry') or 'N/A'} | {r['title']}"
        for r in releases
    )
    result = llm_chat(
        client,
        "You pick the most globally important government press releases. Return only a JSON array of IDs.",
        f"From these {len(releases)} releases from {country_name}, pick the 5 most important "
        f"(policy changes, foreign relations, defence, economic reform, major law).\n\n{listing}\n\n"
        f"Return ONLY a JSON array of 5 IDs, e.g. [123, 456, 789, 101, 102]",
    )
    try:
        if "```" in result:
            result = result.split("```")[1]
            if result.startswith("json"):
                result = result[4:]
            result = result.strip()
        ids = set(json.loads(result))
        filtered = [r for r in releases if r["id"] in ids]
        if filtered:
            return filtered[:5]
    except Exception as e:
        print(f"    Filter failed for {country_name}: {e}")
    return releases[:5]


def summarize_release(client, release_detail):
    content = (release_detail.get("content") or "")[:3000]
    title = release_detail["title"]
    ministry = release_detail.get("ministry") or "N/A"
    country = COUNTRY_NAMES.get(release_detail.get("country", ""), "")

    return llm_chat(
        client,
        f"You summarize government press releases. {STYLE_RULES}",
        f"Title: {title}\nMinistry: {ministry}\nCountry: {country}\n\nContent:\n{content}\n\n"
        f"Write a 200-300 character summary. **Bold** key facts. Be specific with numbers, names, dates.",
    )


def summarize_country(client, country_name, release_summaries):
    if len(release_summaries) == 1:
        rs = release_summaries[0]
        result = llm_chat(
            client,
            f"You write news headlines. {STYLE_RULES}",
            f"Write a short punchy headline (under 10 words) for this from {country_name}:\n\n"
            f"{rs['title']}: {rs['summary']}\n\nReturn only the headline. No quotes.",
        )
        title = result.strip().lstrip("#").strip().rstrip(".")
        return title, rs["summary"]

    items = "\n\n".join(f"- {rs['title']}: {rs['summary']}" for rs in release_summaries)
    result = llm_chat(
        client,
        f"You write country-level news digests. {STYLE_RULES}",
        f"Today's announcements from {country_name}:\n\n{items}\n\n"
        f"First line: Punchy headline under 10 words. No quotes.\n"
        f"Second line onwards: 200-300 characters max. **Bold** key facts. "
        f"Weave stories together. What happened and why it matters.",
    )
    lines = result.strip().split("\n", 1)
    title = lines[0].strip().lstrip("#").strip().rstrip(".")
    summary = lines[1].strip() if len(lines) > 1 else title
    return title, summary


def generate_global_summary(client, country_data):
    items = "\n\n".join(
        f"**{cd['country_name']}** ({cd['title']}): {cd['summary']}"
        for cd in country_data
    )
    result = llm_chat(
        client,
        f"You write a daily global government briefing. {STYLE_RULES}",
        f"Today's country summaries:\n\n{items}\n\n"
        f"First line: Compelling headline under 15 words. No quotes.\n"
        f"Second line onwards: 200-300 characters. **Bold** the biggest story. "
        f"Find threads connecting countries. Hook the reader.",
    )
    lines = result.strip().split("\n", 1)
    title = lines[0].strip().lstrip("#").strip().rstrip(".")
    summary = lines[1].strip() if len(lines) > 1 else ""
    return title, summary


# --- Daily digest ---

def generate_daily(client, conn, target_date):
    print(f"\n{'='*50}")
    print(f"Processing {target_date}")
    print(f"{'='*50}")

    if digest_exists(conn, target_date):
        print(f"  Already exists, skipping.")
        return

    # Fetch releases per country
    all_country_releases = {}
    for country in COUNTRIES:
        releases = fetch_releases_for_country(country, target_date)
        if releases:
            all_country_releases[country] = releases
            print(f"  {COUNTRY_NAMES[country]}: {len(releases)} releases")

    if not all_country_releases:
        print("  No releases found for any country. Skipping.")
        return

    # Filter releases (top 5 for busy countries)
    print("\n  Filtering releases...")
    filtered_releases = {}
    for country, releases in all_country_releases.items():
        filtered = filter_releases(client, releases, COUNTRY_NAMES[country])
        filtered_releases[country] = filtered
        if len(releases) > 5:
            print(f"    {COUNTRY_NAMES[country]}: {len(releases)} -> {len(filtered)}")

    # Batch-fetch full content for all filtered releases
    all_ids = []
    for releases in filtered_releases.values():
        all_ids.extend(r["id"] for r in releases)
    print(f"\n  Batch-fetching {len(all_ids)} releases...")
    details_map = fetch_releases_batch(all_ids)
    print(f"  Got {len(details_map)} release details")

    # Summarize per country
    country_data = []
    for country, releases in filtered_releases.items():
        name = COUNTRY_NAMES[country]
        print(f"\n  [{name}] {len(releases)} release{'s' if len(releases) != 1 else ''}")

        release_summaries = []
        for r in releases:
            detail = details_map.get(r["id"])
            if not detail:
                continue
            print(f"    Summarizing: {detail['title'][:60]}...")
            summary = summarize_release(client, detail)
            release_summaries.append({
                "release_id": detail["id"],
                "title": detail["title"],
                "summary": summary,
                "original_url": detail.get("url", ""),
                "ministry": detail.get("ministry"),
            })

        if not release_summaries:
            continue

        print(f"    Generating country summary...")
        country_title, country_summary = summarize_country(client, name, release_summaries)
        print(f"    Title: {country_title}")

        country_data.append({
            "country_code": country,
            "country_name": name,
            "title": country_title,
            "summary": country_summary,
            "releases": release_summaries,
        })

    if not country_data:
        print("  No summarizable releases. Skipping.")
        return

    country_data.sort(key=lambda c: c["country_name"])

    # Global summary
    print(f"\n  Generating global summary...")
    global_title, global_summary = generate_global_summary(client, country_data)
    print(f"  Global title: {global_title}")

    # Write to DB
    print(f"  Writing to database...")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO daily_digest (date, global_title, global_summary) VALUES (?, ?, ?)",
        (target_date, global_title, global_summary),
    )
    daily_id = cursor.lastrowid

    for cd in country_data:
        cursor.execute(
            "INSERT INTO country_digest (daily_digest_id, country_code, country_name, title, summary) VALUES (?, ?, ?, ?, ?)",
            (daily_id, cd["country_code"], cd["country_name"], cd["title"], cd["summary"]),
        )
        cd_id = cursor.lastrowid
        for rs in cd["releases"]:
            cursor.execute(
                "INSERT INTO release_summary (country_digest_id, release_id, title, summary, original_url, ministry) VALUES (?, ?, ?, ?, ?, ?)",
                (cd_id, rs["release_id"], rs["title"], rs["summary"], rs["original_url"], rs["ministry"]),
            )

    conn.commit()
    total = sum(len(c["releases"]) for c in country_data)
    print(f"\n  Done: {len(country_data)} countries, {total} releases")


# --- Weekly digest ---

def generate_weekly(client, conn):
    """Generate weekly digests from daily digests already in the DB.
    Week = Monday to Sunday. Only generate if a Sunday exists in daily digests."""

    daily_dates = [
        r[0] for r in conn.execute("SELECT date FROM daily_digest ORDER BY date").fetchall()
    ]
    if not daily_dates:
        return

    sundays = set()
    for d_str in daily_dates:
        d = datetime.strptime(d_str, "%Y-%m-%d")
        days_until_sunday = 6 - d.weekday()
        sunday = d + timedelta(days=days_until_sunday)
        sundays.add(sunday.strftime("%Y-%m-%d"))

    for sunday_str in sorted(sundays):
        if conn.execute("SELECT 1 FROM weekly_digest WHERE week_end = ?", (sunday_str,)).fetchone():
            continue

        sunday = datetime.strptime(sunday_str, "%Y-%m-%d")
        monday = sunday - timedelta(days=6)
        monday_str = monday.strftime("%Y-%m-%d")

        rows = conn.execute("""
            SELECT d.date, d.global_title, d.global_summary,
                   c.country_code, c.country_name, c.title as country_title, c.summary as country_summary
            FROM daily_digest d
            JOIN country_digest c ON c.daily_digest_id = d.id
            WHERE d.date >= ? AND d.date <= ?
            ORDER BY d.date, c.country_name
        """, (monday_str, sunday_str)).fetchall()

        if not rows:
            continue

        print(f"\n{'='*50}")
        print(f"Weekly: {monday_str} to {sunday_str}")
        print(f"{'='*50}")

        day_summaries = {}
        country_week = {}
        for r in rows:
            date = r[0]
            if date not in day_summaries:
                day_summaries[date] = r[1]

            code = r[3]
            name = r[4]
            if code not in country_week:
                country_week[code] = {"name": name, "items": []}
            country_week[code]["items"].append(f"{r[0]}: {r[5]} - {r[6]}")

        week_text = ""
        for date in sorted(day_summaries.keys()):
            week_text += f"**{date}**: {day_summaries[date]}\n"

        print("  Generating weekly global summary...")
        result = llm_chat(
            client,
            f"You write a weekly government briefing. {WEEKLY_STYLE}",
            f"Here are this week's daily headlines:\n\n{week_text}\n\n"
            f"And here are the country details:\n\n" +
            "\n\n".join(
                f"**{v['name']}**:\n" + "\n".join(f"- {i}" for i in v["items"])
                for v in sorted(country_week.values(), key=lambda x: x["name"])
            ) +
            f"\n\nFirst line: A compelling weekly headline under 15 words. No quotes.\n"
            f"Rest: Write a 400-500 character weekly overview. Use **bold**, *italic*, and bullet points. "
            f"What were the biggest stories? What trends emerged? Make it a must-read recap.",
        )
        lines = result.strip().split("\n", 1)
        weekly_title = lines[0].strip().lstrip("#").strip().rstrip(".")
        weekly_summary = lines[1].strip() if len(lines) > 1 else ""
        print(f"  Title: {weekly_title}")

        weekly_countries = []
        for code in sorted(country_week.keys(), key=lambda c: country_week[c]["name"]):
            info = country_week[code]
            name = info["name"]
            items_text = "\n".join(f"- {i}" for i in info["items"])
            print(f"  [{name}] weekly summary...")

            result = llm_chat(
                client,
                f"You write weekly country news recaps. {WEEKLY_STYLE}",
                f"This week from {name}:\n\n{items_text}\n\n"
                f"First line: Punchy headline under 10 words. No quotes.\n"
                f"Rest: 400-500 character weekly recap. Use **bold**, *italic*, bullet lists, or a table if it helps. "
                f"What were the key stories? What changed?",
            )
            clines = result.strip().split("\n", 1)
            ctitle = clines[0].strip().lstrip("#").strip().rstrip(".")
            csummary = clines[1].strip() if len(clines) > 1 else ""

            weekly_countries.append({
                "country_code": code,
                "country_name": name,
                "title": ctitle,
                "summary": csummary,
            })

        print("  Writing weekly digest...")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO weekly_digest (week_start, week_end, global_title, global_summary) VALUES (?, ?, ?, ?)",
            (monday_str, sunday_str, weekly_title, weekly_summary),
        )
        wid = cursor.lastrowid
        for wc in weekly_countries:
            cursor.execute(
                "INSERT INTO weekly_country_digest (weekly_digest_id, country_code, country_name, title, summary) VALUES (?, ?, ?, ?, ?)",
                (wid, wc["country_code"], wc["country_name"], wc["title"], wc["summary"]),
            )
        conn.commit()
        print(f"  Done: {len(weekly_countries)} countries")


# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="Generate daily government press release digests")
    parser.add_argument("--backfill", type=int, default=None,
                        help="Number of days to backfill (overrides BACKFILL_DAYS env)")
    args = parser.parse_args()

    days = args.backfill if args.backfill is not None else BACKFILL_DAYS

    if not OPENROUTER_API_KEY:
        print("Error: OPENROUTER_API_KEY environment variable is required.")
        sys.exit(1)

    client = create_llm_client()
    conn = init_db(DB_PATH)

    # Generate daily digests for each day in the backfill window
    for i in range(days, 0, -1):
        target_date = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        generate_daily(client, conn, target_date)

    # Generate weekly digests from existing dailies
    print("\nChecking for weekly digests to generate...")
    generate_weekly(client, conn)

    # Prune old data
    prune_old_digests(conn, PRUNE_DAYS)

    conn.close()
    print("\nAll done!")


if __name__ == "__main__":
    main()
