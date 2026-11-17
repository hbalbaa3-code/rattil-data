#!/usr/bin/env python3
"""Builds the Mushaf data Rattil downloads, from the zonetecde/mushaf-layout dataset
(QPC V2 fonts, Quran.com v2 layout of the Madinah Mushaf, 1441H).

  python tools/build_mushaf.py --src dataset --out dist --version 1

writes
  dist/mushaf-v1.zip     fonts/pNNN.ttf, fonts/bsml.ttf, pages/NNN.json, manifest.json
  dist/mushaf-v1.json    {version, size, sha256, unpacked, files}: what the app checks
  dist/quran-index.json  surahs, juz' starts, first surah of each page (bundled in the app)

The page fonts are converted from WOFF2 to TTF without changing them. Every run validates the
dataset first (604 pages, 6,236 verses, 15 lines a page except 1-2, the 30 juz' on their printed
pages, every glyph present in its page font). Any mismatch stops the build: a wrong Mushaf must
never ship.
"""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

PAGES = 604
VERSES = 6236

# First verse of each juz' and the Madinah page it starts on (cross-checked against the data).
JUZ_STARTS = [
    ("1:1", 1), ("2:142", 22), ("2:253", 42), ("3:93", 62), ("4:24", 82), ("4:148", 102),
    ("5:82", 121), ("6:111", 142), ("7:88", 162), ("8:41", 182), ("9:93", 201), ("11:6", 222),
    ("12:53", 242), ("15:1", 262), ("17:1", 282), ("18:75", 302), ("21:1", 322), ("23:1", 342),
    ("25:21", 362), ("27:56", 382), ("29:46", 402), ("33:31", 422), ("36:28", 442),
    ("39:32", 462), ("41:47", 482), ("46:1", 502), ("51:31", 522), ("58:1", 542), ("67:1", 562),
    ("78:1", 582),
]


def fail(msg):
    sys.exit(f"build_mushaf: {msg}")


def load_pages(src: Path):
    pages = []
    for n in range(1, PAGES + 1):
        data = json.loads((src / "mushaf" / "QPC2" / f"page-{n:03d}.json").read_text("utf-8"))
        if data["page"] != n:
            fail(f"page-{n:03d}.json says page {data['page']}")
        pages.append(data["lines"])
    return pages


def verse_keys(line):
    return {w["location"].rsplit(":", 1)[0] for w in line.get("words", [])}


def validate(pages):
    seen = {}
    for n, lines in enumerate(pages, start=1):
        expected = 8 if n <= 2 else 15
        if len(lines) != expected:
            fail(f"page {n} has {len(lines)} lines, expected {expected}")
        for i, line in enumerate(lines, start=1):
            if line["line"] != i:
                fail(f"page {n} line numbering broken at {i}")
            kind = line["type"]
            if kind == "text":
                if not line["words"] or any(not w["qpcV2"].strip() for w in line["words"]):
                    fail(f"page {n} line {i} has an empty word")
                for key in verse_keys(line):
                    seen.setdefault(key, n)
            elif kind == "basmala":
                if not line.get("qpcV2"):
                    fail(f"page {n} line {i}: basmala without glyphs")
            elif kind != "surah-header":
                fail(f"page {n} line {i}: unknown line type {kind}")
    if len(seen) != VERSES:
        fail(f"found {len(seen)} verses, expected {VERSES}")
    for key, page in JUZ_STARTS:
        if seen.get(key) != page:
            fail(f"juz' start {key} is on page {seen.get(key)}, expected {page}")
    return seen


def build_index(src: Path, pages, verse_page):
    meta = json.loads((src / "src" / "data" / "surahs.json").read_text("utf-8"))
    starts = {}
    for n, lines in enumerate(pages, start=1):
        for line in lines:
            if line["type"] == "surah-header":
                starts.setdefault(int(line["surah"]), n)
    if sorted(starts) != list(range(1, 115)):
        fail("surah headers do not cover 1..114")
    surahs = []
    for s in meta:
        number = s["id"]
        # In this printing 18 headers sit on the last line of the page before the surah's
        # first verse. A surah "starts" where its first verse is: that is where reading begins.
        first_page = verse_page[f"{number}:1"]
        if starts[number] not in (first_page, first_page - 1):
            fail(f"surah {number} header is on page {starts[number]}, first verse on {first_page}")
        surahs.append({
            "n": number,
            "ar": s["arabic"],
            "en": s["name"],
            "ayat": s["totalAyah"],
            "page": first_page,
        })
    first_surah = []
    for lines in pages:
        keys = [k for line in lines for k in verse_keys(line)]
        first_surah.append(min(int(k.split(":")[0]) for k in keys))
    return {
        "source": "zonetecde/mushaf-layout QPC2 (Quran.com v2 layout, Madinah Mushaf)",
        "pages": PAGES,
        "surahs": surahs,
        "juz": [page for _, page in JUZ_STARTS],
        "pageSurah": first_surah,
    }


