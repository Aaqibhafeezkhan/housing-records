// The Housing Records — /api/ask
//
// A question in plain English comes in; an answer grounded in the published data goes out.
//
// The model never sees the dataset and never writes a number from memory. It is given a
// small set of query tools over data.json, calls them, and composes its answer from what
// they return. Every figure in an answer therefore came back from a deterministic lookup
// that also ran on the client, and the client shows those rows under the answer. The
// data records what happened, not why, and the model is told to keep to that line.

import fs from 'node:fs';
import path from 'node:path';

const MODEL = process.env.ASK_MODEL || 'claude-sonnet-5';
const MAX_TURNS = 6;
const MAX_Q = 300;

// ---------- data ----------
let D = null;
function data() {
  if (D) return D;
  const p = path.join(process.cwd(), 'site', 'data.json');
  D = JSON.parse(fs.readFileSync(p, 'utf8'));
  D._prepared = prepare(D);
  return D;
}

// The same measure catalogue the card uses. hib = a higher number is better.
const MEAS = {
  gas_safety_pct: { l: 'Gas safety checks in date', u: '%', hib: 1, safety: 1 },
  fire_risk_assessment_pct: { l: 'Fire risk assessments in date', u: '%', hib: 1, safety: 1 },
  asbestos_pct: { l: 'Asbestos surveys in date', u: '%', hib: 1, safety: 1 },
  legionella_pct: { l: 'Water (legionella) assessments in date', u: '%', hib: 1, safety: 1 },
  lift_pct: { l: 'Lift safety checks in date', u: '%', hib: 1, safety: 1 },
  non_decent_pct: { l: 'Homes failing the Decent Homes Standard', u: '%', hib: 0 },
  non_emergency_repairs_on_time_pct: { l: 'Non-emergency repairs completed on time', u: '%', hib: 1 },
  emergency_repairs_on_time_pct: { l: 'Emergency repairs completed on time', u: '%', hib: 1 },
  stage1_complaints_per_1000: { l: 'Stage 1 complaints per 1,000 homes', u: '', hib: 0 },
  stage1_complaints_on_time_pct: { l: 'Complaints answered within the Ombudsman timescale', u: '%', hib: 1 },
  asb_cases_per_1000: { l: 'Anti-social behaviour cases per 1,000 homes', u: '', hib: 0, neutral: 1 },
  sat_overall: { l: 'Tenants satisfied with the overall service', u: '%', hib: 1 },
  sat_repairs: { l: 'Tenants satisfied with repairs', u: '%', hib: 1 },
  sat_repair_time: { l: 'Tenants satisfied with time taken to repair', u: '%', hib: 1 },
  sat_well_maintained: { l: 'Tenants who say their home is well maintained', u: '%', hib: 1 },
  sat_safe: { l: 'Tenants who say their home is safe', u: '%', hib: 1 },
  sat_listens: { l: 'Tenants who say the landlord listens and acts', u: '%', hib: 1 },
  sat_informed: { l: 'Tenants who say they are kept informed', u: '%', hib: 1 },
  sat_fair_respect: { l: 'Tenants who say they are treated fairly and with respect', u: '%', hib: 1 },
  sat_complaints: { l: 'Tenants satisfied with complaint handling', u: '%', hib: 1 },
  sat_communal: { l: 'Tenants who say communal areas are well maintained', u: '%', hib: 1 },
  sat_neighbourhood: { l: 'Tenants who say the landlord contributes positively to the neighbourhood', u: '%', hib: 1 },
  sat_asb: { l: 'Tenants satisfied with the handling of anti-social behaviour', u: '%', hib: 1 },
  // derived, not in x.m
  safety_checks: { l: 'Homes with safety checks in date (weakest of the five checks)', u: '%', hib: 1, derived: 'safe' },
  ombudsman_findings_per_10k: { l: 'Housing Ombudsman findings against the landlord per 10,000 homes, last 12 months', u: '', hib: 0, derived: 'ho' },
};
const SAFEK = ['fire_risk_assessment_pct', 'gas_safety_pct', 'asbestos_pct', 'legionella_pct', 'lift_pct'];

const levelSafety = v => v == null ? 'none' : v >= 99.95 ? 'good' : v >= 99 ? 'mid' : v >= 95 ? 'poor' : 'bad';
function qLevelHigh(v, q) { if (v == null || !q) return 'none'; return v >= q[4] ? 'bad' : v >= q[3] ? 'poor' : v > q[1] ? 'mid' : 'good'; }
function qLevelLow(v, q) { if (v == null || !q) return 'none'; return v <= q[0] ? 'bad' : v <= q[1] ? 'poor' : v < q[3] ? 'mid' : 'good'; }

function valueOf(x, k) {
  if (k === 'safety_checks') { const s = SAFEK.map(m => x.m[m]).filter(v => v != null); return s.length ? Math.min(...s) : null; }
  if (k === 'ombudsman_findings_per_10k') return x.ho ? x.ho.ho_maladministration_per_10k_12m : null;
  return x.m ? x.m[k] : null;
}

