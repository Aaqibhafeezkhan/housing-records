"""Add the second wave of layers to the landlord spine (run after build_spine.py):
  - RSH regulatory judgements (consumer / governance / viability grades)
  - Local Authority Housing Statistics 2024/25 (council-owned stock, LAD codes)
  - SDR group structure (roll subsidiary stock up to the TSM-reporting parent)
  - a local-authority map table (council + housing association homes per LA)
  - Scottish Housing Regulator Charter indicators (separate table)
"""
import glob, re
import numpy as np
import pandas as pd

from paths import RAW, OUT
spine = pd.read_csv(OUT + "landlord_spine_2024_25.csv")

# --- regulatory judgements
rj = pd.read_excel(glob.glob(RAW + "rsh/*RegulatoryJudgementsNotices*.xlsx")[0], sheet_name="Regulatory Judgements", dtype=str)
rj.columns = [c.strip() for c in rj.columns]
rj["Reg Code"] = rj["Reg Code"].str.strip()
rj.to_csv(OUT + "regulatory_judgements.csv", index=False)
# a few codes appear twice (renamed landlord, re-published judgement): keep the most recent publication
rj = rj.sort_values("Publication Date").drop_duplicates("Reg Code", keep="last")
rj = rj.rename(columns={"Reg Code": "landlord_code", "Consumer grade": "consumer_grade", "Consumer Grade Date": "consumer_grade_date",
                        "Governance Grade": "governance_grade", "Governance Date": "governance_date", "Viability Grade": "viability_grade",
                        "Viability Grade Date": "viability_grade_date", "Other landlords included in the judgement": "judgement_covers",
                        "Consumer Grade Change": "consumer_change", "Governance Grade Change": "governance_change", "Viability Grade Change": "viability_change",
                        "Type of Publication": "rj_publication", "Publication Date": "rj_date", "Engagement Process": "rj_engagement"})
rj = rj[["landlord_code", "consumer_grade", "consumer_grade_date", "governance_grade", "governance_date", "viability_grade", "viability_grade_date", "judgement_covers",
         "consumer_change", "governance_change", "viability_change", "rj_publication", "rj_date", "rj_engagement"]]
for c in ("consumer_grade", "governance_grade", "viability_grade"):
    rj[c] = rj[c].replace("-", np.nan)
# The Regulator's own word for what happened to each grade at the latest judgement, reduced to the
# three a tenant needs: went up, went down, or neither. "Regrade V1 to V2" is a downgrade in all but name.
def direction(v):
    v = str(v).strip().lower()
    if v.startswith("upgrade") or v == "regrade v2 to v1": return "up"
    if v.startswith("downgrade") or v == "regrade v1 to v2": return "down"
    return np.nan
for c in ("consumer_change", "governance_change", "viability_change"):
    rj[c] = rj[c].map(direction)
rj["rj_date"] = pd.to_datetime(rj.rj_date, errors="coerce").dt.strftime("%Y-%m-%d")
rj["grading_under_review"] = rj.rj_publication.eq("Grading Under Review")
# Enforcement notices: the Regulator's formal step beyond a grade. Two providers at the time of writing.
en = pd.read_excel(glob.glob(RAW + "rsh/*RegulatoryJudgementsNotices*.xlsx")[0], sheet_name="Enforcement Notices", dtype=str)
en.columns = [c.strip() for c in en.columns]
en = en[en.Status.str.strip() == "Current"].rename(columns={"Reg Code": "landlord_code", "Date of Enforcement Notice": "enforcement_date", "Explanation": "enforcement_about"})
en["enforcement_date"] = pd.to_datetime(en.enforcement_date, errors="coerce").dt.strftime("%Y-%m-%d")
en = en.sort_values("enforcement_date").drop_duplicates("landlord_code", keep="last")[["landlord_code", "enforcement_date", "enforcement_about"]]
rj = rj.merge(en, on="landlord_code", how="left")

# --- council stock (LAHS)
l = pd.read_csv(glob.glob(RAW + "mhclg/LAHS_open_data*.csv")[0], encoding="latin1", usecols=["LAD24NM", "LAD24CD", "region_name", "Year", "a1a"], dtype=str)
las = l[l.Year == "2024-25"].copy()
las["la_owned_homes"] = pd.to_numeric(las.a1a.str.replace(",", ""), errors="coerce")  # a1a = dwellings owned by the LA
las = las.rename(columns={"LAD24NM": "la_name", "LAD24CD": "la_code", "region_name": "region"})[["la_code", "la_name", "region", "la_owned_homes"]]
# LAHS carries newer ONS codes for two South Yorkshire districts than the boundaries and the SDR do.
# Without this, Barnsley and Sheffield join to nothing and silently lose every housing association.
LAHS_CODE_ALIAS = {"E08000038": "E08000016", "E08000039": "E08000019"}
las["la_code"] = las.la_code.replace(LAHS_CODE_ALIAS)
las.to_csv(OUT + "la_stock_2024_25.csv", index=False)

def norm_la(s):
    s = s.lower()
    s = re.sub(r"\b(the|london borough of|royal borough of|borough of|city of|council|metropolitan|borough|district|city|county|of|and|&|royal|corporation|unitary|authority|mbc|bc|dc|cc)\b", " ", s)
    return " ".join(re.sub(r"[^a-z ]", " ", s).split())