def compact_page(lines):
    out = []
    for line in lines:
        kind = line["type"]
        if kind == "surah-header":
            out.append({"t": "h", "s": int(line["surah"])})
        elif kind == "basmala":
            out.append({"t": "b", "g": line["qpcV2"]})
        else:
            tokens = [t for w in line["words"] for t in w["qpcV2"].split(" ") if t]
            out.append({"t": "x", "g": tokens, "v": line["verseRange"]})
    return {"lines": out}


def to_ttf(src_font: Path, strip_hinting: bool):
    """WOFF2 (or TTF) -> TTF bytes. Unchanged unless strip_hinting, which drops the hint programs."""
    import io
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables import ttProgram

    font = TTFont(str(src_font))
    font.flavor = None
    if strip_hinting:
        for tag in ("fpgm", "prep", "cvt ", "hdmx", "VDMX", "LTSH", "gasp"):
            if tag in font:
                del font[tag]
        glyf = font["glyf"]
        for name in glyf.keys():
            glyph = glyf[name]
            if hasattr(glyph, "program"):
                glyph.program = ttProgram.Program()
                glyph.program.fromBytecode(b"")
        font["maxp"].maxSizeOfInstructions = 0
    out = io.BytesIO()
    font.save(out)
    return out.getvalue(), font.getBestCmap()


def check_glyphs(n, page, cmap):
    for line in page["lines"]:
        glyphs = "".join(line["g"]) if line["t"] == "x" else ""
        missing = {c for c in glyphs if ord(c) not in cmap}
        if missing:
            fail(f"page {n}: font lacks {sorted(hex(ord(c)) for c in missing)}")


FIXED_TIME = (1980, 1, 1, 0, 0, 0)  # reproducible zips: same data, same bytes


def add(zf: zipfile.ZipFile, name: str, data: bytes):
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    zf.writestr(info, data, compresslevel=9)


def build_zip(src: Path, pages, version: int, out: Path, strip_hinting: bool):
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"mushaf-v{version}.zip"
    qpc = src / "fonts" / "QPC2"
    unpacked = 0
    files = 0
    with zipfile.ZipFile(path, "w") as zf:
        for n, lines in enumerate(pages, start=1):
            page = compact_page(lines)
            data, cmap = to_ttf(qpc / f"p{n:03d}.woff2", strip_hinting)
            check_glyphs(n, page, cmap)
            text = json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            add(zf, f"fonts/p{n:03d}.ttf", data)
            add(zf, f"pages/{n:03d}.json", text)
            unpacked += len(data) + len(text)
            files += 2
        data, _ = to_ttf(qpc / "QPC2BSML.ttf", strip_hinting)
        add(zf, "fonts/bsml.ttf", data)
        unpacked += len(data)
        files += 1
        manifest = json.dumps({"version": version, "pages": PAGES, "files": files + 1}).encode("utf-8")
        add(zf, "manifest.json", manifest)
        unpacked += len(manifest)
        files += 1
    blob = path.read_bytes()
    info = {
        "version": version,
        "size": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "unpacked": unpacked,
        "files": files,
    }
    (out / f"mushaf-v{version}.json").write_text(json.dumps(info, indent=2) + "\n", "utf-8")
    print(f"{path.name}: {len(blob) / 1e6:.1f} MB, {files} files, {unpacked / 1e6:.1f} MB unpacked")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path, help="mushaf-layout checkout")
    ap.add_argument("--out", required=True, type=Path, help="output folder")
    ap.add_argument("--version", required=True, type=int, help="data version (the app's MUSHAF_DATA_VERSION)")
    ap.add_argument("--index-only", action="store_true", help="only write quran-index.json")
    ap.add_argument("--strip-hinting", action="store_true", help="drop the fonts' hint programs")
    args = ap.parse_args()

    pages = load_pages(args.src)
    verse_page = validate(pages)
    print(f"dataset ok: {PAGES} pages, {len(verse_page)} verses, 30 juz' boundaries")

    args.out.mkdir(parents=True, exist_ok=True)
    index = build_index(args.src, pages, verse_page)
    (args.out / "quran-index.json").write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), "utf-8")
    print("quran-index.json written")
    if not args.index_only:
        build_zip(args.src, pages, args.version, args.out, args.strip_hinting)


if __name__ == "__main__":
    main()