// Money, rent and stock figures, for ranking and for the national totals. Each has an accessor per
// landlord type, a direction where a tenant would agree with one, and none where it is a cost or a
// count that must not be read as a grade (dir: 0). Values are the card's own figures.
const netHA = S => S.built + S.bought + S.other_gains - S.sold_tenants - S.sold_social - S.sold_out - S.to_shared_ownership - S.demolished - S.other_losses;
const FIGS = {
  homes_built: { l: 'Homes newly built in the year', u: '', dir: 0, ha: x => x.stock && x.stock.built, la: x => x.lahs && x.lahs.built },
  homes_bought: { l: 'Homes bought from other landlords in the year', u: '', dir: 0, ha: x => x.stock && x.stock.bought, la: x => x.lahs && x.lahs.acquired },
  homes_sold_to_tenants: { l: 'Homes sold to tenants (Right to Buy, Right to Acquire and similar)', u: '', dir: 0, ha: x => x.stock && x.stock.sold_tenants, la: x => x.lahs && x.lahs.rtb_sales },
  homes_sold_out_of_social_housing: { l: 'Homes sold out of social housing (open market and other buyers)', u: '', dir: 0, ha: x => x.stock && x.stock.sold_out, la: () => null },
  homes_demolished: { l: 'Homes demolished in the year', u: '', dir: 0, ha: x => x.stock && x.stock.demolished, la: x => x.lahs && x.lahs.demolished },
  net_change_in_homes: { l: 'Net change in social homes over the year (built and bought minus sold, demolished and lost)', u: '', dir: 1, ha: x => x.stock ? netHA(x.stock) : null, la: x => x.lahs ? (x.lahs.built || 0) + (x.lahs.acquired || 0) - (x.lahs.sales_total || 0) - (x.lahs.demolished || 0) : null },
  weekly_rent_general_needs: { l: 'Average weekly net rent, general needs (£)', u: '£/week', dir: 0, ha: x => x.rent && x.rent.gn, la: () => null },
  rent_vs_neighbours_pct: { l: 'Rent difference against other housing associations in the same boroughs (a percentage of rent, not a percentile: +2 means 2% dearer, −2 means 2% cheaper)', u: '%', dir: 0, ha: x => x.rent && x.rent.vs, la: () => null },
  arrears_pct: { l: 'Arrears owed by current tenants at year end, as % of a year\u2019s rent', u: '%', dir: -1, ha: x => x.vfm && x.vfm.flow && x.vfm.flow.arrears, la: x => x.lahs && x.lahs.arrears_pct },
  rent_lost_to_empty_homes_per_home: { l: 'Rent lost to empty homes, £ per home per year', u: '£', dir: -1, ha: x => x.vfm && x.vfm.flow && x.vfm.flow.void, la: x => x.lahs && x.lahs.void_per_home },
  operating_margin_pct: { l: 'Operating margin on social housing lettings (%)', u: '%', dir: 1, ha: x => x.vfm && x.vfm.flow && x.vfm.flow.margin, la: () => null },
  cost_per_home: { l: 'Headline social housing cost per home (£, the Regulator\u2019s measure; a cost, not a grade)', u: '£', dir: 0, ha: x => x.vfm && x.vfm.hshc, la: () => null },
  debt_per_home: { l: 'Owed to lenders, £ per home', u: '£', dir: 0, ha: x => x.vfm && x.vfm.flow && x.vfm.flow.debt, la: () => null },
  rent_collection_rate_pct: { l: 'Rent collected in the year as % of rent due (councils)', u: '%', dir: 1, ha: () => null, la: x => x.lahs && x.lahs.collection_rate },
  homes_empty_pct: { l: 'Homes standing empty at 31 March, % of stock (councils)', u: '%', dir: -1, ha: () => null, la: x => x.lahs && x.lahs.vacant_pct },
  relet_days: { l: 'Average days to re-let an empty home (councils)', u: 'days', dir: -1, ha: () => null, la: x => x.lahs && x.lahs.relet_days },
  evictions_per_1000_homes: { l: 'Evictions per 1,000 homes (councils)', u: '', dir: 0, ha: () => null, la: x => x.lahs && x.lahs.evictions_per_1000 },
  major_works_per_home: { l: 'Capital works on existing homes, £ per home (councils; a cost, not a grade)', u: '£', dir: 0, ha: () => null, la: x => x.lahs && x.lahs.capital_works_per_home },
  decent_homes_inspected_pct: { l: 'Homes physically inspected for the Decent Homes Standard in the last five years (councils)', u: '%', dir: 1, ha: () => null, la: x => x.lahs && x.lahs.dhs_inspected_pct },
};
function figOf(x, k) { const f = FIGS[k]; if (!f) return null; const v = (x.type === 'LA' ? f.la : f.ha)(x); return v == null || Number.isNaN(v) ? null : v; }

function prepare(D) {
  const L = D.landlords, Q = D.q;
  const ALL = Object.values(L);
  const DIST = {};
  for (const k of Object.keys(MEAS)) DIST[k] = ALL.map(x => valueOf(x, k)).filter(v => v != null);
  const betterThan = (vals, v, hib) => { if (v == null || !vals.length) return null; let worse = 0, eq = 0; for (const u of vals) { if (u === v) eq++; else if (hib ? u < v : u > v) worse++; } return (worse + eq / 2) / vals.length; };
  const standingOf = code => { const x = L[code]; if (!x) return 'none';
    const bands = [levelSafety(valueOf(x, 'safety_checks')), qLevelHigh(x.m.non_decent_pct, Q.non_decent_pct),
      qLevelLow(x.m.non_emergency_repairs_on_time_pct, Q.non_emergency_repairs_on_time_pct),
      qLevelHigh(x.ho.ho_maladministration_per_10k_12m, Q.ho_maladministration_per_10k_12m)];
    if (!bands.some(v => v !== 'none')) return 'none';
    return bands.includes('bad') ? 'bad' : bands.includes('poor') ? 'poor' : 'good'; };
  // where a landlord holds homes: code -> [{la, homes}]
  const holdings = {};
  for (const [la, v] of Object.entries(D.las)) for (const h of v.landlords) (holdings[h.code] ||= []).push({ la, homes: h.homes });
  const laBand = code => { const la = D.las[code]; let tot = 0, known = 0, bad = 0, poor = 0;
    for (const h of la.landlords) { tot += h.homes; const b = standingOf(h.code); if (b !== 'none') { known += h.homes; if (b === 'bad') bad += h.homes; if (b === 'poor') poor += h.homes; } }
    return { tot, known, bad, poor, share_bad: tot ? bad / tot : null, share_bad_or_poor: tot ? (bad + poor) / tot : null }; };
  return { ALL, DIST, betterThan, standingOf, holdings, laBand };
}

const BAND_TXT = { good: 'no serious weaknesses in any of the four headline categories', poor: 'in the worst 25% of landlords for at least one headline category', bad: 'in the worst 10% of landlords for at least one headline category', none: 'too small to have to publish figures' };
const fmt = v => v == null ? null : Math.round(v * 10) / 10;
const norm = s => String(s || '').toLowerCase().replace(/[^a-z0-9 ]+/g, ' ').replace(/\s+/g, ' ').trim();

function findLandlord(D, q) {
  const n = norm(q); if (!n) return null;
  const entries = Object.entries(D.landlords);
  let hit = entries.find(([c, x]) => c.toLowerCase() === n || norm(x.name) === n);
  if (hit) return hit;
  const strip = s => norm(s).replace(/\b(limited|ltd|group|housing|association|trust|the|council|borough|of|london|city|district|royal|metropolitan)\b/g, '').replace(/\s+/g, ' ').trim();
  const ns = strip(n);
  hit = entries.find(([, x]) => strip(x.name) === ns) || entries.find(([, x]) => norm(x.name).includes(n)) || entries.find(([, x]) => ns && strip(x.name).includes(ns));
  return hit || null;
}
function findBorough(D, q) {
  const n = norm(q); if (!n) return null;
  const entries = Object.entries(D.las);
  const strip = s => norm(s).replace(/\b(london borough of|royal borough of|city of|borough|council|district|metropolitan)\b/g, '').replace(/\s+/g, ' ').trim();
  const ns = strip(n);
  return entries.find(([c, v]) => c.toLowerCase() === n || norm(v.name) === n) || entries.find(([, v]) => strip(v.name) === ns) || entries.find(([, v]) => norm(v.name).includes(n)) || null;
}
function findRegion(D, q) {
  const n = norm(q); const regions = [...new Set(Object.values(D.las).map(v => v.region))];
  return regions.find(r => norm(r) === n) || regions.find(r => norm(r).includes(n) || n.includes(norm(r).split(' ')[0])) || null;
}

function landlordRow(D, P, code, measure) {
  const x = D.landlords[code]; if (!x) return null;
  const row = { code, name: x.name, type: x.type === 'LA' ? 'council' : 'housing association', homes: Math.round(x.homes || 0), band: P.standingOf(code) };
  if (measure) { const v = valueOf(x, measure); row.value = fmt(v); row.unit = MEAS[measure].u;
    const pct = P.betterThan(P.DIST[measure], v, MEAS[measure].hib); row.better_than_pct_of_landlords = pct == null ? null : Math.round(pct * 100); }
  return row;
}

