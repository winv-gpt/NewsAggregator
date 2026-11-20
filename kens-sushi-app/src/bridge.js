// Ken's Sushi app bridge.
//
// The game was built as a web page that runs inside Claude, where `window.claude.use(...)` hands it a shared
// database (rankings), the player's identity and a file saver. In the app this file stands in for all of that,
// and adds what a store app needs: saves that the phone won't clear, real purchases (RevenueCat), real ads
// (AdMob, with the consent and tracking prompts), the share sheet, store links and the Android back button.
//
// Everything is optional. With nothing configured in app-config.js the game still runs: rankings stay on the
// phone, the shop says it can't be reached, and no ads are offered. Once a key is filled in, that part lights up.
import { Capacitor } from '@capacitor/core';
import { App as AppPlugin } from '@capacitor/app';
import { Preferences as PreferencesPlugin } from '@capacitor/preferences';
import { Share as SharePlugin } from '@capacitor/share';
import { Filesystem as FilesystemPlugin, Directory } from '@capacitor/filesystem';
import { LocalNotifications } from '@capacitor/local-notifications';
import { Purchases as PurchasesPlugin } from '@revenuecat/purchases-capacitor';
import { AdMob as AdMobPlugin, RewardAdPluginEvents, InterstitialAdPluginEvents } from '@capacitor-community/admob';
import { initializeApp } from 'firebase/app';
import { initializeAuth, indexedDBLocalPersistence, signInAnonymously, onAuthStateChanged } from 'firebase/auth';
import { getFirestore, collection, doc, onSnapshot, setDoc } from 'firebase/firestore';

const CFG = window.KEN_CONFIG || {};
// Tests only (test/app-check.cjs): stand-ins for the native plugins. Never set in the app.
const T = window.__kenTestPlugins || null;
const App = T ? T.App : AppPlugin, Preferences = T ? T.Preferences : PreferencesPlugin, Share = T ? T.Share : SharePlugin;
const Filesystem = T ? T.Filesystem : FilesystemPlugin, Purchases = T ? T.Purchases : PurchasesPlugin, AdMob = T ? T.AdMob : AdMobPlugin;
const native = T ? true : Capacitor.isNativePlatform();
const platform = T ? T.platform : Capacitor.getPlatform();   // 'ios', 'android' or 'web'
const log = (...a) => { if (CFG.debug) console.log('[ken]', ...a); };

// ---------- Saves ----------
// The game keeps its save in localStorage. iOS may clear a web view's storage when the phone runs low on space,
// so every change is mirrored into the app's own storage (Preferences), and restored from there on launch.
const MIRROR = 'ken.localStorage';
async function restoreSaves(){
  try {
    const { value } = await Preferences.get({ key: MIRROR });
    if (value){
      const saved = JSON.parse(value);
      for (const k of Object.keys(saved)) if (localStorage.getItem(k) == null) localStorage.setItem(k, saved[k]);
    }
  } catch (e) { log('restore failed', e); }
  let t = 0;
  const persist = () => {
    clearTimeout(t); t = 0;
    const all = {};
    for (let i = 0; i < localStorage.length; i++){ const k = localStorage.key(i); all[k] = localStorage.getItem(k); }
    Preferences.set({ key: MIRROR, value: JSON.stringify(all) }).catch(() => {});
  };
  const later = () => { if (!t) t = setTimeout(persist, 400); };
  const set = Storage.prototype.setItem, del = Storage.prototype.removeItem;
  Storage.prototype.setItem = function (k, v){ set.call(this, k, v); if (this === localStorage) later(); };
  Storage.prototype.removeItem = function (k){ del.call(this, k); if (this === localStorage) later(); };
  document.addEventListener('visibilitychange', () => { if (document.hidden && t) persist(); });
}

