#!/usr/bin/env python3
# Generate blueprint/src/content.tex from all .lean source files.
# Extracts every public declaration, docstring, and best-effort uses deps.

import re, sys
from pathlib import Path

LEAN_DIR = Path.home() / ".openclaw/workspace-matty/workspace/TilingPolyomino/TilingPolyomino"
OUT = Path.home() / ".openclaw/workspace-matty/workspace/TilingPolyomino/blueprint/src/content.tex"

# ── kind mapping ─────────────────────────────────────────────────────────────
KIND_MAP = {
    "theorem":          "theorem",
    "lemma":            "lemma",
    "def":              "definition",
    "noncomputable def":"definition",
    "abbrev":           "definition",
    "structure":        "definition",
    "class":            "definition",
    "instance":         "definition",
}
SKIP_KINDS = {"instance", "class"}   # hide from blueprint (noisy)

# Lean names that are pure boilerplate — skip them
SKIP_NAMES = {
    "hello",   # Basic.lean placeholder
}

# Names to NEVER include in \uses{} -- they're ubiquitous infrastructure that
# would create an explosion of edges connecting everything to everything.
USES_BLOCKLIST = {
    "Cell", "Region", "LTileable", "rectangle", "lTromino", "lTrominoSet",
    "Prototile", "Protoset", "PlacedTile", "TileSet", "Tileable",
    "RectTileableConditions", "translateCell", "translateRegion",
    "swapCell", "swapRegion", "rotateCell", "rotateRegion90",
    "rect", "RExp",
}

# ── parser ───────────────────────────────────────────────────────────────────
DECL_RE = re.compile(
    r'^(?:private\s+|protected\s+)?'
    r'(noncomputable\s+def|theorem|lemma|def|abbrev|structure|class|instance)\s+'
    r'([\w\'\.]+)',
    re.MULTILINE,
)
DOC_RE = re.compile(r'/--' + r'(.*?)' + r'-/', re.DOTALL)
SECTION_RE = re.compile(r'^/-\s*#{1,3}\s+(.*?)\s*-/', re.MULTILINE)

def extract_docstring(text, pos):
    """Find the /-- ... -/ docstring immediately before position pos."""
    before = text[:pos]
    # Find ALL docstrings; take the last one if it's immediately before pos
    all_docs = list(re.finditer(r'/--' + r'(.*?)' + r'-/', before, re.DOTALL))
    if not all_docs:
        return None
    last = all_docs[-1]
    # Only use it if only whitespace follows it before the declaration
    after_doc = before[last.end():].strip()
    if after_doc:
        return None
    doc = last.group(1).strip()
    # Take only the first sentence / first line to keep descriptions short
    first_line = doc.split('\n')[0].strip()
    if len(first_line) > 20:
        doc = first_line
    else:
        doc = re.sub(r'\s+', ' ', doc)
    if len(doc) > 250:
        doc = doc[:247] + '...'
    return doc

def label(name):
    """Convert Lean name to a blueprint label (lowercase, dots→underscores)."""
    return name.replace('.', '_').replace("'", "p")

def tex_escape(s):
    """Minimal TeX escaping for docstring text."""
    s = s.replace('\\', r'\textbackslash{}')
    s = s.replace('&', r'\&')
    s = s.replace('%', r'\%')
    s = s.replace('$', r'\$')  # keep math inline? risky — just escape
    s = s.replace('#', r'\#')
    s = s.replace('^', r'\^{}')
    s = s.replace('_', r'\_')
    s = s.replace('{', r'\{')
    s = s.replace('}', r'\}')
    s = s.replace('~', r'\textasciitilde{}')
    return s

