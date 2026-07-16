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


def fold(s):
    """Case- and punctuation-insensitive key.

    DORIS enters the same requirement under inconsistent casing and hyphenation
    ("Report on freelance law" vs "Report on Freelance Law"; "bio-diesel" vs
    "biodiesel"). Exact-string keys split those into two requirements, which
    strands the older row with a stale filing date and reports it overdue.
    """
    return re.sub(r"[^a-z0-9]", "", norm(s).lower())


def agency_key(a):
    """Canonical agency key: the agency name minus its trailing acronym.

    The two datasets disagree on the acronym for the same agency — the
    requirements list says "Health and Hospitals Corporation (H+H)" while
    filings arrive under "(HHC)" — so a literal string join silently drops
    those filings and reports the requirement staler than it is. The long name
    is the stable part. Verified against both datasets (July 2026): this key
    merges exactly one pair, H+H/HHC, and collides no genuinely distinct
    agencies. Keying on the acronym instead would NOT merge that pair.
    """
    return fold(re.sub(r"\s*\([^)]*\)\s*$", "", norm(a)))


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
# requirement, not the current one. The source is inconsistent about singular
# vs plural and "from" vs "up to", so match the family, not one phrasing.
ERA_CLOSED_RE = re.compile(
    r"\((?:required\s+)?reports?\s+(?:from|up to)\s+[^)]*?(?:-|–|to|through)\s+[^)]*\)", re.I
)
# Same family, but open-ended ("(Report from May 2018)", "(Reports from Sept 2020)").
# Ambiguous on its face: it may mean the requirement began then, or that DORIS's
# holdings stop there. Never used to change status — only to flag the row.
ERA_ANY_RE = re.compile(r"\((?:required\s+)?reports?\s+(?:from|up to)\s+[^)]*\)", re.I)

# ---- Requirements that are no longer owed by this agency ----------------------
# Each is stated in DORIS's own free-text description; none of it is structured.
# We reclassify rather than drop, so the row stays auditable on the site.

# "(This report is now filed by Technology and Innovation, Office of (OTI)"
# Executive Order 3 of 2022 folded DOITT, MODA and MOIP into OTI; their rows
# linger in the list and accrue days late against agencies that no longer exist.
TRANSFER_RE = re.compile(r"now\s+(?:filed|submitted|published)\s+by\s+(.+?)(?:\)|\.|$)", re.I)
# "(Sunsetted by operation of LL 36/2021)" / "until Local Law is deemed repealed"
SUNSET_RE = re.compile(r"sunsetted by[^.)]*|deemed repealed[^.)]*|repealed by[^.)]*", re.I)
# "(See Annual Zero Waste Report)" — folded into another report. Requires the
# word "report" in the pointer so bare cross-references like "(see details)"
# do not match.
FOLDED_RE = re.compile(r"\(see\s+([^)]*report[^)]*)\)", re.I)


def tidy(s):
    """Clean a fragment lifted out of DORIS free text.

    Several descriptions open a parenthetical and never close it — e.g.
    "(This report is now filed by Technology and Innovation, Office of (OTI" —
    so a captured fragment can carry an unbalanced "(". Re-balance it and drop
    trailing punctuation.
    """
    s = norm(s).rstrip(" .;,")
    depth = s.count("(") - s.count(")")
    return s + ")" * depth if depth > 0 else s


def sentence(s):
    """Uppercase the first character only; str.capitalize() would lowercase the
    rest and turn "LL 51/2023" into "ll 51/2023"."""
    return s[:1].upper() + s[1:] if s else s


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
        key = (agency_key(p.get("agency")), fold(rname))
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
        key = (agency_key(r.get("agency")), fold(r.get("name")))
        groups.setdefault(key, []).append(r)

    out = []
    for _, rows in sorted(
        groups.items(), key=lambda kv: (norm(kv[1][0].get("agency")), norm(kv[1][0].get("name")))
    ):
        # Pick the row describing the CURRENT requirement: prefer rows whose
        # description is not a closed era range; among those, latest last_published_date.
        def is_era(r):
            return bool(ERA_CLOSED_RE.search(r.get("description") or ""))

        current = [r for r in rows if not is_era(r)] or rows
        current.sort(key=lambda r: parse_date(r.get("last_published_date")) or date.min, reverse=True)
        r = current[0]
        # Display the chosen row's own agency/name spelling: it is the current-era
        # row, so its casing is the one DORIS is using now.
        agency, name = norm(r.get("agency")), norm(r.get("name"))

        desc = r.get("description") or ""
        completed = "(completed" in desc.lower()
        waived = bool(re.search(r"waiv", desc, re.I))
        freq = norm(r.get("frequency"))
        interval = freq_days(freq)

        # ---- Is this row still owed by this agency at all? ----
        superseded_reason = None
        m_t = TRANSFER_RE.search(desc)
        m_s = SUNSET_RE.search(desc)
        m_f = FOLDED_RE.search(desc)
        if m_t:
            superseded_reason = "Now filed by " + tidy(m_t.group(1))
        elif m_s:
            superseded_reason = sentence(tidy(m_s.group(0)))
        elif m_f:
            superseded_reason = "Folded into the " + tidy(m_f.group(1))

        # A closed- or open-ended era annotation on the row we are actually
        # scoring: the requirement may have lapsed at the end of that window, or
        # the agency may simply have stopped filing. DORIS does not say which, so
        # we keep the computed status and surface the ambiguity instead.
        m_era = ERA_ANY_RE.search(desc)
        era_note = norm(m_era.group(0)).strip("()") if m_era else None

        # Merge filings across every spelling of this requirement (the group can
        # hold several rows whose casing differs).
        key = (agency_key(agency), fold(name))
        f = filings.get(key, {"count": 0, "last": None, "last_title": None})
        spine_last = max(
            (d for d in (clamp(parse_date(x.get("last_published_date"))) for x in rows) if d),
            default=None,
        )
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
        elif superseded_reason:
            # Still shown, still linked, but not counted against the agency: the
            # requirement moved to a successor agency, was repealed, or was
            # folded into another report.
            status = "superseded"
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
            "superseded_reason": superseded_reason,
            "era_note": era_note,
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
    sup = [x for x in out if x["status"] == "superseded"]
    print(f"Superseded (reassigned/repealed/folded), withheld from overdue: {len(sup)}")
    for x in sup:
        print(f"    {x['agency']} | {x['name']} — {x['superseded_reason']}")
    caveat = sum(1 for x in out if x["era_note"] and x["status"] == "overdue")
    print(f"Overdue rows carrying an era caveat: {caveat}")
    # Requirements merged across casing/punctuation variants of the same name.
    print(f"Requirement rows collapsed into fewer requirements: {len(reqs) - len(out)}")


if __name__ == "__main__":
    sys.exit(main())
