# Cut the game's three Japanese fonts (SIL Open Font License, from github.com/google/fonts) down to the characters
# the game actually uses, so they can ship inside the app instead of loading from Google Fonts.
# Usage: python3 -I scripts/subset_fonts.py <game.html> <folder with the downloaded .ttf files> <out folder>
import sys, os, re, html
from fontTools import subset
game, src, out = sys.argv[1:4]
text = html.unescape(open(game, encoding='utf8').read())
chars = set(text) | set(chr(c) for c in range(0x20, 0x7f)) | set('¥×–—’‘“”…·•★☆✦円')
chars = ''.join(sorted(c for c in chars if ord(c) >= 0x20))
FONTS = [  # (file, family, weight, out name, characters)
  ('shipporiminchob1_ShipporiMinchoB1-SemiBold.ttf', 'Shippori Mincho B1', 600, 'shippori-mincho-b1-600', chars),
  ('shipporiminchob1_ShipporiMinchoB1-Bold.ttf', 'Shippori Mincho B1', 700, 'shippori-mincho-b1-700', chars),
  ('shipporiminchob1_ShipporiMinchoB1-ExtraBold.ttf', 'Shippori Mincho B1', 800, 'shippori-mincho-b1-800', chars),
  ('zenkakugothicnew_ZenKakuGothicNew-Regular.ttf', 'Zen Kaku Gothic New', 400, 'zen-kaku-gothic-new-400', chars),
  ('zenkakugothicnew_ZenKakuGothicNew-Medium.ttf', 'Zen Kaku Gothic New', 500, 'zen-kaku-gothic-new-500', chars),
  ('zenkakugothicnew_ZenKakuGothicNew-Bold.ttf', 'Zen Kaku Gothic New', 700, 'zen-kaku-gothic-new-700', chars),
  ('yujisyuku_YujiSyuku-Regular.ttf', 'Yuji Syuku', 400, 'yuji-syuku-400', "KEN’S SUHI'" + ''.join(chr(c) for c in range(0x41, 0x5b))),
]
css = ['/* Subsets of SIL Open Font License fonts (see OFL-*.txt), made by scripts/subset_fonts.py */']
for f, fam, w, name, cs in FONTS:
    opts = subset.Options(); opts.flavor = 'woff2'; opts.layout_features = ['*']; opts.name_IDs = ['*']; opts.notdef_outline = True
    font = subset.load_font(os.path.join(src, f), opts)
    sub = subset.Subsetter(opts); sub.populate(text=cs); sub.subset(font)
    path = os.path.join(out, name + '.woff2'); subset.save_font(font, path, opts)
    css.append("@font-face{font-family:'%s';font-style:normal;font-weight:%d;font-display:swap;src:url(%s.woff2) format('woff2')}" % (fam, w, name))
    print(name, os.path.getsize(path), 'bytes')
open(os.path.join(out, 'fonts.css'), 'w').write('\n'.join(css) + '\n')
for lic, tag in [('shipporiminchob1_OFL.txt', 'ShipporiMinchoB1'), ('zenkakugothicnew_OFL.txt', 'ZenKakuGothicNew'), ('yujisyuku_OFL.txt', 'YujiSyuku')]:
    open(os.path.join(out, 'OFL-' + tag + '.txt'), 'w').write(open(os.path.join(src, lic), encoding='utf8').read())
print(len(chars), 'characters kept')
