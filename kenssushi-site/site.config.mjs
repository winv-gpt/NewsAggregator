// kenssushi.com settings. Fill in the empty ones, then run `node build.mjs`; the finished site is in public/.
// Until company, address and governingLaw are filled in, the pages show a bracketed reminder in their place.
export default {
  siteUrl: 'https://kenssushi.com',

  // Who publishes the app: the legal name of your business (or your own name if you publish as an individual),
  // and a postal address. Both appear in the Privacy Policy and Terms of Use.
  company: 'C Vareekasem',
  address: '335 Sathorn, Bangkok, 10120, Thailand',
  // Whose laws govern the Terms of Use, e.g. 'Singapore', 'England and Wales', 'the State of Delaware, USA'.
  governingLaw: 'Thailand',

  // Set these mailboxes up on kenssushi.com (most domain registrars include email forwarding).
  supportEmail: 'support@kenssushi.com',
  privacyEmail: 'privacy@kenssushi.com',

  // Change this date whenever you change the policies.
  effectiveDate: '20 November 2026',

  // Once the app is live: its store pages. Ken's Sushi then shows App Store and Google Play buttons
  // instead of "Coming soon".
  appStoreUrl: '',
  playStoreUrl: '',

  // AdMob publisher ID (pub-…, from AdMob > Settings). Fills in app-ads.txt, which AdMob checks on this domain.
  admobPublisherId: 'pub-7799816604410900'
};
