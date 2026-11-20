// Checks the app build (www/) in a browser, with Playwright. Run: npm run build && node test/app-check.cjs
//  A. Nothing configured (a plain browser): app mode, no prototype parts, fonts from inside the app (no Google),
//     and the shop and ads fail safely instead of giving anything away.
//  B. A pretend iPhone, with stand-ins for the native plugins: the save comes back from app storage, the store's
//     prices show, purchases grant only on success, Ken's Club follows the subscription (and restores), rewarded
//     ads pay only when watched to the end, the consent and tracking prompts are asked, Android's back button
//     closes sheets, and the share picture goes to the share sheet.
const fs = require('fs'), path = require('path'), http = require('http'), { chromium } = require('playwright');
const WWW = path.join(__dirname, '..', 'www');
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.woff2': 'font/woff2', '.mp3': 'audio/mpeg', '.txt': 'text/plain' };
const srv = http.createServer((q, r) => {
  const u = decodeURIComponent(q.url.split('?')[0]), f = path.join(WWW, u === '/' ? 'index.html' : u);
  if (!f.startsWith(WWW)) { r.writeHead(403); r.end(); return; }
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'content-type': TYPES[path.extname(f)] || 'application/octet-stream' }); r.end(d); });
}).listen(0);
const fails = [], ok = (cond, what, got) => { console.log((cond ? '  ok   ' : '  FAIL ') + what + (got !== undefined ? ': ' + JSON.stringify(got) : '')); if (!cond) fails.push(what); };
const day = () => { const d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); };

