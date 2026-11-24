Web app files: manifest, icons and the offline helper. build_site.py copies them into site/.

Fonts with BULGARIAN letter shapes (24 Nov 2026, David chose option A after Bulgarian philologists pointed out that the
old fonts - Oswald, Golos Text, Noto Serif, Noto Serif Display - had only the Russian shapes). All SIL Open Font License,
from github.com/google/fonts, made with fontTools: fixed at one weight each, cut to Cyrillic or basic Latin, OpenType
features kept (the Bulgarian shapes are a "locl" feature for lang="bg"; Sofia Sans has them by default). The weights
are matched to the old fonts' stroke thickness; size-adjust in site_template.html matches the old letter heights.
- sofia-sans-{cyrillic,latin}-{400,500,600}.woff2: body text. Sofia Sans (Lettersoup), cut at weights 410/610/720.
  Licence OFL-sofia-sans.txt.
- sofia-sans-xcond-{cyrillic,latin}-{200,300,400,500}.woff2: labels and numbers (was Oswald). Sofia Sans Extra
  Condensed, cut at weights 310/390/590/775. Licence OFL-sofia-sans.txt.
- source-serif-{cyrillic,latin}-600.woff2: story headlines. Source Serif 4, weight 600, optical size 20.
  Licence OFL-source-serif-4.txt.
- roboto-serif-narrow-400.woff2 / roboto-serif-narrow-italic-300.woff2: the big page titles. Roboto Serif at width 62,
  optical size 144, weights 410 / italic 250, Bulgarian + basic Latin only. Licence OFL-roboto-serif.txt.

kalam-latin-400.woff2 (22 Nov 2026): the footer's line „Jesus Christ is the greatest of all time." (David). Kalam Regular,
Latin only, from @fontsource/kalam (OFL, licence in OFL-kalam.txt), ~22 KB.
