"""Turn the Housing Ombudsman crawl dumps (raw/ho/*.json) into cases.csv and per-landlord aggregates,
matching Ombudsman landlord names to RSH registration codes.

Each dump is {cases:{id:{id,landlord,ltype,occ,date,dtype,href}}, tags:{'outcome:x':[ids], 'category:y':[ids], 'order:z':[ids], 'month:YYYY-MM':[ids]}}
"""
import glob, gzip, json, re
import pandas as pd

from paths import RAW, OUT, DERIVED

cases, tags = {}, {}
for f in sorted(glob.glob(RAW + "ho/*.json")) + sorted(glob.glob(RAW + "ho/*.json.gz")):
    opener = gzip.open if f.endswith(".gz") else open
    with opener(f, "rt") as fh:
        d = json.load(fh)
    for cid, c in d["cases"].items():
        ex = cases.setdefault(cid, c)
        for k in ("ltype", "occ", "date", "dtype"):
            if not ex.get(k) and c.get(k):
                ex[k] = c[k]
    for name, ids in d["tags"].items():
        tags.setdefault(name, set()).update(ids)

df = pd.DataFrame(cases.values())
df["case_id"] = df["id"]
# month from the month: buckets (exact date only present for recent cases)
month = {}
for name, ids in tags.items():
    if name.startswith("month:"):
        for i in ids:
            month[i] = name[6:]
df["month"] = df.case_id.map(month)
df["date"] = pd.to_datetime(df["date"], format="%d %B %Y", errors="coerce")
df["month"] = df["month"].fillna(df["date"].dt.strftime("%Y-%m"))
for prefix, col in (("outcome:", "outcomes"), ("category:", "categories"), ("order:", "orders")):
    m = {}
    for name, ids in tags.items():
        if name.startswith(prefix):
            for i in ids:
                m.setdefault(i, []).append(name[len(prefix):])
    df[col] = df.case_id.map(lambda i: "|".join(sorted(m.get(i, []))))
sev = {"severe-maladministration": 4, "maladministration": 3, "partial-maladministration": 2, "reasonable-redress": 1, "no-maladministration": 0}
df["worst_outcome"] = df.outcomes.map(lambda s: max((o for o in s.split("|") if o in sev), key=sev.get, default=None))
df["any_maladministration"] = df.outcomes.str.contains("maladministration") & ~df.outcomes.str.fullmatch("no-maladministration")
df["severe"] = df.outcomes.str.contains("severe-maladministration")

# --- landlord name -> RSH registration code
prov = pd.read_csv(OUT + "registered_providers.csv")
spine = pd.read_csv(OUT + "landlord_spine_2024_25.csv")

def norm(s):
    s = str(s).lower().replace("&", " and ")
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"\b(limited|ltd|the|plc|cic|c\.i\.c\.|llp|housing association|association|group|trust|homes|housing|society|london borough of|royal borough of|borough of|city of|council|metropolitan|borough|district|city|county|of|corporation|mbc|bc|dc|cc|ha)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return " ".join(s.split())

names = pd.concat([
    prov[["reg_number", "org_name"]].rename(columns={"reg_number": "code", "org_name": "name"}),
    spine[["landlord_code", "landlord_name"]].rename(columns={"landlord_code": "code", "landlord_name": "name"}),
]).drop_duplicates()
names["k"] = names.name.map(norm)
exact = dict(zip(names.name.str.lower().str.strip(), names.code))
fuzzy = {}
for k, c in zip(names.k, names.code):
    fuzzy.setdefault(k, c)  # first wins; collisions reviewed below

ll = df.groupby("landlord").size().rename("cases").reset_index()
ll["k"] = ll.landlord.map(norm)
ll["code"] = ll.landlord.str.lower().str.strip().map(exact).fillna(ll.k.map(fuzzy))
ll["match"] = ll.code.notna().map({True: "auto", False: "unmatched"})
# manual aliases for frequent unmatched names (edit this dict as the alias table grows)
MANUAL = {  # merged / renamed landlords: Ombudsman name -> current RSH code (successor body)
    "Sovereign Housing Association Limited": "4837", "Network Homes Limited": "4837", "Haringey Council": "00AP",
    "Peabody Trust 2018": "4878", "Peabody Enterprises Limited": "4878", "London & Quadrant H T": "L4517",
    "Karbon Homes Limited inc Byker Community Trust": "4846", "Whitefriars Housing Group Limited": "5075",
    "Victory Housing Trust": "4651", "Somerset West and Taunton Council": "5178", "Sedgemoor District Council": "5178",
    "Selby District Council": "5179", "Twenty11 Homes Ltd": "4682", "GreenSquare Group Limited": "LH3902",
}
ll["code"] = ll.code.astype(object).where(ll.code.notna(), ll.landlord.map(MANUAL))
ll.loc[ll.landlord.isin(MANUAL), "match"] = "manual"
# roll subsidiaries up to the parent that reports TSMs (e.g. Clarion Housing Association -> Clarion Housing Group)
g = pd.read_csv(glob.glob(RAW + "rsh/prp/*/*File 02 - Group Information.csv")[0], encoding="latin1", header=3, dtype=str)
g = g.rename(columns={"PRP registration number": "code", "Registered Parent's code": "parent"})[["code", "parent"]].dropna().drop_duplicates()
pmap = {c: p for c, p in zip(g.code, g.parent) if p in set(spine.landlord_code)}
in_spine = set(spine.landlord_code)
ll["code"] = ll.code.map(lambda c: pmap.get(c, c) if isinstance(c, str) and c not in in_spine else c)
# Predecessor bodies keep their old registration codes after a merger, an ALMO being taken back in-house or
# an authority being abolished, and their Ombudsman history sits under those codes. Attribute it to the body
# that holds those homes now, or the successor's record silently understates itself. CHECK AFTER EVERY MERGER.
SUCCESSOR = {
    "L4628": "5171",   # Southern Housing Group -> Southern Housing
    "L4277": "5060",   # Longhurst Group -> Amplius
    "5186": "L4517",   # Trafford Housing Trust -> London & Quadrant
    "4862": "00FY",    # Nottingham City Homes (registered provider) -> Nottingham City Council
    "4735": "00CZ",    # Kirklees Council (second code) -> Kirklees Metropolitan Borough Council
    "L0308": "00AL",   # Greenwich Council (second code) -> Royal Borough of Greenwich
    "L0715": "L4236",  # Derwent Housing Association -> Places for People
    "L4398": "L4236",  # Chorus Homes Group -> Places for People
    "L0173": "L1556",  # Stonewater (2) -> Stonewater
    "LH4325": "L4491", # Severnside Housing -> The Housing Plus Group
    "L2188": "5179",   # Harrogate Borough Council -> North Yorkshire Council
}
ll["code"] = ll.code.map(lambda c: SUCCESSOR.get(str(c), c) if isinstance(c, str) or not pd.isna(c) else c)
ll.sort_values("cases", ascending=False).to_csv(OUT + "ombudsman_landlord_aliases.csv", index=False)
df = df.merge(ll[["landlord", "code"]], on="landlord", how="left").rename(columns={"code": "landlord_code"})