// ---------- Purchases (RevenueCat) ----------
// Game shop item -> store product ID. Create these products in App Store Connect and Play Console, then add them
// to RevenueCat, with an entitlement (default "club") attached to the subscription.
const PRODUCT_IDS = {
  plus: 'kens_club_monthly', starter: 'starter_pack', wasabi5: 'wasabi_5', hints10: 'hints_10',
  yen40k: 'yen_40k', yen250k: 'yen_250k', yen600k: 'yen_600k', yen1500k: 'yen_1500k'
};
function makeStore(){
  const rc = CFG.revenuecat || {}, key = platform === 'ios' ? rc.iosKey : rc.androidKey, entitlement = rc.entitlement || 'club';
  const products = {}, listeners = [];
  let club = null, ready = null;
  // Play subscriptions come back as "productId:basePlanId"
  const find = sku => { const id = PRODUCT_IDS[sku]; return id && (products[id] || Object.values(products).find(p => p.identifier.split(':')[0] === id)); };
  const setClub = info => {
    const on = !!(info && info.entitlements && info.entitlements.active && info.entitlements.active[entitlement]);
    if (on !== club){ club = on; listeners.forEach(f => { try { f({ club }); } catch (e) {} }); }
  };
  const start = async () => {
    if (!native || !key) throw new Error('store not configured');
    await Purchases.configure({ apiKey: key });
    const ids = Object.values(PRODUCT_IDS);
    const [one, sub] = await Promise.all([
      Purchases.getProducts({ productIdentifiers: ids.filter(i => i !== PRODUCT_IDS.plus), type: 'NON_SUBSCRIPTION' }),
      Purchases.getProducts({ productIdentifiers: [PRODUCT_IDS.plus], type: 'SUBSCRIPTION' })
    ]);
    [...one.products, ...sub.products].forEach(p => { products[p.identifier] = p; });
    setClub((await Purchases.getCustomerInfo()).customerInfo);
    Purchases.addCustomerInfoUpdateListener(setClub);
    listeners.forEach(f => { try { f({ club }); } catch (e) {} });   // prices are in: let the shop redraw
    log('store ready', Object.keys(products));
  };
  const whenReady = () => (ready = ready || start().catch(e => { ready = null; throw e; }));
  whenReady().catch(e => log('store unavailable', e && e.message));
  return {
    price: sku => { const p = find(sku); return p ? p.priceString : null; },
    buy: async sku => {
      await whenReady();
      const p = find(sku);
      if (!p) throw new Error('product not found: ' + sku);
      try { setClub((await Purchases.purchaseStoreProduct({ product: p })).customerInfo); return true; }
      catch (e) { if (e && (e.userCancelled || String(e.code) === '1')) return false; throw e; }
    },
    restore: async () => { await whenReady(); setClub((await Purchases.restorePurchases()).customerInfo); return { club: !!club }; },
    onChange: f => { listeners.push(f); if (club !== null) f({ club }); }
  };
}

// ---------- Ads (AdMob) ----------
// Google's published test ad units, used until real ones are filled in (and always while admob.test is true).
const TEST_UNITS = {
  ios: { rewarded: 'ca-app-pub-3940256099942544/1712485313', interstitial: 'ca-app-pub-3940256099942544/4411468910' },
  android: { rewarded: 'ca-app-pub-3940256099942544/5224354917', interstitial: 'ca-app-pub-3940256099942544/1033173712' }
};
function makeAds(){
  const am = CFG.admob || {}, units = Object.assign({}, TEST_UNITS[platform] || {}, am.test ? {} : (am[platform] || {}));
  let started = null;
  const start = () => (started = started || (async () => {
    if (!native) throw new Error('ads need the app');
    await AdMob.initialize({ initializeForTesting: !!am.test });
    // Europe and the UK: Google's consent form (UMP). Then, on iOS, Apple's tracking prompt.
    try {
      const info = await AdMob.requestConsentInfo();
      if (info.isConsentFormAvailable && info.status === 'REQUIRED') await AdMob.showConsentForm();
    } catch (e) { log('consent', e); }
    if (platform === 'ios'){
      try { const t = await AdMob.trackingAuthorizationStatus(); if (t.status === 'notDetermined') await AdMob.requestTrackingAuthorization(); } catch (e) { log('tracking', e); }
    }
  })().catch(e => { started = null; throw e; }));
  // One ad at a time: resolves 'rewarded' (watched to the end), 'closed' (closed early) or 'failed'.
  const play = async kind => {
    await start();
    const R = kind === 'rewarded', E = R ? RewardAdPluginEvents : InterstitialAdPluginEvents;
    return new Promise(resolve => {
      let earned = false, done = false;
      const handles = [];
      const finish = r => { if (done) return; done = true; handles.forEach(h => h.then(x => x.remove()).catch(() => {})); resolve(r); };
      if (R) handles.push(AdMob.addListener(E.Rewarded, () => { earned = true; }));
      handles.push(AdMob.addListener(E.Dismissed, () => finish(R ? (earned ? 'rewarded' : 'closed') : 'closed')));
      handles.push(AdMob.addListener(E.FailedToShow, () => finish('failed')));
      const opts = { adId: units[kind], isTesting: !!am.test };
      (R ? AdMob.prepareRewardVideoAd(opts).then(() => AdMob.showRewardVideoAd()) : AdMob.prepareInterstitial(opts).then(() => AdMob.showInterstitial()))
        .catch(() => finish('failed'));
      setTimeout(() => finish(earned ? 'rewarded' : 'failed'), 120000);   // never leave the game waiting
    });
  };
  if (native) setTimeout(() => start().catch(e => log('ads unavailable', e && e.message)), 1500);
  return { show: kind => play(kind).catch(() => 'failed') };
}

