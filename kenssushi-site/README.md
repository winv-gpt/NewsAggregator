# kenssushi.com

A plain static website with no server, no cookies and no tracking:

| Page | Address |
|---|---|
| Grandma’s note (home) | https://kenssushi.com/ |
| Support | https://kenssushi.com/support/ |
| Privacy Policy | https://kenssushi.com/privacy/ |
| Terms of Use | https://kenssushi.com/terms/ |

It also has a not-found page, `app-ads.txt` for AdMob, `robots.txt` and a sitemap. The fonts are served from the site
itself rather than by Google.

## 1. Fill in your details
Open `site.config.mjs` and fill in:
- **company**: your legal name
- **address**: your postal address
- **governingLaw**: whose laws apply to the Terms

Then run:

```
node build.mjs
```

The finished site is in `public/`. Until those three are filled in, the pages show a bracketed reminder such as
`[Company legal name]`, and every build lists what's still missing.

When the app is live, add `appStoreUrl` and `playStoreUrl`. Ken’s Sushi on the home page then switches from
"Coming soon" to App Store and Google Play buttons. Add `admobPublisherId` to fill in `app-ads.txt`.

## 2. Put it online
Any static host works. **Cloudflare** is free and also handles the domain's email forwarding. New Cloudflare
projects are "Workers"; `wrangler.jsonc` tells Cloudflare where the built site is.

1. **Clear the registrar's old records.** In Cloudflare, open kenssushi.com › DNS › Records. Delete the **A**,
   **AAAA** and **CNAME** records named `kenssushi.com` (or `@`) and `www`; these are usually the registrar's parking
   page. Leave MX and TXT records alone.
2. **Create the Worker.** Go to Workers & Pages › Create › Import a repository › **winv-gpt/NewsAggregator**, and
   name the project **`kenssushi`** (it must match `name` in `wrangler.jsonc`). Then set:
   - Production branch: `claude/relaxed-edison-cqn24r`
   - Root directory (under advanced settings): `kenssushi-site`
   - Build command: `node build.mjs`
   - Deploy command: `npx wrangler deploy` (the default)
3. Deploy. You get a test address ending in `.workers.dev`.
4. **Add the domain.** In the Worker, go to Settings › Domains & Routes › Add › Custom domain, and add
   `kenssushi.com`, then `www.kenssushi.com`. HTTPS is set up automatically.

Other options:
- **Cloudflare Pages:** under Workers & Pages › Create, choose the "Pages" option. Use the same root directory and
  build command, with build output directory `public`.
- **Netlify:** base `kenssushi-site`, command `node build.mjs`, publish `public`.
- **Your registrar's hosting:** upload the contents of `public/` to the web root.

## 3. Set up the two email addresses
The pages give **support@kenssushi.com** and **privacy@kenssushi.com**. Create them, or forward them to your inbox:
Cloudflare Email Routing is free if the domain's DNS is at Cloudflare, and most registrars offer forwarding.

## 4. Use the addresses in the stores
| Field | App Store Connect | Google Play Console |
|---|---|---|
| Marketing / website | https://kenssushi.com | Store settings › Website |
| Support URL | https://kenssushi.com/support/ | Contact details |
| Privacy Policy | https://kenssushi.com/privacy/ | App content › Privacy policy |
| Terms of Use | Add as a custom EULA, or link it at the end of the description | Optional: link it in the description |

The app already links to Terms, Privacy and Support (in `kens-sushi-app/app-config.js`).

## 5. Keep the policies true
The Privacy Policy describes what the app actually does today:
- the game is saved on the phone
- rankings through Firebase, under a random player ID and a preset name
- purchases through Apple, Google and RevenueCat
- ads through Google AdMob, with the consent form and Apple’s tracking prompt
- notifications scheduled on the phone only
- no analytics

If the app changes (for example, adding analytics, crash reporting, push notifications, accounts, typed names or
another ad network), update the policy and the `effectiveDate` before releasing that version. Also keep the stores'
privacy answers (App Privacy, Data safety) matching it.

These documents were written to fit Ken’s Sushi, but they aren’t legal advice. Have them checked by a lawyer in your
country before launch, especially the governing law and consumer rights sections.

## Files
| Path | What |
|---|---|
| `site.config.mjs` | Your details and links |
| `build.mjs` | Builds `public/` (no dependencies) |
| `wrangler.jsonc` | Tells Cloudflare to serve `public/` |
| `src/index.html` | Grandma’s note, the home page |
| `src/privacy/`, `src/terms/`, `src/support/`, `src/404.html` | The other pages |
| `src/site.css` | Styles for the policy and support pages |
| `src/fonts/` | The site's fonts, cut down to the characters used (SIL Open Font License) |
| `src/img/` | Favicon, home-screen icon and the picture shown when the site is shared |
| `scripts/subset_fonts.py` | Remakes the font files if new characters are added to the pages |
| `test/site-check.cjs` | Browser checks of the built site (needs Playwright) |
