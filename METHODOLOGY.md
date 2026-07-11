# Overdue: the reports New York City owes itself — methodology

Last updated: 2026-07-10

## What this is

A tracker of every report New York City agencies are legally required to publish, cross-referenced against what they have actually filed with the Department of Records and Information Services (DORIS), with a computed status for each requirement: never filed, overdue, up to date, completed, waived or no schedule.

## Data sources

| Source | Dataset | What it provides | Update cadence |
|---|---|---|---|
| DORIS via NYC Open Data | [Government Publication - Required Reports](https://data.cityofnewyork.us/d/9azj-tmjp) (`9azj-tmjp`) | The official list of legally mandated reports: agency, report name, description, frequency, authorizing local law and Charter/Administrative Code citation, last published date. 2,231 rows as of July 2026. | Monthly (manual) |
| DORIS via NYC Open Data | [Government Publications Listing](https://data.cityofnewyork.us/d/xip9-pe9k) (`xip9-pe9k`) | Metadata for every document filed with DORIS under City Charter section 1133 — 78,014 rows as of July 2026, including 4,295 "Delinquent Report Notice" records. | Monthly (manual) |

Both datasets were accessed 2026-07-10 via the Socrata API (no key required). The authorizing law for the whole system is [City Charter section 1133](https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCcharter/0-0-0-1233), added by Local Law 29 of 2019.

## The join

DORIS tags each filed document with the required report it satisfies (`required_report_name`), drawn from the same controlled vocabulary as the requirements list's `name` field. We join on (agency, report name) after trimming and collapsing whitespace. Verified July 2026: 923 of 925 distinct report names in the filings mirror match a requirements-list name exactly; the two exceptions are the deliberate "Other Publication" bucket and one name containing an embedded newline, which whitespace normalization fixes.

Where the same requirement appears as multiple rows (the underlying law changed over time, e.g. "Required report from Jan 2020 - July 2020"), we group rows by agency + name, prefer the row whose description does not describe a closed era, and among those take the one with the latest last-published date. The row count per requirement is retained (`versions`).

## Status logic

For each requirement:

1. **Last filed** = the later of (a) the requirements list's `last_published_date` and (b) the newest `date_published` among that requirement's filings in the publications listing, excluding Delinquent Report Notices. Future-dated values (a known data-quality issue in both datasets — e.g. entries dated 2026-12-29 or 2028) are ignored.
2. **Frequency interval**: "Every N Days/Weeks/Months/Years" is converted to days (month = 30.44, year = 365.25).
3. **Status**:
   - `waived` — description mentions a waiver (the Report and Advisory Board Review Commission, Charter section 1113, can waive requirements; waivers appear only as free-text notes).
   - `completed` — description contains "(Completed" (one-time or superseded requirements), or frequency is "Once" and a filing exists.
   - `never` — no filing ever recorded on either side.
   - `unscheduled` — filings exist but no parseable frequency; no due date can be computed.
   - `overdue` — last filed + interval is before today. Days late is reported.
   - `current` — otherwise.
4. **City late notices**: when a report is overdue, Charter section 1133(d) requires DORIS to post a "Delinquent Report Notice" in its place. We flag a requirement when its most recent late notice is newer than its most recent filing.

### Why our status and the city's late notices can disagree

DORIS knows each report's actual statutory due date (an annual report might be due every January 31). Our computation anchors to the last filing date plus the stated interval, because the statutory due dates are not published as data. Both signals are shown. As of the July 2026 build, 469 active late notices agree with our overdue/never-filed statuses and 123 attach to requirements we compute as current or completed — mostly annual reports filed mid-cycle where DORIS expected the next edition sooner than "last filed + 1 year."

## Known limitations

1. **The list itself is incomplete by design.** Charter section 1133(b) covers reports required "by local law, executive order, or mayoral directive." Reports required by **state or federal law** need only be filed "where practicable" — only about 6 of 2,200+ entries cite state or federal authority, so state-mandated city reports are systematically undercounted.
2. **Absence from DORIS does not always mean a report doesn't exist.** When the system launched, [Gotham Gazette (Aug. 30, 2019)](https://www.gothamgazette.com/city/8765-new-york-city-government-reporting-required-gaps-in-reporting/) found some reports "listed as having not been received" were in fact "created and are regularly maintained by city agencies on their websites" — they were just never filed with DORIS as required. A red badge means the city's recordkeeping system has no copy.
3. **Waivers are free text.** We parse waiver mentions from descriptions; the RABRC's [waiver determinations](https://www.nyc.gov/html/rabrc/downloads/pdf/waiver_determinations.pdf) are the authoritative record.
4. **Both datasets are updated manually, roughly monthly** — the tracker inherits that lag.
5. **Frequency intervals are approximations.** "Every 1 Year" = 365.25 days from the last filing, not the statutory due date.
6. **Blank frequencies.** 231 requirement rows have no stated frequency; where a filing exists we mark them "no schedule" rather than guessing.
7. **Coverage of non-mayoral entities** (district attorneys, Board of Elections, etc.) is thin and should not be treated as exhaustive.

## Reproducing this

`python3 build.py` fetches both datasets and writes `data.json`. Python 3 standard library only. The site (`index.html`) is static and reads `data.json`.
