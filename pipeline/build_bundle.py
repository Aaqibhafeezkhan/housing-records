"""Build the compact JSON bundle the V1 app embeds: local authorities (with stock-weighted metrics and
landlord lists), landlord profiles (two TSM years, ranks, grades, Ombudsman record), recent cases, quartiles, geometry."""
import glob
import json

import numpy as np
import pandas as pd

from paths import OUT, RAW, SITE
s = pd.read_csv(OUT + "landlord_spine_2024_25.csv")
tsm = pd.read_csv(OUT + "tsm_landlords.csv")
sla = pd.read_csv(OUT + "stock_by_la.csv")
las = pd.read_csv(OUT + "la_stock_2024_25.csv")
lk = pd.read_csv(OUT + "la_landlord_lookup.csv")
cases = pd.read_csv(OUT + "ombudsman_cases.csv", dtype={"landlord_code": str})
ho_by = pd.read_csv(OUT + "ombudsman_by_landlord.csv", dtype={"landlord_code": str}).set_index("landlord_code")
orders = {c: dict(zip(g.order, g.n.astype(int))) for c, g in
          pd.read_csv(OUT + "ombudsman_orders_by_landlord.csv", dtype={"landlord_code": str}).sort_values("n", ascending=False, kind="stable").groupby("landlord_code")}
prov = pd.read_csv(OUT + "registered_providers.csv", dtype={"reg_number": str}).set_index("reg_number")
rjall = pd.read_csv(OUT + "regulatory_judgements.csv", dtype=str)
vfm = pd.read_csv(OUT + "vfm_landlords.csv").set_index("landlord_code")
vseg = pd.read_csv(OUT + "vfm_segments.csv").set_index("seg")
rents = pd.read_csv(OUT + "rents_landlords.csv").set_index("code")
stock = pd.read_csv(OUT + "stock_movement.csv").set_index("code")
lahs = pd.read_csv(OUT + "lahs_councils.csv").set_index("la_code")
lahs_meta = pd.read_csv(OUT + "lahs_meta.csv").set_index("measure")
LAHS_KEYS = ["homes", "homes_social_rent", "homes_affordable_rent", "rent_per_home", "arrears_pct", "arrears_pct_pct_below", "collection_rate", "collection_rate_pct_below",
             "void_per_home", "void_per_home_pct_below", "written_off_per_home", "written_off_per_home_pct_below", "dhs_inspected_pct_pct_below", "vacant", "vacant_pct", "vacant_pct_pct_below", "vacant_over_6m", "relet_days", "relet_days_pct_below",
             "evictions", "evictions_arrears", "evictions_per_1000", "nondecent_pct", "nondecent_n", "dhs_inspected_pct", "dhs_inspected_basis",
             "capital_works_per_home", "capital_works_homes_pct", "cost_to_decent_per_home", "built", "acquired", "demolished", "sales_total", "rtb_sales", "rtb_applications", "rtb_avg_price", "rtb_avg_discount"]
rents_la = pd.read_csv(OUT + "rents_la.csv").set_index("la_code")
rents_ll_la = {(r.code, r.la_code): round(float(r.rent), 2) for r in pd.read_csv(OUT + "rents_landlord_la.csv").itertuples()}
geo = json.load(open(glob.glob(RAW + "ons/lad_*_uk_buc.geojson")[0]))  # all 361 UK districts; only England has data so far

MEASURES = ["gas_safety_pct", "fire_risk_assessment_pct", "asbestos_pct", "legionella_pct", "lift_pct", "non_decent_pct",
            "non_emergency_repairs_on_time_pct", "emergency_repairs_on_time_pct", "stage1_complaints_per_1000", "stage1_complaints_on_time_pct",
            "asb_cases_per_1000", "sat_overall", "sat_repairs", "sat_repair_time", "sat_well_maintained", "sat_safe", "sat_listens",
            "sat_informed", "sat_fair_respect", "sat_complaints", "sat_communal", "sat_neighbourhood", "sat_asb"]
HO = ["ho_cases_all", "ho_maladministration_all", "ho_severe_all", "ho_maladministration_rate_all", "ho_repairs_cases_all", "ho_health_safety_cases_all",
      "ho_compensation_orders_all", "ho_compensation_sum_all", "ho_compensation_known_all", "ho_cases_12m", "ho_maladministration_12m", "ho_severe_12m", "ho_maladministration_rate_12m", "ho_repairs_cases_12m",
      "ho_health_safety_cases_12m", "ho_cases_per_10k_all", "ho_maladministration_per_10k_all", "ho_cases_per_10k_12m", "ho_maladministration_per_10k_12m"]

