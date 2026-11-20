// Checks the built site (public/) with Playwright: every page loads without errors or sideways scrolling at phone
// and desktop widths, in light and dark mode; nothing loads from outside the site; every internal link works;
// the fonts come from the site; and Ken's Sushi shows "Coming soon" (or store buttons once links are set).
// Run: node build.mjs && node test/site-check.cjs
const fs = require('fs'), path = require('path'), http = require('http'), { chromium } = require('playwright');
const PUB = path.join(__dirname, '..', 'public');
const TYPES = { '.html': 'text/html', '.css': 'text/css', '.woff2': 'font/woff2', '.png': 'image/png', '.txt': 'text/plain', '.xml': 'application/xml' };
const srv = http.createServer((q, r) => {
  let u = decodeURIComponent(q.url.split('?')[0].split('#')[0]); if (u.endsWith('/')) u += 'index.html';
  const f = path.join(PUB, u);
  fs.readFile(f, (e, d) => { if (e) { fs.readFile(path.join(PUB, '404.html'), (e2, d2) => { r.writeHead(404, { 'content-type': 'text/html' }); r.end(d2); }); return; } r.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' }); r.end(d); });
}).listen(0);
const fails = [], ok = (c, what, got) => { console.log((c ? '  ok   ' : '  FAIL ') + what + (got !== undefined ? ': ' + JSON.stringify(got) : '')); if (!c) fails.push(what); };
(async () => {
  const base = 'http://127.0.0.1:' + srv.address().port, b = await chromium.launch(), shotDir = process.argv[2];
  const pages = ['/', '/privacy/', '/terms/', '/support/', '/nope/'];
  const links = new Set();
  for (const [w, h, scheme] of [[390, 844, 'light'], [1200, 900, 'light'], [390, 844, 'dark']]){
    const c = await b.newContext({ viewport: { width: w, height: h }, colorScheme: scheme });
    for (const pg of pages){
      const p = await c.newPage(), errs = [], external = [];
      p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error' && !/404/.test(m.text())) errs.push(m.text()); });
      p.on('request', q => { if (!q.url().startsWith(base)) external.push(q.url()); });
      const res = await p.goto(base + pg); await p.waitForTimeout(700);
      const info = await p.evaluate(() => ({ sw: document.documentElement.scrollWidth, title: document.title, hrefs: [...document.querySelectorAll('a[href]')].map(a => a.href), fonts: [...document.fonts].filter(f => f.status === 'loaded').length, brackets: (document.body.innerText.match(/\[[A-Z][^\]]{3,60}\]/g) || []) }));
      info.hrefs.filter(u => u.startsWith(base)).forEach(u => links.add(u.split('#')[0]));
      ok(info.sw <= w && !errs.length && !external.length && info.fonts > 0, w + ' ' + scheme + ' ' + pg + ' (' + info.title + ')', { status: res.status(), scrollWidth: info.sw, errors: errs, external, fontsLoaded: info.fonts });
      if (w === 390 && scheme === 'light' && pg === '/privacy/') console.log('  note: placeholders shown until site.config.mjs is filled in:', [...new Set(info.brackets)]);
      if (shotDir && pg !== '/nope/') await p.screenshot({ path: path.join(shotDir, 'site-' + (pg.replace(/\//g, '') || 'home') + '-' + w + '-' + scheme + '.png'), fullPage: pg !== '/' });
      await p.close();
    }
    await c.close();
  }
  // every internal link resolves
  const bad = [];
  for (const u of links){ const r = await fetch(u.replace(/^http:\/\/127\.0\.0\.1:\d+/, base)); if (r.status !== 200) bad.push(u + ' ' + r.status); }
  ok(bad.length === 0, 'all ' + links.size + ' internal links work', bad);
  // Ken's Sushi on the home page: the lantern and the game's card
  const p = await b.newPage({ viewport: { width: 390, height: 844 } });
  await p.goto(base + '/'); await p.waitForTimeout(500);
  const lantern = await p.evaluate(() => [...document.querySelectorAll('.line')].map(l => l.querySelector('.ln-stat').textContent));
  ok(lantern.join('|') === 'Coming later|Coming later|Coming later|Coming soon|Coming later', 'game statuses on the note', lantern);
  await p.click('.line.live'); await p.waitForTimeout(600);
  const sheet = await p.evaluate(() => { const d = document.querySelector('[role="dialog"]:not([hidden]), dialog[open]'); return d ? d.innerText : ''; });
  ok(/Coming soon to iPhone and Android/.test(sheet) && !/prototype/i.test(sheet), 'Ken’s Sushi card says it’s coming soon', (sheet.match(/Coming soon[^\n]*/) || ['(not found)'])[0]);
  if (shotDir) await p.screenshot({ path: path.join(shotDir, 'site-home-sheet.png') });
  const txt = fs.readFileSync(path.join(PUB, 'app-ads.txt'), 'utf8');
  ok(/^#|google\.com, pub-\d+, DIRECT, f08c47fec0942fa0/.test(txt), 'app-ads.txt is valid', txt.trim());
  await b.close(); srv.close();
  console.log(fails.length ? '\nFAIL: ' + fails.length : '\nPASS: all checks'); process.exit(fails.length ? 1 : 0);
})();
