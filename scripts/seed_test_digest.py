#!/usr/bin/env python3
"""Pull real data from world_news.db, summarize with OpenRouter, and create test digests.
NOT for production — just to preview the site design."""

import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta

from openai import OpenAI

SOURCE_DB = "/home/kaichogami/projects/world-news/world_news.db"
DEST_DB = os.path.join(os.path.dirname(__file__), "..", "data", "digests.db")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
MODEL = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")

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

TARGET_DATES = ["2026-02-17", "2026-02-16", "2026-02-15"]

STYLE_RULES = """Writing rules (follow strictly):
- Write like a sharp newsroom editor, not an AI assistant.
- Use markdown: **bold** key facts, names, numbers. Use *italic* for quotes or emphasis.
- HARD LIMIT: 200-300 characters total. Be ruthlessly concise.
- Never use long dashes or em dashes. Use commas or periods.
- Never count releases or statements. Never say "issued" or "announced X statements".
- Never use: notably, delve, comprehensive, robust, furthermore, landscape, paradigm, pivotal, streamline, underscores, leveraging.
- No filler. Every word must earn its place.
- If content is in a foreign language, summarize in English."""


def llm(client, system, user):
    for attempt in range(3):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
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


def init_dest_db():
    os.makedirs(os.path.dirname(os.path.abspath(DEST_DB)), exist_ok=True)
    conn = sqlite3.connect(DEST_DB)
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


