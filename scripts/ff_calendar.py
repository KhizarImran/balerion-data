"""
ForexFactory Economic Calendar - Data Collection Script
=======================================================
Fetches high-impact economic events from the ForexFactory XML feed and saves
them to data/calendar/ as weekly Parquet files.

How the data lifecycle works
-----------------------------
ForexFactory's XML feed provides:
  - title      : Event name
  - country    : Currency code (USD, EUR, GBP, ...)
  - date       : Event date  (MM-DD-YYYY)
  - time       : Event time  (hh:mmam/pm, Eastern Time)
  - impact     : Low / Medium / High
  - forecast   : Analyst consensus estimate (may be empty)
  - previous   : Prior period's actual result (may be empty)

There is NO 'actual' field in the XML. Actuals are only shown on the FF
website after the event has released. The workaround used here:

  1. Run on Monday (or Sunday night): fetch thisweek.xml -> saves the
     SCHEDULE for the coming week (forecast + previous).

  2. Run again on Friday/Saturday (end-of-week refresh): re-fetch
     thisweek.xml and UPSERT into the same weekly file. By this point
     FF may have updated the 'previous' field on some events.

  3. The following week, the prior week's file is left intact as the
     archive. The 'previous' column in the NEW week's data will contain
     the actual values from the prior week's releases.

  4. Over time you build a table where each row has:
       week_start | event | currency | forecast | previous (=last actual)
     and you can reconstruct actuals by looking at next-week's 'previous'.

Storage layout
--------------
  data/calendar/
    weekly/
      2026-W09_high_impact.parquet   <- week of Mar 2, 2026
      2026-W10_high_impact.parquet
      ...
    calendar_all.parquet             <- merged master file (all weeks)

Usage
-----
  # Fetch & save this week's high-impact events
  python scripts/ff_calendar.py

  # Force re-fetch even if file already exists (end-of-week refresh)
  python scripts/ff_calendar.py --refresh

  # Also rebuild the merged master file
  python scripts/ff_calendar.py --refresh --rebuild-master
"""

import argparse
import time
import xml.etree.ElementTree as ET

import requests
from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

FF_THISWEEK_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
FF_NEXTWEEK_URL = "https://nfs.faireconomy.media/ff_calendar_nextweek.xml"

# Only save events for these currencies (matches our traded symbols)
WATCHED_CURRENCIES = {"USD", "EUR", "GBP", "JPY", "CAD", "AUD", "NZD", "CHF"}

# Only save High impact by default (Medium included if you want context)
SAVE_IMPACTS = {"High"}

BASE_DIR = Path(__file__).parent.parent
CALENDAR_DIR = BASE_DIR / "data" / "calendar"
WEEKLY_DIR = CALENDAR_DIR / "weekly"
MASTER_FILE = CALENDAR_DIR / "calendar_all.parquet"

# Request headers - polite user-agent
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )
}

MAX_RETRIES = 2
RETRY_DELAY_S = 5  # seconds between retries on 429


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def week_label(ref_date: date) -> str:
    """Return an ISO week label like '2026-W09' for a given date."""
    iso = ref_date.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def week_start(ref_date: date) -> date:
    """Monday of the ISO week containing ref_date."""
    return ref_date - timedelta(days=ref_date.weekday())


def weekly_filepath(ref_date: date) -> Path:
    label = week_label(ref_date)
    return WEEKLY_DIR / f"{label}_high_impact.parquet"


