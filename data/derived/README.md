# Derived data

Figures this project worked out from published text, rather than took from a published table. They are
committed because they cannot be downloaded from anywhere else. Licensed under CC BY 4.0 (see
[`DATA-LICENCE.md`](../../DATA-LICENCE.md)).

## `ombudsman_compensation.csv`

The Housing Ombudsman's search records **that** a compensation order was made in a decision, not **how much**.
Amounts exist only in the "Orders" section of each published decision. This file holds one row per decision
that has a compensation order (12,861 decisions).

It is written by [`pipeline/read_compensation.py`](../../pipeline/read_compensation.py) from the Orders text of
every decision, collected in November 2026 with [`pipeline/orders_crawler.js`](../../pipeline/orders_crawler.js)
and committed as `data/raw/ho/ho_orders_2026-11.json.gz`. Running `bash pipeline/run.sh` regenerates it.

| Column | Meaning |
|---|---|
| `case_id` | The Ombudsman's case number. The decision is linked from `data/out/ombudsman_cases.csv`. |
| `total` | Pounds the decision orders the landlord to pay. Empty when quarantined. |
| `status` | `parsed` or `quarantined`. |
| `notes` | `hand-checked` when the figure was checked by a person against the decision (see below). On quarantined rows, why: `no-amount-in-orders` (the Orders section names no sum of money), `open-ended` (for example "the replacement value", interest without a sum, an order to "re-offer", a sum for each of several residents), `recurring` (a weekly or monthly award with no single total), `total-mismatch` (separate orders and a stated total do not reconcile), `calculation-table` (the sums are set out in a table the reader cannot follow), `page-not-found` (no published decision page). On parsed rows, `unread-line` means the Orders section also mentions money that is not an order to pay, which was left out. |

**Results:** 12,355 decisions with a figure, totalling **£9.86m**; 506 quarantined (about one decision in 25).

### The rules the amounts are read with

The reader refuses rather than guesses:

- only the Orders section is read, never the account of the complaint around it, which is full of other sums
  (a resident's claim, service charges, the landlord's earlier offers);
- each order to pay counts once, at the amount it names. A breakdown under it ("made up of", "comprising", a
  list) is part of that amount, never added to it. A stated grand total ("in total the Ombudsman has ordered
  £X") wins over adding up separate orders;
- an order to pay an amount the landlord offered earlier counts, because the order says to pay it. An offer
  only referred to ("this replaces its offer of £200", "in addition to the £500 already offered") does not;
- a decision is quarantined, with no figure, where the award is recurring or open ended, where the order names
  no amount, or where the parts do not reconcile.

### Checked by hand

`ombudsman_compensation_checks.csv` lists 361 decisions checked by a person against the published decision,
with the old figure, the correct one and why. These always override the reader. They are:

- every award over £5,000 in the previous version of this file (311 decisions);
- a random sample of 50 smaller awards from the previous version.

**Why the file was rebuilt.** The previous version of this file was produced by a reader that was not kept, and
was hand-checked against only 13 decisions. Checking it properly showed it was badly wrong: of the 310 awards over
£5,000 with a published page, only 82 were right. 103 had counted a total *and* its breakdown, 92 had taken sums
from the account of the complaint rather than the order, and five more included the largest, a £3,582.82 award
recorded as £358,282. In the random sample of smaller awards, 13 of 50 were wrong. Its national total of
£11.83m was overstated.

**How good the new reader is.** On a further random 50 decisions it had not been tuned on, it gave the right
figure for 43. It left out four it could have read and read two too low; one was a judgement call. It read none
too high. Those 50 are not in the checks file; the reader's rules were then improved to read them correctly.
Because the reader errs towards leaving a decision out or reading it low, **every total built from this file is
a floor**. The site always says "at least £X, read from N of M decisions" and never calls it a total.

### Safety check

`pipeline/build_ombudsman.py` stops the build if any single award over £20,000 has not been checked by hand,
so a misreading like £358,282 cannot reach the site again.
