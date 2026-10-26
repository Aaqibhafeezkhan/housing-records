# Data licence

There are two kinds of data in this repository, under two licences. The code is separate and is under the
MIT licence in [`LICENSE`](LICENSE).

## 1. Data published by public bodies — Open Government Licence v3.0

Almost every figure starts life in a file published by a public body: the Regulator of Social Housing, the
Ministry of Housing, Communities and Local Government (MHCLG), the Office for National Statistics and the
Scottish Housing Regulator. That information is Crown copyright and is reused under the
[Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

If you reuse it, keep its attribution:

- Contains public sector information licensed under the Open Government Licence v3.0.
- Contains OS data © Crown copyright and database right 2024 (district boundaries, via ONS).

Each source, file and download date is listed in [`data/SOURCES.md`](data/SOURCES.md).

### Housing Ombudsman Service

The Housing Ombudsman Service publishes its decisions on its website one at a time. We could not find a
published statement of reuse terms for that material. The repository holds only facts about each published
decision — case number, landlord, month, outcome, complaint categories, the types of order made and a link to
the decision — and amounts of compensation read from the decisions' "Orders" sections (see below). It does not
republish the text of decisions. The Service is credited as the source publisher and is not affiliated with
this project.

## 2. What this project worked out — Creative Commons Attribution 4.0

The joined tables, positions, rankings, scores, per-10,000-homes rates and the compensation amounts read from
decision text are this project's own work, built from the sources above. They are released under
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).

That covers, in particular:

- `data/out/*.csv` and `site/data.json`
- `data/derived/ombudsman_compensation.csv`

You may copy, adapt and republish them for any purpose, including commercially, as long as you credit
**Housing Records (housingrecords.org)**, say if you changed anything, and keep the public-sector attribution
from section 1 alongside.

Please carry the project's rules with the data: a missing figure is not a zero or a clean record; cost per home
and rent are not grades; and the compensation figures are a floor (see
[`data/derived/README.md`](data/derived/README.md)), never a total.

This is not legal advice. If you are unsure whether a particular reuse is allowed, check the original
publisher's terms.
