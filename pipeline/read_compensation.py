"""Read the amount of compensation ordered in each Housing Ombudsman decision.

The Ombudsman's dataset records THAT a compensation order was made, not how much. The amount exists only in
the "Orders" section of each published decision. This reads that section (collected by orders_crawler.js into
data/raw/ho/ho_orders_*.json.gz) and writes data/derived/ombudsman_compensation.csv.

The rules (see data/derived/README.md) - the reader refuses rather than guesses:
  * only the Orders section is read, never the story of the complaint around it;
  * each order to pay counts once, at the amount the order names. A breakdown under it ("made up of",
    "comprising", a list) is part of that amount, never added to it;
  * a separate order to pay an amount the landlord offered earlier counts, because the order says to pay it;
    an offer only referred to ("in addition to the £500 already offered", "this replaces its offer of £200")
    does not;
  * a stated grand total ("in total the Ombudsman has ordered £X", "a total of £X should be awarded") wins
    over adding up the separate orders;
  * the decision is quarantined, with no figure, where the award is recurring or open ended (weekly, "the
    replacement value", "the estimate", interest without a sum), where the order names no amount, or where the
    separate orders and a stated total do not reconcile.
Decisions checked by hand against the published decision are listed, with the reason, in
data/derived/ombudsman_compensation_checks.csv; that file always wins over the reader.

Usage: python3 read_compensation.py            (run from pipeline/, like the other steps)
"""
import csv, glob, gzip, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "data", "raw", "ho")
DERIVED = os.path.join(HERE, "..", "data", "derived")

AMT = r"£\s?(\d[\d,]*(?:\.\d{1,2})?)"
PAY = re.compile(
    r"(\bpay\b|\bpays\b|\bpaid\b|\bpayment\b|\baward\b|\bcompensation (?:of|totalling)\b)[^£]{0,120}?" + AMT, re.I)
TOTAL = re.compile(
    r"(\bin total\b[^£]{0,80}|\ba total of\b|\bthe total (?:compensation|amount|sum|award)(?: award| figure| to be paid)?"
    r"(?: is| of| would be)?(?: therefore)?\b)[^£]{0,40}?" + AMT, re.I)
NOT_TOTAL = re.compile(r"bring the total|including the|inclusive of|offered|previously|already|would replace", re.I)
REFER_ONLY = re.compile(
    r"^(this|that|these|the above|all|any|the (amount|sum|figure|total|compensation|award|amounts|sums)( above)?)\b[^£]{0,60}"
    r"\b(replaces|replace|includes|include|inclusive|deduct|deducted|offset|is in addition|are in addition|was offered|"
    r"had offered|offered|already paid)\b", re.I)
RECURRING = re.compile(r"\bper (week|month|day)\b|\ba week\b|\bweekly\b|\bfor each (week|month)\b until|\buntil the "
                       r"(works|repairs) (are|have been) completed", re.I)
OPEN_ENDED = re.compile(r"re-offer|\beach (resident|leaseholder|household|tenant)\b|replacement value|the estimate for|\binterest\b|reasonable costs|actual cost|"
                        r"consider (paying|whether)|reimburse[^£.]{0,40}(receipts|evidence)", re.I)
BREAK_OPEN = re.compile(r"made up|compris|compromis|consist|broken down|break ?down|as follows|which includes|"
                        r"calculated as follows|is based on|this includes:|:\s*$", re.I)


def num(s):
    s = s.replace(" ", "").rstrip(".,")
    if re.fullmatch(r"\d{1,3}(,\d{3})*,\d{2}", s):        # a typo like "£3,582,82"
        s = s[:-3].replace(",", "") + "." + s[-2:]
    return float(s.replace(",", ""))


def lines_of(text):
    out = []
    for l in text.split("\n"):
        l = re.sub(r"\s+", " ", l).strip()
        if l:
            out.append(l)
    return out


ORDER_CTX = re.compile(
    r"^(\(?[a-z0-9]{1,3}[.)]\s*)?((within|by|if)[^£,]{0,60}, )?(pay|pays|paid|make a payment|re-?pay)\b|\bthe landlord (pays|provides the resident with a payment)\b|\b(must|shall|should|will|is to|are to|to|ordered to|"
    r"order(s|ed)? (that )?(the landlord|it)( to)?|requires that the landlord|is ordered to|has been ordered to)\b[^£.]{0,60}?"
    r"\b(pay|pays|award|make a payment|provides? the resident with a payment|provide (documentary )?evidence (that )?it has (directly )?paid|"
    r"ensure it has (directly )?paid)\b", re.I)


def is_order_start(l):
    low = l.lower()
    if REFER_ONLY.search(low) or (low.startswith("if ") and "the full amount" in low):   # a conditional restatement
        return False
    return bool(ORDER_CTX.search(low))