function landlordProfile(D, P, code) {
  const x = D.landlords[code];
  const measures = {};
  for (const k of Object.keys(MEAS)) { const v = valueOf(x, k); if (v == null) continue;
    const pct = P.betterThan(P.DIST[k], v, MEAS[k].hib);
    measures[k] = { label: MEAS[k].l, value: fmt(v), unit: MEAS[k].u, better_than_pct_of_landlords: Math.round(pct * 100) }; }
  const g = x.grades || {};
  const holds = (P.holdings[code] || []).slice().sort((a, b) => b.homes - a.homes).slice(0, 6).map(h => ({ borough: D.las[h.la].name, homes: h.homes }));
  return {
    code, name: x.name, type: x.type === 'LA' ? 'council' : 'housing association', homes_in_england: Math.round(x.homes || 0),
    overall_band: P.standingOf(code), overall_band_meaning: BAND_TXT[P.standingOf(code)],
    regulator_grades: { consumer: g.C, consumer_date: g.C_date, governance: g.G, viability: g.V,
      moved_at_latest_judgement: g.chg && Object.keys(g.chg).length ? g.chg : undefined, latest_judgement_date: g.date || undefined, route_to_judgement: g.route || undefined,
      grading_under_review: g.under_review || undefined, enforcement_notice: g.enforcement || undefined,
      note: 'C1 best to C4 worst on how tenants are treated; G and V are governance and financial viability. Null means not yet inspected. moved_at_latest_judgement is the Regulator\u2019s own up/down for each grade; "Responsive Engagement" means the Regulator stepped in over a concern raised with it.' },
    previous_year_measures: x.prev ? Object.fromEntries(Object.entries(x.prev).filter(([k, v]) => v != null && MEAS[k]).map(([k, v]) => [k, fmt(v)])) : undefined,
    weekly_rent: rentOf(D, x),
    council_return: councilOf(D, x),
    homes_built_and_sold: x.stock ? { source: 'Regulator Statistical Data Return, low cost rental stock owned, all rent types', homes_start_of_year: x.stock.start, newly_built: x.stock.built, bought_from_other_landlords: x.stock.bought, other_gains: x.stock.other_gains,
      sold_to_tenants_right_to_buy_and_similar: x.stock.sold_tenants, sold_to_other_social_landlords: x.stock.sold_social, sold_out_of_social_housing: x.stock.sold_out, converted_to_shared_ownership: x.stock.to_shared_ownership,
      demolished: x.stock.demolished, other_losses: x.stock.other_losses, moved_within_group_net: x.stock.intra_group_net, homes_end_of_year: x.stock.end } : undefined,
    ombudsman: x.ho ? { decisions_since_dec_2020: x.ho.ho_cases_all, went_against_landlord: x.ho.ho_maladministration_all, severe_maladministration: x.ho.ho_severe_all,
      last_12_months: { decisions: x.ho.ho_cases_12m, went_against_landlord: x.ho.ho_maladministration_12m, severe: x.ho.ho_severe_12m, findings_per_10k_homes: x.ho.ho_maladministration_per_10k_12m } } : null,
    measures, largest_holdings: holds, complaints_page: x.cx || null,
    cost_per_home: costOf(D, x),
  };
}

// The Regulator's Headline Social Housing Cost per unit, for housing associations in the Global
// Accounts. Handed over with its own reading rules, because a cost is the one figure here that
// must not be turned into a grade.
const SEG_WORD = { GN: 'general-needs housing associations', SH: 'supported-housing providers', HOP: 'providers of housing for older people' };
function costOf(D, x) {
  const M = D.vfm_meta;
  if (x.type === 'LA') return { available: false, reason: 'Councils are outside the Regulator\u2019s Global Accounts; no like-for-like cost per home is published.' };
  const v = x.vfm;
  if (!v || v.hshc == null || !M) return { available: false, reason: 'Not in the Regulator\u2019s Value for Money tables for this year (reports inside a group, newer or for-profit provider, or merged in the year).' };
  const seg = M.segments[v.seg] || M.segments.GN;
  return {
    available: true, year: M.year, spent_per_home_gbp: v.hshc, previous_year_gbp: v.hshc_prev,
    compared_with: `${seg.n} ${SEG_WORD[v.seg] || SEG_WORD.GN}`, segment_median_gbp: seg.median,
    share_of_that_group_costing_less_pct: v.pct_below,
    where_it_went_gbp_per_home: v.parts ? { repairs_and_maintenance: v.parts.rm, management: v.parts.mgmt, service_charges: v.parts.svc, other: v.parts.oth,
      repairs_and_maintenance_share_of_group_spending_less_pct: v.rm_pct_below, group_median_repairs_and_maintenance_gbp: seg.rm_median,
      source: 'Global Accounts 2025 datafile, consolidated group figures; the parts reproduce the published headline' }
      : { note: 'The Regulator\u2019s published total leaves out some items in the accounts for this landlord, so no split is given.' },
    lettings_account: v.flow ? { rent_and_service_charges_collected_gbp_per_home: v.flow.rent, lost_to_empty_homes_gbp_per_home: v.flow.void,
      kept_after_running_costs_gbp_per_home: v.flow.surplus, operating_margin_pct: v.flow.margin, margin_share_of_group_lower_pct: v.flow.margin_pct_below, group_median_margin_pct: seg.margin_median,
      interest_to_lenders_gbp_per_social_home: v.flow.interest, owed_to_lenders_gbp_per_home: v.flow.debt,
      arrears_owed_by_current_tenants_pct_of_annual_rent: v.flow.arrears, arrears_share_of_group_lower_pct: v.flow.arrears_pct_below, group_median_arrears_pct: seg.arrears_median,
      written_off_as_uncollectable_gbp_per_home: v.flow.baddebt, social_homes_built_or_bought: v.flow.built, social_homes_sold_or_demolished: v.flow.sold, social_homes_transferred_net: v.flow.transf, social_homes_owned_year_end: v.flow.owned,
      note: 'A surplus is not profit: it pays interest and funds new homes. Kept is the Regulator\u2019s operating surplus on lettings and does not equal rent minus cost per home. A loss is a negative kept figure.' } : undefined,
    how_to_read: 'This is a cost, not a grade: higher is not worse and lower is not better. London and older or high-rise stock cost more to run; a low figure can mean efficiency or under-spending. State it beside the repairs and safety figures and let the reader weigh them; do not call a landlord efficient or wasteful from this number alone.',
  };
}

// What tenants pay, from the Statistical Data Return. Rent follows a national formula on local
// earnings and property values, so the only comparison offered is with neighbours in the same boroughs.
function rentOf(D, x) {
  const R = x.rent, M = D.rent_meta;
  if (x.type === 'LA') return { available: false, reason: 'Councils are outside the Statistical Data Return; no like-for-like weekly rent is published here yet.' };
  if (!R || R.gn == null || !M) return { available: false };
  return { available: true, year: M.year, general_needs_average_weekly_net_rent_gbp: R.gn, one_bed_gbp: R.gn1, two_bed_gbp: R.gn2, three_bed_gbp: R.gn3,
    average_weekly_service_charge_gbp: R.svc, share_of_homes_with_service_charge: R.svc_share, supported_and_older_people_average_weekly_rent_gbp: R.sh,
    pct_dearer_than_other_landlords_in_same_boroughs: R.vs, england_general_needs_average_gbp: M.england_gn,
    how_to_read: 'Net rent excludes service charges. Compare only with landlords in the same boroughs: pct_dearer_than_other_landlords_in_same_boroughs is a percentage difference in rent, not a percentile — +0.7 means this landlord charges 0.7% more than the other housing associations in the boroughs where it has homes, −2 means 2% less; within about 1% either way call it in line. A London landlord charging more than a northern one says nothing about either.' };
}

