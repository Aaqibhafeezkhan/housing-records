// Collect the "Orders" section of every Housing Ombudsman decision with a compensation order.
//
// The Ombudsman publishes compensation amounts only in the text of each decision, and has no bulk download,
// so this reads the decision pages one at a time, politely (about one every 3 seconds), and keeps only
// the Orders section. The result is the snapshot pipeline/read_compensation.py reads.
//
// How to run (about 11 hours for ~12,800 pages; it can be stopped and resumed):
//   1. Open any decision page on https://www.housing-ombudsman.org.uk/ in a desktop browser.
//   2. Paste this whole file into the developer console and press Enter. Progress is in window.__p.
//      Pages read are kept in the browser (IndexedDB), so reloading and re-running carries on where it stopped.
//   3. When window.__done is true, run  await saveOrders()  to download ho_orders.json. Gzip it and commit it
//      as data/raw/ho/ho_orders_<YYYY-MM>.json.gz, then run  bash pipeline/run.sh.
(async () => {
  const DATA = 'https://raw.githubusercontent.com/crbtgab/housing-records/main/data/';
  const parse = t => {
    const L = t.trim().split('\n'), h = L[0].split(',');
    return L.slice(1).map(l => {
      const o = {}, m = l.match(/("([^"]|"")*"|[^,]*)(,|$)/g) || [];
      h.forEach((k, i) => o[k] = (m[i] || '').replace(/,$/, '').replace(/^"|"$/g, ''));
      return o;
    });
  };
  const cases = parse(await fetch(DATA + 'out/ombudsman_cases.csv').then(r => r.text()));
  const comp = parse(await fetch(DATA + 'derived/ombudsman_compensation.csv').then(r => r.text()));
  const href = {};
  cases.forEach(c => href[c.case_id] = c.href);
  const ids = comp.map(r => r.case_id);

  const db = await new Promise((res, rej) => {
    const q = indexedDB.open('hrorders', 1);
    q.onupgradeneeded = () => q.result.createObjectStore('p');
    q.onsuccess = () => res(q.result);
    q.onerror = () => rej(q.error);
  });
  const store = mode => db.transaction('p', mode).objectStore('p');
  const put = (k, v) => new Promise((res, rej) => {
    const tx = db.transaction('p', 'readwrite'); tx.objectStore('p').put(v, k);
    tx.oncomplete = res; tx.onerror = () => rej(tx.error);
  });
  const all = () => new Promise(res => {
    const out = {}, q = store('readonly').openCursor();
    q.onsuccess = () => { const c = q.result; if (c) { out[c.key] = c.value; c.continue(); } else res(out); };
  });

  // Keep only the Orders section: from its heading to the next section ("Recommendations", "Our investigation").
  const orders = text => {
    const ls = text.split('\n');
    let s = -1;
    for (let i = 0; i < ls.length; i++) {
      if (/^(Orders?|Orders? and recommendations)$/i.test(ls[i].trim())) { s = i; break; }
    }
    if (s < 0) return '';
    let e = ls.length;
    for (let i = s + 2; i < ls.length; i++) {
      if (/^(Recommendations?|Our investigation|Back to top|Using this site)$/i.test(ls[i].trim())) { e = i; break; }
    }
    return ls.slice(s, e).join('\n').replace(/[ \t]+/g, ' ').replace(/\n\s*\n+/g, '\n').slice(0, 9000);
  };

  window.saveOrders = async () => {
    const got = await all(), out = {};
    for (const id of ids) out[id] = got[id] ? got[id].o : null;   // null: no published page found
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(out)], { type: 'application/json' }));
    a.download = 'ho_orders.json'; document.body.appendChild(a); a.click(); a.remove();
    return Object.keys(out).length;
  };

  const have = new Set(Object.keys(await all()));
  const box = document.createElement('div');
  box.style.cssText = 'position:absolute;left:-99999px;top:0;width:900px';
  document.body.appendChild(box);
  window.__p = { done: have.size, todo: ids.filter(i => href[i]).length, fail: 0 };
  window.__done = false;
  for (const id of ids) {
    if (window.__stop) break;
    if (have.has(id) || !href[id]) continue;
    let ok = false;
    try {
      const r = await fetch(href[id], { credentials: 'omit' });
      if (r.ok) {
        const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
        doc.querySelectorAll('script,style,noscript,iframe,header,footer,nav,img,svg,form').forEach(e => e.remove());
        box.innerHTML = doc.body.innerHTML;
        const o = orders(box.innerText);
        box.innerHTML = '';
        await put(id, { o });
        have.add(id); window.__p.done++; ok = true;
      }
    } catch (e) { /* counted below; re-running retries it */ }
    if (!ok) window.__p.fail++;
    await new Promise(r => setTimeout(r, (ok ? 1100 : 8000) + Math.random() * 500));
  }
  box.remove();
  window.__done = true;
})();
