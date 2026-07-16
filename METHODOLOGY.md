# Overdue: the reports New York City owes itself — methodology

Last updated: 2026-07-16

## What this is

A tracker of every report New York City agencies are legally required to publish, cross-referenced against what they have actually filed with the Department of Records and Information Services (DORIS), with a computed status for each requirement: never filed, overdue, up to date, completed, waived or no schedule.

## Data sources

| Source | Dataset | What it provides | Update cadence |
|---|---|---|---|
| DORIS via NYC Open Data | [Government Publication - Required Reports](https://data.cityofnewyork.us/d/9azj-tmjp) (`9azj-tmjp`) | The official list of legally mandated reports: agency, report name, description, frequency, authorizing local law and Charter/Administrative Code citation, last published date. 2,231 rows as of July 2026. | Monthly (manual) |
| DORIS via NYC Open Data | [Government Publications Listing](https://data.cityofnewyork.us/d/xip9-pe9k) (`xip9-pe9k`) | Metadata for every document filed with DORIS under City Charter section 1133 — 78,014 rows as of July 2026, including 4,295 "Delinquent Report Notice" records. | Monthly (manual) |

Both datasets were accessed 2026-07-16 via the Socrata API (no key required). The authorizing law for the whole system is [City Charter section 1133](https://codelibrary.amlegal.com/codes/newyorkcity/latest/NYCcharter/0-0-0-1233), added by Local Law 29 of 2019.

## The join

DORIS tags each filed document with the required report it satisfies (`required_report_name`), drawn from the same controlled vocabulary as the requirements list's `name` field. We join on (agency, report name), normalizing both sides: whitespace collapsed, then case and punctuation folded away.

The folding is not cosmetic. A literal string join produces false overdue statuses, because DORIS enters the same requirement inconsistently:

- **Report name casing.** The list carries `Report on freelance law` (last published 2018-05-15) and `Report on Freelance Law` (last published 2023-11-08) as separate rows under the same agency and the same authorizing law (LL 140/2016, Admin. Code § 936(c)). Keyed literally, the lowercase row is stranded with the 2018 date and computes as ~1,150 days overdue, while the same report shows as current one row away. Verified July 2026: five such pairs exist across the list; folding case and punctuation merges exactly those five and no others.
- **Agency acronyms.** The requirements list says `Health and Hospitals Corporation (H+H)`; 72 filings arrive under `Health and Hospitals Corporation (HHC)`. We key agencies on the long name with the trailing parenthetical stripped. Verified July 2026: this merges exactly one pair (H+H/HHC) and collides no genuinely distinct agencies. Keying on the acronym instead does *not* merge them.

Where the same requirement appears as multiple rows (the underlying law changed over time, e.g. "Required report from Jan 2020 - July 2020"), we group rows by the folded agency + name, prefer the row whose description does not describe a closed era, and among those take the one with the latest last-published date. That row's own spelling is what the site displays. The row count per requirement is retained (`versions`), and "last filed" is taken across every row in the group, not just the chosen one.

## Status logic

For each requirement:

1. **Last filed** = the later of (a) the requirements list's `last_published_date` and (b) the newest `date_published` among that requirement's filings in the publications listing, excluding Delinquent Report Notices. Future-dated values (a known data-quality issue in both datasets — e.g. entries dated 2026-12-29 or 2028) are ignored.
2. **Frequency interval**: "Every N Days/Weeks/Months/Years" is converted to days (month = 30.44, year = 365.25).
3. **Status**:
   - `waived` — description mentions a waiver (the Report and Advisory Board Review Commission, Charter section 1113, can waive requirements; waivers appear only as free-text notes).
   - `completed` — description contains "(Completed" (one-time requirements), or frequency is "Once" and a filing exists.
   - `superseded` — the requirement is no longer owed by the agency named. See below.
   - `never` — no filing ever recorded on either side.
   - `unscheduled` — filings exist but no parseable frequency; no due date can be computed.
   - `overdue` — last filed + interval is before today. Days late is reported.
   - `current` — otherwise.

### Superseded requirements

The list retains rows for reports that are no longer owed by the agency named. Left alone, these accrue "days late" indefinitely against requirements nobody owes — in several cases against agencies that no longer exist. As of the July 2026 build, 21 rows qualify. Three patterns, all detected from DORIS's own free-text description and all reclassified rather than dropped (they remain listed, searchable and linked under a `superseded` badge, with the reason shown):

1. **Moved to a successor agency** — "(This report is now filed by Technology and Innovation, Office of (OTI)". [Executive Order 3 of 2022](https://www.nyc.gov/mayors-office/news/2022/01/executive-order-3) (Jan. 19, 2022) dissolved DOITT, the Mayor's Office of Data Analytics and the Mayor's Office of Information Privacy into OTI. Their rows remain in the list. Six of them duplicate an OTI row that is filed and current — e.g. DOITT's "Annual Report on 311 System Customer Satisfaction Surveys" computed as ~1,470 days late while OTI filed the same report on 2026-07-01. The Mayor's Office of Sustainability's long-term plan likewise moved to the Mayor's Office of Climate and Environmental Justice.
2. **Repealed or sunsetted by law** — e.g. DOHMH's "Report on Implementation of Homebound Senior COVID-19 Vaccination Plan," whose description reads "(Sunsetted by operation of LL 36/2021)," and the Municipal Drug Strategy Council report, whose local law is "deemed repealed" after the February 2022 filing.
3. **Folded into another report** — e.g. DSNY's "Citywide Recycling Plan/Annual Recycling Report," annotated "(See Annual Zero Waste Report)." The pointer must name a *report*, so bare cross-references like "(see details)" do not match.

This is detection from unstructured text, not a structured field, and it is therefore conservative: it catches only what DORIS wrote down. Requirements that lapsed without a note remain counted as overdue.

### Ambiguous date ranges (flagged, not resolved)

59 overdue requirements carry an annotation like "(Required Reports from Jan 2020 to Nov 2020)" or "(Reports up to Jul 2020)". This is genuinely ambiguous in the source: it may mean the requirement lapsed at the end of that window, or that the agency simply stopped filing a report it still owes. DORIS does not distinguish the two, and the underlying local laws would have to be read individually to tell.

We do not guess. These keep their computed `overdue` status and are counted in the overdue total, but each carries an `era_note` and is flagged on the site with the source's own wording and an explicit statement that the requirement may have lapsed. This is the single largest known source of possible overstatement in the overdue count, and it is concentrated in the long tail: many of the entries above 1,900 days late carry one of these notes.
4. **City late notices**: when a report is overdue, Charter section 1133(d) requires DORIS to post a "Delinquent Report Notice" in its place. We flag a requirement when its most recent late notice is newer than its most recent filing.

### Why our status and the city's late notices can disagree

DORIS knows each report's actual statutory due date (an annual report might be due every January 31). Our computation anchors to the last filing date plus the stated interval, because the statutory due dates are not published as data. Both signals are shown. As of the July 16, 2026 build, 465 active late notices agree with our overdue/never-filed statuses and 127 attach to requirements we compute as current, completed or superseded — mostly annual reports filed mid-cycle where DORIS expected the next edition sooner than "last filed + 1 year."

## Known limitations

1. **The list itself is incomplete by design.** Charter section 1133(b) covers reports required "by local law, executive order, or mayoral directive." Reports required by **state or federal law** need only be filed "where practicable" — only about 6 of 2,200+ entries cite state or federal authority, so state-mandated city reports are systematically undercounted.
2. **Absence from DORIS does not always mean a report doesn't exist.** When the system launched, [Gotham Gazette (Aug. 30, 2019)](https://www.gothamgazette.com/city/8765-new-york-city-government-reporting-required-gaps-in-reporting/) found some reports "listed as having not been received" were in fact "created and are regularly maintained by city agencies on their websites" — they were just never filed with DORIS as required. A red badge means the city's recordkeeping system has no copy.
3. **Waivers are free text.** We parse waiver mentions from descriptions; the RABRC's [waiver determinations](https://www.nyc.gov/html/rabrc/downloads/pdf/waiver_determinations.pdf) are the authoritative record.
4. **Both datasets are updated manually, roughly monthly** — the tracker inherits that lag.
5. **Frequency intervals are approximations.** "Every 1 Year" = 365.25 days from the last filing, not the statutory due date.
8. **Supersession is detected from free text, not a field.** The `superseded` status relies on DORIS having written a note in the description. A requirement that quietly lapsed, or whose successor agency is named only in the underlying law, still shows as overdue.
9. **Future-dated filings are discarded, which can overstate lateness.** Both datasets contain obvious data-entry errors (dates in 2028, or "2026-12-31"). We ignore any date after the build date. Where such an entry is a typo for a real recent filing, the requirement will read staler than it is. Three overdue rows were affected in the July 2026 build.
6. **Blank frequencies.** 231 requirement rows have no stated frequency; where a filing exists we mark them "no schedule" rather than guessing.
7. **Coverage of non-mayoral entities** (district attorneys, Board of Elections, etc.) is thin and should not be treated as exhaustive.

## Reproducing this

`python3 build.py` fetches both datasets and writes `data.json`. Python 3 standard library only. The site (`index.html`) is static and reads `data.json`.
