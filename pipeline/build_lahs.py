"""The council card: what each stock-owning council reports in its Local Authority Housing Statistics return.

Source: MHCLG "Local Authority Housing Statistics open data 1978-79 to 2024-25" (one row per council per
year, every cell of the LAHS form as a coded column). Codes are decoded from the 2024-25 LAHS bulk-upload
form and guidance notes (data/raw/mhclg/2024-25_LAHS_form.xlsx, LAHS_Guidance_2024-25.pdf), never guessed.

Units. Section H (rents and arrears) is in pounds: Camden's rent roll of £163m over 22,720 homes is £138 a
week. Sections B and F money columns are in thousands of pounds in the open-data file, whatever the form
says: the form's own derived cell f16c (average cost per non-decent dwelling, £) equals f16b/f16a x 1000
for every council that reports it, and Right to Buy receipts b2ab/b2aa come out at £50k-£210k a sale only
on that reading. Both checks are reproduced below and the build stops if they fail.

Councils are only ever compared with councils. The Regulator's HSHC does not exist for them, and LAHS
capital works are not the same thing, so the card labels the cost lines as what they are.

Weekly rents for councils moved out of LAHS into the Regulator's Local Authority Data Return in 2023, so
that field waits for that file.
"""
import glob

import numpy as np
import pandas as pd

from paths import OUT, RAW

COLS = {  # LAHS code -> our name (see the form: section letter, question number, column letter)
    "a0a": "has_hra", "a1a": "la_owned_in_area", "a2ia": "homes", "a2iaa": "homes_social_rent", "a2iab": "homes_affordable_rent",
    "a4a": "demolished", "a4c": "built", "a4d": "acquired",
    "b1a": "rtb_applications", "b2aa": "rtb_sales", "b2ab": "rtb_receipts_k", "b2ac": "rtb_discounts_k", "b2fa": "sales_total",
    "e2dc": "vacant", "e2da": "vacant_available", "e2cc": "vacant_over_6m",
    "f13e": "nondecent_n_flow", "f14e": "cost_to_decent_k", "f16a": "nondecent_n", "f16b": "nondecent_cost_k", "f16c": "nondecent_cost_per_home",
    "f16e": "dhs_inspected_pct", "f16f": "dhs_inspected_basis", "f17a": "nondecent_pct",
    "f25aa": "capital_works_n", "f25ab": "capital_works_k", "f25ac": "capital_works_homes",
    "g1a": "relet_days", "g2a": "evictions", "g2aa": "evictions_arrears", "g2ab": "evictions_asb",
    "h5a": "arrears_current", "h6a": "arrears_former", "h8a": "arrears_written_off", "h9a": "rent_roll", "h10a": "rent_reductions",
    "h11a": "void_loss", "h12a": "rent_income", "h13a": "arrears_total_pct_lahs", "h14a": "collection_rate",
}
TEXT = {"has_hra", "dhs_inspected_basis"}

l = pd.read_csv(glob.glob(RAW + "mhclg/LAHS_open_data*.csv")[0], encoding="latin1", dtype=str,
                usecols=["LAD24NM", "LAD24CD", "Year"] + list(COLS))
l = l[l.Year == "2024-25"].rename(columns=COLS).rename(columns={"LAD24NM": "la_name", "LAD24CD": "la_code"})
for c in COLS.values():
    if c not in TEXT:
        l[c] = pd.to_numeric(l[c].str.replace(",", ""), errors="coerce")
LAHS_CODE_ALIAS = {"E08000038": "E08000016", "E08000039": "E08000019"}   # same two South Yorkshire codes as build_layers
l["la_code"] = l.la_code.replace(LAHS_CODE_ALIAS)
c = l[l.homes > 0].copy()

# --- unit checks (see module note). f16c is the form's own £-per-dwelling cell.
chk = c[(c.nondecent_n > 0) & (c.nondecent_cost_k > 0) & c.nondecent_cost_per_home.notna()]
ratio = chk.nondecent_cost_per_home / (chk.nondecent_cost_k / chk.nondecent_n)
assert ((ratio - 1000).abs() < 25).mean() > 0.95, f"F-section money is not in £'000 as assumed: {ratio.describe()}"
rtb = c[(c.rtb_sales > 0) & c.rtb_receipts_k.notna()]
avg_price = rtb.rtb_receipts_k * 1000 / rtb.rtb_sales
assert avg_price.median() > 30000 and avg_price.median() < 400000, f"B-section receipts unit check failed: median £{avg_price.median():,.0f}"
rent_pw = c.rent_roll / c.homes / 52
assert 60 < rent_pw.median() < 200, f"H-section rent roll unit check failed: median £{rent_pw.median():.0f}/week"

# --- per-home figures
c["rent_per_home"] = (c.rent_income / c.homes).round(0)                    # rent collectable in the year, per home (£)
c["arrears_pct"] = (c.arrears_current / c.rent_roll * 100).round(1)          # current tenants' arrears as % of the rent roll
c["void_per_home"] = (c.void_loss / c.homes).round(0)
c["written_off_per_home"] = (c.arrears_written_off / c.homes).round(0)
c["vacant_pct"] = (c.vacant / c.homes * 100).round(1)
c["evictions_per_1000"] = (c.evictions / c.homes * 1000).round(1)
c["capital_works_per_home"] = (c.capital_works_k * 1000 / c.homes).round(0)    # £'000 -> £, over all homes owned
c["capital_works_homes_pct"] = (c.capital_works_homes / c.homes * 100).round(0)
c["cost_to_decent_per_home"] = (c.cost_to_decent_k * 1000 / c.homes).round(0)  # outstanding bill spread over every home
c["rtb_avg_price"] = (c.rtb_receipts_k * 1000 / c.rtb_sales.replace(0, np.nan)).round(0)
c["rtb_avg_discount"] = (c.rtb_discounts_k * 1000 / c.rtb_sales.replace(0, np.nan)).round(0)
c["net_change"] = c.built.fillna(0) + c.acquired.fillna(0) - c.sales_total.fillna(0) - c.demolished.fillna(0)

# --- position among councils, for the figures with a direction a tenant would agree with
LOWER_BETTER = ["arrears_pct", "void_per_home", "vacant_pct", "relet_days", "written_off_per_home"]
HIGHER_BETTER = ["collection_rate", "dhs_inspected_pct"]
meta = {}
for col in LOWER_BETTER + HIGHER_BETTER:
    vals = c[col].dropna()
    c[col + "_pct_below"] = c[col].map(lambda v: round(100.0 * (vals < v).sum() / max(1, len(vals) - 1), 0) if pd.notna(v) else np.nan)
    meta[col] = {"median": float(vals.median()), "n": int(len(vals))}
for col in ["rent_per_home", "capital_works_per_home", "nondecent_pct", "evictions_per_1000"]:
    vals = c[col].dropna(); meta[col] = {"median": float(vals.median()), "n": int(len(vals))}

c.to_csv(OUT + "lahs_councils.csv", index=False)
pd.DataFrame([{"measure": k, **v} for k, v in meta.items()]).to_csv(OUT + "lahs_meta.csv", index=False)
print(f"councils with owned stock in LAHS 2024-25: {len(c)}; unit checks passed (f16c ratio {ratio.median():.0f}, "
      f"RTB average price £{avg_price.median():,.0f}, rent £{rent_pw.median():.0f}/week)")
print("medians:", {k: round(v["median"], 1) for k, v in meta.items()})
