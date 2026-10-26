# The Housing Records — method, sources and update guide

**What this file is.** Everything needed to rebuild, update or defend the data on
[housingrecords.org](https://housingrecords.org). Paste it into a new session and it should be possible to
carry on without re-deriving any of it.

Last verified against the live site: **16 September 2026**. Repo: `github.com/crbtgab/housing-records`,
deploying to Vercel from `main` (`outputDirectory: "site"`).

---

## 1. The rules that override everything else

These are not style preferences. Breaking any of them is a bug, however good the result looks.

1. **Never fabricate a figure.** Every number on the site traces to a published official file, named on the
   card it appears on. Nothing is modelled, estimated, interpolated or filled in. If a landlord has not
   reported something, the card says so — a blank is never treated as a zero or as good news.
2. **An absence is not a clean record.** Where data is missing, say *why* it is missing. "Not reported"
   understates it when the Regulator has actually withheld something and published its reason.
3. **Cost is never a grade.** Cost per home is ranked but never coloured good or bad. London and older stock
   cost more to run; a low figure can mean efficiency or under-investment. Always set it beside repairs.
4. **Rent is never a grade.** Social rents follow a national formula built on local earnings and property
   values. The only fair comparison is inside the same borough.
5. **Compare like with like.** Positions are computed within the Regulator's own segments (general needs /
   supported housing / housing for older people), never across them. Councils are compared only with
   councils. A segment with fewer than 8 providers falls back to an all-association comparison.
6. **Small numbers are not rates.** Below 10 decisions, show counts, not percentages. 67% maladministration
   from three cases is true and misleading.
7. **When the parse is ambiguous, refuse.** Better a gap than a wrong number (see §6, compensation).
8. **Write for a tenant, not an analyst.** Plain British English.

---

## 2. What is on the record now

| | |
|---|---|
| Landlords | **360** — 200 housing associations, 160 councils |
| Threshold | 1,000+ social homes in England, reporting to the Regulator |
| Homes covered | ~4.04m, about **95%** of England's social homes |
| Boroughs | 296 English districts (361 drawn, incl. greyed Scotland/Wales/NI) |
| Map dots | 8,434 landlord holdings |
| Ombudsman decisions | **18,123**, Dec 2020 – Aug 2026 |
| Ombudsman-only landlords | **96** — have decisions but file none of the Regulator's returns |
| Not on the record | Of 1,578 registered providers, 1,219 own under 1,000 homes; 26 councils own none |

---

## 3. Sources

All raw files live in `data/raw/` (gitignored). `pipeline/fetch_sources.sh` re-downloads them from exact
URLs. **Asset URLs on `assets.publishing.service.gov.uk` are versioned and change when a publication is
updated** — if one 404s, open the landing page and take the current link, then update the script.

### Regulator of Social Housing

