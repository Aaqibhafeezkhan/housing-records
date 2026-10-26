# Starter issues

The first issues to open when the repository goes public. Each section is one issue: the heading is its title
and the text below is its description. Suggested labels are in brackets.

---

## Add Wales and Scotland to the record  [good first issue, new-source, help wanted]

Housing Records covers England only. The map already draws every UK district, with Scotland, Wales and
Northern Ireland greyed out.

**Scotland.** The Scottish Housing Regulator's 2025/26 Charter indicators for all 168 Scottish landlords are
already downloaded (`data/raw/shr/charter_current.csv`) and turned into a table
(`data/out/scotland_charter_2025_26.csv`), but nothing on the site uses them yet. The Charter measures are not
the same as England's Tenant Satisfaction Measures, so Scottish landlords need a card of their own rather than
being squeezed into the English one.

**Wales.** The Welsh Government publishes regulatory judgements for each housing association. We have not yet
found a single published dataset of performance measures. Finding one is the first step.

What a good contribution looks like:

- a short note on what each nation publishes, under what licence, and how it differs from England;
- for Scotland, a card design (in words or a sketch is fine) that never presents a Scottish figure as if it
  were comparable with an English one;
- Scottish and Welsh landlords compared only with landlords in the same nation.

See `METHOD.md` §10 and `data/SOURCES.md`.

---

## Review the scoring system  [discussion, method]

Every ranked landlord gets a score out of 100, shown as a coloured pill. It is worked out in the browser
(`site/index.html`, `posOf` and `scoreBand`):

- four measures: statutory safety checks, homes below the Decent Homes Standard, non-emergency repairs on time,
  and Ombudsman maladministration findings per 10,000 homes in the last 12 months;
- each becomes a position from 0 (worst in England) to 1 (best), and the score is their average, with equal
  weight;
- only landlords with 1,000+ homes and all four figures are scored;
- the colour bands are the bottom quarter, middle half and top quarter of all scores.

We would like an outside review before more people rely on it. Questions to start with:

- Is equal weighting defensible, and how should the site explain it?
- `METHOD.md` says councils are compared only with councils, and housing associations within the Regulator's
  segments. Should the score follow the same rule?
- Three of the measures are self-reported by landlords; one is the Ombudsman's independent finding. Should that
  difference show?
- How should a score handle a landlord whose homes figure is its group's stock (`homes_grp`), or a measure the
  Regulator withheld?

Please discuss here before opening a pull request; any change must keep to the rules in `METHOD.md`.

---

## Automate the yearly data refresh  [automation, help wanted]

Each source is updated on its own calendar (`METHOD.md` §7): the register and regulatory judgements monthly,
Global Accounts in January, Value for Money metrics in March, stock and rents in October, and the Tenant
Satisfaction Measures each November.

Proposal: a scheduled GitHub Action that, on those dates, downloads the latest files, runs `bash pipeline/run.sh`
and opens a pull request with a plain-English summary of what changed (for example "12 landlords' measures
changed; 2 new landlords; 1 merger"). **It must never publish anything itself**: a person reviews the preview
and merges.

Things to solve:

- government download links change with each release, so the action needs to find the current link from each
  landing page, and fail loudly when it can't;
- the pipeline's asserts must stop the run when a publisher changes a format (sheet names, column codes);
- the Ombudsman decisions have no download and need a browser crawl (`pipeline/crawler.js`), so leave them out
  of the first version.

---

## Rebuild the compensation reader  [data, help wanted]

The site shows how much compensation the Housing Ombudsman ordered each landlord to pay, for example
"at least £X, read from N of M decisions". The Ombudsman publishes amounts only in the text of each decision,
so they had to be read from 12,861 decisions.

The results are committed in `data/derived/ombudsman_compensation.csv`, and the rules they were read with are
written down in `data/derived/README.md`, but **the program that read them was not kept**. Until it is rebuilt,
nobody can regenerate the file from the decisions or check the rules were applied consistently.

The task:

1. Collect the "Orders" section of each of the 12,861 decisions, politely (no more than a request or two a
   second) and saving only that section.
2. Write the reader in `pipeline/`, following the rules in `data/derived/README.md`: refuse rather than guess.
3. Compare its output with the committed file, decision by decision, and explain every difference. The target
   is: 11,562 parsed (10,925 with a figure, £11.83m in total), 1,299 quarantined.
4. Hand-check at least 10 real decisions, including some that are quarantined.

---

## Fix: landlords with all-number codes get the group's homes, or none  [data, bug, priority]

The Regulator's spreadsheets store registration codes like `4878` as numbers but codes like `L4517` as text.
In `pipeline/build_spine.py`, the landlord list (from the Tenant Satisfaction Measures workbook) is joined to the
stock-by-borough return (a CSV, where every code is text). For the 56 landlords whose codes are all digits, the
join silently fails. The pipeline then falls back to the **group's** stock, or to nothing at all.

This affects the homes figure, the number of boroughs, the per-10,000-homes Ombudsman rates and the score of
these housing associations:

| Code | Landlord | Homes shown now (group, or none) | Own stock in the return |
|---|---|---|---|
| 4651 | Flagship Housing Limited | none (not ranked) | 30,192 |
| 4878 | Peabody Trust | 82,017 | 70,758 |
| 4846 | Karbon Homes Limited | 31,562 | 28,265 |
| 4729 | The Guinness Partnership Limited | 57,324 | 56,778 |
| 4880 | Notting Hill Genesis | 40,844 | 40,686 |
| 4653 | Regenda Limited | 10,991 | 10,858 |
| 5171 | Southern Housing | 60,846 | 60,752 |
| 4837 | Sovereign Network Group | 67,102 | 67,099 |
| 4789 | Platform Housing Group Limited | 41,429 (group) | 2 — its homes sit in a subsidiary, so the group figure is right, but it should be flagged `homes_grp` like Curo, Jigsaw and Orbit |

Every other housing association uses its own stock, so these nine are treated inconsistently.

The fix:

1. Compare codes as text everywhere in the pipeline: strip spaces and convert to a string as soon as a file is
   read.
2. Rebuild, and check that only these landlords (and the rankings and borough figures they feed) change.
3. Check Flagship's card now shows its homes and is ranked.
4. Spot-check three of them by hand against `File 04 - Stock by LA.csv` in the stock and rents return.

The same mismatch is why `build_bundle.py` looks up register facts (legal form, registration year) by code as
text; that lookup can be simplified once the codes are fixed at source.