// The council card: the council's own Local Authority Housing Statistics return, compared only
// with other stock-owning councils. Not the Regulator's cost figure and never set against housing
// associations.
function councilOf(D, x) {
  const C = x.lahs, M = D.lahs_meta;
  if (x.type !== 'LA') return undefined;
  if (!C || !M) return { available: false, reason: 'No owned-stock return in the Local Authority Housing Statistics for this year.' };
  const med = k => (M.m[k] || {}).median;
  return { available: true, year: M.year, compared_with: `${M.n} councils that own homes`,
    homes_owned: C.homes, rent_due_gbp_per_home_per_year: C.rent_per_home, council_median_rent_due_gbp: med('rent_per_home'),
    arrears_owed_by_current_tenants_pct_of_rent_roll: C.arrears_pct, arrears_share_of_councils_lower_pct: C.arrears_pct_pct_below, council_median_arrears_pct: med('arrears_pct'),
    rent_collection_rate_pct: C.collection_rate, collection_share_of_councils_lower_pct: C.collection_rate_pct_below, council_median_collection_pct: med('collection_rate'),
    lost_to_empty_homes_gbp_per_home: C.void_per_home, written_off_gbp_per_home: C.written_off_per_home,
    homes_empty_at_31_march: C.vacant, homes_empty_pct: C.vacant_pct, empty_over_six_months: C.vacant_over_6m, average_relet_days: C.relet_days, council_median_relet_days: med('relet_days'),
    evictions: C.evictions, evictions_for_rent_arrears: C.evictions_arrears, evictions_per_1000_homes: C.evictions_per_1000,
    homes_built: C.built, homes_bought: C.acquired, homes_sold_total: C.sales_total, right_to_buy_sales: C.rtb_sales, right_to_buy_applications: C.rtb_applications,
    right_to_buy_average_price_gbp: C.rtb_avg_price, right_to_buy_average_discount_gbp: C.rtb_avg_discount, homes_demolished: C.demolished,
    major_works_on_existing_homes_gbp_per_home: C.capital_works_per_home, council_median_major_works_gbp: med('capital_works_per_home'), share_of_homes_with_major_works_pct: C.capital_works_homes_pct,
    outstanding_cost_to_make_all_homes_decent_gbp_per_home: C.cost_to_decent_per_home, non_decent_homes: C.nondecent_n,
    homes_inspected_for_decent_homes_last_5_years_pct: C.dhs_inspected_pct, inspected_basis: C.dhs_inspected_basis, council_median_inspected_pct: med('dhs_inspected_pct'),
    how_to_read: 'Compare a council only with other councils. Major works spending is capital spending, not the Regulator\u2019s cost per home, and is not a grade. A low inspection percentage means the council\u2019s Decent Homes figure rests on few inspections. Weekly rents for councils are not in this return.' };
}

function boroughProfile(D, P, code, limit = 10) {
  const la = D.las[code]; const b = P.laBand(code);
  const rows = la.landlords.slice().sort((a, c) => c.homes - a.homes).slice(0, limit).map(h => { const r = landlordRow(D, P, h.code); return r ? { ...r, homes_here: h.homes } : { code: h.code, homes_here: h.homes, note: 'under 1,000 homes nationally, so not required to publish' }; });
  return {
    code, name: la.name, region: la.region, social_homes: la.total, council_homes: la.council_homes, housing_association_homes: la.prp_homes, landlords: la.n_landlords,
    share_of_homes_with_a_worst_10pct_landlord: b.share_bad == null ? null : Math.round(b.share_bad * 100),
    share_of_homes_with_a_worst_25pct_landlord: b.share_bad_or_poor == null ? null : Math.round(b.share_bad_or_poor * 100),
    weighted_metrics: la.metrics, largest_landlords_here: rows,
  };
}

function regionSummary(D, P, region, limit = 8) {
  const las = Object.entries(D.las).filter(([, v]) => v.region === region);
  let tot = 0, bad = 0, poor = 0;
  const boroughs = las.map(([c, v]) => { const b = P.laBand(c); tot += b.tot; bad += b.bad; poor += b.poor;
    return { code: c, name: v.name, social_homes: v.total, share_with_worst_10pct_landlord: b.share_bad == null ? null : Math.round(b.share_bad * 100) }; })
    .sort((a, b) => (b.share_with_worst_10pct_landlord ?? -1) - (a.share_with_worst_10pct_landlord ?? -1));
  // landlords with the most homes in the region, with their band
  const homesBy = {};
  for (const [c, v] of las) for (const h of v.landlords) homesBy[h.code] = (homesBy[h.code] || 0) + h.homes;
  const top = Object.entries(homesBy).sort((a, b) => b[1] - a[1]).slice(0, limit).map(([code, h]) => { const r = landlordRow(D, P, code); return r ? { ...r, homes_in_region: h } : null; }).filter(Boolean);
  return { region, boroughs: las.length, social_homes: tot,
    share_of_homes_with_a_worst_10pct_landlord: tot ? Math.round(bad / tot * 100) : null,
    share_of_homes_with_a_worst_25pct_landlord: tot ? Math.round((bad + poor) / tot * 100) : null,
    boroughs_by_exposure: boroughs.slice(0, limit), largest_landlords_in_region: top };
}

