# Ken's Sushi: the store app

The web game wrapped with [Capacitor](https://capacitorjs.com), the same code for the App Store and Google Play.

## What's done
- **App mode in the game.** Only the app turns it on, so the web page is unchanged. In the app:
  - Hidden: the Business view (test sliders and event log), the "prototype" notes, the claude.ai link, the
    invite offer (nothing pays its reward yet), and the "all five games" Club line.
  - Added: the store's own prices, the subscription terms with Terms and Privacy links, a **Restore purchases**
    button, store links in the share text, and Android's back button closing sheets.
- **Purchases (RevenueCat).** Something is granted only when the store confirms it. Ken's Club follows the
  subscription: it ends if the subscription lapses and comes back with Restore purchases.
- **Ads (AdMob).** Rewarded ads pay only when watched to the end. Before any ad, Google's consent form is shown in
  Europe and the UK, and Apple's tracking prompt on iOS. Google's test ads are used until you put in real IDs.
- **Saves.** Every change is copied into the app's own storage, so iOS clearing web storage can't lose progress.
- **Rankings and leagues (Firebase).** Players sign in anonymously and get a preset name such as "Hana 42"
  (there's no typed text to moderate).
- **Share picture.** Goes to the phone's share sheet.
- **Fonts and music ship inside the app.** The fonts are cut down to the game's characters, so the app works
  offline and loads nothing from Google.
- **Native projects.**
  - Android: targets API 36; exact-alarm permission removed, because Google Play only allows it for alarm and
    calendar apps.
  - iOS: Swift Package Manager, with no CocoaPods needed.
  - Both: portrait only, iPhone-only on iOS, icons and launch screens generated.
- **`test/app-check.cjs`** checks all of this in a browser, with stand-ins for the phone plugins.

Not tested yet: on real phones, against real store and ad accounts, and with Firebase. Those need the accounts below.

## What you need to do
1. **Choose the app ID.** It's `com.yourcompany.kenssushi` in `capacitor.config.json` and can never change after
   the first upload. Change it there, then rebuild the native projects:
   delete `android/` and `ios/`, then run `npx cap add android && npx cap add ios && node scripts/native-config.mjs && npm run assets`.
2. **Fill in `app-config.js`** as each account is ready:
   - links: store links, Terms of Use, Privacy Policy
   - RevenueCat public keys
   - AdMob ad unit IDs, and set `test: false` for release
   - the Firebase web config
3. **AdMob app IDs.** These go in the native files rather than `app-config.js`. Run
   `ADMOB_IOS_APP_ID=ca-app-pub-…~… ADMOB_ANDROID_APP_ID=ca-app-pub-…~… node scripts/native-config.mjs`.
   For iOS, also add Google's full SKAdNetwork list (from Google's AdMob iOS guide) if you use mediation.
4. **Store products.** Create these in App Store Connect and Play Console, add them to RevenueCat, and attach the
   `club` entitlement to the subscription:

   | ID | What | Type | Price |
   |---|---|---|---|
   | `kens_club_monthly` | Ken's Club | Auto-renewing subscription, monthly | $2.99 |
   | `starter_pack` | Ken's starter pack | Consumable (the game offers it once) | $1.99 |
   | `wasabi_5` | 5 wasabi | Consumable | $0.99 |
   | `hints_10` | 10 hints | Consumable | $1.99 |
   | `yen_40k` | ¥40,000 for station improvements | Consumable | $0.99 |
   | `yen_250k` | ¥250,000 for station improvements | Consumable | $4.99 |
   | `yen_600k` | ¥600,000 for station improvements | Consumable | $9.99 |
   | `yen_1500k` | ¥1,500,000 for station improvements | Consumable | $19.99 |
5. **Firebase.**
   - Create a project, add a Web app, and turn on Authentication > Anonymous.
   - Create a Firestore database and publish `firestore.rules`.
   - Paste the web config into `app-config.js`.
6. **Build and run on your phones.** You need a Mac with Xcode 26 for iOS (or a cloud build service such as
   Codemagic), and Android Studio for Android:
   ```
   npm install
   npm run ios        # builds www/, syncs, opens Xcode: set your signing team, run on a phone
   npm run android    # same for Android Studio
   ```
   Test purchases with App Store sandbox testers and Play license testers, and test ads with Google's test ads.
7. **Upload.**
   - iOS: Archive in Xcode, then TestFlight, then submit.
   - Android: build a signed App Bundle (.aab), then internal testing, then closed testing, then production.

## Updating the game later
Copy the new web build over `game/kaiten.html` (and `game/music/` if the music changed). If new text uses
characters the fonts don't have yet, run `python3 -I scripts/subset_fonts.py game/kaiten.html <ttf folder> game/fonts`
with the original fonts from github.com/google/fonts (ofl/shipporiminchob1, zenkakugothicnew, yujisyuku).
Then run `npm run sync` and rebuild in Xcode or Android Studio. Run `node test/app-check.cjs` after `npm run build`
to recheck the app (it needs Playwright).

## Good to know
- **Leagues work out groups on the phone from every player's scores**, as the web page does. That's fine for the
  first few thousand players. Before that, move league grouping to a Firebase Cloud Function so each phone reads
  only its own league.
- **Ken's Club is for this app only.** One subscription across separate apps needs player accounts; the "all five
  games" line stays hidden until then.
- **The invite offer is hidden** until there's a way to redeem codes, such as a deep link plus a server check.
- **Licences.** The fonts are SIL Open Font License (licence files in `game/fonts/`). The music uses CC0 samples from
  Versilian Studios, credited in How to play.

## Files
| Path | What |
|---|---|
| `game/` | The web game (`kaiten.html`), its music, and the fonts cut down to its characters |
| `src/bridge.js` | Connects the game to the phone: saves, purchases, ads, rankings, share, back button |
| `app-config.js` | Your keys and links |
| `scripts/build-web.mjs` | Builds `www/` (what goes inside the app) |
| `scripts/native-config.mjs` | Store settings for the native projects (orientation, AdMob IDs, tracking text, …) |
| `scripts/subset_fonts.py` | Cuts the fonts down to the game's characters |
| `firestore.rules` | Security rules for the rankings database |
| `assets/` | Icon and launch screen art (`npm run assets` makes every size) |
| `android/`, `ios/` | The native projects |
| `test/app-check.cjs` | Browser checks of the app build |
