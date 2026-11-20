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
Any static host works. **Cloudflare Pages** is free and the simplest with a custom domain:
1. In Cloudflare, go to Workers & Pages › Create › Pages › Connect to Git, and pick this repository.
2. Set the root directory to `kenssushi-site`, the build command to `node build.mjs`, and the output directory to
   `public`.
3. After the first deploy, go to Custom domains › Add `kenssushi.com` (and `www.kenssushi.com`). If the domain's DNS
   is at Cloudflare, it sets up the records for you. Otherwise, it shows the records to add at your registrar.

Other options:
- **Netlify:** same settings: base `kenssushi-site`, command `node build.mjs`, publish `public`.
- **GitHub Pages:** publish the contents of `public/`, then add the domain under Settings › Pages.
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
| `src/index.html` | Grandma’s note, the home page |
| `src/privacy/`, `src/terms/`, `src/support/`, `src/404.html` | The other pages |
| `src/site.css` | Styles for the policy and support pages |
| `src/fonts/` | The site's fonts, cut down to the characters used (SIL Open Font License) |
| `src/img/` | Favicon, home-screen icon and the picture shown when the site is shared |
| `scripts/subset_fonts.py` | Remakes the font files if new characters are added to the pages |
| `test/site-check.cjs` | Browser checks of the built site (needs Playwright) |
