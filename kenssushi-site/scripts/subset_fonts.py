# Cut the site's fonts (SIL Open Font License, from github.com/google/fonts) down to the characters its pages use.
# Usage: python3 -I scripts/subset_fonts.py <folder with the downloaded .ttf and OFL.txt files>
# Run it again after adding text in new scripts (for example more Japanese) to the pages.
import sys, os, glob, html
from fontTools import subset
src = sys.argv[1]
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = os.path.join(root, 'src', 'fonts')
text = ''.join(html.unescape(open(f, encoding='utf8').read()) for f in glob.glob(os.path.join(root, 'src', '**', '*.html'), recursive=True))
chars = ''.join(sorted(c for c in set(text) | set(chr(c) for c in range(0x20, 0x7f)) | set('¥×–—’‘“”…·•★☆[]鮨') if ord(c) >= 0x20))
FONTS = [
  ('shipporiminchob1_ShipporiMinchoB1-Bold.ttf', 'Shippori Mincho B1', 700, 'shippori-mincho-b1-700'),
  ('shipporiminchob1_ShipporiMinchoB1-ExtraBold.ttf', 'Shippori Mincho B1', 800, 'shippori-mincho-b1-800'),
  ('zenkakugothicnew_ZenKakuGothicNew-Regular.ttf', 'Zen Kaku Gothic New', 400, 'zen-kaku-gothic-new-400'),
  ('zenkakugothicnew_ZenKakuGothicNew-Medium.ttf', 'Zen Kaku Gothic New', 500, 'zen-kaku-gothic-new-500'),
  ('zenkakugothicnew_ZenKakuGothicNew-Bold.ttf', 'Zen Kaku Gothic New', 700, 'zen-kaku-gothic-new-700'),
  ('yujisyuku_YujiSyuku-Regular.ttf', 'Yuji Syuku', 400, 'yuji-syuku-400'),
]
css = ['/* Subsets of SIL Open Font License fonts (licences in this folder), made by scripts/subset_fonts.py */']
for f, fam, w, name in FONTS:
    o = subset.Options(); o.flavor = 'woff2'; o.layout_features = ['*']; o.name_IDs = ['*']; o.notdef_outline = True
    font = subset.load_font(os.path.join(src, f), o); s = subset.Subsetter(o); s.populate(text=chars); s.subset(font)
    p = os.path.join(out, name + '.woff2'); subset.save_font(font, p, o)
    css.append("@font-face{font-family:'%s';font-style:normal;font-weight:%d;font-display:swap;src:url(%s.woff2) format('woff2')}" % (fam, w, name))
    print(name, os.path.getsize(p), 'bytes')
open(os.path.join(out, 'fonts.css'), 'w').write('\n'.join(css) + '\n')
for lic, tag in [('shipporiminchob1_OFL.txt', 'ShipporiMinchoB1'), ('zenkakugothicnew_OFL.txt', 'ZenKakuGothicNew'), ('yujisyuku_OFL.txt', 'YujiSyuku')]:
    open(os.path.join(out, 'OFL-' + tag + '.txt'), 'w').write(open(os.path.join(src, lic), encoding='utf8').read())
print(len(chars), 'characters kept')
