// Ken's Sushi app settings. Fill these in as the accounts come together; anything left empty simply stays off
// (rankings stay on the phone, the shop says it can't be reached, test ads are used).
// These values end up inside the app, so only put public keys here (never a secret or server key).
window.KEN_CONFIG = {
  // Links shown in the shop and used in the share text. Both stores need the terms and privacy pages.
  links: {
    appStore: '',        // https://apps.apple.com/app/id0000000000 (App Store Connect shows the ID once the app exists)
    playStore: '',       // https://play.google.com/store/apps/details?id=com.example.kenssushi
    terms: 'https://kenssushi.com/terms/',       // Terms of Use (Apple requires them for the Ken's Club subscription)
    privacy: 'https://kenssushi.com/privacy/',   // Privacy Policy
    support: 'https://kenssushi.com/support/'    // Support page
  },

  // RevenueCat: Project settings > API keys > the public app-specific keys (they start appl_ and goog_).
  revenuecat: {
    iosKey: 'appl_zghfsotmWVIqrMqBIpQkiDECXUS',
    androidKey: '',
    entitlement: 'ken_s_sushi_pro'  // RevenueCat entitlement for Ken's Club; attach kens_club_monthly to it
  },

  // AdMob ad unit IDs. While test is true, Google's test ads are shown whatever is filled in below:
  // keep it true while developing (tapping your own real ads can get an AdMob account suspended),
  // and set it to false for the build you send to the stores.
  // The AdMob *app* IDs go in the native files instead: see README, "AdMob app IDs".
  admob: {
    test: true,
    ios: { rewarded: 'ca-app-pub-7799816604410900/4346126348', interstitial: 'ca-app-pub-7799816604410900/8345081107' },
    android: { rewarded: 'ca-app-pub-7799816604410900/5910489458', interstitial: 'ca-app-pub-7799816604410900/4537698038' }
  },

  // Firebase: Project settings > Your apps > Web app > the firebaseConfig object. Turns on shared rankings.
  // No measurementId on purpose: the app doesn't use Google Analytics (the Privacy Policy says so).
  firebase: {
    apiKey: 'AIzaSyBUg8RP1pKID-qUaBtJGrb0vDvT11_77jo',
    authDomain: 'ken-s-sushi.firebaseapp.com',
    projectId: 'ken-s-sushi',
    storageBucket: 'ken-s-sushi.firebasestorage.app',
    messagingSenderId: '795868275854',
    appId: '1:795868275854:web:3d42b23d0ee59e848dd5df'
  },

  debug: false
};
