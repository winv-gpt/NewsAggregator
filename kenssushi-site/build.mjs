// Builds kenssushi.com into public/ from src/ and site.config.mjs. No dependencies: `node build.mjs`.
import { readFileSync, writeFileSync, mkdirSync, rmSync, cpSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import C from './site.config.mjs';

const ROOT = dirname(fileURLToPath(import.meta.url)), SRC = join(ROOT, 'src'), OUT = join(ROOT, 'public');
const missing = [];
const need = (v, label) => { if (v && String(v).trim()) return String(v).trim(); missing.push(label); return '[' + label + ']'; };
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const site = C.siteUrl.replace(/\/$/, '');

// Ken's Sushi: store buttons once the app is live, "coming soon" until then
const stores = [[C.appStoreUrl, 'App Store'], [C.playStoreUrl, 'Google Play']].filter(([u]) => u);
const storeHtml = stores.map(([u, n]) => '<a class="store-btn" href="' + esc(u) + '" target="_blank" rel="noopener">' + n + '</a>').join('');
const T = {
  SITE_URL: site,
  COMPANY: esc(need(C.company, 'Company legal name')),
  ADDRESS: esc(need(C.address, 'Postal address')),
  GOVERNING_LAW: esc(need(C.governingLaw, 'Country or state whose laws apply')),
  SUPPORT_EMAIL: esc(C.supportEmail),
  PRIVACY_EMAIL: esc(C.privacyEmail),
  EFFECTIVE_DATE: esc(C.effectiveDate),
  YEAR: String(new Date().getFullYear()),
  SUSHI_STAT: stores.length ? 'Play now' : 'Coming soon',
  SUSHI_STATUS: stores.length ? 'Play now' : 'Coming soon to iPhone and Android',
  SUSHI_PLAY: storeHtml || '<span class="pill on">Coming soon to iPhone and Android</span>',
  SUSHI_PLAY_JS: JSON.stringify(storeHtml)
};
const fill = (s, file) => s.replace(/\{\{([A-Z_]+)\}\}/g, (m, k) => { if (!(k in T)) throw new Error('unknown token ' + m + ' in ' + file); return T[k]; });

rmSync(OUT, { recursive: true, force: true });
const walk = d => readdirSync(d).flatMap(f => { const p = join(d, f); return statSync(p).isDirectory() ? walk(p) : [p]; });
for (const f of walk(SRC)){
  const rel = relative(SRC, f), to = join(OUT, rel);
  mkdirSync(dirname(to), { recursive: true });
  if (/\.(html|css|txt|xml)$/.test(f)) writeFileSync(to, fill(readFileSync(f, 'utf8'), rel));
  else cpSync(f, to);
}
// app-ads.txt: AdMob looks for this on the domain listed as the app's website in the stores
writeFileSync(join(OUT, 'app-ads.txt'), C.admobPublisherId
  ? 'google.com, ' + C.admobPublisherId.replace(/^ca-app-/, '') + ', DIRECT, f08c47fec0942fa0\n'
  : '# Add your AdMob publisher ID to site.config.mjs and rebuild to fill this in.\n');
writeFileSync(join(OUT, 'robots.txt'), 'User-agent: *\nAllow: /\nSitemap: ' + site + '/sitemap.xml\n');
writeFileSync(join(OUT, 'sitemap.xml'), '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
  ['/', '/support/', '/privacy/', '/terms/'].map(p => '  <url><loc>' + site + p + '</loc></url>').join('\n') + '\n</urlset>\n');

const left = walk(OUT).filter(f => /\.(html|css)$/.test(f)).filter(f => /\{\{[A-Z_]+\}\}/.test(readFileSync(f, 'utf8')));
if (left.length) throw new Error('unfilled tokens in ' + left.join(', '));
console.log('public/ built: ' + walk(OUT).length + ' files');
if (missing.length) console.log('Still to fill in site.config.mjs (shown in brackets on the pages): ' + [...new Set(missing)].join(', '));