df = df[["case_id", "landlord", "landlord_code", "ltype", "occ", "dtype", "date", "month", "outcomes", "worst_outcome", "any_maladministration", "severe", "categories", "orders", "href"]]
df.to_csv(OUT + "ombudsman_cases.csv", index=False)

# per-landlord aggregates, last 12 complete months and all-time
# Compensation amounts: the Ombudsman publishes THAT compensation was ordered, but the amount only in the
# text of each decision. data/derived/ombudsman_compensation.csv holds one row per decision with an order:
# status "parsed" (total in pounds, 0 where no monetary order) or "quarantined" (no figure, by design).
comp = pd.read_csv(DERIVED + "ombudsman_compensation.csv")
parsed = comp[comp.status == "parsed"].set_index("case_id").total
df["comp_total"] = df.case_id.astype(int).map(parsed)
df["ym"] = pd.to_datetime(df.month, format="%Y-%m", errors="coerce")
recent = df[df.ym >= (df.ym.max() - pd.DateOffset(months=12))]
def agg(x):
    return pd.Series({
        "ho_cases": len(x), "ho_maladministration": int(x.any_maladministration.sum()), "ho_severe": int(x.severe.sum()),
        "ho_maladministration_rate": round(x.any_maladministration.mean() * 100, 1) if len(x) else None,
        "ho_repairs_cases": int(x.categories.str.contains("responsive-repairs").sum()),
        "ho_health_safety_cases": int(x.categories.str.contains("health-and-safety").sum()),
        "ho_compensation_orders": int(x.orders.str.contains("compensation").sum()),
        "ho_compensation_sum": round(float(x.comp_total.sum()), 2),   # a floor: quarantined decisions add nothing
        "ho_compensation_known": int(x.comp_total.notna().sum()),
    })
a_all = df.dropna(subset=["landlord_code"]).groupby("landlord_code").apply(agg).add_suffix("_all")
a_12 = recent.dropna(subset=["landlord_code"]).groupby("landlord_code").apply(agg).add_suffix("_12m")
out = a_all.join(a_12, how="left").fillna(0).reset_index()
out.to_csv(OUT + "ombudsman_by_landlord.csv", index=False)
# what the Ombudsman ordered, all-time, per landlord: {order type: number of decisions}
o = df.dropna(subset=["landlord_code"]).assign(order=df.orders.fillna("").str.split("|")).explode("order")
o = o[o.order.astype(bool)].groupby(["landlord_code", "order"]).size().rename("n").reset_index()
o.to_csv(OUT + "ombudsman_orders_by_landlord.csv", index=False)
# --- attach to the spine, with per-10,000-homes rates on the homes_estimate basis
spine = spine.drop(columns=[c for c in spine.columns if c.startswith("ho_")]).merge(out, on="landlord_code", how="left")
for c in [c for c in spine.columns if c.startswith("ho_") and not c.endswith("rate_all") and not c.endswith("rate_12m")]:
    spine[c] = spine[c].fillna(0)
for w in ("all", "12m"):
    spine[f"ho_cases_per_10k_{w}"] = (spine[f"ho_cases_{w}"] / spine.homes_estimate * 1e4).round(1)
    spine[f"ho_maladministration_per_10k_{w}"] = (spine[f"ho_maladministration_{w}"] / spine.homes_estimate * 1e4).round(1)
spine.to_csv(OUT + "landlord_spine_2024_25.csv", index=False)

matched = df.landlord_code.notna().mean()
print(f"cases {len(df)}, landlords {df.landlord.nunique()}, matched to a registration code: {matched:.1%} of cases; "
      f"{(ll.match=='unmatched').sum()} landlord names unmatched (see ombudsman_landlord_aliases.csv)")
