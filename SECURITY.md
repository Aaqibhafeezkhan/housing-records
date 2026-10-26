# Security

If you find a security problem — for example a way to misuse the "ask anything" feature, to run up costs, or
to change what the site shows — please **do not open a public issue**.

Email **[hello@housingrecords.org](mailto:hello@housingrecords.org)** with what you found and how to reproduce
it. You will get a reply within a week. Please give us a reasonable chance to fix it before telling anyone else.

## How the site is set up

- The website is static files served by Vercel; there is no database and no user accounts.
- The only server code is `api/ask.js`. Its service key is stored as a Vercel setting for the live site only.
  It is never in this repository and never available to preview builds.
- Questions are rate-limited per visitor and capped per day.