def read(text):
    """Return (total or None, status, notes) for one decision's Orders section."""
    ls = lines_of(text)
    notes = []
    if not any("£" in l for l in ls):
        return None, "quarantined", ["no-amount-in-orders"]
    orders, totals = [], []
    in_break, items, comp_left = False, False, None
    for i, l in enumerate(ls):
        low = l.lower()
        if re.fullmatch(r"\d{1,2}|order|what the landlord must do|due date|no later than.*|\d{1,2} \w+ 20\d\d", low):
            in_break = False
            continue
        if "£" not in l:
            if is_order_start(l) and re.search(r":\s*$|the following (amounts|payments|sums)", l):
                items, in_break, comp_left = True, False, None   # "the landlord is ordered to pay the resident:" then a list
                continue
            if in_break and len(l) > 60 and not re.match(r"^[–\-•a-z(]", low):
                in_break = False
            continue
        t = TOTAL.search(l)
        if t and not NOT_TOTAL.search(l[: t.end() + 15]) and not re.match(r"^a total of £[\d,.]+ for", low) and (not is_order_start(l) or re.match(r"^(in total|a total of|the total)", low)):
            totals.append(num(t.group(2)))
            continue
        if in_break and orders and comp_left is not None:
            m = re.search(AMT, l)
            if m and num(m.group(1)) <= comp_left + 0.005:
                comp_left -= num(m.group(1))           # a component of the order above: never added
                continue
        if is_order_start(l) or items:
            m = PAY.search(l) or (items and re.match(r"^(\(?[a-z0-9]{1,3}[.)]\s*|[–\-•]\s*)?(the |a further |an additional )?" + AMT
                                              + r"\s+(?:for|as|in|to|towards|compensation|reimbursement|rent|offered|it offered|previously|already)\b", l, re.I))
            if m:
                v = num(m.groups()[-1])
                orders.append((v, l))
                extra = re.search(r"sum of £[\d,.]+ already offered,? and (an additional|a further)( amount of)? " + AMT, l, re.I)
                if extra:
                    orders.append((num(extra.groups()[-1]), l))
                in_break = bool(BREAK_OPEN.search(l)) and not items
                comp_left = v if in_break else None
                continue
        if in_break:
            continue                                   # a component of the order above: never added
        # a money line that is neither an order nor a breakdown: say so, and do not count it
        notes.append("unread-line")
    if any(re.search(r"\bre-?offer\b", l, re.I) for l in ls):
        return None, "quarantined", ["open-ended"]        # an order to offer again is not an order to pay
    inc = [re.search(r"increase its compensation[^£]{0,40}from " + AMT + r" to " + AMT, l, re.I) for l in ls]
    inc = [m for m in inc if m]
    if inc and not orders:
        orders = [(num(m.group(2)), m.group(0)) for m in inc]
    if any(RECURRING.search(l) for _, l in orders):
        return None, "quarantined", ["recurring"]
    if any(OPEN_ENDED.search(l) for _, l in orders):
        return None, "quarantined", ["open-ended"]
    if not orders and not totals:
        return None, "quarantined", ["no-amount-in-orders"]
    if sum(1 for l in ls if re.fullmatch(r"£\s?[\d,]+(\.\d{1,2})?\*?", l)) >= 3:
        return None, "quarantined", ["calculation-table"]    # amounts set out in a table the text reader cannot follow
    s = round(sum(v for v, _ in orders), 2)
    if totals:
        t = totals[-1]
        if orders and abs(s - t) > 0.005 and len(orders) > 1:
            return None, "quarantined", ["total-mismatch"]
        return round(t, 2), "parsed", sorted(set(notes))
    if "unread-line" in notes and len(orders) == 0:
        return None, "quarantined", ["no-amount-in-orders"]
    return s, "parsed", sorted(set(notes))


def main():
    snap = sorted(glob.glob(os.path.join(RAW, "ho_orders_*.json.gz")))[-1]
    pages = json.load(gzip.open(snap, "rt", encoding="utf-8"))
    checks = {r["case_id"]: r for r in csv.DictReader(open(os.path.join(DERIVED, "ombudsman_compensation_checks.csv")))}
    rows = []
    for cid in sorted(pages):                                # one row per decision with a compensation order
        if cid in checks:
            c = checks[cid]
            rows.append((cid, c["total"], c["status"], "hand-checked"))
            continue
        p = pages.get(cid)
        if p is None:                                        # no published page could be found for it
            rows.append((cid, "", "quarantined", "page-not-found"))
            continue
        total, status, notes = read(p)
        rows.append((cid, "" if total is None else f"{total:.2f}".rstrip("0").rstrip("."), status, " ".join(notes)))
    with open(os.path.join(DERIVED, "ombudsman_compensation.csv"), "w", newline="") as f:
        f.write("case_id,total,status,notes\n")
        for cid, t, s, n in rows:
            f.write(f'{cid},{t},{s},"{n}"\n')
    parsed = [r for r in rows if r[2] == "parsed"]
    money = [float(r[1]) for r in parsed if r[1] and float(r[1]) > 0]
    print(f"compensation: {len(rows)} decisions, {len(parsed)} parsed ({len(money)} with a figure, "
          f"£{sum(money):,.0f}), {len(rows) - len(parsed)} quarantined, {sum(1 for r in rows if r[3] == 'hand-checked')} hand-checked")


if __name__ == "__main__":
    main()
