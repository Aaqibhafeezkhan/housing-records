"""Attach the Regulator's Value for Money cost figure to each housing association on the spine.

Source: RSH "Value for money metrics and reporting 2025" additional tables (annex to the 2024 Global
Accounts; year ending March 2025). Tables 10, 18 and 19 list every private registered provider in the
Global Accounts by name with its Headline Social Housing Cost per unit (HSHC) for 2024 and 2025. HSHC
is the Regulator's own headline efficiency measure: management, maintenance, major repairs, service
charges and other social-housing costs, divided by units owned or managed.

Two things the reader must not be allowed to misread, and the bundle carries what is needed to say so:
  * Cost is not a grade. London and older stock cost more to run; a low figure can mean efficiency or
    under-investment. So this step ranks but does not band, and the card must read it alongside repairs.
  * The Regulator splits providers into general needs, supported housing and housing for older people
    because their costs differ several-fold. Position is computed within the provider's own segment
    and never across segments.

The Global Accounts datafile (same publication family, keyed by provider code) supplies the parts behind
the headline: management, service charges, repairs and maintenance, and other social-housing costs, all
in £'000 with the units they are spread over. The Regulator's own formula reproduces its published
HSHC to the pound for most providers; where the parts do not sum to the published figure within 1% the
Regulator has excluded something we cannot see, and the card shows the headline alone and says so.

Councils are not in the Global Accounts, so this leaves them untouched; the card says so in words.
"""
import re

import numpy as np
import pandas as pd

from paths import OUT, RAW

SRC = RAW + "rsh/2026-02-11_1231_VFM_Metrics_tables.xlsx"
GA = RAW + "rsh/20251211_GA2025_Datafile_for_Publication.xlsx"
SEGMENTS = {"Table_10_HSHC_General_needs": "GN", "Table_18_HSHC_SH": "SH", "Table_19_HSHC_HOP": "HOP"}
SEG_LABEL = {"GN": "general needs", "SH": "supported housing", "HOP": "housing for older people"}

xl = pd.ExcelFile(SRC)
rows = []
for sheet, seg in SEGMENTS.items():
    t = pd.read_excel(xl, sheet_name=sheet, header=4)
    t = t[t["RP name"].notna() & ~t["RP name"].astype(str).str.match(r"^(Source|Note|Go back|This worksheet)")]
    t = t.rename(columns={"RP name": "vfm_name", "All social stock owned": "vfm_stock", "Number of new social units": "vfm_new_units",
                          "HSHC 2024 (£)": "hshc_2024", "HSHC 2025 (£)": "hshc_2025"})
    t["seg"] = seg
    rows.append(t[["vfm_name", "vfm_stock", "vfm_new_units", "hshc_2024", "hshc_2025", "seg"]])
vfm = pd.concat(rows, ignore_index=True)
for c in ("hshc_2024", "hshc_2025", "vfm_stock", "vfm_new_units"):
    vfm[c] = pd.to_numeric(vfm[c], errors="coerce")   # "Not applicable" -> NaN

# Comparison figure: the median of the providers in the same published table, so a general-needs landlord
# is set against general-needs landlords only. The Regulator's own all-provider England median (Table 9)
# is kept alongside for the methodology note.
seg_median = {}
for seg, g in vfm.groupby("seg"):
    vals = g.hshc_2025.dropna()
    q = [float(vals.quantile(p)) for p in (0.10, 0.25, 0.50, 0.75, 0.90)]   # the card's position bar, same shape as the TSM ones
    seg_median[seg] = {"median": q[2], "n": int(len(vals)), "q10": q[0], "q25": q[1], "q75": q[3], "q90": q[4]}
t9 = pd.read_excel(xl, sheet_name="Table_9_Sub_sector_HSHC", header=4)
t9 = t9[t9["Sub sector"].astype(str).str.strip() == "England"]
t9["Year"] = pd.to_numeric(t9["Year"], errors="coerce")
med_col = [c for c in t9.columns if "median" in str(c).lower()][0]
england_median = float(t9[t9.Year == 2025][med_col].iloc[0])