MANUAL_LA = {"Haringey London Borough Council": "Haringey", "Newcastle City Council": "Newcastle upon Tyne"}
tsm_las = spine[spine.landlord_type == "LA"][["landlord_code", "landlord_name"]].copy()
tsm_las["k"] = tsm_las.landlord_name.map(lambda n: norm_la(MANUAL_LA.get(n, n)))
las["k"] = las.la_name.map(norm_la)
lk = tsm_las.merge(las[["k", "la_code", "la_name", "la_owned_homes"]], on="k", how="left").drop(columns="k")
assert lk.la_code.notna().all(), lk[lk.la_code.isna()]
lk.to_csv(OUT + "la_landlord_lookup.csv", index=False)
lk = lk.rename(columns={"la_code": "council_la_code", "la_name": "council_la_name", "la_owned_homes": "council_owned_homes_lahs"}).drop(columns="landlord_name")

# --- group roll-up of SDR stock
g = pd.read_csv(glob.glob(RAW + "rsh/prp/*/*File 02 - Group Information.csv")[0], encoding="latin1", header=3, dtype=str)
g = g.rename(columns={"PRP registration number": "code", "Registered Parent's code": "parent"})[["code", "parent"]].dropna().drop_duplicates()
g = g[g.parent.str.match(r"^[A-Z0-9]+$", na=False)]
pmap = dict(zip(g.code, g.parent))
sla = pd.read_csv(OUT + "stock_by_la.csv")
sla["group_code"] = sla.landlord_code.map(pmap).fillna(sla.landlord_code)
sla.to_csv(OUT + "stock_by_la.csv", index=False)
gfoot = sla.groupby("group_code").agg(group_lcra_owned=("lcra_owned", "sum"), group_la_count=("la_code", "nunique"),
                                      group_dhs_fails=("dhs_fails", "sum")).reset_index().rename(columns={"group_code": "landlord_code"})

# --- merge
for extra in (rj, lk, gfoot):
    spine = spine.drop(columns=[c for c in extra.columns if c in spine.columns and c != "landlord_code"]).merge(extra, on="landlord_code", how="left")
spine["homes_estimate"] = spine.lcra_owned_sdr.where(spine.landlord_type == "PRP", spine.council_owned_homes_lahs).fillna(spine.group_lcra_owned)
# Some group parents file the TSMs for the whole group while their own stock return records almost nothing
# (the homes sit in subsidiaries). Their own figure would make per-home rates absurd, so take the group's
# stock instead and flag it, so the card can say the figure is the group's.
grp = (spine.landlord_type == "PRP") & (spine.lcra_owned_sdr < 0.01 * spine.group_lcra_owned)
spine["homes_grp"] = grp
spine.loc[grp, "homes_estimate"] = spine.loc[grp, "group_lcra_owned"]
spine.loc[grp, "la_count"] = spine.loc[grp, "group_la_count"]   # and the boroughs those group homes are in
gmain = sla.groupby(["group_code", "la_name"]).lcra_owned.sum().reset_index().sort_values(["lcra_owned", "la_name"], ascending=[False, True]).drop_duplicates("group_code").set_index("group_code").la_name
spine.loc[grp, "main_la"] = spine.loc[grp, "landlord_code"].astype(str).map(gmain)
spine["la_count"] = spine.la_count.fillna(spine.group_la_count)
spine.to_csv(OUT + "landlord_spine_2024_25.csv", index=False)

# --- local authority map table
prp = sla.groupby("la_code").agg(prp_homes=("lcra_owned", "sum"), prp_landlords=("landlord_code", "nunique"), prp_dhs_fails=("dhs_fails", "sum")).reset_index()
m = las.drop(columns="k").merge(prp, on="la_code", how="left").fillna({"prp_homes": 0, "prp_landlords": 0})
m["social_homes_total"] = m.la_owned_homes.fillna(0) + m.prp_homes
m.to_csv(OUT + "map_local_authorities.csv", index=False)

# --- Scotland
d = pd.read_csv(glob.glob(RAW + "shr/charter_current.csv")[0], encoding="latin1", low_memory=False)
keep = {"F1.3 Landlord name": "landlord_name", "F1.4 RSL Registration Number": "rsl_number", "F1.5 Social Landlord ID": "landlord_id", "F1.8 Landlord type": "landlord_type", "F1.2 Financial year": "year",
        "1 - Percentage of tenants satisfied with the overall service provided landlord": "sat_overall", "7 - Percentage tenants satisfied with quality of home": "sat_quality_home",
        "12 - Percentage tenants satisfied with repairs service": "sat_repairs", "6 - Percentage properties meeting SHQS year end": "shqs_pct",
        "8 - Average hours to complete emergency repairs": "emergency_repair_hours", "9 - Average working days to complete non-emergency repairs": "non_emergency_repair_days",
        "10 - Percentage reactive repairs completed right first time": "right_first_time_pct", "11 - Number of times gas safety check not met": "gas_checks_missed",
        "3 & 4 - Percentage of all complaints responded to in full Stage 1": "complaints_stage1_full_response_pct", "3 & 4 - Average time in working days for full response Stage 1": "complaints_stage1_days",
        "14 - Anti-social behaviour per 100 properties": "asb_per_100", "C8.1 Total self-contained stock (at end of the reporting year)": "stock"}
s = d[list(keep)].rename(columns=keep)
for c in s.columns[5:]:
    s[c] = pd.to_numeric(s[c], errors="coerce")
s.to_csv(OUT + "scotland_charter_2025_26.csv", index=False)

print(f"spine {len(spine)} rows; consumer grades on {spine.consumer_grade.notna().sum()}; homes_estimate missing {spine.homes_estimate.isna().sum()}; "
      f"map {len(m)} LAs / {int(m.social_homes_total.sum()):,} social homes; Scotland {len(s)} landlords")