def fetch_xml(url: str) -> str | None:
    """Fetch XML from URL with retry logic for 429 rate limiting."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=(5, 12))
            if resp.status_code == 200:
                return resp.content.decode("windows-1252")
            if resp.status_code == 404:
                print(f"  [INFO] 404 - feed not available: {url}")
                return None
            if resp.status_code == 429:
                print(
                    f"  [WARN] Rate limited (429). Waiting {RETRY_DELAY_S}s "
                    f"before retry {attempt}/{MAX_RETRIES}..."
                )
                time.sleep(RETRY_DELAY_S)
                continue
            print(f"  [ERROR] HTTP {resp.status_code} fetching {url}")
            return None
        except requests.exceptions.Timeout:
            print(f"  [WARN] Request timed out (attempt {attempt}/{MAX_RETRIES})")
            time.sleep(RETRY_DELAY_S)
            continue
        except Exception as e:
            print(f"  [ERROR] Fetching {url}: {e}")
            return None
    print(f"  [ERROR] All {MAX_RETRIES} retries exhausted for {url}")
    return None


def parse_events(xml_content: str, week_ref: date) -> pd.DataFrame:
    """
    Parse XML into a DataFrame of high-impact events for watched currencies.

    Parameters
    ----------
    xml_content : raw XML string
    week_ref    : the Monday date of this week (used as week_start column)

    Returns
    -------
    DataFrame with columns:
        week_start, event_date, event_time_et, currency, impact,
        title, forecast, previous, url, fetched_at
    """
    root = ET.fromstring(xml_content)
    rows = []

    for e in root.findall("event"):
        impact = e.findtext("impact", "").strip()
        currency = e.findtext("country", "").strip()

        # Filter
        if impact not in SAVE_IMPACTS:
            continue
        if currency not in WATCHED_CURRENCIES:
            continue

        # Parse date (MM-DD-YYYY)
        raw_date = e.findtext("date", "").strip()
        try:
            event_date = datetime.strptime(raw_date, "%m-%d-%Y").date()
        except ValueError:
            event_date = None

        rows.append(
            {
                "week_start": week_ref.isoformat(),
                "event_date": event_date.isoformat() if event_date else raw_date,
                "event_time_et": e.findtext("time", "").strip(),  # Eastern Time
                "currency": currency,
                "impact": impact,
                "title": e.findtext("title", "").strip(),
                "forecast": e.findtext("forecast", "").strip() or None,
                "previous": e.findtext("previous", "").strip() or None,
                "url": e.findtext("url", "").strip(),
                "fetched_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            }
        )

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values(["event_date", "event_time_et"]).reset_index(drop=True)
    return df


def save_weekly(df: pd.DataFrame, filepath: Path, refresh: bool = False) -> bool:
    """
    Save or upsert weekly parquet file.

    If file exists and refresh=True: merge new fetch over existing rows
    (new fetch wins on duplicate title+event_date, preserving any manual edits).
    If file exists and refresh=False: skip.
    """
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if filepath.exists() and not refresh:
        print(f"  [SKIP] File already exists: {filepath.name}  (use --refresh to overwrite)")
        return False

    if filepath.exists() and refresh:
        existing = pd.read_parquet(filepath)
        # Upsert: new data wins on (event_date + title)
        combined = pd.concat([existing, df], ignore_index=True)
        combined = (
            combined.drop_duplicates(subset=["event_date", "title"], keep="last")
            .sort_values(["event_date", "event_time_et"])
            .reset_index(drop=True)
        )
        combined.to_parquet(filepath, index=False, compression="snappy")
        print(
            f"  [OK] Refreshed (upserted {len(df)} rows -> {len(combined)} total): {filepath.name}"
        )
    else:
        df.to_parquet(filepath, index=False, compression="snappy")
        print(f"  [OK] Saved {len(df)} high-impact events: {filepath.name}")

    return True


def rebuild_master():
    """Merge all weekly parquet files into a single master file."""
    files = sorted(WEEKLY_DIR.glob("*_high_impact.parquet"))
    if not files:
        print("  [WARN] No weekly files found to merge.")
        return

    frames = [pd.read_parquet(f) for f in files]
    master = pd.concat(frames, ignore_index=True)
    master = (
        master.drop_duplicates(subset=["event_date", "title"], keep="last")
        .sort_values(["event_date", "event_time_et"])
        .reset_index(drop=True)
    )

    MASTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    master.to_parquet(MASTER_FILE, index=False, compression="snappy")
    print(f"  [OK] Master file rebuilt: {len(master)} total events -> {MASTER_FILE.name}")


def print_events(df: pd.DataFrame, label: str):
    """Pretty-print events to console."""
    if df.empty:
        print(f"  No high-impact events found for {label}.")
        return

    print(f"\n  {label} - {len(df)} High Impact Events")
    print(f"  {'Date':<12} {'Time (ET)':<12} {'CCY':<5} {'Forecast':<12} {'Previous':<12} Title")
    print(f"  {'-' * 12} {'-' * 12} {'-' * 5} {'-' * 12} {'-' * 12} {'-' * 40}")
    for _, row in df.iterrows():
        fc = row["forecast"] or ""
        pv = row["previous"] or ""
        print(
            f"  {row['event_date']:<12} {row['event_time_et']:<12} {row['currency']:<5} {fc:<12} {pv:<12} {row['title']}"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Fetch ForexFactory high-impact calendar data.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch and upsert even if weekly file already exists (use end-of-week)",
    )
    parser.add_argument(
        "--rebuild-master",
        action="store_true",
        help="Rebuild the merged master calendar_all.parquet from all weekly files",
    )
    args = parser.parse_args()

    today = date.today()
    this_mon = week_start(today)
    next_mon = this_mon + timedelta(weeks=1)

    print("=" * 60)
    print("ForexFactory Calendar Fetcher")
    print(f"Run date : {today}  (Week of {this_mon})")
    print("=" * 60)

    # --- This week ---
    print(f"\n[1/2] Fetching THIS week ({week_label(this_mon)})...")
    xml = fetch_xml(FF_THISWEEK_URL)
    if xml:
        df_this = parse_events(xml, this_mon)
        print_events(df_this, f"This week ({week_label(this_mon)})")
        save_weekly(df_this, weekly_filepath(this_mon), refresh=args.refresh)
    else:
        print("  [ERROR] Could not fetch this week's calendar.")

    # Small polite delay between requests
    time.sleep(3)

    # --- Next week ---
    print(f"\n[2/2] Fetching NEXT week ({week_label(next_mon)})...")
    xml_next = fetch_xml(FF_NEXTWEEK_URL)
    if xml_next:
        df_next = parse_events(xml_next, next_mon)
        print_events(df_next, f"Next week ({week_label(next_mon)})")
        save_weekly(df_next, weekly_filepath(next_mon), refresh=args.refresh)
    else:
        print("  [INFO] Next week feed not yet available (normal early in the week).")

    # --- Rebuild master ---
    if args.rebuild_master:
        print("\n[*] Rebuilding master calendar file...")
        rebuild_master()

    print("\n[DONE]")
    print(f"Files saved to: {CALENDAR_DIR}")


if __name__ == "__main__":
    main()