# Hand-curated \uses{} for the key top-level theorems only.
# Keys = Lean declaration name; values = list of Lean names it directly uses.
CURATED_USES = {
    "rect_tileable_iff": [
        "LTileable.area_div_3", "not_tileable_1_by_n", "not_tileable_3_by_odd",
        "tileable_odd_x_mult3", "tileable_even_mult3",
    ],
    "rectMinusCorner_tileable_iff": [
        "rect_tileable_iff",
        "tileable_rectMinusCorner_mod2_case", "tileable_rectMinusCorner_mod1_case",
        "rectMinusCorner_tileable_area_div_3",
    ],
    "rectMinus2Corner_tileable_of_area_mod2": [
        "rectMinusCorner_tileable_iff",
        "tileable_rectangleMinus2Corner_3jplus2_3kplus1",
        "tileable_rectangleMinus2Corner_3jplus1_3kplus2",
    ],
    "tileable_rectangleMinus2Corner_3jplus1_3kplus2": [
        "tileable_rectangleMinus2Corner_4_3kplus2",
        "tileable_rectangleMinus2Corner_3jplus2_3kplus1",
    ],
    "tileable_rectangleMinus2Corner_4_3kplus2": [
        "rectMinusCorner_tileable_iff",
    ],
    "tileable_rectangleMinus2Corner_3jplus2_3kplus1": [
        "rect_tileable_iff", "rectMinusCorner_tileable_iff",
        "LTileable_topRightLTromino",
    ],
    "tileable_rectMinusCorner_mod2_case": [
        "tileable_rectMinusCorner_mod2_jk_ge2",
        "tileable_3kplus2_x2_minus", "tileable_5x_3kplus2_minus",
    ],
    "tileable_rectMinusCorner_mod1_case": [
        "tileable_rectMinusCorner_mod1_jk_ge",
        "tileable_4x_rectMinus_3kplus1", "tileable_7x7_minus",
    ],
    "tileable_rectMinusCorner_mod2_jk_ge2": [
        "tileable_3kplus2_x2_minus", "rect_tileable_iff",
    ],
    "tileable_rectMinusCorner_mod1_jk_ge": [
        "tileable_4x_rectMinus_3kplus1", "rect_tileable_iff",
    ],
    "tileable_4x_rectMinus_3kplus1": [
        "tileable_4x4_minus", "rect_tileable_iff",
    ],
    "tileable_3kplus2_x2_minus": [
        "tileable_2x2_minus", "tileable_mult3_x2",
    ],
    "tileable_5x_3kplus2_minus": [
        "tileable_5x_6kplus2_minus", "tileable_5x_6kplus5_minus",
    ],
    "tileable_5x_6kplus2_minus": ["tileable_5x2_minus", "tileable_5x6j"],
    "tileable_5x_6kplus5_minus": ["tileable_5x5_minus", "tileable_5x6j"],
    "tileable_odd_x_mult3": [
        "tileable_odd_x_6j", "tileable_odd_ge5_x_6iplus3",
    ],
    "tileable_even_mult3": ["tileable_3x_even", "tileable_2x_mult3"],
    "tileable_odd_x_6j": ["tileable_5x6j", "tileable_even_mult3"],
    "tileable_odd_ge5_x_6iplus3": [
        "tileable_odd_x_6j", "tileable_5x_9plus6j",
    ],
    "tileable_5x6j":      ["tileable_even_mult3"],
    "tileable_5x_9plus6j":["tileable_5x6j"],
    "tileable_3x_even":   ["tileable_2x3"],
    "tileable_2x_mult3":  ["tileable_2x3"],
    "not_tileable_3_by_odd": ["not_tileable_1_by_n"],
    "not_tileable_n_by_1":   ["not_tileable_1_by_n"],
    "not_tileable_odd_by_3": ["not_tileable_n_by_1"],
}

# ── main ─────────────────────────────────────────────────────────────────────
files = sorted(LEAN_DIR.glob("*.lean"))
print(f"Processing {len(files)} files: {[f.name for f in files]}")

# First pass: collect ALL declaration names across all files
all_decls = {}   # name -> {file, kind, pos, doc, label}
file_decls = {}  # filename -> list of (pos, name)