function englandSummary(D, P) {
  // Same basis as the map and the England card: every holding in every borough, so the
  // denominator includes homes whose landlord is too small to report. The card's 46% and
  // this figure must agree.
  let tot = 0, bad = 0, good = 0, severe = 0;
  for (const [la, v] of Object.entries(D.las)) for (const h of v.landlords) { tot += h.homes; const b = P.standingOf(h.code); if (b === 'bad') bad += h.homes; if (b === 'good') good += h.homes; }
  for (const x of Object.values(D.landlords)) severe += (x.ho && x.ho.ho_severe_all) || 0;
  const regions = [...new Set(Object.values(D.las).map(v => v.region))].map(r => { const s = regionSummary(D, P, r, 1); return { region: r, social_homes: s.social_homes, share_with_worst_10pct_landlord: s.share_of_homes_with_a_worst_10pct_landlord }; })
    .sort((a, b) => b.share_with_worst_10pct_landlord - a.share_with_worst_10pct_landlord);
  // The year's supply: every housing association stock return and every council return on the record, summed.
  const HA = { landlords_counted: 0, homes_start_of_year: 0, newly_built: 0, bought_from_other_landlords: 0, other_gains: 0, sold_to_tenants: 0, sold_to_other_social_landlords: 0, sold_out_of_social_housing: 0, converted_to_shared_ownership: 0, demolished: 0, other_losses: 0, net_change: 0, homes_end_of_year: 0 };
  const LA = { councils_counted: 0, newly_built: 0, bought: 0, sold_total: 0, of_which_right_to_buy: 0, demolished: 0, net_change: 0, homes_owned_31_march: 0 };
  for (const x of Object.values(D.landlords)) {
    const S = x.stock, C = x.lahs;
    if (S) { HA.landlords_counted++; HA.homes_start_of_year += S.start; HA.newly_built += S.built; HA.bought_from_other_landlords += S.bought; HA.other_gains += S.other_gains; HA.sold_to_tenants += S.sold_tenants;
      HA.sold_to_other_social_landlords += S.sold_social; HA.sold_out_of_social_housing += S.sold_out; HA.converted_to_shared_ownership += S.to_shared_ownership; HA.demolished += S.demolished; HA.other_losses += S.other_losses; HA.net_change += netHA(S); HA.homes_end_of_year += S.end; }
    if (x.type === 'LA' && C) { LA.councils_counted++; LA.newly_built += C.built || 0; LA.bought += C.acquired || 0; LA.sold_total += C.sales_total || 0; LA.of_which_right_to_buy += C.rtb_sales || 0; LA.demolished += C.demolished || 0;
      LA.net_change += (C.built || 0) + (C.acquired || 0) - (C.sales_total || 0) - (C.demolished || 0); LA.homes_owned_31_march += C.homes || 0; }
  }
  const median = arr => { const a = arr.filter(v => v != null).sort((x, y) => x - y); return a.length ? a[Math.floor(a.length / 2)] : null; };
  const all = Object.values(D.landlords);
  const supply = { year: D.rent_meta ? D.rent_meta.year : '2024/25', housing_associations: HA, councils: LA, combined_net_change: HA.net_change + LA.net_change,
    note: 'Housing associations: Regulator Statistical Data Return stock balance sheet, low cost rental homes owned, all rent types, landlords of 1,000+ homes; sales to other social landlords are still social homes, just under a different landlord. Councils: MHCLG Local Authority Housing Statistics, homes the council owns. Net change counts built and bought minus sold, demolished and lost. Homes moved within a group are excluded. This is the record, not a national statistic: landlords under 1,000 homes are not on it.' };
  const medians = { arrears_pct_housing_associations: median(all.filter(x => x.type !== 'LA').map(x => figOf(x, 'arrears_pct'))), arrears_pct_councils: median(all.filter(x => x.type === 'LA').map(x => figOf(x, 'arrears_pct'))),
    operating_margin_pct_housing_associations: median(all.map(x => figOf(x, 'operating_margin_pct'))), weekly_rent_general_needs_housing_associations: D.rent_meta ? D.rent_meta.england_gn : null,
    cost_per_home_general_needs_housing_associations: D.vfm_meta ? D.vfm_meta.segments.GN.median : null, rent_collection_rate_pct_councils: median(all.map(x => figOf(x, 'rent_collection_rate_pct'))) };
  return { landlords_on_the_record: Object.keys(D.landlords).length, boroughs: Object.keys(D.las).length, social_homes: Math.round(tot), homes_built_and_sold_this_year: supply, sector_medians: medians,
    share_of_homes_with_a_worst_10pct_landlord: Math.round(bad / tot * 100), share_of_homes_with_a_landlord_with_no_serious_weakness: Math.round(good / tot * 100),
    severe_maladministration_findings_since_2020: severe, tsm_year: D.meta.tsm_year, ombudsman_window: `${D.meta.ho_window_from} to ${D.meta.ho_latest_month}`, regions_by_exposure: regions };
}

// ---------- tools ----------
const TOOLS = [
  { name: 'rank_landlords', description: 'Rank landlords on one measure. Use for best/worst questions. Returns real published values with each landlord\'s percentile among all reporting landlords.',
    input_schema: { type: 'object', properties: {
      measure: { type: 'string', enum: Object.keys(MEAS), description: 'Which measure. safety_checks is the weakest of the five safety checks; ombudsman_findings_per_10k is Ombudsman findings against the landlord per 10,000 homes in the last 12 months.' },
      direction: { type: 'string', enum: ['best', 'worst'] },
      limit: { type: 'integer', minimum: 1, maximum: 15, default: 5 },
      type: { type: 'string', enum: ['council', 'housing association', 'any'], default: 'any' },
      region: { type: 'string', description: 'Optional English region name, e.g. London, North West' },
      borough: { type: 'string', description: 'Optional borough or council area name; ranks only landlords with homes there' },
      min_homes: { type: 'integer', description: 'Optional minimum homes in England, e.g. 5000 to exclude small landlords' } },
      required: ['measure', 'direction'] } },
  { name: 'rank_figures', description: 'Rank landlords on a money, rent or stock figure: homes built, bought, sold or demolished this year, net change in homes, weekly rent, arrears, rent lost to empty homes, operating margin, cost per home, debt, and the council-only figures (collection rate, empty homes, re-let days, evictions, capital works, Decent Homes inspections). Use for questions like who built the most, who sold the most, who charges the most rent, who has the highest arrears. Returns real published values.',
    input_schema: { type: 'object', properties: {
      figure: { type: 'string', enum: Object.keys(FIGS) },
      direction: { type: 'string', enum: ['highest', 'lowest'] },
      limit: { type: 'integer', minimum: 1, maximum: 15, default: 5 },
      type: { type: 'string', enum: ['council', 'housing association', 'any'], default: 'any' },
      region: { type: 'string', description: 'Optional English region name' },
      borough: { type: 'string', description: 'Optional borough or council area name; ranks only landlords with homes there' },
      min_homes: { type: 'integer', description: 'Optional minimum homes in England' } },
      required: ['figure', 'direction'] } },
  { name: 'get_landlord', description: 'Full published profile of one landlord: every measure with its percentile, Regulator grades, Ombudsman record, weekly rent, lettings account, homes built and sold, where it holds homes.',
    input_schema: { type: 'object', properties: { name: { type: 'string', description: 'Landlord name or code' } }, required: ['name'] } },
  { name: 'get_borough', description: 'Profile of one borough or council area: homes, the share of its homes with a worst-10% landlord, homes-weighted metrics, and its largest landlords with their band.',
    input_schema: { type: 'object', properties: { name: { type: 'string' }, limit: { type: 'integer', minimum: 1, maximum: 30, default: 10 } }, required: ['name'] } },
  { name: 'region_summary', description: 'Summary of an English region: total homes, share with a worst-10% landlord, boroughs ranked by that exposure, largest landlords in the region with their band. Use this for questions about London, the North, etc.',
    input_schema: { type: 'object', properties: { region: { type: 'string', description: 'One of: East Midlands, East of England, London, North East, North West, South East, South West, West Midlands, Yorkshire and The Humber' }, limit: { type: 'integer', minimum: 1, maximum: 20, default: 8 } }, required: ['region'] } },
  { name: 'england_summary', description: 'National figures: homes on the record, share of homes with a worst-10% landlord, severe maladministration findings, every region ranked by exposure, and the year\u2019s supply totals — homes built, bought, sold (to tenants, to other landlords, out of social housing), demolished and the net change, for housing associations and councils — plus sector medians for arrears, margin, rent and cost.',
    input_schema: { type: 'object', properties: {} } },
  { name: 'compare_landlords', description: 'Side-by-side comparison of two to five landlords on the four headline categories and their grades.',
    input_schema: { type: 'object', properties: { names: { type: 'array', items: { type: 'string' }, minItems: 2, maxItems: 5 } }, required: ['names'] } },
];

