# Overdue: the reports New York City owes itself

City law requires agencies to publish more than 2,100 recurring reports and file them with the Department of Records and Information Services (DORIS). This tracker cross-references the city's official list of required reports with what agencies have actually filed, and badges every requirement: never filed, overdue, up to date, completed, waived or no schedule.

- `build.py` — fetches both DORIS datasets from NYC Open Data and writes `data.json` (Python 3, standard library only)
- `index.html` — the static site
- `METHODOLOGY.md` — sources, join logic, status definitions, limitations
- `.github/workflows/refresh.yml` — weekly automated data refresh

Local preview: `python3 -m http.server 8214` in this directory.