(async () => {
  const base = 'http://127.0.0.1:' + srv.address().port + '/', b = await chromium.launch({ args: ['--autoplay-policy=no-user-gesture-required'] });
  const toast = p => p.evaluate(() => document.getElementById('toast').hidden ? '' : document.getElementById('toast').textContent);
  const shopSub = p => p.evaluate(() => document.getElementById('shopSub').textContent);
  // a fresh install greets you with today's catch; close whatever sheet is open first, as a player would
  const clearSheets = async p => { for (let i = 0; i < 4 && await p.evaluate(() => !document.getElementById('scrim').hidden); i++){ await p.keyboard.press('Escape'); await p.waitForTimeout(350); } };
  const openShop = async p => { await clearSheets(p); await p.click('#shopBtn'); await p.waitForTimeout(400); };
  const closeShop = async p => { await p.click('#shopClose'); await p.waitForTimeout(400); };

  // ---------- A. plain browser, nothing configured ----------
  console.log('A. nothing configured');
  {
    const c = await b.newContext({ viewport: { width: 390, height: 844 } }), p = await c.newPage(), errs = [], external = [];
    p.on('pageerror', e => errs.push(e.message));
    p.on('request', q => { if (!q.url().startsWith(base)) external.push(q.url()); });
    await p.goto(base); await p.waitForTimeout(2500);
    const ui = await p.evaluate(() => ({
      app: document.documentElement.classList.contains('app'),
      protoShown: [...document.querySelectorAll('[data-proto]')].filter(e => getComputedStyle(e).display !== 'none').map(e => e.textContent.trim().slice(0, 40)),
      text: document.body.innerText,
      fonts: [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/"/g, '') + ' ' + f.weight)
    }));
    ok(ui.app, 'app mode is on');
    ok(ui.protoShown.length === 0, 'no prototype-only parts showing', ui.protoShown);
    ok(!/Business view|Prototype|simulated|placeholder/i.test(ui.text), 'no prototype wording on the page');
    ok(/The other four games are on their way/.test(ui.text), 'Grandma’s note says the other games are coming');
    ok(external.length === 0, 'nothing loaded from outside the app (fonts are bundled)', external.slice(0, 3));
    ok(ui.fonts.some(f => /Shippori/.test(f)) && ui.fonts.some(f => /Zen Kaku/.test(f)), 'bundled fonts loaded', ui.fonts);
    await openShop(p);
    const shown = await p.evaluate(() => ({ restore: getComputedStyle(document.getElementById('restoreBtn')).display !== 'none', invite: !!document.getElementById('shopInvite').offsetParent }));
    ok(shown.restore && !shown.invite, 'shop shows Restore purchases, hides the invite offer', shown);
    const before = await shopSub(p);
    await p.click('[data-sku="wasabi5"]'); await p.waitForTimeout(500);
    ok(/didn’t go through/.test(await toast(p)) && (await shopSub(p)) === before, 'a purchase fails safely (nothing granted)', await toast(p));
    await p.click('#watchAd'); await p.waitForTimeout(800);
    ok(/No ad is ready/.test(await toast(p)), 'an ad fails safely', await toast(p));
    ok(errs.length === 0, 'no page errors', errs);
    await c.close();
  }

  // ---------- B. pretend iPhone ----------
  console.log('B. pretend iPhone with stand-in plugins');
  {
    const c = await b.newContext({ viewport: { width: 390, height: 844 } }), p = await c.newPage(), errs = [];
    p.on('pageerror', e => errs.push(e.message));
    await p.route('**/app-config.js', r => r.fulfill({ contentType: 'text/javascript', body: 'window.KEN_CONFIG = ' + JSON.stringify({
      links: { appStore: 'https://apps.apple.com/app/id123', playStore: 'https://play.google.com/store/apps/details?id=x', terms: 'https://example.com/terms', privacy: 'https://example.com/privacy' },
      revenuecat: { iosKey: 'appl_test', androidKey: 'goog_test', entitlement: 'club' }, admob: { test: true }, firebase: null }) }));
    await c.addInitScript(([today]) => {
      const log = window.__kenLog = [], L = (...a) => log.push(a);
      // app storage that survives a reload, seeded with a level 9 save the web view has "lost"
      const prefs = JSON.parse(sessionStorage.getItem('prefs') || 'null') || { 'ken.localStorage': JSON.stringify({ 'kenskaiten.v1': JSON.stringify({ v: 1, level: 9, best: 8, wasabi: 3, hints: 3, sound: false, catchSeen: today, lastDay: today, stats: { finished: 8 }, restoOpen: true }) }) };
      const PRICES = { kens_club_monthly: '¥480', starter_pack: '¥300', wasabi_5: '¥160', hints_10: '¥300', yen_40k: '¥160', yen_250k: '¥800', yen_600k: '¥1,500', yen_1500k: '¥3,000' };
      const info = () => ({ entitlements: { active: window.__club ? { club: { isActive: true } } : {} } });
      const handlers = {};
      const emit = ev => (handlers[ev] || []).slice().forEach(f => f({}));
      window.__kenTestPlugins = {
        platform: 'ios',
        Preferences: { get: async ({ key }) => ({ value: prefs[key] == null ? null : prefs[key] }), set: async ({ key, value }) => { prefs[key] = value; sessionStorage.setItem('prefs', JSON.stringify(prefs)); L('prefs.set', key); } },
        App: { addListener: (ev, fn) => { window.__kenBack = fn; return Promise.resolve({ remove() {} }); }, minimizeApp: async () => L('minimize') },
        Share: { share: async o => L('share', o.files) },
        Filesystem: { writeFile: async o => { L('write', o.path); return { uri: 'file:///cache/' + o.path }; } },
        Purchases: {
          configure: async o => L('rc.configure', o.apiKey),
          getProducts: async ({ productIdentifiers }) => ({ products: productIdentifiers.map(id => ({ identifier: id, priceString: PRICES[id] })) }),
          getCustomerInfo: async () => ({ customerInfo: info() }),
          addCustomerInfoUpdateListener: async fn => { window.__rcListener = fn; return 'cb'; },
          purchaseStoreProduct: async ({ product }) => {
            L('rc.buy', product.identifier); const m = window.__buyMode || 'ok';
            if (m === 'cancel') throw { userCancelled: true, code: '1' };
            if (m === 'error') throw { code: '2', message: 'store problem' };
            if (product.identifier === 'kens_club_monthly') window.__club = true;
            return { customerInfo: info() };
          },
          restorePurchases: async () => { L('rc.restore'); window.__club = !!window.__restoreClub; return { customerInfo: info() }; }
        },
        AdMob: {
          initialize: async () => L('ads.init'),
          requestConsentInfo: async () => ({ status: 'REQUIRED', isConsentFormAvailable: true }),
          showConsentForm: async () => { L('consent'); return { status: 'OBTAINED' }; },
          trackingAuthorizationStatus: async () => ({ status: 'notDetermined' }),
          requestTrackingAuthorization: async () => L('tracking'),
          addListener: (ev, fn) => { (handlers[ev] = handlers[ev] || []).push(fn); return Promise.resolve({ remove: () => { handlers[ev] = handlers[ev].filter(x => x !== fn); } }); },
          prepareRewardVideoAd: async () => L('ads.prepare.rewarded'),
          showRewardVideoAd: async () => {
            const m = window.__adMode || 'watch';
            if (m === 'fail') throw new Error('no fill');
            setTimeout(() => { if (m === 'watch') emit('onRewardedVideoAdReward'); emit('onRewardedVideoAdDismissed'); }, 300);
            return {};
          },
          prepareInterstitial: async () => L('ads.prepare.interstitial'),
          showInterstitial: async () => { setTimeout(() => emit('interstitialAdDismissed'), 200); }
        }
      };
    }, [day()]);
    await p.goto(base); await p.waitForTimeout(3000);
    const boot = await p.evaluate(() => ({ text: document.body.innerText, restored: localStorage.getItem('kenskaiten.v1'), link: window.KEN_APP && window.KEN_APP.link, log: window.__kenLog.map(x => x[0]) }));
    ok(/Level 9/.test(boot.text) && !!boot.restored, 'the save came back from app storage (opens on level 9)');
    ok(boot.log.includes('prefs.set'), 'changes are copied back into app storage');
    ok(boot.log.includes('consent') && boot.log.includes('tracking'), 'consent form and Apple’s tracking prompt are asked', boot.log.filter(x => /consent|tracking|ads/.test(x)));
    ok(boot.link === 'https://apps.apple.com/app/id123', 'share text uses the App Store link', boot.link);

    await openShop(p);
    const shop = await p.evaluate(() => ({ w: document.querySelector('.products [data-sku="wasabi5"]').textContent, club: document.getElementById('clubPrice').textContent, terms: document.getElementById('clubTerms').innerText, termsHref: document.getElementById('termsLink').href }));
    ok(shop.w === '¥160' && shop.club === '¥480', 'the store’s own prices show', shop);
    ok(/Renews automatically at ¥480 a month/.test(shop.terms) && /Terms of Use/.test(shop.terms) && /Privacy Policy/.test(shop.terms), 'subscription terms with links are on the Club card', shop.terms);
    ok(shop.termsHref === 'https://example.com/terms', 'Terms of Use link set');
    const w0 = await shopSub(p);
    await p.click('.products [data-sku="wasabi5"]'); await p.waitForTimeout(600);
    const w1 = await shopSub(p);
    ok(/You have 8 wasabi/.test(w1) && /thank you/.test(await toast(p)), 'a successful purchase grants 5 wasabi', [w0, w1]);
    await p.evaluate(() => { window.__buyMode = 'cancel'; }); await p.click('.products [data-sku="hints10"]'); await p.waitForTimeout(600);
    ok((await shopSub(p)) === w1, 'a cancelled purchase grants nothing');
    await p.evaluate(() => { window.__buyMode = 'error'; }); await p.click('.products [data-sku="hints10"]'); await p.waitForTimeout(600);
    ok((await shopSub(p)) === w1 && /didn’t go through/.test(await toast(p)), 'a failed purchase grants nothing and says so', await toast(p));
    await p.evaluate(() => { window.__buyMode = 'ok'; }); await p.click('.cl-join'); await p.waitForTimeout(700);
    ok(await p.evaluate(() => document.getElementById('clubCard').classList.contains('member')), 'joining Ken’s Club makes you a member');
    await p.evaluate(() => window.__rcListener({ entitlements: { active: {} } })); await p.waitForTimeout(300);
    ok(!(await p.evaluate(() => document.getElementById('clubCard').classList.contains('member'))), 'when the subscription lapses, the Club ends');
    await p.evaluate(() => { window.__restoreClub = true; }); await p.click('#restoreBtn'); await p.waitForTimeout(700);
    ok(/restored/.test(await toast(p)) && await p.evaluate(() => document.getElementById('clubCard').classList.contains('member')), 'Restore purchases brings the Club back', await toast(p));
    await p.evaluate(() => window.__rcListener({ entitlements: { active: {} } })); await p.waitForTimeout(300);   // back to a non-member for the ad tests

    // Android's back button: closes the open sheet first, then sends the app to the background
    await p.evaluate(() => window.__kenBack()); await p.waitForTimeout(400);
    const afterBack = await p.evaluate(() => ({ shop: !document.getElementById('scrim').hidden, min: window.__kenLog.filter(x => x[0] === 'minimize').length }));
    ok(!afterBack.shop && afterBack.min === 0, 'back button closes the shop', afterBack);
    await p.evaluate(() => window.__kenBack()); await p.waitForTimeout(200);
    ok(await p.evaluate(() => window.__kenLog.some(x => x[0] === 'minimize')), 'back button with nothing open sends the app to the background');

    // rewarded ads: +1 wasabi only when watched to the end
    const wasabi = async () => { await openShop(p); const n = +((await shopSub(p)).match(/You have (\d+) wasabi/) || [, -1])[1]; await closeShop(p); return n; };
    for (const [mode, want, gain] of [['watch', /\+1 wasabi/, 1], ['close', /closed early/, 0], ['fail', /No ad is ready/, 0]]){
      const before = await wasabi();
      await p.evaluate(m => { window.__adMode = m; }, mode);
      await openShop(p); await p.click('#watchAd'); await p.waitForTimeout(1200);
      const t = await toast(p), after = await wasabi();
      ok(want.test(t) && after - before === gain, 'rewarded ad, ' + mode + ': ' + (gain ? '+1 wasabi' : 'no reward'), [t, before, after]);
    }
    const inter = await p.evaluate(() => window.KEN_APP.ads.show('interstitial'));
    ok(inter === 'closed', 'an ad between levels plays and returns', inter);

    // the share picture goes to the share sheet
    await p.evaluate(async () => { const dl = await window.claude.use('downloads'); await dl.save({ filename: 'kens-sushi.png', data: new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' }) }); });
    const sh = await p.evaluate(() => window.__kenLog.filter(x => x[0] === 'write' || x[0] === 'share'));
    ok(sh.length === 2 && sh[1][1][0] === 'file:///cache/kens-sushi.png', 'share picture is saved and handed to the share sheet', sh);
    ok(errs.length === 0, 'no page errors', errs);
    await c.close();
  }
  await b.close(); srv.close();
  console.log(fails.length ? '\nFAIL: ' + fails.length + ' check(s)' : '\nPASS: all checks');
  process.exit(fails.length ? 1 : 0);
})();
