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

So we read the current text of the cited section for **all 59**. The results are recorded in `law_review.json`, one entry per requirement, each with the citation, a verbatim quote of the operative language and a link:

- **52 are still in force.** The statutes use open-ended recurring language — "and 30 days after every quarter thereafter" (§ 14-171(b)), "and annually thereafter" (§ 21-914(d)), "each succeeding calendar quarter" (§ 21-312(e)) — in which the only dated language is a *start* date. Several have been affirmatively maintained since the supposed lapse: DOC's visitation report was re-enacted by LL 2025/044 effective January 2026; ACS's detention incident reports were rewritten and expanded by LL 2024/112 with a fresh January 2025 baseline; Charter § 815(i) survived four amendments through 2024.
- **5 had been repealed.** See below.
- **2 could not be resolved** — both DEP rows resting on Admin. Code § 24-504.2(a)(6), where the quarterly report is item 6 in an enumerated list of what a *one-time* analysis "shall include" rather than a freestanding perpetual duty. The section is not repealed (and the code flags repeals explicitly — adjacent § 24-504.1 is marked "[Repealed]"), so it did not silently lapse; the text simply does not say whether the cadence survives the study. Two independent reviewers reached the same conclusion. These keep the caveat.

**Mostly the era annotation describes DORIS's holdings, not the scope of the legal duty — but not always.** A data-only test pointed that way without settling it: in 15 of 26 testable cases the annotation's end date matched the last filing DORIS holds, consistent with "these are the reports we have," but in 11 it extended past the last filing. And in at least one case (FDNY, below) the annotation was reporting a real sunset. Only the statutes distinguish the two.

Requirements with a reading attached carry a `law_review` object and are labeled "Still required" on the site with the section text shown. `build.py` warns at build time if a review's key no longer matches any requirement, so the file cannot rot silently when DORIS renames a row.

### The eight dead requirements the list still carries

Five were found by reading the ambiguous entries; three more by the Local Law 69 sweep below. All are now labeled `superseded` with the repealing law named, and withheld from the overdue count:

| Requirement | Was shown as | Killed by |
|---|---|---|
| DCAS — clean on-site power generation assessment | 3,118 days late (the most overdue entry in the tracker) | § 4-207 repealed, LL 2023/069 |
| SBS — Division of Economic and Financial Opportunity activities | 1,856 days late | Charter § 1304(e)(5) repealed, LL 2023/069 |
| NYPD — Patrol Guide Procedures Quarterly Report | 1,737 days late | § 14-150(a)(2) repealed, LL 2016/129 |
| Mayor's Office of Operations — Algorithms Management and Policy Officer report | 1,323 days late | EO 50/2019 revoked by EO 3/2022 § 10 |
| FDNY — fire safety materials developed with DOE | 908 days late | § 15-133(b) self-repealed June 12, 2023 |
| MOCS — Small Purchases Quarterly Report | 203 days late | Charter § 314(b) repealed, LL 2023/069 |
| DOT — Traffic Calming Study | never filed | § 19-179 repealed, LL 2023/069 |
| DOHMH — Electronic Death Registration System Evaluation | never filed | § 17-196(i) repealed, LL 2023/069 |

Two deserve elaboration.

**The FDNY report is the one the code page cannot tell you about.** Admin. Code § 15-133(b) still prints in the current code reading "Beginning January 31, 2019 and annually thereafter…" — it looks perfectly live. The self-repealer sits in the enacting law's *unconsolidated provisions*, not the running text: LL 2018/116 § 2 provides that subdivision (b) "is deemed repealed 5 years after it becomes law." The clerk certifies the law was returned unsigned on June 12, 2018, so the duty died June 12, 2023. The only clue on the code page is an editor's note pointing to Appendix A. DORIS's era note here ("Reports from Nov 2020 to Jan 2023") was accurate — the January 2023 filing was the last one ever owed.

**The Algorithms Officer report never rested on a statute at all.** It came from Executive Order 50 of 2019, which Executive Order 3 of 2022 both discontinued (§ 4) and revoked outright (§ 10) — the same order that folded DOITT, MODA and MOIP into OTI. No local law preserves it, and the residual function went to OTI, so the attribution to the Mayor's Office of Operations is wrong even as to the successor.

### Local Law 69 of 2023: a repeal the list missed

