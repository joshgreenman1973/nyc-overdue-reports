#!/usr/bin/env python3
# Title: Overdue — the reports New York City owes itself (build script)
# Author: Josh Greenman with Claude Code
# Date: 2026-07-10
# Data sources:
#   1. "Government Publication - Required Reports" (DORIS via NYC Open Data),
#      dataset 9azj-tmjp — the list of reports city agencies are legally
#      required to publish, mandated by City Charter section 1133(b).
#      https://data.cityofnewyork.us/resource/9azj-tmjp.json
#   2. "Government Publications Listing" (DORIS via NYC Open Data),
#      dataset xip9-pe9k — metadata for every document filed with DORIS
#      under Charter section 1133 (the Government Publications Portal).
#      https://data.cityofnewyork.us/resource/xip9-pe9k.json
# Description: joins the requirements list to actual filings on
#   (normalized agency, normalized report name), computes an overdue status
#   for every requirement, and writes data.json for the static site.
# Dependencies: Python 3 standard library only (urllib, json, csv, re).

import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
TODAY = date.today()

REQ_URL = "https://data.cityofnewyork.us/resource/9azj-tmjp.json"
PUB_URL = "https://data.cityofnewyork.us/resource/xip9-pe9k.json"
PAGE = 50000  # Socrata max rows per page


def fetch_all(base_url, select=None):
    """Page through a Socrata dataset and return every row."""
    rows = []
    offset = 0
    while True:
        params = {"$limit": PAGE, "$offset": offset, "$order": ":id"}
        if select:
            params["$select"] = select
        url = base_url + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": "overdue-tracker/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            page = json.load(resp)
        rows.extend(page)
        print(f"  fetched {len(rows)} rows from {base_url.split('/')[-1]}")
        if len(page) < PAGE:
            return rows
        offset += PAGE


def norm(s):
    """Join key hygiene: trim, collapse all internal whitespace (incl. newlines)."""
    return re.sub(r"\s+", " ", (s or "").strip())