for fpath in files:
    text = fpath.read_text()
    decls = []
    for m in DECL_RE.finditer(text):
        raw_kind = m.group(1).strip()
        name = m.group(2)
        if name in SKIP_NAMES:
            continue
        kind = KIND_MAP.get(raw_kind, "definition")
        doc = extract_docstring(text, m.start())
        lbl = label(name)
        all_decls[name] = {
            "file": fpath.name,
            "kind": kind,
            "raw_kind": raw_kind,
            "pos": m.start(),
            "doc": doc,
            "label": lbl,
        }
        decls.append((m.start(), name))
    file_decls[fpath.name] = decls

all_names = set(all_decls.keys())
print(f"Total declarations: {len(all_names)}")

# Second pass: assign \uses{} from curated table only (no text-scanning)
for name, info in all_decls.items():
    raw_uses = CURATED_USES.get(name, [])
    # Filter to names that actually exist in our decl set
    info["uses"] = [u for u in raw_uses if u in all_decls]

# ── generate content.tex ─────────────────────────────────────────────────────
FILE_TITLES = {
    "Tiling.lean":    "Tiling Infrastructure",
    "RectOmega.lean": "Rectangle and Omega Infrastructure",
    "LTromino.lean":  "L-tromino Tiling of Rectangles and Deficient Rectangles",
    "Basic.lean":     "Miscellaneous",
}

lines = []
lines.append(r"% AUTO-GENERATED by gen_blueprint.py — do not edit by hand")
lines.append(r"% Regenerate with: python3 gen_blueprint.py")
lines.append("")

for fpath in files:
    fname = fpath.name
    decl_list = file_decls[fname]
    if not decl_list:
        continue

    title = FILE_TITLES.get(fname, fname.replace(".lean", ""))
    lines.append(r"\chapter{" + title + "}")
    lines.append("")

    text = fpath.read_text()

    # Find section comments within the file to add \section{} breaks
    section_positions = []
    for sm in SECTION_RE.finditer(text):
        section_positions.append((sm.start(), sm.group(1)))

    sec_idx = 0
    for pos, name in decl_list:
        info = all_decls[name]
        if info["kind"] in SKIP_KINDS:
            continue

        # Emit any section headers that come before this declaration
        while sec_idx < len(section_positions) and section_positions[sec_idx][0] < pos:
            lines.append(r"\section{" + section_positions[sec_idx][1] + "}")
            lines.append("")
            sec_idx += 1

        kind = info["kind"]
        lbl  = info["label"]
        doc  = info["doc"]
        uses = info["uses"]

        lines.append(r"\begin{" + kind + "}")
        lines.append(r"  \label{" + lbl + "}")
        lines.append(r"  \lean{" + name + "}")
        if uses:
            # split into lines of ≤4 labels each
            use_labels = [all_decls[u]["label"] for u in uses if u in all_decls]
            # deduplicate keeping order
            seen = set(); use_labels_u = []
            for ul in use_labels:
                if ul not in seen: seen.add(ul); use_labels_u.append(ul)
            chunks = [use_labels_u[i:i+4] for i in range(0, len(use_labels_u), 4)]
            use_str = (",\n        ").join(", ".join(c) for c in chunks)
            lines.append(r"  \uses{" + use_str + "}")
        lines.append(r"  \leanok")
        lines.append(r"  \proven")
        if doc:
            lines.append(r"  " + tex_escape(doc))
        else:
            lines.append(r"  \((" + tex_escape(name) + r")\)")
        lines.append(r"\end{" + kind + "}")
        lines.append("")

    # flush remaining section headers
    while sec_idx < len(section_positions):
        lines.append(r"\section{" + section_positions[sec_idx][1] + "}")
        lines.append("")
        sec_idx += 1

OUT.write_text("\n".join(lines) + "\n")
print(f"Written {OUT} ({OUT.stat().st_size} bytes, {len(lines)} lines)")

# Post-process: fix useWorker: true → false for proxy compatibility
dep_graph_html = OUT.parent.parent / "web" / "dep_graph_document.html"
if dep_graph_html.exists():
    content = dep_graph_html.read_text()
    fixed = content.replace("useWorker: true", "useWorker: false")
    if fixed != content:
        dep_graph_html.write_text(fixed)
        print(f"Patched useWorker in {dep_graph_html}")