// ---------- Rankings and leagues (Firebase) ----------
// Anonymous sign-in gives each phone a player ID; each player's scores live in ranks/{id}, as on the web page.
// Names are picked from a preset list (not typed), so there's nothing offensive to moderate.
const NAMES = ['Hana', 'Ren', 'Yui', 'Sora', 'Kaito', 'Mio', 'Riku', 'Aoi', 'Haru', 'Emi', 'Taro', 'Nao', 'Kenta', 'Saki', 'Yuto', 'Rin',
  'Daichi', 'Koharu', 'Sota', 'Mei', 'Hiro', 'Ami', 'Shun', 'Nanami', 'Kota', 'Ema', 'Yuki', 'Akari', 'Takumi', 'Hinata', 'Itsuki', 'Mana'];
const chefName = id => { let h = 0; for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0; return NAMES[h % NAMES.length] + ' ' + (10 + (h >> 8) % 90); };
function makeCloud(){
  if (!CFG.firebase || !CFG.firebase.projectId) return null;
  const app = initializeApp(CFG.firebase);
  const auth = initializeAuth(app, { persistence: indexedDBLocalPersistence });
  const fs = getFirestore(app);
  const names = {};
  const uid = new Promise((resolve, reject) => {
    const off = onAuthStateChanged(auth, u => { if (u){ off(); resolve(u.uid); } });
    signInAnonymously(auth).catch(e => { off(); reject(e); });
  });
  const remember = docs => docs.forEach(d => { const n = d.data().name; if (n) names[d.id] = n; });
  const db = {
    collection: path => ({
      onSnapshot: (next, error) => {
        let off = null, stop = false;
        uid.then(() => { if (stop) return; off = onSnapshot(collection(fs, path), { includeMetadataChanges: true }, snap => {
          remember(snap.docs);
          next({ metadata: { fromCache: snap.metadata.fromCache }, docs: snap.docs.map(d => ({ id: d.id, exists: d.exists(), data: () => d.data() })) });
        }, e => error && error(e)); }, e => error && error(e));
        return () => { stop = true; if (off) off(); };
      }
    }),
    doc: path => ({ set: async value => { const id = await uid; return setDoc(doc(fs, path), Object.assign({}, value, { name: chefName(id) })); } })
  };
  const user = {
    id: () => uid,
    me: async () => { const id = await uid; return { id, name: chefName(id) }; },
    profiles: async ids => { const out = {}; for (const id of ids) out[id] = { name: names[id] || chefName(id) }; return out; }
  };
  return { db, user };
}

// ---------- The share picture ----------
async function blobToBase64(blob){
  const buf = new Uint8Array(await blob.arrayBuffer());
  let s = ''; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode.apply(null, buf.subarray(i, i + 0x8000));
  return btoa(s);
}
const downloads = {
  save: async ({ filename, data }) => {
    if (!native){ const a = document.createElement('a'); a.href = URL.createObjectURL(data); a.download = filename; a.click(); return; }
    const file = await Filesystem.writeFile({ path: filename, data: await blobToBase64(data), directory: Directory.Cache });
    try { await Share.share({ title: 'Ken’s Sushi', files: [file.uri] }); }
    catch (e) { if (!/cancel/i.test(String(e && e.message))) throw Object.assign(new Error('share failed'), { code: 'failed' }); throw Object.assign(new Error('declined'), { code: 'declined' }); }
  }
};

// ---------- Start ----------
async function boot(){
  await restoreSaves();
  const links = CFG.links || {};
  const cloud = makeCloud();
  window.KEN_APP = {
    platform,
    link: (platform === 'android' ? links.playStore : links.appStore) || links.appStore || links.playStore || '',
    links,
    store: makeStore(),
    ads: makeAds()
  };
  // The game looks for the notifications plugin on Capacitor.Plugins
  if (window.Capacitor && window.Capacitor.Plugins && !window.Capacitor.Plugins.LocalNotifications) window.Capacitor.Plugins.LocalNotifications = LocalNotifications;
  // What the Claude page provided, from the app instead
  window.claude = { use: async name => name === 'db' ? (cloud && cloud.db) : name === 'user' ? (cloud && cloud.user) : name === 'downloads' ? downloads : null };
  if (native) App.addListener('backButton', () => {
    const go = document.dispatchEvent(new CustomEvent('ken:back', { cancelable: true }));
    if (go) App.minimizeApp();
  });
  const s = document.createElement('script'); s.src = 'game.js'; document.body.appendChild(s);
}
boot();