function runTool(D, P, name, input, refs) {
  const addL = c => { if (c && !refs.landlords.includes(c) && refs.landlords.length < 10) refs.landlords.push(c); };
  const addB = c => { if (c && !refs.boroughs.includes(c) && refs.boroughs.length < 10) refs.boroughs.push(c); };
  const addScope = codes => { for (const c of codes) if (!refs.scope.includes(c)) refs.scope.push(c); };
  const regionLAs = r => Object.entries(D.las).filter(([, v]) => v.region === r).map(([c]) => c);
  switch (name) {
    case 'rank_landlords': {
      const m = input.measure; if (!MEAS[m]) return { error: `Unknown measure ${m}` };
      const hib = MEAS[m].hib; const best = input.direction !== 'worst';
      let pool = Object.keys(D.landlords);
      if (input.type && input.type !== 'any') pool = pool.filter(c => (D.landlords[c].type === 'LA') === (input.type === 'council'));
      if (input.min_homes) pool = pool.filter(c => (D.landlords[c].homes || 0) >= input.min_homes);
      let scope = 'England';
      if (input.borough) { const b = findBorough(D, input.borough); if (!b) return { error: `No borough matching "${input.borough}"` };
        const set = new Set(b[1].landlords.map(h => h.code)); pool = pool.filter(c => set.has(c)); scope = b[1].name; addB(b[0]); addScope([b[0]]); }
      else if (input.region) { const r = findRegion(D, input.region); if (!r) return { error: `No region matching "${input.region}"` };
        const set = new Set(); for (const v of Object.values(D.las)) if (v.region === r) for (const h of v.landlords) set.add(h.code); pool = pool.filter(c => set.has(c)); scope = r; addScope(regionLAs(r)); }
      const rows = pool.map(c => ({ c, v: valueOf(D.landlords[c], m) })).filter(r => r.v != null)
        // best with higher-is-better, and worst with lower-is-better, both mean descending
        .sort((a, b) => (!!hib === !!best) ? b.v - a.v : a.v - b.v)
        .slice(0, Math.min(15, input.limit || 5))
        .map(r => landlordRow(D, P, r.c, m));
      rows.forEach(r => addL(r.code));
      return { measure: MEAS[m].l, higher_is_better: !!hib, direction: best ? 'best' : 'worst', scope, reporting_landlords_in_scope: pool.filter(c => valueOf(D.landlords[c], m) != null).length, results: rows,
        note: MEAS[m].neutral ? 'This measure is reported but not judged: more recorded cases can mean more problems or better recording.' : undefined };
    }
    case 'rank_figures': {
      const k = input.figure; const f = FIGS[k]; if (!f) return { error: `Unknown figure ${k}` };
      const highest = input.direction !== 'lowest';
      let pool = Object.keys(D.landlords);
      if (input.type && input.type !== 'any') pool = pool.filter(c => (D.landlords[c].type === 'LA') === (input.type === 'council'));
      if (input.min_homes) pool = pool.filter(c => (D.landlords[c].homes || 0) >= input.min_homes);
      let scope = 'England';
      if (input.borough) { const b = findBorough(D, input.borough); if (!b) return { error: `No borough matching "${input.borough}"` };
        const set = new Set(b[1].landlords.map(h => h.code)); pool = pool.filter(c => set.has(c)); scope = b[1].name; addB(b[0]); addScope([b[0]]); }
      else if (input.region) { const r = findRegion(D, input.region); if (!r) return { error: `No region matching "${input.region}"` };
        const set = new Set(); for (const v of Object.values(D.las)) if (v.region === r) for (const h of v.landlords) set.add(h.code); pool = pool.filter(c => set.has(c)); scope = r; addScope(regionLAs(r)); }
      const all = pool.map(c => ({ c, v: figOf(D.landlords[c], k) })).filter(r => r.v != null);
      const rows = all.slice().sort((a, b) => highest ? b.v - a.v : a.v - b.v).slice(0, Math.min(15, input.limit || 5))
        .map(r => { const x = D.landlords[r.c]; return { code: r.c, name: x.name, type: x.type === 'LA' ? 'council' : 'housing association', homes: Math.round(x.homes || 0), value: r.v, unit: f.u }; });
      rows.forEach(r => addL(r.code));
      const total = all.reduce((s, r) => s + r.v, 0);
      return { figure: f.l, direction: highest ? 'highest' : 'lowest', scope, landlords_with_a_figure: all.length, total_across_them: f.u === '' ? Math.round(total) : undefined, results: rows,
        reading: f.dir === 0 ? 'This figure has no good or bad direction: report it as a fact, not a judgement. Cost and rent follow location and stock; counts follow size.' : f.dir > 0 ? 'Higher is better for tenants.' : 'Lower is better for tenants.',
        coverage: 'Housing association figures are from the Regulator\u2019s returns for landlords of 1,000+ homes; council figures from the council return. Some figures exist for one type only.' };
    }
    case 'get_landlord': { const hit = findLandlord(D, input.name); if (!hit) return { error: `No landlord on the record matching "${input.name}". Only landlords with 1,000+ homes in England are on it.` };
      addL(hit[0]); return landlordProfile(D, P, hit[0]); }
    case 'get_borough': { const hit = findBorough(D, input.name); if (!hit) return { error: `No borough matching "${input.name}"` };
      addB(hit[0]); addScope([hit[0]]); const prof = boroughProfile(D, P, hit[0], input.limit || 10); prof.largest_landlords_here.forEach(r => addL(r.code)); return prof; }
    case 'region_summary': { const r = findRegion(D, input.region); if (!r) return { error: `No region matching "${input.region}"` };
      addScope(regionLAs(r)); const s = regionSummary(D, P, r, input.limit || 8); s.boroughs_by_exposure.forEach(b => addB(b.code)); s.largest_landlords_in_region.forEach(l => addL(l.code)); return s; }
    case 'england_summary': return englandSummary(D, P);
    case 'compare_landlords': { const out = []; for (const n of (input.names || []).slice(0, 5)) { const hit = findLandlord(D, n); if (!hit) { out.push({ query: n, error: 'not on the record' }); continue; }
        addL(hit[0]); const p = landlordProfile(D, P, hit[0]);
        out.push({ name: p.name, type: p.type, homes: p.homes_in_england, overall_band: p.overall_band, consumer_grade: p.regulator_grades.consumer,
          safety_checks: p.measures.safety_checks, homes_failing_decent_homes: p.measures.non_decent_pct, repairs_on_time: p.measures.non_emergency_repairs_on_time_pct, ombudsman_findings_per_10k: p.measures.ombudsman_findings_per_10k }); }
      return { landlords: out }; }
    default: return { error: `Unknown tool ${name}` };
  }
}

