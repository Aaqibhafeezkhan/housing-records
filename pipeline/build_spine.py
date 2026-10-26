"""Build the landlord spine: RSH register + TSM 2023/24 & 2024/25 + SDR stock by local authority.

Inputs  (raw/):  List_of_registered_providers_*.xlsx, 2025_TSM_Full_Data_*.xlsx, 2024_TSM_Full_Data_*.xlsx,
                 SDR_Data_Release_2025 ... File 04 - Stock by LA.csv (from the SDR full-data zip)
Outputs (out/):  registered_providers.csv, tsm_landlords.csv (both years, long),
                 stock_by_la.csv (provider x local authority), landlord_spine_2024_25.csv (one row per landlord, with ranks)
"""
import glob, re
import pandas as pd

from paths import RAW, OUT

MI = {"BS01": "gas_safety_pct", "BS02": "fire_risk_assessment_pct", "BS03": "asbestos_pct", "BS04": "legionella_pct",
      "BS05": "lift_pct", "NM01 1": "asb_cases_per_1000", "RP01": "non_decent_pct",
      "RP02 1": "non_emergency_repairs_on_time_pct", "RP02 2": "emergency_repairs_on_time_pct",
      "CH01 1": "stage1_complaints_per_1000", "CH01 2": "stage2_complaints_per_1000",
      "CH02 1": "stage1_complaints_on_time_pct", "CH02 2": "stage2_complaints_on_time_pct"}
TP = {"TP01": "sat_overall", "TP02": "sat_repairs", "TP03": "sat_repair_time", "TP04": "sat_well_maintained",
      "TP05": "sat_safe", "TP06": "sat_listens", "TP07": "sat_informed", "TP08": "sat_fair_respect",
      "TP09": "sat_complaints", "TP10": "sat_communal", "TP11": "sat_neighbourhood", "TP12": "sat_asb"}


def load_sheet(path, sheet):
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    hr = df.index[df[0].astype(str).str.strip() == "Landlord name"][0]
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.iloc[hr]]
    return df.iloc[hr + 1:].reset_index(drop=True)


def pick(df, code):
    pat = re.compile(r"\(" + re.escape(code) + r"\)\s*\d*$")
    cands = [c for c in df.columns if pat.search(c) and not c.startswith("Did you own")
             and "for each survey method" not in c and "target timescale for" not in c]
    assert cands, f"no column for {code}"
    return cands[0]


def not_included(path, sheet):
    """The Regulator's published reason for leaving one half of a landlord's return out ({code: reason})."""
    try:
        df = load_sheet(path, sheet)
    except ValueError:  # older releases have no "Not included" sheets
        return {}
    note = [c for c in df.columns if c.startswith("Notes from RSH")][0]
    df = df.dropna(subset=["Landlord code"])
    return {c: str(n).strip() for c, n in zip(df["Landlord code"], df[note]) if isinstance(n, str)}


BASE = {"Landlord name": "landlord_name", "Landlord code": "landlord_code", "Landlord type": "landlord_type",
        "Landlord group size (homes owned, LCRA and LCHO combined)": "homes_owned", "Landlord predominant region": "region",
        "Landlord TSM Publication URL1": "tsm_url"}


def build_tsm(year, path, mi_sheet, tp_sheet):
    """One row per landlord from the UNION of the two halves of the return. The Regulator sometimes publishes
    one half and withholds the other, saying why in the "Not_Inc" sheets; building from one sheet alone would
    silently drop that landlord. The reason is carried through so the card can say why the figures are missing."""
    mi, pe = load_sheet(path, mi_sheet), load_sheet(path, tp_sheet)
    # footnote rows at the bottom of the older workbooks have no landlord code
    mi, pe = (df[df["Landlord code"].notna()].copy() for df in (mi, pe))
    m = mi[list(BASE)].rename(columns=BASE)
    for code, name in MI.items():
        m[name] = pd.to_numeric(mi[pick(mi, code)], errors="coerce")
    p = pe[list(BASE)].rename(columns=BASE)
    for code, name in TP.items():
        p[name] = pd.to_numeric(pe[pick(pe, code)], errors="coerce")
    p["survey_responses"] = pd.to_numeric(pe["Total sample size achieved"], errors="coerce")
    p["survey_method"] = pe["Predominant collection method"]
    out = m.merge(p.drop(columns=[c for c in BASE.values() if c != "landlord_code"]), on="landlord_code", how="outer")
    # landlords present only in the perception half take their name, type, size, region and URL from it
    only_p = ~out.landlord_code.isin(m.landlord_code)
    pb = p.set_index("landlord_code")
    for c in [c for c in BASE.values() if c != "landlord_code"]:
        out.loc[only_p, c] = out.loc[only_p, "landlord_code"].map(pb[c])
    pfx = mi_sheet.split("_")[0]
    mi_out, tp_out = not_included(path, pfx + "_Man_Info_Not_Inc"), not_included(path, pfx + "_Perception_Not_Inc")
    out["withheld_mi"] = out.landlord_code.map(mi_out)
    out["withheld_tp"] = out.landlord_code.map(tp_out)
    out["tsm_year"] = year
    return out