def clean(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return round(float(v), 1)
    return v

prev = tsm[tsm.tsm_year == "2023/24"].set_index("landlord_code")
landlords = {}
for _, r in s.iterrows():
    code = r.landlord_code
    d = {"name": r.landlord_name, "type": r.landlord_type, "size": r.homes_owned, "region": r.region, "homes": clean(r.homes_estimate),
         "la_count": clean(r.la_count), "main_la": r.main_la if isinstance(r.main_la, str) else (r.council_la_name if isinstance(r.council_la_name, str) else None),
         "council_la": r.council_la_code if isinstance(r.council_la_code, str) else None,
         "tsm_url": r.tsm_url if isinstance(r.tsm_url, str) and r.tsm_url.startswith("http") else None,
         "survey": {"n": clean(r.survey_responses), "method": r.survey_method if isinstance(r.survey_method, str) else None},
         "m": {k: clean(r[k]) for k in MEASURES}, "rank": {k: clean(r[k + "_rank_worst"]) for k in MEASURES if k + "_rank_worst" in s.columns},
         "prev": {k: clean(prev.loc[code, k]) if code in prev.index else None for k in MEASURES},
         "grades": {"C": clean(r.consumer_grade), "C_date": str(r.consumer_grade_date)[:10] if isinstance(r.consumer_grade_date, str) else None,
                    "G": clean(r.governance_grade), "G_date": str(r.governance_date)[:10] if isinstance(r.governance_date, str) else None,
                    "V": clean(r.viability_grade), "V_date": str(r.viability_grade_date)[:10] if isinstance(r.viability_grade_date, str) else None,
                    # what moved at the latest judgement, the route that led to it, and the two formal flags
                    "chg": {k: clean(r[c]) for k, c in (("C", "consumer_change"), ("G", "governance_change"), ("V", "viability_change")) if isinstance(r[c], str)},
                    "route": r.rj_engagement if isinstance(r.rj_engagement, str) else None, "date": r.rj_date if isinstance(r.rj_date, str) else None,
                    "under_review": bool(r.grading_under_review) if not pd.isna(r.grading_under_review) else False,
                    "enforcement": {"date": r.enforcement_date, "about": r.enforcement_about} if isinstance(r.enforcement_date, str) else None},
         "ho": {k: clean(r[k]) for k in HO},
         # register facts: legal form, for-profit or not, and the year it registered with the Regulator
         # (looked up by code as text: the workbooks store numeric registration codes as numbers)
         "form": prov.corporate_form.get(str(code)), "profit": prov.designation.get(str(code)),
         "since": str(prov.reg_date.get(str(code)))[:4] if str(code) in prov.index else None,
         "homes_grp": bool(r.homes_grp),   # True where "homes" is the group's stock (see build_layers.py)
         # where the Regulator withheld one half of the return, its published reason (never read as a clean record)
         "withheld": {"mi": r.withheld_mi if isinstance(r.withheld_mi, str) else None,
                      "tp": r.withheld_tp if isinstance(r.withheld_tp, str) else None}}
    if str(code) in orders:
        d["orders"] = orders[str(code)]
    # The Regulator's cost per home, housing associations only. Kept as a plain figure with its position
    # among like providers: the card must not colour it, because dear is not bad and cheap is not good.
    if code in vfm.index:
        v = vfm.loc[code]
        d["vfm"] = {"seg": v.seg, "hshc": clean(v.hshc_2025), "hshc_prev": clean(v.hshc_2024),
                    "pct_below": clean(v.pct_below), "stock": clean(v.vfm_stock), "new_units": clean(v.vfm_new_units)}
        if bool(v.recon):   # the split is shown only where it reproduces the Regulator's published headline
            d["vfm"]["parts"] = {"rm": clean(v.rm), "works": clean(v.works), "mgmt": clean(v.mgmt), "svc": clean(v.svc), "oth": clean(v.oth)}
            d["vfm"]["rm_pct_below"] = clean(v.rm_pct_below)
        if pd.notna(v.rent):   # the lettings account and stock movement, wherever the return has them
            d["vfm"]["flow"] = {k: clean(getattr(v, k)) for k in ("rent", "void", "void_pct_below", "surplus", "margin", "margin_pct_below", "interest", "built", "sold", "transf", "owned", "arrears", "arrears_pct_below", "debt", "baddebt", "baddebt_pct_below")}
    # What tenants pay: average weekly net rent from the Statistical Data Return, with the landlord's
    # premium or discount against the other landlords in the same boroughs (the only fair comparison).
    if code in rents.index:
        rr = rents.loc[code]
        d["rent"] = {k: (round(float(rr[c]), 2) if pd.notna(rr[c]) else None) for k, c in
                     (("gn", "gn_rent"), ("gn1", "gn_rent_1"), ("gn2", "gn_rent_2"), ("gn3", "gn_rent_3"), ("svc", "gn_svc"), ("sh", "sh_rent"))}
        d["rent"]["svc_share"] = clean(rr.gn_svc_share)
        d["rent"]["vs"] = clean(rr.vs_neighbours_pct)
        d["rent"]["gn_units"] = clean(rr.gn_units)
    # The year's stock movement from the Statistical Data Return balance sheet (housing associations)
    if code in stock.index:
        d["stock"] = {k: int(stock.loc[code, k]) for k in ("start", "built", "bought", "other_gains", "sold_tenants", "sold_social", "sold_out", "to_shared_ownership", "demolished", "other_losses", "intra_group_net", "end", "net")}
    # The council card: the council's own LAHS return, compared only with other councils.
    if d["council_la"] and d["council_la"] in lahs.index:
        row = lahs.loc[d["council_la"]]
        d["lahs"] = {k: (row[k] if isinstance(row[k], str) else clean(row[k])) for k in LAHS_KEYS}
    if d["homes"] is None or d["homes"] < 1000:  # per-10k rates are meaningless on a tiny owned-stock base
        for k in ("ho_cases_per_10k_all", "ho_maladministration_per_10k_all", "ho_cases_per_10k_12m", "ho_maladministration_per_10k_12m"):
            d["ho"][k] = None
    landlords[code] = d

# recent cases per landlord (last 12 months window used in the spine), newest first, capped
cases["ym"] = pd.to_datetime(cases.month, format="%Y-%m", errors="coerce")
cut = cases.ym.max() - pd.DateOffset(months=12)
# Ombudsman-only landlords: decisions published, but none of the Regulator's returns (under 1,000 homes there
# is no requirement to file them). They get a card of their own and no map dot: where their homes are is not published.
small_codes = sorted(set(ho_by.index) - set(map(str, landlords)))
small, smallcases = {}, {}
prev_band = dict(zip(tsm[tsm.tsm_year == "2023/24"].landlord_code.astype(str), tsm[tsm.tsm_year == "2023/24"].homes_owned))
rjl = rjall.sort_values("Publication Date").drop_duplicates("Reg Code", keep="last").set_index("Reg Code")
def nd(v):
    return None if not isinstance(v, str) or v.strip() in ("-", "") else v.strip()
for c in small_codes:
    p_ = prov.loc[c] if c in prov.index else None
    h = ho_by.loc[c]
    e = {"name": p_.org_name if p_ is not None else None,
         "type": "LA" if p_ is not None and p_.designation == "Local authority" else "PRP",
         "form": p_.corporate_form if p_ is not None else None, "profit": p_.designation if p_ is not None else None,
         "since": str(p_.reg_date)[:4] if p_ is not None else None,
         "ho": {k: clean(h[k]) for k in HO if k in h.index}}
    if c in rjl.index:
        j = rjl.loc[c]
        e["grades"] = {"C": nd(j["Consumer grade"]), "G": nd(j["Governance Grade"]), "V": nd(j["Viability Grade"]),
                       "C_date": (nd(j["Consumer Grade Date"]) or "")[:10] or None, "G_date": (nd(j["Governance Date"]) or "")[:10] or None,
                       "V_date": (nd(j["Viability Grade Date"]) or "")[:10] or None}
        if c in prev_band:
            e["prev_band"] = prev_band[c]
    if c in orders:
        e["orders"] = orders[c]
    small[c] = e
cases["cid"] = cases.case_id.astype(int)
newest = cases.sort_values(["ym", "cid"], ascending=False)
for c, g in newest[newest.landlord_code.isin(small_codes)].groupby("landlord_code"):
    smallcases[c] = [[int(x.case_id), x.month, x.worst_outcome if isinstance(x.worst_outcome, str) else None,
                      x.categories if isinstance(x.categories, str) else "", x.href.split("/decisions/")[-1].strip("/")] for x in g.itertuples()]
rec = newest[(newest.ym >= cut) & newest.landlord_code.isin(set(map(str, landlords)) | set(small_codes))]
recent = {}
for code, g in rec.groupby("landlord_code"):
    recent[code] = [[int(x.case_id), x.month, x.worst_outcome if isinstance(x.worst_outcome, str) else None,
                     x.categories if isinstance(x.categories, str) else "", x.href.split("/decisions/")[-1].strip("/")] for x in g.head(12).itertuples()]
# category mix all-time per landlord
catmix = {}
for code, g in cases[cases.landlord_code.isin(set(map(str, landlords)) | set(small_codes))].groupby("landlord_code"):
    ex = g.categories.dropna().str.split("|").explode()
    catmix[code] = ex.value_counts().head(6).to_dict()

# quartiles per measure across the 359
q = {k: [clean(v) for v in s[k].quantile([0.1, 0.25, 0.5, 0.75, 0.9]).tolist()] for k in MEASURES}
ok = s.homes_estimate >= 1000
q["ho_maladministration_per_10k_12m"] = [clean(v) for v in s.loc[ok, "ho_maladministration_per_10k_12m"].quantile([0.1, 0.25, 0.5, 0.75, 0.9]).tolist()]
q["ho_cases_per_10k_12m"] = [clean(v) for v in s.loc[ok, "ho_cases_per_10k_12m"].quantile([0.1, 0.25, 0.5, 0.75, 0.9]).tolist()]

# local authorities: landlords operating there + stock-weighted metrics
council_of_la = dict(zip(lk.la_code, lk.landlord_code))
sla["tsm_code"] = sla.group_code.where(sla.group_code.isin(landlords), sla.landlord_code)
la_out = {}
for _, la in las.iterrows():
    g = sla[sla.la_code == la.la_code]
    rows = []
    if la.la_code in council_of_la:
        rows.append({"code": council_of_la[la.la_code], "homes": int(la.la_owned_homes), "council": True})
    agg = g.groupby("tsm_code").agg(homes=("lcra_owned", "sum"), name=("landlord_name", "first")).sort_values("homes", ascending=False)
    for code, x in agg.iterrows():
        row = {"code": code, "homes": int(x.homes)} | ({} if code in landlords else {"name": x["name"]})
        if (code, la.la_code) in rents_ll_la:
            row["rent"] = rents_ll_la[(code, la.la_code)]   # this landlord's average weekly net rent in this borough
        rows.append(row)
    # A council's ALMO (Derby Homes, Stockport Homes, Westminster Community Homes...) is a registered provider
    # in its own right and rolls up to the council. Its few hundred owned homes then sit beside the council's
    # LAHS stock as a second row for the same landlord. One landlord, one row: fold them together.
    merged = {}
    for r in rows:
        if r["code"] in merged:
            merged[r["code"]]["homes"] += r["homes"]
            if r.get("council"): merged[r["code"]]["council"] = True
        else:
            merged[r["code"]] = dict(r)
    rows = sorted(merged.values(), key=lambda r: (not r.get("council"), -r["homes"], str(r["code"])))  # code breaks ties, so rebuilds are stable
    total = float(la.la_owned_homes if not np.isnan(la.la_owned_homes) else 0) + float(g.lcra_owned.sum())
    metrics = {}
    for k in ["ho_maladministration_per_10k_12m", "fire_risk_assessment_pct", "non_decent_pct", "sat_complaints", "sat_overall", "sat_safe"]:
        num = den = 0.0
        for rrow in rows:
            L = landlords.get(rrow["code"])
            v = (L["ho"] if k.startswith("ho_") else L["m"])[k] if L else None
            if L and v is not None:
                num += v * rrow["homes"]; den += rrow["homes"]
        metrics[k] = round(num / den, 1) if den else None
        metrics[k + "_cov"] = round(den / total, 2) if total else 0
    bad = sum(rrow["homes"] for rrow in rows if landlords.get(rrow["code"]) and landlords[rrow["code"]]["grades"]["C"] in ("C3", "C4"))
    metrics["share_homes_c3_c4"] = round(bad / total * 100, 1) if total else None
    la_out[la.la_code] = {"name": la.la_name, "region": la.region, "council_homes": clean(la.la_owned_homes), "prp_homes": int(g.lcra_owned.sum()),
                          "total": int(total), "n_landlords": len(rows), "landlords": rows, "metrics": metrics}
    if la.la_code in rents_la.index:   # units-weighted general-needs rent across every housing association in the borough
        rl = rents_la.loc[la.la_code]
        la_out[la.la_code]["rent"] = {"gn": round(float(rl.rent), 2), "n": int(rl.n_landlords), "units": int(rl.units),
                                      "gn1": clean(rl.rent_1), "gn2": clean(rl.rent_2), "gn3": clean(rl.rent_3)}

# geometry: project all 361 UK districts once (equirectangular, cos 55N) into a portrait viewBox
import math
K = math.cos(math.radians(55))
xs, ys = [], []
def walk(c):
    if isinstance(c[0], (int, float)): xs.append(c[0]); ys.append(c[1])
    else:
        for x in c: walk(x)
for f in geo["features"]: walk(f["geometry"]["coordinates"])
bb = [min(xs), min(ys), max(xs), max(ys)]
H = 1000.0
sc = H / (bb[3] - bb[1])
W = round((bb[2] - bb[0]) * K * sc)
def ring(r):  # flat [x0,y0,x1,y1,...] in viewBox units, consecutive duplicates dropped
    out, last = [], None
    for c in r:
        p = (round((c[0] - bb[0]) * K * sc, 1), round((bb[3] - c[1]) * sc, 1))
        if p == last: continue
        out.extend(p); last = p
    return out
paths, names = {}, {}
for f in geo["features"]:
    g = f["geometry"]; code = f["properties"]["LAD24CD"]
    rings = g["coordinates"] if g["type"] == "Polygon" else [r for poly in g["coordinates"] for r in poly]
    paths[code] = [ring(r) for r in rings]
    names[code] = f["properties"]["LAD24NM"]
# districts we have no data for yet (Scotland, Wales, NI) still draw, greyed and inert
nodata = {c: names[c] for c in paths if c not in la_out}

orphans = sorted(set(la_out) - set(paths))
assert not orphans, f"local authority codes with no ONS boundary (add an alias in build_layers.py): {orphans}"

bundle = {"meta": {"built": "2026-09-10", "tsm_year": "2024/25", "tsm_prev": "2023/24", "n_landlords": len(landlords), "ho_cases": int(len(cases)),
                   "ho_window_from": str(cut.date())[:7], "ho_latest_month": str(cases.ym.max().date())[:7], "grades_date": "2026-09-09"},
          "vfm_meta": {"year": "2024/25", "published": "2026-03-06",
                       "segments": {k: {"label": row.label, "median": clean(row["median"]), "n": int(row.n),
                                        "q": [clean(row[c]) for c in ("q10", "q25", "median", "q75", "q90")],
                                        "rm_median": clean(row.rm_median), "rm_n": int(row.rm_n) if pd.notna(row.rm_n) else 0,
                                        "margin_median": clean(row.margin_median), "margin_n": int(row.margin_n) if pd.notna(row.margin_n) else 0,
                                        "void_median": clean(row.void_median), "void_n": int(row.void_n) if pd.notna(row.void_n) else 0,
                                        "arrears_median": clean(row.arrears_median), "arrears_n": int(row.arrears_n) if pd.notna(row.arrears_n) else 0,
                                        "baddebt_n": int(row.baddebt_n) if pd.notna(row.baddebt_n) else 0} for k, row in vseg.iterrows()},
                       "england_median": clean(vseg.england_median_all_providers.iloc[0])},
          "lahs_meta": {"year": "2024/25", "n": int(len(lahs)), "m": {k: {"median": clean(r["median"]), "n": int(r.n)} for k, r in lahs_meta.iterrows()}},
          "rent_meta": {"year": "2024/25", "england_gn": round(float((rents.gn_rent * rents.gn_units).sum() / rents.gn_units.sum()), 2)},
          "landlords": landlords, "small": small, "smallcases": smallcases, "recent": recent, "catmix": catmix, "q": q, "las": la_out, "paths": paths, "nodata": nodata, "viewBox": [W, int(H)]}
js = json.dumps(bundle, separators=(",", ":"))
open(SITE + "data.json", "w").write(js)
holdings = sum(len(v["landlords"]) for v in la_out.values())
print(f"bundle {len(js)/1e6:.2f} MB; landlords {len(landlords)}, LAs with data {len(la_out)}, districts drawn {len(paths)}, holdings (map dots) {holdings}, recent cases {sum(len(v) for v in recent.values())}")