// What a lookup did, in words a reader can follow while they wait. Built after the tool
// has run so it can use the names the record resolved, not the model's spelling.
function describe(name, input, out) {
  const and = xs => xs.length < 2 ? xs.join('') : xs.slice(0, -1).join(', ') + ' and ' + xs[xs.length - 1];
  const the = x => /^(North|South|East|West|Yorkshire)/.test(x) ? `the ${x}` : x;   // the North West; London
  switch (name) {
    case 'rank_landlords': {
      if (out.error) return `Looking for landlords in ${the(input.borough || input.region || 'England')}`;
      const who = input.type === 'council' ? 'councils' : input.type === 'housing association' ? 'housing associations' : 'landlords';
      const size = input.min_homes ? ` with ${input.min_homes.toLocaleString('en-GB')}+ homes` : '';
      return `Ranking ${who}${size} in ${the(out.scope)} on ${out.measure.toLowerCase()}, ${out.direction} first`; }
    case 'rank_figures': { if (out.error) return `Looking for landlords in ${the(input.borough || input.region || 'England')}`;
      const who = input.type === 'council' ? 'councils' : input.type === 'housing association' ? 'housing associations' : 'landlords';
      return `Ranking ${who} in ${the(out.scope || 'England')} by ${(out.figure || input.figure).split(' (')[0].toLowerCase()}`; }
    case 'get_landlord': return out.error ? `Looking for “${input.name}” on the record` : `Looking up ${out.name}`;
    case 'get_borough': return out.error ? `Looking for “${input.name}” on the record` : `Reading ${out.name}’s figures`;
    case 'region_summary': return out.error ? `Looking for “${input.region}”` : `Summing up ${the(out.region)}`;
    case 'england_summary': return 'Reading the national picture';
    case 'compare_landlords': { const names = (out.landlords || []).filter(l => !l.error).map(l => l.name); return names.length ? `Comparing ${and(names)}` : 'Comparing landlords'; }
    default: return 'Looking something up';
  }
}

// ---------- prompt ----------
function systemPrompt(D) {
  return `You answer questions about England's social landlords for The Housing Records, a public accountability site. You have query tools over the site's dataset. Rules, which are absolute:

1. Every number, name, grade and ranking you state must come from a tool result in this conversation. Never state a figure from memory. If you have not called a tool that returns it, you do not know it.
2. Call tools before answering. For best/worst questions on performance use rank_landlords. For who built, bought, sold or demolished the most, who charges the most rent, arrears, margins, cost or debt, use rank_figures. For how many homes were built, sold or added across England this year, use england_summary (it carries the year's supply totals). For a place, use get_borough or region_summary. For a landlord, get_landlord. Call several if the question needs them. Only say a figure is not on the record after the relevant tool has returned without it.
3. The data records WHAT is happening, not WHY. It has no information about funding, stock age, management, policy or history. When asked why, describe the pattern the data shows precisely, then say plainly that the record does not hold causes. Do not speculate about reasons.
4. Only landlords with 1,000 or more homes in England are on the record (${D.meta.n_landlords} of them). If a landlord is not found, say it is not on the record rather than guessing about it.
5. Be plain and specific. Name the landlords and give the actual figures, with the percentile where useful. Two to five short paragraphs at most; no headings. Write for a tenant, not an analyst. British English.
5a. Formatting: the page renders **bold**, *italic* and simple - bulleted or 1. numbered lists. Prose is the default and what most answers should be; reach for a short list only when the answer really is a list of landlords or places, and use **bold** sparingly — a name or a single figure that carries the answer, never a whole sentence. Nothing else in markdown is rendered, so do not use headings, tables, links or code marks: they would show as raw characters.
6. "Worst 10%" and "worst 25%" mean position among the reporting landlords on a measure. The four headline categories are: safety checks in date, homes failing the Decent Homes Standard, repairs on time, and Ombudsman findings per 10,000 homes.
7. Tenant satisfaction figures are self-reported by the landlord's own survey; safety and repairs figures are self-reported by the landlord to the Regulator; Ombudsman decisions are independent. Mention this only when it bears on the answer.
8. Sources: Regulator of Social Housing Tenant Satisfaction Measures ${D.meta.tsm_year}; Regulator consumer grades to ${D.meta.grades_date}; Housing Ombudsman decisions ${D.meta.ho_window_from} to ${D.meta.ho_latest_month}; Regulator Value for Money metrics ${D.vfm_meta ? D.vfm_meta.year : '2024/25'} for cost per home (housing associations only); Regulator Global Accounts 2025 datafile for the lettings account, arrears and debt; Regulator Statistical Data Return ${D.rent_meta ? D.rent_meta.year : '2024/25'} for weekly rents; MHCLG Local Authority Housing Statistics ${D.lahs_meta ? D.lahs_meta.year : '2024/25'} for the council return (arrears, empty homes, evictions, Right to Buy, capital works). Do not cite anything else.
8a. Cost per home is a cost, not a grade. Never describe a landlord as efficient, wasteful, or under-investing from it alone. Give the figure, the group it is compared with and its position, then set it beside the repairs or safety figure and stop. Councils have no comparable figure; say so if asked.
9. If the question is not about social housing in England, say briefly that this is all you can answer about.
10. Each question stands alone; there is no conversation to continue. Finish the answer completely and do not offer to look anything else up or ask what the reader wants next. The reader can open any landlord or place you name for its full card.`;
}

// ---------- rate limiting (per instance; good enough to stop casual abuse) ----------
const hits = new Map(); let dayKey = '', dayCount = 0;
function limited(ip) {
  const now = Date.now(); const k = new Date().toISOString().slice(0, 10);
  if (k !== dayKey) { dayKey = k; dayCount = 0; }
  if (dayCount >= (+process.env.ASK_DAILY_CAP || 200)) return 'The record has answered its daily quota of questions. Please try again tomorrow.';
  const arr = (hits.get(ip) || []).filter(t => now - t < 60_000);
  if (arr.length >= 8) return 'Too many questions in a minute. Give it a moment.';
  arr.push(now); hits.set(ip, arr); dayCount++;
  if (hits.size > 5000) hits.clear();
  return null;
}

