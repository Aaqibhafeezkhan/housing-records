# Sources

Every input, where it comes from, and what the pipeline takes from it. All files were downloaded on
**10 September 2026**; `pipeline/fetch_sources.sh` re-downloads them from these exact URLs.

Asset URLs on `assets.publishing.service.gov.uk` are versioned and change when a publication is
updated — if one 404s, open the landing page in the second column and take the current link.

## Regulator of Social Housing (England)

| File | Landing page | What we take | Cadence |
|---|---|---|---|
| `rsh/List_of_registered_providers_17_August_2026.xlsx` | [Registered providers of social housing](https://www.gov.uk/government/publications/registered-providers-of-social-housing) | The canonical register: name, registration number, designation, legal form. The key everything else joins on. | Monthly, mid-month |
| `rsh/2025_TSM_Full_Data_v1.1_FINAL.xlsx` | [Tenant Satisfaction Measures 2024/25](https://www.gov.uk/government/statistics/tenant-satisfaction-measures-202425) | 22 measures per landlord: 12 tenant-perception, 10 management-information (safety checks, non-decent homes, repairs, complaints, ASB). | Annual, November |
| `rsh/2024_TSM_Full_Data_v2.1_FINAL.xlsx` | [Data release TSM 2024](https://www.gov.uk/government/statistics/data-release-tsm-2024) | The same measures for 2023/24, for year-on-year change. | — |
| `rsh/PRP_Data_Release_2025_Full_Data_FINAL_V1.1.zip` | [PRP stock and rents 2024/25](https://www.gov.uk/government/statistics/private-registered-provider-social-housing-stock-and-rents-in-england-2024-to-2025) | File 04 (stock by local authority, per provider) and File 02 (group structure, for rolling subsidiaries up to parents). Files 09 and 10: average weekly net rent (52-week basis, excluding service charges, Affordable Rent, intermediate rent and historic arrangements) and units, per provider per local authority, for general needs and for supported housing/housing for older people; also the average service charge eligible for housing benefit. Weighted by units to a landlord figure and to a borough figure; a landlord's premium or discount is computed only against the other landlords in the same boroughs. File 16 (low cost rental stock balance sheet): units brought forward, new build, purchases from other landlords, other gains, sales to tenants, sales to other social landlords, sales out of social housing, conversions to shared ownership, demolitions, other losses and expected year-end stock, per provider; intra-group transfers kept apart as a single net line after roll-up. | Annual, October |
| `rsh/GEO_PRP_TOOL_2025_FINAL_V1.0.xlsx` | same | Cross-check on the stock-by-area figures. Not read by the pipeline. | Annual |
| `rsh/20260909_RegulatoryJudgementsNotices_Published.xlsx` | [Regulatory judgements and enforcement notices](https://www.gov.uk/government/publications/regulatory-judgements-and-enforcement-notices) | Consumer (C1–C4), governance (G1–G4) and viability (V1–V4) grades with dates; the Regulator's own description of what moved at the latest judgement (upgrade, downgrade, regrade), the engagement route (inspection, stability check, responsive engagement), publications marked "Grading Under Review", and the "Enforcement Notices" sheet. | At least monthly |
| `rsh/2026-02-11_1231_VFM_Metrics_tables.xlsx` | [Value for money metrics and reporting 2025](https://www.gov.uk/government/publications/value-for-money-metrics-and-reporting-2025) (annex to the 2024 Global Accounts; year ending March 2025) | Tables 10, 18 and 19: Headline Social Housing Cost per unit for every private registered provider in the Global Accounts, 2024 and 2025, by name; split into general needs, supported housing and housing for older people. Table 9 for the Regulator's own England median. Downloaded 13 Sep 2026. Councils are not in scope of the Global Accounts. | Annual, March |
| `rsh/20251211_GA2025_Datafile_for_Publication.xlsx` | [2025 Global Accounts of private registered providers](https://www.gov.uk/government/publications/2025-global-accounts-of-private-registered-providers) | Sheet "GA2025 Consolidated": every provider's financial return by RP code, £'000. We take the social housing lettings cost lines (management, service charge costs, routine and planned maintenance, major repairs expensed and capitalised, other costs, lease costs), other social-housing activity operating expenditure, and social homes owned or managed — the Regulator's own HSHC formula, which reproduces its published figure to the pound for most providers. Also from the same sheet: rents and service charge income, void losses, operating surplus on social housing lettings, interest payable, gross current-tenant arrears (shown as a share of the year's rent and service charge income), short- and long-term debt (per home owned or managed), the bad-debt charge (per home), and the year's social housing unit movements. Downloaded 13 Sep 2026. | Annual, January |

Crown copyright, licensed under the Open Government Licence v3.0.

## Housing Ombudsman Service

| File | Source | What we take |
|---|---|---|
| `ho/ho_dump_months_cats_orders.json.gz`, `ho/ho_crawl_outcomes.json.gz` | [Decisions archive](https://www.housing-ombudsman.org.uk/decisions/), crawled 10 Sep 2026 with `pipeline/crawler.js` | All 18,123 published determinations: case ID, landlord, landlord type, tenure, decision month, outcome, complaint categories, orders, link. |

There is no API or bulk export. The crawler drives the site's own search endpoint, one filter at a time,
and reconstructs each case's tags from which result sets it appears in. Decisions are published three
months after the decision date, so the most recent months are always incomplete.

The Service is credited as the source publisher and is not affiliated with this project. We could not find
published reuse terms for the decisions archive; the repository holds facts about each decision and a link to
it, not the text of decisions (see `DATA-LICENCE.md`).

| File | Source | What we take |
|---|---|---|
| `derived/ombudsman_compensation.csv` (committed) | The "Orders" section of each of the 12,861 decisions with a compensation order, read September 2026 | The amount ordered, or a refusal to give one. A floor, never a total. See `data/derived/README.md`. |

## MHCLG

| File | Landing page | What we take |
|---|---|---|
| `mhclg/LAHS_open_data_1978-79_to_2024-25.csv` | [Local Authority Housing Statistics open data](https://www.gov.uk/government/statistical-data-sets/local-authority-housing-statistics-open-data) | Field `a1a` for 2024-25: dwellings owned by each council. Gives council landlords a homes figure and puts council stock on the map. Also the council card (build_lahs.py): `a2ia` homes owned; `a4a/a4c/a4d` demolished, built, acquired; `b1a`, `b2aa–b2ac`, `b2fa` Right to Buy applications, sales, receipts, discounts and total sales; `e2dc`, `e2cc` empty homes and those empty over six months; `f14e`, `f16a–f16c`, `f16e–f16f`, `f17a` Decent Homes cost, count, inspection coverage and share; `f25ab–f25ac` capital works spend and homes receiving works; `g1a`, `g2a`, `g2aa` re-let days and evictions; `h5a`, `h8a`, `h9a`, `h11a`, `h12a`, `h14a` current arrears, write-offs, rent roll, void loss, rent collectable and collection rate. Codes decoded from the 2024-25 LAHS form and guidance (`mhclg/2024-25_LAHS_form.xlsx`, `mhclg/LAHS_Guidance_2024-25.pdf`, both from [Completing LAHS 2024 to 2025](https://www.gov.uk/government/publications/completing-local-authority-housing-statistics-2024-to-2025-guidance-notes-and-bulk-upload)). Money in section H is in £; in sections B and F the open-data file is in £'000, verified against the form's derived cell `f16c` and against Right to Buy average prices — the build stops if either check fails. |

Crown copyright, Open Government Licence v3.0.

## Office for National Statistics

| File | Source | What we take |
|---|---|---|
| `ons/lad_dec2024_uk_buc.geojson` | [ONS Open Geography Portal](https://geoportal.statistics.gov.uk/), Local Authority Districts December 2024 UK BUC | Boundaries for all 361 UK districts. England's 296 carry data; Scotland, Wales and Northern Ireland are drawn greyed. Ultra-generalised and clipped to the coastline, so the tidal Thames appears as a gap. |

Contains OS data © Crown copyright and database right 2024; ONS licensed under the Open Government Licence v3.0.

## Scottish Housing Regulator

| File | Landing page | What we take |
|---|---|---|
| `shr/charter_current.csv` | [Statistical information](https://www.housingregulator.gov.scot/landlord-performance/statistical-information/) | 2025/26 Scottish Social Housing Charter indicators for all 168 Scottish landlords. Collected; not yet on the site. |

### A note on district codes

Three sources disagree about two districts: the council statistics use `E08000038`/`E08000039` for
Barnsley and Sheffield, while the boundaries and the housing-association returns use
`E08000016`/`E08000019`. `build_layers.py` carries the alias, and `build_bundle.py` asserts that every
local authority has a boundary, so a future code change fails loudly instead of silently emptying a
borough.

## Identified but not yet used

| Source | Why it matters | What it needs |
|---|---|---|
| [Domestic EPC bulk data](https://get-energy-performance-data.communities.gov.uk/) | Address-level footprint of social homes (`tenure = rental (social)`) — the basis of a building-level map. | A GOV.UK One Login account |
| [HM Land Registry CCOD](https://use-land-property-data.service.gov.uk/datasets/ccod) | Which company owns which title — attributes blocks to landlords. Monthly. | A free account and licence acceptance |
| [High-rise residential building register](https://www.register-high-rise-building.service.gov.uk/public-register/search) | 18m+ buildings, height, storeys, accountable person. The Grenfell-shaped layer. | Postcode-by-postcode search; no bulk download |
| [Fire statistics incident-level data](https://www.gov.uk/government/statistics/fire-statistics-incident-level-datasets) | Dwelling fires by property type, including purpose-built flats by height band. | Nothing — ODS download |
| Landlords' own annual complaints reports | Required since 2024 by the statutory Complaint Handling Code, published on ~1,600 separate websites. | A crawler |
| Wales | Regulatory judgements exist per landlord; no single performance dataset located yet. | Investigation |