# Position within segment: share of that segment's providers with a LOWER cost per unit.
vfm["pct_below"] = None
for seg, g in vfm.groupby("seg"):
    vals = g.hshc_2025.dropna()
    for i, v in g.hshc_2025.items():
        if pd.notna(v):
            vfm.at[i, "pct_below"] = round(100.0 * (vals < v).sum() / max(1, len(vals) - 1), 0)

# Match to the spine by name. Exact registered name first; a normalised form second; never a guess.
spine = pd.read_csv(OUT + "landlord_spine_2024_25.csv")[["landlord_code", "landlord_name", "landlord_type"]]
prp = spine[spine.landlord_type == "PRP"]

def norm(s):
    s = re.sub(r"[^a-z0-9 ]", " ", str(s).lower())
    s = re.sub(r"\b(limited|ltd|the|plc|llp|cic)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()

exact = {n.strip().lower(): c for c, n in zip(prp.landlord_code, prp.landlord_name)}
normed = {}
for c, n in zip(prp.landlord_code, prp.landlord_name):
    normed.setdefault(norm(n), []).append(c)

codes = []
for n in vfm.vfm_name:
    c = exact.get(str(n).strip().lower())
    if c is None:
        cands = normed.get(norm(n), [])
        c = cands[0] if len(cands) == 1 else None
    codes.append(c)
vfm["landlord_code"] = codes

matched = vfm[vfm.landlord_code.notna()]
dupes = matched[matched.landlord_code.duplicated(keep=False)]
assert dupes.empty, f"two VFM rows matched one landlord: {dupes[['vfm_name', 'landlord_code']].to_dict('records')}"

# ---- the parts behind the headline, from the Global Accounts datafile (consolidated group figures, £'000) ----
raw = pd.read_excel(GA, sheet_name="GA2025 Consolidated", header=None)
ga = raw.iloc[5:].copy(); ga.columns = raw.iloc[4].tolist(); ga = ga[ga["RP_code"].notna()].set_index("RP_code")
gnum = lambda c: pd.to_numeric(ga[c], errors="coerce").abs().fillna(0)
gsig = lambda c: pd.to_numeric(ga[c], errors="coerce").fillna(0)     # signed, for income and surplus lines
parts = pd.DataFrame({
    "rm_k":   gnum("Routine maintenance") + gnum("Planned maintenance") + gnum("Major repairs expenditure") + gnum("Capitalised major repairs expenditure for period"),
    "works_k": gnum("Capitalised major repairs expenditure for period"),   # the capital part of the above: major works that improve homes
    "mgmt_k": gnum("Management"),
    "svc_k":  gnum("Service charge costs"),
    "oth_k":  gnum("Other costs") + gnum("Lease costs") + gnum("Total other SH activities: Operating expenditure"),
    "units":  pd.to_numeric(ga["Closing SH units owned and/or managed"], errors="coerce"),
}, index=ga.index)
parts = parts[parts.units > 0]
for k in ("rm", "works", "mgmt", "svc", "oth"):
    parts[k] = (parts[k + "_k"] * 1000 / parts.units).round(0)     # £ per home
parts["parts_total"] = parts[["rm", "mgmt", "svc", "oth"]].sum(axis=1)

# What happens to the rent: the lettings account and the stock movement, straight from the same return.
# None of these has a published per-provider headline to reconcile against, so each is what the
# datafile says, divided by the homes it says. 'Kept' is the Regulator's operating surplus on social
# housing lettings, which is struck after depreciation, not after major works, so it is a different
# cut from the cost figure and the card must not present them as one sum.
flow = pd.DataFrame({
    "rent":     ((gsig("Rents") + gsig("Service charge income")) * 1000 / parts.units).round(0),
    "void":     (gnum("Void losses") * 1000 / parts.units).round(0),
    "surplus":  (gsig("Operating surplus/(deficit) on SHL") * 1000 / parts.units).round(0),
    "margin":   (gsig("Operating surplus/(deficit) on SHL") / gsig("Turnover from SHL").replace(0, np.nan) * 100).round(1),
    "interest": (gnum("Interest payable and financing costs") * 1000 / parts.units).round(0),
    "built":    gsig("SH units acquired or developed").round(0),
    "sold":     gnum("SH units sold/demolished").round(0),
    "transf":   gsig("SH units transferred and other movements").round(0),
    "owned":    gsig("Closing SH units owned").round(0),
    # Arrears owed by current tenants at year end, as a share of the year's rent and service charge
    # income: the sector's usual way of saying how much of the rent roll is unpaid. Debt is what the
    # landlord owes its lenders, per home; bad debts are what it wrote off as unrecoverable in the year
    # (negative where it recovered more than it wrote off).
    "arrears":  (gnum("Gross arrears Current") / (gsig("Rents") + gsig("Service charge income")).replace(0, np.nan) * 100).round(1),
    "debt":     ((gnum("Long-term debt") + gnum("Short-term debt")) * 1000 / parts.units).round(0),
    "baddebt":  (gsig("Bad debts") * 1000 / parts.units).round(0),
}, index=parts.index)

matched = matched.set_index("landlord_code").join(parts[["rm", "works", "mgmt", "svc", "oth", "parts_total", "units"]], how="left").join(flow, how="left")
# Reconcile against the Regulator's published headline. Exact for most; where it is not, the Regulator
# has taken something out that the datafile does not let us isolate, so the split is withheld.
matched["recon"] = ((matched.parts_total - matched.hshc_2025).abs() / matched.hshc_2025 < 0.01) & matched.parts_total.notna()
n_recon = int(matched.recon.sum())

# Position of repairs-and-maintenance spend per home within the segment, same method as the headline.
matched["rm_pct_below"] = None
for seg, g in matched[matched.recon].groupby("seg"):
    vals = g.rm.dropna()
    for i, v in g.rm.items():
        if pd.notna(v):
            matched.at[i, "rm_pct_below"] = round(100.0 * (vals < v).sum() / max(1, len(vals) - 1), 0)
    seg_median[seg]["rm_median"] = float(vals.median()); seg_median[seg]["rm_n"] = int(len(vals))
# Positions within the segment for the two lettings figures that have a direction a tenant would
# agree with: operating margin (one of the Regulator's own VFM metrics; a loss is a loss) and rent
# lost to empty homes (less is better, full stop), and arrears as a share of the rent roll. Rent
# collected, interest and debt are left unranked — all three are set by geography and by how much a
# landlord is building.
for col in ("margin", "void", "arrears", "baddebt"):
    matched[col + "_pct_below"] = None
    for seg, g in matched[matched[col].notna()].groupby("seg"):
        vals = g[col].dropna()
        for i, v in g[col].items():
            if pd.notna(v):
                matched.at[i, col + "_pct_below"] = round(100.0 * (vals < v).sum() / max(1, len(vals) - 1), 0)
        seg_median[seg][col + "_median"] = float(vals.median()); seg_median[seg][col + "_n"] = int(len(vals))
matched = matched.reset_index()

out = matched[["landlord_code", "vfm_name", "seg", "vfm_stock", "vfm_new_units", "hshc_2024", "hshc_2025", "pct_below",
               "rm", "works", "mgmt", "svc", "oth", "parts_total", "recon", "rm_pct_below",
               "rent", "void", "void_pct_below", "surplus", "margin", "margin_pct_below", "interest", "built", "sold", "transf", "owned",
               "arrears", "arrears_pct_below", "debt", "baddebt", "baddebt_pct_below"]]
out.to_csv(OUT + "vfm_landlords.csv", index=False)
segs = pd.DataFrame([{"seg": k, "label": SEG_LABEL[k], **v} for k, v in seg_median.items()])
segs["england_median_all_providers"] = england_median
segs.to_csv(OUT + "vfm_segments.csv", index=False)

unmatched = vfm[vfm.landlord_code.isna()]
missing = prp[~prp.landlord_code.isin(matched.landlord_code)]
print(f"VFM rows {len(vfm)}; matched to spine {len(matched)}; VFM providers not on the map {len(unmatched)}: {unmatched.vfm_name.tolist()}")
print(f"housing associations on the map with no Global Accounts row: {len(missing)}")
for n in missing.landlord_name:
    print("   ", n)
print(f"parts reconcile to the published headline within 1% for {n_recon} of {len(matched)}; the split is withheld for the rest")
print("segment medians (HSHC 2025, £/unit):", seg_median, "| Regulator England all-provider median:", england_median)
