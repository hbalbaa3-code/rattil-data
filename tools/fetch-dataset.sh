#!/usr/bin/env bash
# Checks out the Mushaf layout dataset at a pinned commit, so every pack is built from the same
# reviewed data. To move to a newer dataset: change SHA, run build_mushaf.py (it re-validates
# everything), regenerate app/src/main/assets/quran-index.json, and bump rattil.mushafPack.
set -euo pipefail

DEST="${1:-dataset}"
REPO="https://github.com/zonetecde/mushaf-layout"
SHA="421e9eaa991897ecd50d7abb79160651a45976d3"

rm -rf "$DEST"
git init -q "$DEST"
GIT_LFS_SKIP_SMUDGE=1 git -C "$DEST" fetch -q --depth 1 "$REPO" "$SHA"
git -C "$DEST" checkout -q FETCH_HEAD
echo "dataset $SHA -> $DEST"
