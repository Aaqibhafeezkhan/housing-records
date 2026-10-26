# Contributing to Housing Records

Thank you for helping. This project exists so that tenants, campaigners, journalists and policymakers can see
how social landlords perform, using figures anyone can check. Contributions of every size are welcome: a
corrected figure, a new source, a plainer sentence, or code.

## Before you start

- **Read the rules** at the top of [`METHOD.md`](METHOD.md). The three that matter most:
  1. Never fabricate a figure. Every number must trace to a published source.
  2. Where data is missing or withheld, say why. A blank is never a zero or a clean record.
  3. Cost and rent are never grades.
- **Found a figure that looks wrong?** You don't need to write code. [Open an issue](../../issues/new/choose)
  using the "A figure looks wrong" form, with a link to the source.
- **Planning something bigger?** Open an issue first to talk it through, so nobody's work is wasted.

## How a change gets made

1. **Fork** the repository and create a branch for your change.
2. **Make the change.** If it touches data, change the pipeline and rebuild with `bash pipeline/run.sh`. Never
   edit `site/data.json` or `data/out/*.csv` by hand: they must always be what the pipeline produces.
3. **Open a pull request** against `main` and fill in the checklist.
4. **Automated checks run** on your pull request, and Vercel builds a **preview** of the site with your change.
5. **The maintainer reviews it.** Every change needs the maintainer's approval before it is merged.
6. **Once merged**, the live site updates automatically within a few minutes.

The "ask anything" box does not work on preview links. That is deliberate: previews never get access to the
service key.

## Checklist for changes that touch figures

These come from the "Before shipping anything" list in `METHOD.md`:

- [ ] `bash pipeline/run.sh` completes with no assert failures (the asserts are the safety net, not noise)
- [ ] The landlord count matches the Regulator's own coverage sheet
- [ ] Three landlords spot-checked by hand against the source file
- [ ] Any new figure read or parsed from text is hand-checked against at least 10 real records
- [ ] No figure is shown where the underlying data was withheld
- [ ] New sources are added to `data/SOURCES.md` (landing page, file, what is taken, licence) and to
      `pipeline/fetch_sources.sh`
- [ ] Opened a full landlord card, a small-landlord card and a borough card on the preview

## Adding a new data source

A new source needs:

- a public landing page and a licence that allows reuse (the Open Government Licence v3.0 is ideal);
- an entry in `data/SOURCES.md` and a download line in `pipeline/fetch_sources.sh`;
- a pipeline step that joins it on the Regulator's registration code, with asserts that fail loudly if the
  publisher changes the format;
- wording on the site that says where each figure comes from and what it does not show.

If a source has gaps, show what is published and explain what is missing and why. Never fill the gap.

## Writing for the site

Write for a tenant, not an analyst: plain British English, short sentences, no jargon. Say what a figure is,
where it comes from and what it doesn't tell you.

## Conduct and contact

Everyone taking part agrees to the [code of conduct](CODE_OF_CONDUCT.md). Questions:
[hello@housingrecords.org](mailto:hello@housingrecords.org). Security problems: see [`SECURITY.md`](SECURITY.md).

By contributing, you agree that your code is released under the MIT licence and your data work under CC BY 4.0
(see [`LICENSE`](LICENSE) and [`DATA-LICENCE.md`](DATA-LICENCE.md)).
