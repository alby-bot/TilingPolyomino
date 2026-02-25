#!/usr/bin/env python3
"""
Install the tectonicmupdf imager into the local plasTeX installation.
Run once after installing plasTeX:  python3 blueprint/install_imager.py
"""
import os, shutil, re, sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

# ── 1. Copy imager module ────────────────────────────────────────────────────
import plasTeX.Imagers
imagers_dir = Path(plasTeX.Imagers.__file__).parent
dest = imagers_dir / 'tectonicmupdf.py'
src  = SCRIPT_DIR / 'tectonicmupdf_imager.py'
shutil.copy2(str(src), str(dest))
print(f"Copied imager → {dest}")

# ── 2. Patch the renderer to recognise 'tectonicmupdf' ──────────────────────
import plasTeX.Renderers
renderers_init = Path(plasTeX.Renderers.__file__).parent / '__init__.py'
text = renderers_init.read_text()

PATCH_MARKER = "elif name == 'tectonicmupdf':"
if PATCH_MARKER in text:
    print("Renderer already patched — skipping.")
else:
    old = "            elif name == 'OSXCoreGraphics':\n                from plasTeX.Imagers.OSXCoreGraphics  import Imager\n            else:"
    new = ("            elif name == 'OSXCoreGraphics':\n"
           "                from plasTeX.Imagers.OSXCoreGraphics  import Imager\n"
           "            elif name == 'tectonicmupdf':\n"
           "                from plasTeX.Imagers.tectonicmupdf import Imager\n"
           "            else:")
    if old not in text:
        print("WARNING: Could not find expected patch location in renderer — check manually.", file=sys.stderr)
    else:
        renderers_init.write_text(text.replace(old, new))
        print(f"Patched renderer → {renderers_init}")

print("Done.")