| File | Landing page | Taken | Cadence |
|---|---|---|---|
| `List_of_registered_providers_*.xlsx` | [Registered providers of social housing](https://www.gov.uk/government/publications/registered-providers-of-social-housing) | The canonical register — name, registration number, designation (profit/non-profit/LA), legal form, registration date. Everything joins on this. | Monthly |
| `2025_TSM_Full_Data_*.xlsx` | [Tenant Satisfaction Measures 2024/25](https://www.gov.uk/government/statistics/tenant-satisfaction-measures-202425) | 22 measures: 12 tenant-perception, 10 management-information (safety checks, non-decent homes, repairs, complaints, ASB). | Annual, Nov |
| `2024_TSM_Full_Data_*.xlsx` | [Data release TSM 2024](https://www.gov.uk/government/statistics/data-release-tsm-2024) | Same measures for 2023/24, for year-on-year change. | — |
| `PRP_Data_Release_2025_Full_Data_*.zip` (SDR) | [PRP stock and rents 2024/25](https://www.gov.uk/government/statistics/private-registered-provider-social-housing-stock-and-rents-in-england-2024-to-2025) | File 02 group structure; File 04 stock by local authority; Files 09/10 average weekly net rent and units; File 16 stock balance sheet. | Annual, Oct |
| `*_RegulatoryJudgementsNotices_Published.xlsx` | [Regulatory judgements and enforcement notices](https://www.gov.uk/government/publications/regulatory-judgements-and-enforcement-notices) | C1–C4 / G1–G4 / V1–V4 grades with dates, what moved at the latest judgement, engagement route, "Grading Under Review", enforcement notices. | Monthly+ |
| `*_VFM_Metrics_tables.xlsx` | [Value for money metrics 2025](https://www.gov.uk/government/publications/value-for-money-metrics-and-reporting-2025) | Tables 10/18/19: Headline Social Housing Cost per unit by segment. Table 9 for the England median. | Annual, Mar |
| `*_GA2025_Datafile_for_Publication.xlsx` | [2025 Global Accounts](https://www.gov.uk/government/publications/2025-global-accounts-of-private-registered-providers) | Sheet "GA2025 Consolidated": cost lines behind HSHC, rents and service charge income, void losses, operating surplus, interest, arrears, debt, bad debt, unit movements. £'000. | Annual, Jan |

### Housing Ombudsman Service

No API, no bulk export. `pipeline/crawler.js` drives the site's own search endpoint month by month and
reconstructs each case's tags from which result sets it appears in. **Decisions are published three months
after the decision date**, so recent months are always incomplete.

Snapshot committed in `data/raw/ho/`. Compensation amounts read from decision text are committed in
`data/derived/ombudsman_compensation.csv` (see `data/derived/README.md`; the reader itself is to be rebuilt).

### MHCLG

`LAHS_open_data_1978-79_to_2024-25.csv` — [Local Authority Housing Statistics open data](https://www.gov.uk/government/statistical-data-sets/local-authority-housing-statistics-open-data).
The council card. Codes decoded from the published form and guidance, never guessed.

### ONS

`lad_dec2024_*.geojson` — Local Authority Districts December 2024 UK BUC from the
[Open Geography Portal](https://geoportal.statistics.gov.uk/). Ultra-generalised and clipped to the
coastline, so the tidal Thames appears as a gap.

### Scottish Housing Regulator

`charter_current.csv` — 2025/26 Charter indicators, 168 landlords. Collected, not yet on the site.

**Licensing.** Crown copyright material under the Open Government Licence v3.0; ONS contains OS data
© Crown copyright and database right 2024. No published reuse terms were found for the Ombudsman's
decisions archive; we hold facts about each decision and a link, not decision text, and credit the Service as
source publisher (not affiliated). Our own derived data is CC BY 4.0 — see `DATA-LICENCE.md`.

---

## 4. The pipeline

```
pipeline/fetch_sources.sh     # re-download the CURRENT official files into data/raw/
pipeline/fetch_snapshot.sh    # or: the exact files the committed data was built from (GitHub release)
pipeline/run.sh               # rebuild data/out/ and site/data.json
```

`run.sh` runs these in order — the order matters, each adds to the spine:

| Script | What it does |
|---|---|
| `build_spine.py` | RSH register + TSMs + stock by LA. Builds the landlord list. |
| `build_layers.py` | Regulatory grades, council stock (LAHS), group roll-up, Scotland. |
| `build_ombudsman.py` | Cases → per-landlord record; merges compensation amounts. |
| `build_vfm.py` | Cost per home (housing associations only) + the lettings account. |
| `build_rents.py` | Average weekly rent per landlord and per borough. |
| `build_lahs.py` | The council card from LAHS. |
| `build_stock.py` | Homes built, bought, sold, demolished (SDR File 16). |
| `build_bundle.py` | `site/data.json` for the map. |
| `build_standalone.py` | `dist/the-housing-record.html`, single-file build. |

Outputs land in `data/out/` as CSVs — inspect those when something looks wrong, before touching the site.

---

## 5. Decisions and gotchas that will bite

**The spine must come from both TSM sheets.** The Regulator sometimes publishes one half of a landlord's
return and withholds the other, saying why in `TSM25_Man_Info_Not_Inc` and `TSM25_Perception_Not_Inc`.
Building from the management sheet alone silently drops those landlords entirely. Take the union of both,
and carry the Regulator's reason through to the card.
*Currently: Tandridge DC (management info withheld), Cannock Chase and Stoke on Trent (perception withheld).*

**Where data is withheld, the summary must not read a clean bill of health out of the gap.** "Not in the
worst 25% on any of the four measures" is false when three of them were withheld.

**LAHS units.** Section H is in pounds. Sections B and F are in **£'000** in the open-data file despite the
form saying pounds — verified against the form's own derived cell `f16c` and against Right to Buy average
prices. Three asserts stop the build if this changes.

**District codes.** The council statistics use `E08000038`/`E08000039` for Barnsley and Sheffield; boundaries
and housing-association returns use `E08000016`/`E08000019`. `build_layers.py` carries the alias and
`build_bundle.py` asserts every LA has a boundary, so a code change fails loudly.

**Predecessor bodies.** Mergers, ALMOs wound back into councils and abolished authorities keep their old
registration codes, and their Ombudsman history sits under them. `build_ombudsman.py` holds a `SUCCESSOR`
map. **Check this after every merger** — without it a landlord's record silently understates itself.
*Currently mapped: Southern Housing Group → Southern Housing; Longhurst → Amplius; Trafford HT → L&Q;
Nottingham City Homes → Nottingham City Council; Kirklees and Greenwich (two codes each); Derwent and
Chorus → Places for People; Stonewater (2) → Stonewater; Severnside → Housing Plus; Harrogate → North Yorkshire.*

**Intra-group transfers are not new homes.** A subsidiary selling to its parent is real for the subsidiary
and invisible for the group. Kept apart as a single net line after roll-up.

**Ombudsman-only landlords.** 96 landlords have published determinations but file none of the Regulator's
returns, because under 1,000 homes there is no requirement to. They are searchable with a card of their own
and an explicit explanation. They carry **no map dot** — the stock-by-borough return that places dots is
filed only by landlords in the current returns, so where their homes are is not published.

**HSHC reconciliation.** The Regulator's own formula reproduces its published figure to the pound for 162 of
190 providers and within 1% for 172. Where the parts don't reconcile, the card shows the headline alone and
says so.

**LAHS Section I is unusable as a borough supply total.** The guidance states questions 3–5 "should only
include those dwellings not reported to HE or the GLA". Housing-association building is not published by
borough at all.

---

## 6. Compensation ordered — read with care

The Ombudsman's dataset records *that* a compensation order was made, not how much. Amounts exist only in
the prose of each decision. They are read from the "Orders" section of all 13,341 decisions that have one.

**The parser refuses rather than guesses:**

- everything after a breakdown marker ("made up as follows", "which includes", "comprising", "of which",
  "broken down as") is components of a total already counted, never an addition;
- clauses that *refer* to money rather than order it are dropped ("this replaces its previous offer of £200",
  "this sum includes the £380 offered at stage 2", "does not include the £440");
- a decision is **quarantined with no figure** where a stated total and its breakdown do not reconcile, or
  where the award is a weekly calculation.

**Results:** 10,925 of 12,861 parsed (£11.8m); 1,299 quarantined; 637 no monetary order. Hand-checked
against 13 decisions — 12 exact, the 13th quarantined rather than wrong.

**Roughly one decision in eight is excluded by design, so the figure is a floor.** The card must always read
*"at least £X, read from N of M decisions"* and must never call it a total.

---

## 7. Update playbook

### Calendar

| When | What | Action |
|---|---|---|
| Monthly | Register of providers; regulatory judgements | Re-download, re-run. Check the `SUCCESSOR` map for new mergers. |
| Rolling | Ombudsman decisions | Re-crawl with `crawler.js` (~35 min discovery + ~10 min detail, from a browser). Then re-run the compensation pass. |
| Jan | Global Accounts | New datafile → re-run `build_vfm.py`. |
| Mar | Value for Money metrics | New tables → check sheet names, re-run. |
| Oct | SDR (stock and rents) | New zip → check File numbering hasn't shifted. |
| Nov | Tenant Satisfaction Measures | **The big one.** New year of data; see below. |

### The annual TSM update

1. Add the new file to `fetch_sources.sh`; run it.
2. In `build_spine.py`, add a `build_tsm()` line for the new year and shift `tsm_year` / `tsm_prev`.
3. **Check the "Not Inc" sheet names** — they follow `TSM26_Man_Info_Not_Inc` style and will change.
4. Run `pipeline/run.sh`. Watch for assert failures — they are the safety net, not noise.
5. Compare landlord count against the Regulator's own coverage sheet. A drop means someone fell out of the
   spine; find out why before shipping.

### Before shipping anything

- [ ] `run.sh` completes with no assert failures
- [ ] Landlord count matches the Regulator's coverage sheet
- [ ] Spot-check three landlords against the source file by hand
- [ ] Any new parsed figure hand-verified against at least 10 real records
- [ ] No figure shown where the underlying data was withheld
- [ ] `node --check` on the site's script block
- [ ] Load locally, open a full card, an Ombudsman-only card and a borough card

### Deploy

Every change goes through a pull request (see `CONTRIBUTING.md`). Vercel builds a preview for each one;
the automated checks run; the maintainer reviews and merges. Merging to `main` deploys to housingrecords.org
in about two minutes. Verify at `housingrecords.org/?v=N` with a fresh `v`. Never upload files straight to
`main`.

---

## 8. The ask-anything feature

`api/ask.js` — a model with query tools over the bundle. Its system prompt carries the same rules, absolutely:

1. Every number must come from a tool result in that conversation. Never from memory.
2. Call tools before answering. Only say a figure is not on the record *after* the relevant tool has returned
   without it.
3. The data records **what**, not **why**. When asked why, describe the pattern precisely, then say the record
   does not hold causes. Never speculate.
4. Cost is a cost, not a grade.

Tools: `rank_landlords`, `rank_figures`, `get_landlord`, `get_borough`, `region_summary`, `england_summary`,
`compare_landlords`.

**Test it after every data change.** The failure mode is silent: the model says "I don't know" when the data
is right there but no tool returns it.

---

## 9. How positions are calculated

- `betterThan(vals, v, higherBetter)` — share of landlords this one beats, ties split down the middle.
- `bandOfPct(p)` — `p<0.10` bad (red), `p<0.25` poor (orange), `p<0.75` mid, else good (green).
- Safety checks are banded absolutely, not relatively: `≥99.95%` good, `≥99%` mid, `≥95%` poor, below that
  bad. **The standard is 100%** — a relative band would let the whole sector drift.
- Grades map `C1/G1/V1` good → `C4/G4/V4` bad.
- The four headline measures: safety checks in date, homes failing the Decent Homes Standard, repairs on
  time, Ombudsman findings per 10,000 homes.

---

## 10. Identified but not yet used

| Source | Why it matters | What it needs |
|---|---|---|
| [Domestic EPC bulk data](https://get-energy-performance-data.communities.gov.uk/) | Address-level footprint of social homes — the basis of a building-level map | A GOV.UK One Login account |
| [Land Registry CCOD](https://use-land-property-data.service.gov.uk/datasets/ccod) | Which company owns which title — attributes blocks to landlords | Free account, licence acceptance |
| [High-rise building register](https://www.register-high-rise-building.service.gov.uk/public-register/search) | 18m+ buildings, height, storeys, accountable person — the Grenfell-shaped layer | Postcode-by-postcode; no bulk download |
| [Fire statistics incident data](https://www.gov.uk/government/statistics/fire-statistics-incident-level-datasets) | Dwelling fires by property type and height band | Nothing — ODS download |
| Landlords' annual complaints reports | Required since 2024 by the Complaint Handling Code; published on ~1,600 separate websites | A crawler |
| Scotland | `charter_current.csv` already collected, 168 landlords | A card design for a different regulator's measures |
| Wales | Regulatory judgements exist per landlord | No single performance dataset located yet |

---

## 11. Known angles in the data

Re-verified against source files. Useful for press, and worth re-checking each update.

- **Statutory safety checks short of 100%** — 62 instances below 90% across the record, where the standard is
  100% in every case. Adur legionella 0%; Castle Point asbestos 0%; Winchester asbestos 0% and fire risk
  21.9%; Sandwell asbestos 34.1% (27,717 homes); North Tyneside lifts 41.6% (13,942 homes).
- **Decent Homes figures resting on almost no inspection** — 23 councils covering 270,910 homes report a
  non-decency figure having inspected under a quarter of their stock in five years; 3 published a figure
  having inspected none. **Pitch as a standard measured unevenly, never as concealment** — councils
  inspecting least report slightly *more* non-decency (4.1% vs 2.7% median).
- **Where the year's social homes went** — net gain 27,045; councils −229 with 89 of 159 shrinking; 7,601
  sold under Right to Buy; 4,752 sold out of social housing entirely; 42 of 200 associations ended smaller.
- **Severe maladministration, concentrated** — L&Q 16 of 1,151 cases; Southern Housing 9 of 578; Lambeth 8
  of 357; Peabody 8 of 711; Haringey 7 of 202.
- **£11.8m of compensation ordered** across 10,925 decisions, and that is a floor. Nobody has published this
  before, because the Ombudsman only publishes amounts one decision at a time.

When a named landlord disputes any of these, the answer is the same and it is strong: *this is the figure you
reported to your regulator, and here is the file.*