Reading the individual entries surfaced a systematic problem. [Local Law 69 of 2023](https://intro.nyc/local-laws/2023-69) is titled, in part, "in relation to eliminating certain reporting requirements selected for waiver by the report and advisory board review commission." It repealed **21 reporting provisions at once**, effective June 28, 2023 — among them Charter §§ 314(b), 613, 1063(c), 1075(b)-(c), 1304(e)(5) and Admin. Code §§ 3-706(1)(d), 4-207, 6-139(c)(3), 16-316.2, 16-428(b), 17-196(i), 19-177(d)(2), 19-178.1, 19-179, 19-180.1, 19-192, 19-307(j), 22-226, 22-269, 24-504.1 and 24-526.1(b)(4).

DORIS's requirements list still carries entries for several of these with no indication they are dead. We swept every repealed provision against the list and checked the subject matter of each candidate before acting — which matters, because the match must be more than a section number: MOCS's worker cooperatives report cites § 6-139(b), and LL 69/2023 repealed only § 6-139(c)(3), so that duty survives and is correctly still counted.

This is also a caution about the tracker's `waived` status. The RABRC's waiver determinations are what LL 69/2023 implemented, so a requirement can be waived in substance without the word "waiver" ever appearing in its DORIS description.

#### Errors found in DORIS's own metadata

Reading the laws surfaced seven bad citations in the requirements list itself. None changes a status on its own, but each would mislead anyone trying to follow the tracker back to the source:

| Requirement | DORIS says | Actually |
|---|---|---|
| MOCJ, nightlife inspections | Admin. Code § 9-309 | § 9-308 — § 9-309 is an unrelated district attorney reporting section (LL 2021/161). LL 220/2019 as enacted said "§ 9-307," but that was already taken by LL 2019/192, so the codifier moved it. |
| NYPD, Special Victims Division audits | Admin. Code § 14-177(c) | § 14-178(c) — § 14-177 is "Harassment and sexual assault survivor sensitivity training" (LL 2018/189) and has no subsection (c). |
| ENDGBV, domestic violence fatality review | Admin. Code § 3-171(b)(1) | § 3-181 — § 3-171 is "Pay and employment equity data" and has nothing to do with domestic violence. |
| DOC, post-arraignment bail holds | LL 85 of 2015 (Int. 706) | § 9-149(d), from LL 124/2017. LL 85/2015 is codified at § 9-140 and covers jail visitation, not bail. |
| EDC, quarterly expenditure reports | Charter § 119 | § 110 — Charter Chapter 6 runs § 100–111; there is no § 119. |
| DOF, report on revocations | Admin. Code Title 11, Chapter 140 | § 11-140. |
| DOC, Board of Correction report | *(no citation; attributed to LL 102/1977)* | Charter § 626(d), amended as recently as LL 2025/105 (eff. 11/11/2025). |

Stale law attributions are a related problem: ACS's detention incident reports are still credited to LL 14/2010 and LL 44/2013 though LL 2024/112 rewrote the section in November 2024, and the NYPD patrol guide row never records the 2016 law that repealed it.

Four labels or frequencies are also wrong: HRA's "reports for individuals aged 16 to 25" covers ages 16 **through 24**, and its § 21-134(b) duty is **monthly**, not the semiannual cadence DORIS records (the semiannual duty is subdivision (c)). ACS's "Demographic Data on Population Placements and Transfers" is recorded as annual but § 21-905 has required it **quarterly** since LL 2024/112. FDNY's "Section 130(3)" should be § 15-130(c). DEP's "Maintenance, Costs and Expenses" is really § 24-357, "Report to comptroller of expenses and liabilities."

#### Cases where the report exists but DORIS has no copy

CCRB's Administrative Prosecution Unit reports (2,267 days late, now the most overdue entry in the tracker) rest not on a statute but on paragraph 18 of the 2012 CCRB–NYPD memorandum of understanding, which requires quarterly status reports to the NYPD. The MOU is still presented as operative, and **CCRB has published APU quarterly reports through 2026 Q1** — they are simply not filed with DORIS. This is limitation 2 above in its purest form: the red badge is accurate about the city's recordkeeping and misleading about the underlying work. Note also that the duty runs to the NYPD rather than to the public, and paragraph 29 lets either party terminate on written notice, so it is legally weaker than the statutory duties around it.

Two others fit the pattern. ACS has continued publishing its annual child fatality reviews — the 2022 and 2023 editions cite § 21-915 by name — despite the tracker showing the requirement 1,477 days late. And DEP's clean heating oil waiver report may be satisfied through the Mayor's Management Report under § 24-168.1(d)(2), which would explain its sparse DORIS record.

#### Where the duty and the agency have drifted apart

Several in-force requirements are attributed to the wrong body, because the statute names a function rather than an office and the office has since moved:

- MOPT's three-quarter housing report: § 3-152(h) assigns it to "a city agency or office designated by the mayor," not to the Mayor's Office to Protect Tenants by name.
- MOFP's food metrics report: § 3-120 places the duty on the office of long-term planning and sustainability, though MOFP publishes it in practice.
- DHS's homeless diversion teams report: § 21-124.1 places it on the Social Services commissioner, and the screening happens at HRA centers.
- MOIA's and DCLA's identifying-information and EEO reports: both statutes run to "each city agency," so these rows are instances of a citywide duty rather than office-specific ones.
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
