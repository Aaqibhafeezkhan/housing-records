"""Inline site/data.json into site/index.html to make a single file that opens straight from disk
(no web server), for emailing or handing to someone who just wants to look at it.

Output: dist/the-housing-record.html
"""
import os

from paths import DIST, SITE

html = open(SITE + "index.html").read()
data = open(SITE + "data.json").read().replace("</", "<\\/")  # can't close the script tag early
marker = "<script>\n(async()=>{"
assert marker in html, "site/index.html no longer has the expected script opening"
html = html.replace(marker, f"<script>window.__DATA__={data};</script>\n{marker}", 1)

os.makedirs(DIST, exist_ok=True)
out = DIST + "the-housing-record.html"
open(out, "w").write(html)
print(f"{out}  {os.path.getsize(out)/1e6:.2f} MB")
