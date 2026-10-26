"""Homes built, bought, sold and lost in the year, per housing association, from the Regulator's Statistical
Data Return (File 16, low cost rental stock balance sheet: every provider of 1,000+ homes, owned units,
all rent types together — general needs, supported, intermediate and Affordable Rent).

The return reconciles the year: units brought forward, then every gain (new build, purchases from other
landlords, other gains) and every loss (sales to tenants under Right to Buy and the like, sales to other
social landlords, sales out of social housing, conversion to shared ownership, demolition, leases ending,
other), to the units expected at year end.

Movements inside a group (a subsidiary selling to its parent) are real for the subsidiary and invisible for
the group. Because the map rolls subsidiaries up to the parent that reports TSMs, intra-group lines are kept
apart and shown only as a single net row, so a group restructure never reads as thousands of homes bought.
"""
import glob

import pandas as pd

from paths import OUT, RAW

F = glob.glob(RAW + "rsh/prp/*/*File 16 - Stock Balance Sheet.csv")[0]
G = glob.glob(RAW + "rsh/prp/*/*File 02 - Group Information.csv")[0]
t = pd.read_csv(F, encoding="latin1", header=3).rename(columns={"PRP registration number": "code"})
T = lambda prefix: [c for c in t.columns if c.startswith(prefix) and c.rstrip().endswith("- Total") and "tenanted" not in c]
def col(prefix):
    c = T(prefix); assert len(c) == 1, (prefix, c); return c[0]
num = lambda c: pd.to_numeric(t[c], errors="coerce").fillna(0)

out = pd.DataFrame({"code": t.code})
out["start"] = num(col("Revised units brought forward"))
out["built"] = num(col("Newly built rental accommodation"))
out["bought"] = (num(col("Units purchased by/ transferred to the PRP for rent from another PRP")) + num(col("Units purchased by/ transferred to the PRP for rent from a Local Authority RP"))
                 + num(col("Units purchased by/ transferred to the PRP for rent from other sources")))
out["other_gains"] = num(col("All other gains from outside your existing low cost rental stock"))
intra_in = num(col("Units purchased by/ transferred to the PRP for rent from a PRP in the same group")) + num(col("Units purchased by/ transferred to the PRP for rent from an unregistered entity in the same group"))
out["sold_tenants"] = num(col("Total sales - "))   # the return's own total of sales to tenants, freehold and leasehold
out["sold_social"] = num(col("Sales to another RP - for social housing use")) + num(col("Sales to a Local Authority RP - for social housing use"))
out["sold_out"] = (num(col("Sales to another RP - for non-social housing use")) + num(col("Sales to a Local Authority RP - for non-social housing use"))
                   + num(col("Sales to the open market - for non-social housing use")) + num(col("Sales to other - for non-social housing use")))
intra_out = (num(col("Sales to a RP in the same group - for social housing use")) + num(col("Sales to a RP in the same group - for non-social housing use"))
             + num(col("Sales to an unregistered entity in the same group - for non-social housing use")))
out["to_shared_ownership"] = num(col("Conversions to LCHO"))
out["demolished"] = num(col("Demolitions"))
out["other_losses"] = num(col("Loss of social housing rental stock as a result of expiry or termination of lease")) + num(col("All other losses"))
out["intra_group_net"] = intra_in - intra_out
out["end"] = num(col("Expected stock"))
out["net"] = num(col("Net change in stock"))

# roll up to the parent on the map, as the stock and rent tables do
spine = pd.read_csv(OUT + "landlord_spine_2024_25.csv")
g = pd.read_csv(G, encoding="latin1", header=3, dtype=str).rename(columns={"PRP registration number": "code", "Registered Parent's code": "parent"})[["code", "parent"]].dropna().drop_duplicates()
on_map = set(spine.landlord_code)
pmap = {c: p for c, p in zip(g.code, g.parent) if p in on_map}
out["code"] = out.code.map(lambda c: c if c in on_map else pmap.get(c, c))
out = out.groupby("code", as_index=False).sum(numeric_only=True)
for c in out.columns[1:]:
    out[c] = out[c].round(0).astype(int)
# the return's arithmetic, checked: start + gains − losses (+ intra-group net) = end, within rounding of the return's own adjustments
gap = (out.start + out.built + out.bought + out.other_gains + out.intra_group_net - out.sold_tenants - out.sold_social - out.sold_out
       - out.to_shared_ownership - out.demolished - out.other_losses - out.end)
out["reconciles"] = gap.abs() <= 2
out.to_csv(OUT + "stock_movement.csv", index=False)
print(f"stock balance sheets: {len(t)} providers -> {len(out)} landlords after roll-up, {out.code.isin(on_map).sum()} on the map; "
      f"reconcile to the year-end figure: {out.reconciles.mean():.0%}; built {out.built.sum():,}, sold to tenants {out.sold_tenants.sum():,}, "
      f"sold out of social housing {out.sold_out.sum():,}, demolished {out.demolished.sum():,}")
