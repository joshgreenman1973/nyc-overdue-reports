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

### Ambiguous date ranges — and what reading the laws showed

59 overdue requirements carry an annotation like "(Required Reports from Jan 2020 to Nov 2020)" or "(Reports up to Jul 2020)". On its face this is ambiguous: it may mean the requirement lapsed at the end of that window, or that the agency simply stopped filing a report it still owes. DORIS does not distinguish the two, and nothing in either dataset answers it — only the authorizing statute does.

So for the 32 most overdue of these (every entry at 1,900+ days late), we read the current text of the cited section. The results are recorded in `law_review.json`, one entry per requirement, each with the citation, a verbatim quote of the operative language and a link:

- **30 of 32 are still in force.** **None had lapsed.** The statutes use open-ended recurring language — "and 30 days after every quarter thereafter" (§ 14-171(b)), "and annually thereafter" (§ 21-914(d)), "each succeeding calendar quarter" (§ 21-312(e)) — in which the only dated language is a *start* date. Several have been affirmatively maintained since: DOC's visitation report was re-enacted by LL 2025/044 effective January 2026; the nightlife inspections report was amended effective January 2024; Charter § 815(i) survived four amendments through 2024.
- **2 could not be resolved** — both DEP rows resting on Admin. Code § 24-504.2(a)(6), where the quarterly report is item 6 in an enumerated list of what a *one-time* analysis "shall include" rather than a freestanding perpetual duty. The section is not repealed (and the code flags repeals explicitly — adjacent § 24-504.1 is marked "[Repealed]"), so it did not silently lapse; the text simply does not say whether the cadence survives the study. Two independent reviewers reached the same conclusion. These keep the caveat.

**The conclusion generalizes: the era annotation describes DORIS's holdings, not the scope of the legal duty.** A weaker data-only test pointed the same way but was not decisive — in 15 of 26 testable cases the annotation's end date matched the last filing DORIS holds, consistent with "these are the reports we have," but in 11 it extended past the last filing, so it is not purely a holdings description. The statutes settle what the correlation could not.

Requirements with a reading attached carry a `law_review` object and are labeled "Still required" on the site with the section text shown. The 27 era-flagged entries below 1,900 days late have not been read yet and keep the caveat. `build.py` warns at build time if a review's key no longer matches any requirement, so the file cannot rot silently when DORIS renames a row.

#### Errors found in DORIS's own metadata

Reading the laws surfaced four bad citations in the requirements list itself. None changes a status, but each would mislead anyone trying to follow the tracker back to the source:

| Requirement | DORIS says | Actually |
|---|---|---|
| MOCJ, nightlife inspections | Admin. Code § 9-309 | § 9-308 — § 9-309 is an unrelated district attorney reporting section (LL 2021/161). LL 220/2019 as enacted said "§ 9-307," but that was already taken by LL 2019/192, so the codifier moved it. |
| NYPD, Special Victims Division audits | Admin. Code § 14-177(c) | § 14-178(c) — § 14-177 is "Harassment and sexual assault survivor sensitivity training" (LL 2018/189) and has no subsection (c). |
| EDC, quarterly expenditure reports | Charter § 119 | § 110 — Charter Chapter 6 runs § 100–111; there is no § 119. |
| DOF, report on revocations | Admin. Code Title 11, Chapter 140 | § 11-140. |

Two labels are also wrong: HRA's "reports for individuals aged 16 to 25" covers ages 16 **through 24**, and its § 21-134(b) duty is **monthly**, not the semiannual cadence DORIS records (the semiannual duty is subdivision (c)). DEP's "Maintenance, Costs and Expenses" is really § 24-357, "Report to comptroller of expenses and liabilities."

#### One case where the report exists but DORIS has no copy

CCRB's Administrative Prosecution Unit reports (2,267 days late, the most overdue entry in the tracker) rest not on a statute but on paragraph 18 of the 2012 CCRB–NYPD memorandum of understanding, which requires quarterly status reports to the NYPD. The MOU is still presented as operative, and **CCRB has published APU quarterly reports through 2026 Q1** — they are simply not filed with DORIS. This is limitation 2 above in its purest form: the red badge is accurate about the city's recordkeeping and misleading about the underlying work. Note also that the duty runs to the NYPD rather than to the public, and paragraph 29 lets either party terminate on written notice, so it is legally weaker than the statutory duties around it.
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