def parse_date(s):
    """Socrata floating timestamp -> date, or None."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.split("T")[0]).date()
    except ValueError:
        return None


def clamp(d):
    """Future-dated rows exist in both datasets (fat-fingered entry); clamp to today."""
    if d and d > TODAY:
        return None  # a "last published" date in the future is unusable
    return d


FREQ_RE = re.compile(r"Every (\d+) (Day|Week|Month|Year)s?", re.I)
UNIT_DAYS = {"day": 1, "week": 7, "month": 30.44, "year": 365.25}


def freq_days(freq):
    """'Every 3 Months' -> 91 (approx). None for blank/'Once'/unparseable."""
    m = FREQ_RE.match(norm(freq))
    if not m:
        return None
    return int(round(int(m.group(1)) * UNIT_DAYS[m.group(2).lower()]))


# Era annotations look like "(Required report from Jan 2020 - July 2020)" —
# a closed date range means the row describes a superseded version of the
# requirement, not the current one.
ERA_CLOSED_RE = re.compile(r"\(required report from .+? (?:-|to|through) .+?\)", re.I)


def main():
    print("Fetching requirements list (9azj-tmjp)...")
    reqs = fetch_all(REQ_URL)
    print("Fetching publications listing (xip9-pe9k)...")
    pubs = fetch_all(
        PUB_URL,
        select="agency,required_report_name,date_published,report_type,title",
    )

    # ---- Index filings by (agency, required_report_name) ----
    filings = {}          # key -> {count, last, last_title}
    late_notices = {}     # key -> latest Delinquent Report Notice date
    for p in pubs:
        rname = norm(p.get("required_report_name"))
        if not rname or rname == "Other Publication":
            continue
        key = (norm(p.get("agency")), rname)
        d = clamp(parse_date(p.get("date_published")))
        if norm(p.get("report_type")) == "Delinquent Report Notice":
            # DORIS's own overdue signal (Charter sec. 1133(d)) — track separately,
            # never count a late notice as a filing of the report itself.
            if d and (key not in late_notices or d > late_notices[key]):
                late_notices[key] = d
            continue
        f = filings.setdefault(key, {"count": 0, "last": None, "last_title": None})
        f["count"] += 1
        if d and (f["last"] is None or d > f["last"]):
            f["last"] = d
            f["last_title"] = norm(p.get("title"))

    # ---- Group requirement rows by (agency, name); same report can appear as
    # multiple rows when the requirement changed over time ("era" rows). ----
    groups = {}
    for r in reqs:
        key = (norm(r.get("agency")), norm(r.get("name")))
        groups.setdefault(key, []).append(r)

    out = []
    for (agency, name), rows in sorted(groups.items()):
        # Pick the row describing the CURRENT requirement: prefer rows whose
        # description is not a closed era range; among those, latest last_published_date.
        def is_era(r):
            return bool(ERA_CLOSED_RE.search(r.get("description") or ""))

        current = [r for r in rows if not is_era(r)] or rows
        current.sort(key=lambda r: parse_date(r.get("last_published_date")) or date.min, reverse=True)
        r = current[0]

        desc = r.get("description") or ""
        completed = "(completed" in desc.lower()
        waived = bool(re.search(r"waiv", desc, re.I))
        freq = norm(r.get("frequency"))
        interval = freq_days(freq)

        key = (agency, name)
        f = filings.get(key, {"count": 0, "last": None, "last_title": None})
        spine_last = clamp(parse_date(r.get("last_published_date")))
        # Best available "last filed": max of the spine's own field and the
        # filings mirror (they can disagree; take the more recent).
        last = max((d for d in (spine_last, f["last"]) if d), default=None)

        notice = late_notices.get(key)
        # A late notice newer than the last real filing means DORIS is still
        # waiting on the report.
        active_notice = notice if (notice and (last is None or notice > last)) else None

        # ---- Status ----
        due = None
        days_late = None
        if waived:
            status = "waived"
        elif completed:
            status = "completed"
        elif freq == "Once":
            status = "completed" if last else "never"
        elif interval is None:  # blank/unparseable frequency: no schedule to compute
            status = "never" if last is None else "unscheduled"
        elif last is None:
            status = "never"
        else:
            due = last + timedelta(days=interval)
            if due < TODAY:
                status = "overdue"
                days_late = (TODAY - due).days
            else:
                status = "current"

        link = None
        if isinstance(r.get("see_all_reports"), dict):
            link = r["see_all_reports"].get("url")

        out.append({
            "agency": agency,
            "name": name,
            "description": norm(desc),
            "frequency": freq or None,
            "local_law": norm(r.get("local_law")) or None,
            "charter_code": norm(r.get("charter_code")) or None,
            "status": status,
            "last_filed": last.isoformat() if last else None,
            "due": due.isoformat() if due else None,
            "days_late": days_late,
            "filings": f["count"],
            "late_notice": notice.isoformat() if notice else None,
            "late_notice_active": bool(active_notice),
            "link": link,
            "versions": len(rows),
        })

    counts = {}
    for rec in out:
        counts[rec["status"]] = counts.get(rec["status"], 0) + 1

    data = {
        "meta": {
            "built": TODAY.isoformat(),
            "requirement_rows": len(reqs),
            "requirements": len(out),
            "publications_rows": len(pubs),
            "status_counts": counts,
            "sources": {
                "requirements": "https://data.cityofnewyork.us/d/9azj-tmjp",
                "publications": "https://data.cityofnewyork.us/d/xip9-pe9k",
            },
        },
        "reports": out,
    }
    (HERE / "data.json").write_text(json.dumps(data, separators=(",", ":")))
    print(f"\nWrote data.json: {len(out)} requirements from {len(reqs)} rows")
    print("Status counts:", json.dumps(counts, indent=2))
    # Cross-check: how do computed statuses line up with DORIS's own late notices?
    both = sum(1 for x in out if x["late_notice_active"] and x["status"] in ("overdue", "never"))
    only_notice = sum(1 for x in out if x["late_notice_active"] and x["status"] not in ("overdue", "never"))
    print(f"Active DORIS late notices agreeing with computed overdue/never: {both}")
    print(f"Active DORIS late notices where we computed something else: {only_notice}")


if __name__ == "__main__":
    sys.exit(main())