// ---------- model ----------
// The model's reply is streamed so the page can be told what is happening as it happens:
// a lookup as soon as the model starts to ask for it, its full description once the
// arguments are in, and the answer text word by word. The events are folded back into an
// ordinary message object for the tool loop.
async function callModel(messages, system, hooks = {}, attempt = 0) {
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: { 'content-type': 'application/json', 'x-api-key': process.env.ANTHROPIC_API_KEY, 'anthropic-version': '2023-06-01' },
    // The system prompt and tool schemas are identical on every call, and a question makes
    // two or three calls seconds apart, so the later ones read the prefix from cache at a
    // tenth of the price.
    body: JSON.stringify({ model: MODEL, max_tokens: 1400, tools: TOOLS, stream: true,
      system: [{ type: 'text', text: system, cache_control: { type: 'ephemeral' } }], messages }),
  });
  if (!res.ok) {
    const t = await res.text();
    // a momentary upstream failure (overloaded, gateway) is worth one more go before giving up
    if ((res.status >= 500 || res.status === 529) && attempt === 0) { await new Promise(r => setTimeout(r, 800)); return callModel(messages, system, hooks, 1); }
    throw new Error(`model ${res.status}: ${t.slice(0, 300)}`);
  }
  const msg = { content: [], stop_reason: null, model: MODEL };
  const blocks = [], partial = {};
  const handle = ev => {
    switch (ev.type) {
      case 'message_start': if (ev.message && ev.message.model) msg.model = ev.message.model; break;
      case 'content_block_start': { const b = ev.content_block || {};
        blocks[ev.index] = b.type === 'tool_use' ? { type: 'tool_use', id: b.id, name: b.name, input: {} } : { type: 'text', text: b.text || '' };
        partial[ev.index] = ''; if (hooks.onBlockStart) hooks.onBlockStart(blocks[ev.index]); break; }
      case 'content_block_delta': { const b = blocks[ev.index], d = ev.delta || {}; if (!b) break;
        if (d.type === 'text_delta') { b.text += d.text; if (hooks.onText) hooks.onText(d.text); }
        else if (d.type === 'input_json_delta') partial[ev.index] += d.partial_json; break; }
      case 'content_block_stop': { const b = blocks[ev.index]; if (!b) break;
        if (b.type === 'tool_use') { try { b.input = partial[ev.index] ? JSON.parse(partial[ev.index]) : {}; } catch { b.input = {}; } }
        if (hooks.onBlockDone) hooks.onBlockDone(b); break; }
      case 'message_delta': if (ev.delta && ev.delta.stop_reason) msg.stop_reason = ev.delta.stop_reason; break;
      case 'error': throw new Error(`model stream: ${JSON.stringify(ev.error || ev).slice(0, 300)}`);
    }
  };
  const rd = res.body.getReader(), dec = new TextDecoder(); let buf = '';
  for (;;) {
    const { value, done } = await rd.read(); if (done) break;
    buf += dec.decode(value, { stream: true });
    let i; while ((i = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, i); buf = buf.slice(i + 2);
      const data = chunk.split('\n').filter(l => l.startsWith('data:')).map(l => l.slice(5).trim()).join('');
      if (data) handle(JSON.parse(data));
    }
  }
  msg.content = blocks.filter(b => b && !(b.type === 'text' && !b.text.trim()));
  return msg;
}

// What to show the moment the model starts asking for a lookup, before its arguments are in.
const STARTING = { rank_landlords: 'Ranking landlords', get_landlord: 'Looking up a landlord', get_borough: 'Reading a borough\u2019s figures',
  region_summary: 'Summing up a region', england_summary: 'Reading the national picture', compare_landlords: 'Comparing landlords' };

// onEvent is told what is happening as it happens: {step, replace} for a lookup or a stage
// of the work (replace: the last step is refined, not a new one), {text} for a piece of the
// answer as it is written, {discard} if text turned out to be thinking aloud before a lookup.
export async function answer(question, { model = callModel, onEvent = () => {} } = {}) {
  const D = data(), P = D._prepared;
  const refs = { landlords: [], boroughs: [], scope: [] };   // scope: borough codes the question was about, for the map
  const system = systemPrompt(D);
  const messages = [{ role: 'user', content: question }];
  const calls = [], steps = [];
  const STAGES = ['Weighing up the figures', 'Writing the answer'];
  const step = (t, replace) => { if (replace && steps.length) steps[steps.length - 1] = t; else steps.push(t); onEvent({ step: t, replace: !!replace }); };
  for (let turn = 0; turn < MAX_TURNS; turn++) {
    if (turn > 0) step('Weighing up the figures');
    const results = [], seen = new Set(); let streamed = false, writing = false;
    const hooks = {
      onBlockStart: b => { if (b.type === 'tool_use') { writing = false; step(STARTING[b.name] || 'Looking something up'); } },
      onBlockDone: b => {
        if (b.type !== 'tool_use' || seen.has(b.id)) return; seen.add(b.id);
        const out = runTool(D, P, b.name, b.input || {}, refs); calls.push({ tool: b.name, input: b.input });
        step(describe(b.name, b.input || {}, out), true);
        results.push({ type: 'tool_result', tool_use_id: b.id, content: JSON.stringify(out) }); },
      onText: t => { if (!t.trim() && !writing) return;
        if (!writing) { writing = true; step('Writing the answer', turn > 0 && steps[steps.length - 1] === 'Weighing up the figures'); }
        streamed = true; onEvent({ text: t }); },
    };
    const resp = await model(messages, system, hooks);
    const uses = (resp.content || []).filter(b => b.type === 'tool_use');
    if (resp.stop_reason !== 'tool_use' || !uses.length) {
      const text = (resp.content || []).filter(b => b.type === 'text').map(b => b.text).join('\n').trim();
      return { answer: text, refs, calls, steps: steps.filter(t => !STAGES.includes(t)), model: resp.model || MODEL };
    }
    if (streamed) {                                          // words before a lookup were not the answer
      for (let i = steps.length - 1; i >= 0; i--) if (steps[i] === 'Writing the answer') steps.splice(i, 1);
      onEvent({ discard: true }); }
    messages.push({ role: 'assistant', content: resp.content });
    uses.forEach(u => hooks.onBlockDone(u));                // a model that did not stream its blocks
    messages.push({ role: 'user', content: results });
  }
  return { answer: 'I could not settle on an answer from the data in a reasonable number of steps. Try a more specific question.', refs, calls, steps: steps.filter(t => !STAGES.includes(t)), model: MODEL };
}

// ---------- handler ----------
// Web-standard signature so the response can be streamed: one JSON line per step as the
// lookups happen, then a final line carrying the answer. A client that does not read
// streams still gets the whole thing at once.
const json = (status, obj) => new Response(JSON.stringify(obj), { status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });
export async function GET() { return json(405, { error: 'POST a JSON body {question}' }); }
export async function POST(request) {
  if (!process.env.ANTHROPIC_API_KEY) return json(503, { error: 'Asking is not switched on yet.' });
  let body = {}; try { body = await request.json(); } catch { body = {}; }
  const q = String((body && body.question) || '').trim();
  if (q.length < 3) return json(400, { error: 'Ask a question.' });
  if (q.length > MAX_Q) return json(400, { error: `Keep it under ${MAX_Q} characters.` });
  const ip = (request.headers.get('x-forwarded-for') || '').split(',')[0].trim() || 'anon';
  const lim = limited(ip); if (lim) return json(429, { error: lim });
  const enc = new TextEncoder();
  const stream = new ReadableStream({
    async start(ctrl) {
      const line = obj => ctrl.enqueue(enc.encode(JSON.stringify(obj) + '\n'));
      try { const out = await answer(q, { onEvent: line }); line({ done: out }); }
      catch (e) { console.error(e); line({ error: 'The record could not reach its model just now. Try again in a moment.' }); }
      ctrl.close();
    },
  });
  return new Response(stream, { status: 200, headers: { 'content-type': 'application/x-ndjson; charset=utf-8', 'cache-control': 'no-store', 'x-accel-buffering': 'no' } });
}
