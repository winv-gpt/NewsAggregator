// Builds www/ (what Capacitor puts inside the app) from the web game in game/:
//   game/kaiten.html  ->  www/index.html (page and styles) + www/game.js (the game's script)
//   game/fonts, game/music, app-config.js, src/bridge.js (bundled with its plugins and Firebase)
// The game's script loads only after the bridge has restored the save, so the game always starts with it.
import { readFileSync, writeFileSync, mkdirSync, rmSync, cpSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..'), WWW = join(ROOT, 'www');
const src = readFileSync(join(ROOT, 'game/kaiten.html'), 'utf8');

const scripts = [...src.matchAll(/<script>([\s\S]*?)<\/script>/g)];
if (scripts.length !== 1) throw new Error('expected the game to have exactly one <script>, found ' + scripts.length);
const title = (src.match(/<title>([^<]*)<\/title>/) || [, "Ken's Sushi"])[1];
const body = src
  .replace(scripts[0][0], '')
  .replace(/<title>[^<]*<\/title>/, '')
  .replace(/<link[^>]+fonts\.(googleapis|gstatic)\.com[^>]*>\s*/g, '');   // fonts ship inside the app instead
if (/fonts\.googleapis\.com|fonts\.gstatic\.com/.test(body)) throw new Error('the game still refers to Google Fonts');

rmSync(WWW, { recursive: true, force: true });
mkdirSync(WWW, { recursive: true });
// The same small reset the Claude page wraps the game in, with the phone's safe areas (notch, home bar) kept clear.
const shell = ':root{color-scheme:light;box-sizing:border-box;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px);padding-left:env(safe-area-inset-left,0px);padding-right:env(safe-area-inset-right,0px)}' +
  'html{scroll-padding-top:env(safe-area-inset-top,0px);-webkit-text-size-adjust:100%;-webkit-tap-highlight-color:transparent}' +
  'body{margin:0;padding:0;font:14px -apple-system,BlinkMacSystemFont,sans-serif;background:#fff;color:#000;overscroll-behavior:none}' +
  'img{max-width:100%}[hidden]:not([hidden=until-found i]){display:none!important}';
writeFileSync(join(WWW, 'index.html'),
  '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">\n' +
  '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n' +
  '<meta name="color-scheme" content="light dark">\n<title>' + title + '</title>\n' +
  '<link rel="stylesheet" href="fonts/fonts.css">\n<style>' + shell + '</style>\n</head><body>\n' + body.trim() + '\n' +
  '<script src="app-config.js"></script>\n<script src="bridge.js"></script>\n</body></html>\n');
writeFileSync(join(WWW, 'game.js'), scripts[0][1].trim() + '\n');
cpSync(join(ROOT, 'game/fonts'), join(WWW, 'fonts'), { recursive: true });
cpSync(join(ROOT, 'game/music'), join(WWW, 'music'), { recursive: true });
cpSync(join(ROOT, 'app-config.js'), join(WWW, 'app-config.js'));
await build({ entryPoints: [join(ROOT, 'src/bridge.js')], bundle: true, format: 'iife', target: ['es2020', 'safari15'], minify: true, outfile: join(WWW, 'bridge.js'), logLevel: 'warning', legalComments: 'linked' });
console.log('www/ built: index.html, game.js (' + Math.round(scripts[0][1].length / 1024) + ' KB), bridge.js, fonts, music');
