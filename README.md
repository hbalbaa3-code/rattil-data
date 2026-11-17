# Rattil Mushaf data

The Mushaf data the [Rattil](https://github.com/hbalbaa3-code) Khatma app downloads on first
launch: the Madinah Mushaf (Hafs 'an 'Asim) as 604 page fonts plus the line layout of every page.

| Release file | What it is |
|---|---|
| `mushaf-vN.zip` | `fonts/pNNN.ttf` (one QPC V2 font per page), `fonts/bsml.ttf` (basmala), `pages/NNN.json` (lines of each page), `manifest.json` |
| `mushaf-vN.json` | size, SHA-256 and file count of the zip; the app checks the download against it |
| `quran-index.json` | surahs, juz' starts and the first surah of each page |

## Sources

- **Fonts:** QPC V2, by the King Fahd Glorious Quran Printing Complex. They are converted from
  WOFF2 to TTF without changes, so their copyright and terms stay in the files.
- **Page layout:** [Quran.com](https://quran.com)'s v2 layout, via the
  [zonetecde/mushaf-layout](https://github.com/zonetecde/mushaf-layout) dataset, pinned to one
  commit in `tools/fetch-dataset.sh`.

## Checks

`tools/build_mushaf.py` stops the build unless the data has 604 pages, 6,236 verses, 15 lines a
page (8 on the two opening pages), all 30 juz' starting on their printed pages, and every glyph a
page uses present in that page's font. The zip is reproducible: the same data gives the same bytes.

## Publishing

`VERSION` holds the data version. Pushing to `main` builds and publishes release `mushaf-v<VERSION>`
if it doesn't exist yet. A published version is never replaced; bump `VERSION` (and the app's
`rattil.mushafData`) to ship new data.
