# Housing Records

**[housingrecords.org](https://housingrecords.org)** — a free, non-profit public record of every large social
landlord in England: what the Regulator, the Housing Ombudsman and tenants themselves say about each one, on a
single map, in plain English.

Social housing data exists, but it is scattered across several public bodies, published as spreadsheets and
one-page-at-a-time decisions, and organised for regulators rather than for the people who live in the homes.
This project joins it together, keyed to each landlord, and presents it plainly. Every figure on the site comes
from a published official source, named beneath it.

This repository holds everything: the data pipeline, the joined tables, the website and the "ask anything"
feature. You are welcome to check the method, reuse the data and help improve it.

## The rules

These override everything else. A change that breaks one is a bug, however good it looks.

1. **Never fabricate a figure.** Every number traces to a published source. Nothing is modelled, estimated or
   filled in.
2. **Where data is missing or withheld, say why.** A blank is never a zero, and never a clean record.
3. **Cost and rent are never grades.** They are shown and compared, never coloured good or bad.

[`METHOD.md`](METHOD.md) has the full method, the rest of the rules and every known gotcha. Read it before
changing anything that touches a figure.

## What's on the record

| | |
|---|---|
| 360 | landlords with 1,000+ social homes in England — 200 housing associations and 160 councils — each with up to 22 Tenant Satisfaction Measures for two years |
| 96 | smaller landlords with Ombudsman decisions but no Regulator returns, shown with whatever is published |
| 18,123 | Housing Ombudsman decisions, December 2020 to August 2026, tagged by outcome, category and order |
| 289 | landlords with a published regulatory grade |
| 296 | English districts, with council and housing-association homes (all 361 UK districts are drawn) |
| 8,434 | landlord holdings — one map dot each: a landlord's homes in one borough |

## How it fits together

```
data/raw/        official downloads (not committed; fetched by a script) + the Ombudsman crawl snapshot
data/derived/    figures we worked out from published text, e.g. compensation amounts (committed)
   │
   │   pipeline/run.sh runs, in order:
   │   build_spine → build_layers → build_ombudsman → build_vfm → build_rents
   │   → build_lahs → build_stock → build_bundle → build_standalone
   ▼
data/out/*.csv   the joined tables — the reusable public good (committed)
site/data.json   what the map reads (committed)
   ▼
site/            the website Vercel serves
api/ask.js       the "ask anything" feature (a Vercel serverless function)
```

The hard part is joining the sources, not finding them. Different bodies name the same landlord in different
ways, and only the Regulator's registration code is stable. `build_ombudsman.py` carries the alias table and
the map of merged and renamed landlords; `data/out/ombudsman_landlord_aliases.csv` lists every name and how it
was matched.

## Running it yourself

You need Python 3.10+ and, for the "ask anything" feature, Node 20+.

```bash
pip install -r requirements.txt
bash pipeline/fetch_sources.sh   # downloads the official files into data/raw/ (about 60 MB)
bash pipeline/run.sh             # rebuilds data/out/, site/data.json and dist/
python3 -m http.server --directory site 8000    # then open http://localhost:8000
```

`data/raw/` is not committed: the files are large and can be downloaded again from the official sources listed
in [`data/SOURCES.md`](data/SOURCES.md). Government download links change when a publication is updated; if one
fails, the landing page in `SOURCES.md` has the current link. Once a year a dated copy of the raw files
will be attached to a GitHub release, so older figures can always be checked.

The Ombudsman snapshot in `data/raw/ho/` **is** committed, because the Ombudsman has no bulk download and a later
crawl is a different dataset. Re-crawling takes about 45 minutes with `pipeline/crawler.js`, run from a browser.

### The "ask anything" feature

Type a question into the search box and `api/ask.js` answers it. A language model is given query tools over
`site/data.json` and may only use numbers those tools return. It is told the data records what happened, not
why, and must say so when asked why.

It needs these settings on the Vercel project. The site works without them; only the question box does not.

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Required for the feature. Set for Production only, never for previews. |
| `ASK_MODEL` | Optional. Which model to use. |
| `ASK_DAILY_CAP` | Optional. Questions per day per server instance; default 200. |

There is also a limit of eight questions a minute per visitor.

## Deploying

The site deploys automatically to Vercel when a change is merged into `main`. The output directory is `site/`
(see `vercel.json`); there is no build step. Every pull request gets its own preview link. See
[`CONTRIBUTING.md`](CONTRIBUTING.md) for how changes get made.

## Known limits

- **Landlord-level, not building-level.** No official source says which landlord owns which block, so a dot
  marks a landlord's homes in a borough, not a building at a real address.
- **Tenant Satisfaction Measures are self-reported** by landlords. The site shows them next to the Ombudsman's
  independent findings for that reason.
- **Compensation figures are a floor.** About one decision in eight is deliberately left without a figure
  because its wording was ambiguous. See [`data/derived/README.md`](data/derived/README.md).
- **England only for now.** Scotland's data is collected but not yet on the site; Wales is not yet covered.

## Contributing

Corrections, new sources and code are all welcome — see [`CONTRIBUTING.md`](CONTRIBUTING.md). If a figure looks
wrong, please [open an issue](../../issues/new/choose) with a link to the source.

## Licences

- **Code:** MIT — see [`LICENSE`](LICENSE).
- **Data:** public-sector source data is under the Open Government Licence v3.0; the tables and figures this
  project worked out are CC BY 4.0 — see [`DATA-LICENCE.md`](DATA-LICENCE.md).

Housing Records is independent. It is not affiliated with, endorsed by or acting for the Regulator of Social
Housing, the Housing Ombudsman Service, MHCLG or any landlord.

Contact: [hello@housingrecords.org](mailto:hello@housingrecords.org)
