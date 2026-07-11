#!/usr/bin/env python3
"""Runs INSIDE GitHub Actions (US IP — Fandango is geo-walled from Europe).

Pulls the theaterswithshowtimes feed around zip 10003 for the next 8 days,
keeps New York State theaters, and writes data/chains-nyc.json in the
digest's normalized screening-row schema. The Mac-side adapter just reads
that file raw from the repo.
"""
import json
import re
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

NAPI = ("https://www.fandango.com/napi/theaterswithshowtimes"
        "?zipCode=10003&limit=50&date={d}&filter=open-theaters")
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36",
      "Referer": "https://www.fandango.com/"}
DAYS = 8


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def iso_start(ticketing_date):
    # "2026-07-11+19:30" -> "2026-07-11T19:30:00-04:00" (NY local)
    m = re.match(r"(\d{4}-\d{2}-\d{2})\+(\d{2}:\d{2})", ticketing_date or "")
    return f"{m.group(1)}T{m.group(2)}:00" if m else None


def main():
    rows, seen = [], set()
    for offset in range(DAYS):
        d = (date.today() + timedelta(days=offset)).isoformat()
        try:
            data = get(NAPI.format(d=d))
        except Exception as e:  # noqa: BLE001
            print(f"{d}: FAILED {e}", file=sys.stderr)
            continue
        for t in data.get("theaters", []):
            if ", NY" not in (t.get("cityStateZip") or ""):
                continue  # keep it to New York State
            geo = t.get("geo") or {}
            for m in t.get("movies", []):
                year = (m.get("releaseDate") or "")[:4]
                for variant in m.get("variants", []):
                    fmt = variant.get("filmFormatHeader") or ""
                    fmt = None if fmt.lower() in ("", "standard") else fmt
                    for grp in variant.get("amenityGroups", []):
                        for st in grp.get("showtimes", []):
                            if st.get("expired"):
                                continue
                            start = iso_start(st.get("ticketingDate"))
                            if not start:
                                continue
                            key = (t["name"], m["title"], start)
                            if key in seen:
                                continue
                            seen.add(key)
                            rows.append({
                                "city": "nyc",
                                "venue": t["name"].strip(),
                                "lat": geo.get("latitude"),
                                "lng": geo.get("longitude"),
                                "screen": None,
                                "title": m["title"],
                                "year": int(year) if year.isdigit() else None,
                                "start": start,
                                "format": fmt,
                                "price": None,
                                "price_kind": None,
                                "availability": "available"
                                                if st.get("type") == "available"
                                                else None,
                                "ticket_url": st.get("ticketingJumpPageURL"),
                                "source": "uschains",
                            })
        print(f"{d}: total rows {len(rows)}")
        time.sleep(2)
    out = Path(__file__).parent.parent / "data" / "chains-nyc.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(
        {"generated": date.today().isoformat(), "rows": rows},
        ensure_ascii=False))
    print(f"wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
