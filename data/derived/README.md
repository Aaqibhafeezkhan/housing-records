# Derived data

Figures this project worked out from published text, rather than took from a published table. They are
committed because they cannot be downloaded from anywhere else. Licensed under CC BY 4.0 (see
[`DATA-LICENCE.md`](../../DATA-LICENCE.md)).

## `ombudsman_compensation.csv`

The Housing Ombudsman's search records **that** a compensation order was made in a decision, not **how much**.
Amounts exist only in the "Orders" section of each published decision. This file holds one row per decision
that has a compensation order (12,861 decisions, crawled September 2026).

| Column | Meaning |
|---|---|
| `case_id` | The Ombudsman's case number. The decision is at `https://www.housing-ombudsman.org.uk/decisions/` (link in `data/out/ombudsman_cases.csv`). |
| `total` | Pounds ordered to be paid. `0` where the order is not monetary. Empty when quarantined. |
| `status` | `parsed` or `quarantined`. |
| `notes` | Labels the reader left. On quarantined rows they say why: `breakdown-mismatch` (a stated total and its breakdown do not reconcile) or `recurring` (a weekly or otherwise recurring award with no single total). On parsed rows, `prior-offer` marks a decision where a reference to an earlier offer was dropped rather than added. `head-only` and `parts-only` are further labels from the original reader; their exact rules will be written down when the reader is rebuilt. |

**Results:** 11,562 parsed (10,925 with a monetary figure, totalling £11.83m; 637 with no monetary order) and
1,299 quarantined.

### The rules the amounts were read with

The reader refuses rather than guesses:

- everything after a breakdown marker ("made up as follows", "which includes", "comprising", "of which",
  "broken down as") is a component of a total already counted, never an addition;
- clauses that *refer* to money rather than order it are dropped ("this replaces its previous offer of £200",
  "this sum includes the £380 offered at stage 2", "does not include the £440");
- a decision is quarantined, with no figure, where a stated total and its breakdown do not reconcile, or where
  the award is a weekly or recurring calculation.

Hand-checked against 13 decisions: 12 exact, the 13th quarantined rather than wrong.

**About one decision in eight has no figure by design, so every total built from this file is a floor.** The
site always says "at least £X, read from N of M decisions" and never calls it a total.

### Known gap

The program that produced this file was not kept with the project. The file is published as it was used on the
site, and `pipeline/build_ombudsman.py` reads it. Rebuilding the reader in `pipeline/`, so this file can be
regenerated and checked from the decisions themselves, is an open task. Until then, any figure can be checked by
hand against the linked decision.
