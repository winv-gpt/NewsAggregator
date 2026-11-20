// Store-ready settings for the generated android/ and ios/ projects. Safe to run again: each change is applied once.
// Run it after `npx cap add android` / `npx cap add ios` (for example after changing the app ID).
//   - portrait only, iPhone only (it still runs on iPads, so no iPad screenshots are needed)
//   - AdMob app IDs (Google's test IDs until you put in your own: edit ADMOB below)
//   - Apple's tracking prompt text, the ad networks list Apple asks for, and the export-compliance answer
//   - no exact-alarm permission on Android (Google Play only allows it for alarm and calendar apps)
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const ADMOB = {
  android: process.env.ADMOB_ANDROID_APP_ID || 'ca-app-pub-3940256099942544~3347511713',   // Google's test app ID
  ios: process.env.ADMOB_IOS_APP_ID || 'ca-app-pub-3940256099942544~1458002511'            // Google's test app ID
};
const TRACKING_TEXT = 'Ken’s Sushi uses this to show ads that suit you better. The game plays the same either way.';
const edit = (rel, fn) => { const p = join(ROOT, rel); if (!existsSync(p)) { console.log('skip (not found):', rel); return; } const a = readFileSync(p, 'utf8'), b = fn(a); if (a !== b) { writeFileSync(p, b); console.log('updated', rel); } else console.log('ok     ', rel); };

// ---------- Android ----------
edit('android/app/src/main/AndroidManifest.xml', s => {
  if (!/xmlns:tools=/.test(s)) s = s.replace('<manifest xmlns:android="http://schemas.android.com/apk/res/android"', '<manifest xmlns:android="http://schemas.android.com/apk/res/android"\n    xmlns:tools="http://schemas.android.com/tools"');
  if (!/android:screenOrientation=/.test(s)) s = s.replace(/android:name="\.MainActivity"/, 'android:name=".MainActivity"\n            android:screenOrientation="portrait"');
  s = s.replace(/(<meta-data\s+android:name="com\.google\.android\.gms\.ads\.APPLICATION_ID"\s+android:value=")[^"]*(")/, '$1' + ADMOB.android + '$2');
  if (!/gms\.ads\.APPLICATION_ID/.test(s)) s = s.replace('</application>', '        <meta-data android:name="com.google.android.gms.ads.APPLICATION_ID" android:value="' + ADMOB.android + '"/>\n    </application>');
  if (!/SCHEDULE_EXACT_ALARM/.test(s)) s = s.replace('</manifest>', '    <uses-permission android:name="android.permission.SCHEDULE_EXACT_ALARM" tools:node="remove" />\n</manifest>');
  return s;
});

// ---------- iOS ----------
const plistSet = (s, key, xml) => {
  const re = new RegExp('\\t<key>' + key + '</key>\\n\\t(<(string|true|false)\\s*/?>[^\\n]*|<array>[\\s\\S]*?\\n\\t</array>)\\n');
  return re.test(s) ? s.replace(re, '\t<key>' + key + '</key>\n\t' + xml + '\n') : s.replace(/\n<\/dict>\n<\/plist>/, '\n\t<key>' + key + '</key>\n\t' + xml + '\n</dict>\n</plist>');
};
edit('ios/App/App/Info.plist', s => {
  s = plistSet(s, 'UISupportedInterfaceOrientations', '<array>\n\t\t<string>UIInterfaceOrientationPortrait</string>\n\t</array>');
  s = plistSet(s, 'UISupportedInterfaceOrientations~ipad', '<array>\n\t\t<string>UIInterfaceOrientationPortrait</string>\n\t\t<string>UIInterfaceOrientationPortraitUpsideDown</string>\n\t</array>');
  s = plistSet(s, 'GADApplicationIdentifier', '<string>' + ADMOB.ios + '</string>');
  s = plistSet(s, 'NSUserTrackingUsageDescription', '<string>' + TRACKING_TEXT + '</string>');
  s = plistSet(s, 'ITSAppUsesNonExemptEncryption', '<false/>');
  // Google's own network ID; add the full list from Google's AdMob iOS guide if you use mediation partners.
  s = plistSet(s, 'SKAdNetworkItems', '<array>\n\t\t<dict>\n\t\t\t<key>SKAdNetworkIdentifier</key>\n\t\t\t<string>cstr6suwn9.skadnetwork</string>\n\t\t</dict>\n\t</array>');
  return s;
});
edit('ios/App/App.xcodeproj/project.pbxproj', s => s.replace(/TARGETED_DEVICE_FAMILY = "1,2";/g, 'TARGETED_DEVICE_FAMILY = 1;'));