def main():
    prov = pd.read_excel(glob.glob(RAW + "rsh/List_of_registered_providers_*.xlsx")[0])
    prov.columns = ["org_name", "reg_number", "reg_date", "designation", "corporate_form", "notes"]
    prov.to_csv(OUT + "registered_providers.csv", index=False)

    tsm = pd.concat([
        build_tsm("2024/25", glob.glob(RAW + "rsh/2025_TSM_Full_Data*.xlsx")[0], "TSM25_Management_Info", "TSM25_LCRA_Perception"),
        build_tsm("2023/24", glob.glob(RAW + "rsh/2024_TSM_Full_Data*.xlsx")[0], "TSM24_Management_Info", "TSM24_LCRA_Perception"),
    ], ignore_index=True)
    tsm.to_csv(OUT + "tsm_landlords.csv", index=False)

    sla = pd.read_csv(glob.glob(RAW + "rsh/prp/*/*File 04 - Stock by LA.csv")[0], encoding="latin1", header=3)
    sla = sla.rename(columns={"PRP name": "landlord_name", "PRP registration number": "landlord_code",
                              "Size of organisation": "size", "Local Authority name": "la_name", "LA code": "la_code"})
    owned = [c for c in sla.columns if "Owned low cost rental" in c]
    sla["lcra_owned"] = sla[owned].apply(pd.to_numeric, errors="coerce").sum(axis=1)
    sla["dhs_fails"] = pd.to_numeric(sla[[c for c in sla.columns if "fail the DHS" in c][0]], errors="coerce")
    sla = sla[sla.la_code.astype(str).str.startswith("E") & (sla.lcra_owned > 0)]
    sla = sla[["landlord_name", "landlord_code", "size", "la_name", "la_code", "lcra_owned", "dhs_fails"]]
    sla.to_csv(OUT + "stock_by_la.csv", index=False)

    t = tsm[tsm.tsm_year == "2024/25"].copy()
    lower_is_worse = [c for c in t.columns if c.endswith("_pct") and c != "non_decent_pct"] + list(TP.values())
    higher_is_worse = ["non_decent_pct", "stage1_complaints_per_1000", "stage2_complaints_per_1000", "asb_cases_per_1000"]
    for c in lower_is_worse:
        t[c + "_rank_worst"] = t[c].rank(ascending=True, method="min")
    for c in higher_is_worse:
        t[c + "_rank_worst"] = t[c].rank(ascending=False, method="min")
    t["n_landlords"] = len(t)
    t = t.merge(prov[["reg_number", "designation", "corporate_form", "reg_date"]],
                left_on="landlord_code", right_on="reg_number", how="left").drop(columns="reg_number")
    foot = sla.groupby("landlord_code").agg(
        la_count=("la_code", "nunique"), lcra_owned_sdr=("lcra_owned", "sum"), dhs_fails_sdr=("dhs_fails", "sum"),
        main_la=("la_name", lambda s: sla.loc[s.index].sort_values("lcra_owned", ascending=False).la_name.iloc[0]),
    ).reset_index()
    t = t.merge(foot, on="landlord_code", how="left")
    t.to_csv(OUT + "landlord_spine_2024_25.csv", index=False)
    print(f"spine: {len(t)} landlords; stock_by_la: {len(sla)} rows, {sla.landlord_code.nunique()} providers, {sla.la_code.nunique()} LAs")


if __name__ == "__main__":
    main()