def filter_top_releases(client, releases, country_name):
    if len(releases) <= 5:
        return releases

    listing = "\n".join(
        f"- ID:{r['id']} | {r.get('ministry') or 'N/A'} | {r['title']}"
        for r in releases
    )
    result = llm(
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


def summarize_release(client, release):
    content = (release.get("content") or "")[:3000]
    title = release["title"]
    ministry = release.get("ministry") or "N/A"
    country = COUNTRY_NAMES.get(release.get("country", ""), "")

    return llm(
        client,
        f"You summarize government press releases. {STYLE_RULES}",
        f"Title: {title}\nMinistry: {ministry}\nCountry: {country}\n\nContent:\n{content}\n\n"
        f"Write a 200-300 character summary. **Bold** key facts. Be specific with numbers, names, dates.",
    )


def summarize_country(client, country_name, release_summaries):
    if len(release_summaries) == 1:
        rs = release_summaries[0]
        result = llm(
            client,
            f"You write news headlines. {STYLE_RULES}",
            f"Write a short punchy headline (under 10 words) for this from {country_name}:\n\n"
            f"{rs['title']}: {rs['summary']}\n\nReturn only the headline. No quotes.",
        )
        title = result.strip().lstrip("#").strip().rstrip(".")
        return title, rs["summary"]

    items = "\n\n".join(f"- {rs['title']}: {rs['summary']}" for rs in release_summaries)
    result = llm(
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
    result = llm(
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


def generate_daily(client, src, dest, target_date):
    print(f"\n{'='*50}")
    print(f"Processing {target_date}")
    print(f"{'='*50}")

    if dest.execute("SELECT 1 FROM daily_digest WHERE date = ?", (target_date,)).fetchone():
        print("  Already exists, skipping.")
        return

    rows = src.execute("""
        SELECT id, source_id, country, title, subtitle, content, url, ministry, published_at
        FROM releases WHERE DATE(published_at) = ? ORDER BY country, id
    """, (target_date,)).fetchall()

    if not rows:
        print("  No releases found, skipping.")
        return

    by_country = {}
    for r in rows:
        code = r["country"]
        if code not in by_country:
            by_country[code] = []
        by_country[code].append(dict(r))

    print(f"  {len(rows)} releases across {len(by_country)} countries")

    country_data = []
    for code in sorted(by_country.keys(), key=lambda c: COUNTRY_NAMES.get(c, c)):
        name = COUNTRY_NAMES.get(code, code)
        releases = by_country[code]
        print(f"\n  [{name}] {len(releases)} release{'s' if len(releases) != 1 else ''}")

        selected = filter_top_releases(client, releases, name)
        print(f"    Selected {len(selected)}")

        release_summaries = []
        for r in selected:
            print(f"    Summarizing: {r['title'][:60]}...")
            summary = summarize_release(client, r)
            release_summaries.append({
                "release_id": r["id"],
                "title": r["title"],
                "summary": summary,
                "original_url": r["url"],
                "ministry": r.get("ministry"),
            })

        print(f"    Generating country summary...")
        country_title, country_summary = summarize_country(client, name, release_summaries)
        print(f"    Title: {country_title}")

        country_data.append({
            "country_code": code,
            "country_name": name,
            "title": country_title,
            "summary": country_summary,
            "releases": release_summaries,
        })

    country_data.sort(key=lambda c: c["country_name"])

    print(f"\n  Generating global summary...")
    global_title, global_summary = generate_global_summary(client, country_data)
    print(f"  Global title: {global_title}")

    print(f"  Writing to database...")
    cursor = dest.cursor()
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

    dest.commit()
    total = sum(len(c["releases"]) for c in country_data)
    print(f"\n  Done: {len(country_data)} countries, {total} releases")


# --- Weekly digest ---

WEEKLY_STYLE = """Writing rules (follow strictly):
- Write like a sharp newsroom editor, not an AI assistant.
- Use markdown freely: **bold** key facts, *italic* for emphasis or quotes.
- Use bullet lists, tables, blockquotes, and horizontal rules where they help readability.
- HARD LIMIT: 500 characters max for each section.
- Never use long dashes or em dashes. Use commas or periods.
- Never count releases or statements.
- Never use: notably, delve, comprehensive, robust, furthermore, landscape, paradigm, pivotal, streamline, underscores, leveraging.
- If content is in a foreign language, summarize in English."""


def generate_weekly(client, dest):
    """Generate weekly digest from daily digests already in the DB.
    Week = Monday to Sunday. Only generate if a Sunday exists in daily digests."""

    daily_dates = [
        r[0] for r in dest.execute("SELECT date FROM daily_digest ORDER BY date").fetchall()
    ]
    if not daily_dates:
        return

    # Find Sundays that have daily digest data in their week
    sundays = set()
    for d_str in daily_dates:
        d = datetime.strptime(d_str, "%Y-%m-%d")
        # Sunday of that week (weekday: Mon=0 .. Sun=6)
        days_until_sunday = 6 - d.weekday()
        sunday = d + timedelta(days=days_until_sunday)
        sundays.add(sunday.strftime("%Y-%m-%d"))

    for sunday_str in sorted(sundays):
        if dest.execute("SELECT 1 FROM weekly_digest WHERE week_end = ?", (sunday_str,)).fetchone():
            continue

        sunday = datetime.strptime(sunday_str, "%Y-%m-%d")
        monday = sunday - timedelta(days=6)
        monday_str = monday.strftime("%Y-%m-%d")

        # Get all daily digests in that week
        rows = dest.execute("""
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

        # Collect per-day summaries and per-country across the week
        day_summaries = {}
        country_week = {}
        for r in rows:
            date = r[0]
            if date not in day_summaries:
                day_summaries[date] = r[1]  # global_title

            code = r[3]
            name = r[4]
            if code not in country_week:
                country_week[code] = {"name": name, "items": []}
            country_week[code]["items"].append(f"{r[0]}: {r[5]} - {r[6]}")

        # Build a text blob of the week for the LLM
        week_text = ""
        for date in sorted(day_summaries.keys()):
            week_text += f"**{date}**: {day_summaries[date]}\n"

        # Generate weekly global summary
        print("  Generating weekly global summary...")
        result = llm(
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

        # Generate per-country weekly summaries
        weekly_countries = []
        for code in sorted(country_week.keys(), key=lambda c: country_week[c]["name"]):
            info = country_week[code]
            name = info["name"]
            items_text = "\n".join(f"- {i}" for i in info["items"])
            print(f"  [{name}] weekly summary...")

            result = llm(
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

        # Write to DB
        print("  Writing weekly digest...")
        cursor = dest.cursor()
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
        dest.commit()
        print(f"  Done: {len(weekly_countries)} countries")


def main():
    if not OPENROUTER_API_KEY:
        print("Error: Set OPENROUTER_API_KEY environment variable")
        sys.exit(1)

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)

    src = sqlite3.connect(SOURCE_DB)
    src.row_factory = sqlite3.Row
    dest = init_dest_db()

    # Generate daily digests
    for target_date in TARGET_DATES:
        generate_daily(client, src, dest, target_date)

    # Generate weekly digests from existing dailies
    generate_weekly(client, dest)

    src.close()
    dest.close()
    print("\nAll done!")


if __name__ == "__main__":
    main()
