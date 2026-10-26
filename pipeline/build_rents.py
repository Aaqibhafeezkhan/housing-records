"""What tenants pay: average weekly rent per housing association, from the Regulator's Statistical Data Return.

Source: RSH "Private registered provider social housing stock and rents in England 2024 to 2025" full data
release (SDR), File 09 (general needs, all providers of 1,000+ homes, by local authority) and File 10
(supported housing and housing for older people). Each row is one provider in one local authority with the
number of units and the average weekly NET rent (52-week basis, excluding service charges, and excluding
Affordable Rent, intermediate rent and units under historic arrangements).

Rent is not a grade either. Social rents follow a national formula built on local earnings and property
values, so a London landlord charges more than a Yorkshire one whatever it does. The only fair comparison
is inside the same borough, and that is what this step prepares: each landlord's rent in each borough
next to the units-weighted average for every landlord in that borough. A landlord-wide figure is kept for
the card's headline, weighted by the units behind it and rolled up to the parent that reports TSMs.

Councils are not in the SDR; their rents come from LAHS where that step exists.
"""
import glob

import numpy as np
import pandas as pd

from paths import OUT, RAW

F = glob.glob(RAW + "rsh/prp/*/*File 09 - GN rents combined.csv")[0]
S = glob.glob(RAW + "rsh/prp/*/*File 10 - SHHOP rents comb.csv")[0]
G = glob.glob(RAW + "rsh/prp/*/*File 02 - Group Information.csv")[0]

def col(df, prefix, what, size):
    c = [c for c in df.columns if c.startswith(prefix) and what in c and c.endswith(" - " + size)]
    assert len(c) == 1, (what, size, c)
    return c[0]

gn = pd.read_csv(F, encoding="latin1", header=3)
P = "Combined general needs"
UNITS, RENT, SVC = "Total units/bedspaces (excluding IR, AR and HIST)", "Average weekly NET rent", "Average service charge eligible for HB / UC"
gn = gn.rename(columns={"PRP registration number": "code", "LA code": "la_code", "Local Authority name": "la_name"})
for size, suf in (("All units", ""), ("One bedroom", "_1"), ("Two bedrooms", "_2"), ("Three bedrooms", "_3")):
    gn["units" + suf] = pd.to_numeric(gn[col(gn, P, UNITS, size)], errors="coerce")
    gn["rent" + suf] = pd.to_numeric(gn[col(gn, P, RENT, size)], errors="coerce")
gn["svc"] = pd.to_numeric(gn[col(gn, P, SVC, "All units")], errors="coerce")
gn["svc_n"] = pd.to_numeric(gn[col(gn, P, "Number of units/bedspaces with service charges eligible for HB / UC", "All units")], errors="coerce")
gn = gn[gn.la_code.astype(str).str.startswith("E") & (gn.units > 0) & gn.rent.notna()]

# roll subsidiaries up to the parent that appears on the map (same rule as the stock table)
spine = pd.read_csv(OUT + "landlord_spine_2024_25.csv")
g = pd.read_csv(G, encoding="latin1", header=3, dtype=str)
g = g.rename(columns={"PRP registration number": "code", "Registered Parent's code": "parent"})[["code", "parent"]].dropna().drop_duplicates()
on_map = set(spine.landlord_code)
pmap = {c: p for c, p in zip(g.code, g.parent) if p in on_map}
gn["code"] = gn.code.map(lambda c: c if c in on_map else pmap.get(c, c))

def wavg(df, v, w):
    m = df[v].notna() & df[w].notna() & (df[w] > 0)
    return float((df.loc[m, v] * df.loc[m, w]).sum() / df.loc[m, w].sum()) if m.any() else np.nan

# landlord x borough: the comparison a tenant can actually make
ll_la = gn.groupby(["code", "la_code"]).apply(lambda d: pd.Series({
    "la_name": d.la_name.iloc[0], "units": d.units.sum(), "rent": wavg(d, "rent", "units")})).reset_index()
# borough: every landlord's units together
la = gn.groupby("la_code").apply(lambda d: pd.Series({
    "la_name": d.la_name.iloc[0], "units": d.units.sum(), "n_landlords": d.code.nunique(), "rent": wavg(d, "rent", "units"),
    "rent_1": wavg(d, "rent_1", "units_1"), "rent_2": wavg(d, "rent_2", "units_2"), "rent_3": wavg(d, "rent_3", "units_3")})).reset_index()
# landlord-wide
ll = gn.groupby("code").apply(lambda d: pd.Series({
    "gn_units": d.units.sum(), "gn_rent": wavg(d, "rent", "units"), "gn_rent_1": wavg(d, "rent_1", "units_1"),
    "gn_rent_2": wavg(d, "rent_2", "units_2"), "gn_rent_3": wavg(d, "rent_3", "units_3"), "gn_svc": wavg(d, "svc", "svc_n"),
    "gn_svc_share": d.svc_n.sum() / d.units.sum() if d.units.sum() else np.nan})).reset_index()

# How a landlord's rent sits against the other landlords in the same boroughs, weighted by where its
# homes are: +5% means it charges 5% more than its neighbours do, borough by borough. Boroughs with a
# single landlord contribute nothing (there is no one to compare with).
la_idx = la.set_index("la_code")
rows = []
for code, d in ll_la.groupby("code"):
    num = den = 0.0
    for r in d.itertuples():
        b = la_idx.loc[r.la_code]
        others_units = b.units - r.units
        if others_units <= 0 or b.n_landlords < 2:
            continue
        others_rent = (b.rent * b.units - r.rent * r.units) / others_units
        num += (r.rent / others_rent - 1) * r.units; den += r.units
    rows.append({"code": code, "vs_neighbours_pct": round(num / den * 100, 1) if den else np.nan, "vs_units": den})
ll = ll.merge(pd.DataFrame(rows), on="code", how="left")

# supported housing and housing for older people, landlord-wide only
sh = pd.read_csv(S, encoding="latin1", header=3).rename(columns={"PRP registration number": "code", "LA code": "la_code"})
PS = "Supported housing and housing for older people"
sh["units"] = pd.to_numeric(sh[col(sh, PS, UNITS, "All units")], errors="coerce")
sh["rent"] = pd.to_numeric(sh[col(sh, PS, RENT, "All units")], errors="coerce")
sh = sh[sh.la_code.astype(str).str.startswith("E") & (sh.units > 0) & sh.rent.notna()]
sh["code"] = sh.code.map(lambda c: c if c in on_map else pmap.get(c, c))
shl = sh.groupby("code").apply(lambda d: pd.Series({"sh_units": d.units.sum(), "sh_rent": wavg(d, "rent", "units")})).reset_index()
ll = ll.merge(shl, on="code", how="outer")

for df, name in ((ll, "rents_landlords.csv"), (ll_la, "rents_landlord_la.csv"), (la, "rents_la.csv")):
    for c in df.columns:
        if df[c].dtype.kind == "f" and c.startswith(("rent", "gn_rent", "sh_rent", "gn_svc")):
            df[c] = df[c].round(2)
    df.to_csv(OUT + name, index=False)

eng = wavg(gn, "rent", "units")
on = ll[ll.code.isin(on_map)]
print(f"general needs rows {len(gn)}; landlords with a rent {len(ll)}, of which on the map {len(on)}; boroughs {len(la)}; "
      f"England units-weighted GN net rent £{eng:.2f}/wk; landlords with a neighbours comparison {on.vs_neighbours_pct.notna().sum()}")
print(on.sort_values('vs_neighbours_pct').tail(3)[['code','gn_rent','vs_neighbours_pct']].to_string())
