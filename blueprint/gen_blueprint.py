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

# ── TikZ figures injected after specific theorem descriptions ─────────────────
# Each value is raw LaTeX inserted inside the theorem env, after the description.
# Use \cs (=0.50cm cell), \filledcell{x}{y}{color}, \removedcell{x}{y},
# \drawgrid{w}{h}, and the named colors defined in web.tex.
FIGURE_INJECTIONS = {

"tileable_2x2_minus": r"""
  \begin{center}\begin{tikzpicture}
    \drawgrid{2}{2}
    \filledcell{0}{0}{tcolor1}\filledcell{0}{1}{tcolor1}\filledcell{1}{0}{tcolor1}
    \removedcell{1}{1}
  \end{tikzpicture}\end{center}""",

"tileable_5x2_minus": r"""
  \begin{center}\begin{tikzpicture}
    \drawgrid{5}{2}
    \filledcell{0}{0}{tcolor1}\filledcell{0}{1}{tcolor1}\filledcell{1}{0}{tcolor1}
    \filledcell{1}{1}{tcolor2}\filledcell{2}{0}{tcolor2}\filledcell{2}{1}{tcolor2}
    \filledcell{3}{0}{tcolor3}\filledcell{3}{1}{tcolor3}\filledcell{4}{0}{tcolor3}
    \removedcell{4}{1}
  \end{tikzpicture}\end{center}""",

"tileable_4x4_minus": r"""
  \begin{center}\begin{tikzpicture}
    \drawgrid{4}{4}
    \filledcell{0}{0}{tcolor1}\filledcell{0}{1}{tcolor1}\filledcell{1}{0}{tcolor1}
    \filledcell{2}{0}{tcolor2}\filledcell{3}{0}{tcolor2}\filledcell{3}{1}{tcolor2}
    \filledcell{0}{2}{tcolor3}\filledcell{0}{3}{tcolor3}\filledcell{1}{3}{tcolor3}
    \filledcell{2}{2}{tcolor4}\filledcell{2}{3}{tcolor4}\filledcell{3}{2}{tcolor4}
    \filledcell{1}{1}{tcolor5}\filledcell{1}{2}{tcolor5}\filledcell{2}{1}{tcolor5}
    \removedcell{3}{3}
  \end{tikzpicture}\end{center}""",

"tileable_5x5_minus": r"""
  \begin{center}\begin{tikzpicture}
    \drawgrid{5}{5}
    \filledcell{0}{0}{tcolor1}\filledcell{0}{1}{tcolor1}\filledcell{1}{0}{tcolor1}
    \filledcell{0}{2}{tcolor1}\filledcell{1}{1}{tcolor1}\filledcell{1}{2}{tcolor1}
    \filledcell{2}{0}{tcolor2}\filledcell{2}{1}{tcolor2}\filledcell{3}{0}{tcolor2}
    \filledcell{3}{1}{tcolor2}\filledcell{4}{0}{tcolor2}\filledcell{4}{1}{tcolor2}
    \filledcell{0}{3}{tcolor3}\filledcell{0}{4}{tcolor3}\filledcell{1}{4}{tcolor3}
    \filledcell{1}{3}{tcolor4}\filledcell{2}{2}{tcolor4}\filledcell{2}{3}{tcolor4}
    \filledcell{2}{4}{tcolor5}\filledcell{3}{3}{tcolor5}\filledcell{3}{4}{tcolor5}
    \filledcell{3}{2}{tcolor6}\filledcell{4}{2}{tcolor6}\filledcell{4}{3}{tcolor6}
    \removedcell{4}{4}
  \end{tikzpicture}\end{center}""",

"tileable_3kplus2_x2_minus": r"""
  Split off a $3k\times 2$ full rectangle (left, tileable); right piece is $R^{-}(2,2)$.
  Example $k=2$: $8\times 2$ minus corner.
  \begin{center}\begin{tikzpicture}
    \drawgrid{8}{2}
    \foreach \x in {0,1,2,3,4,5}{\foreach \y in {0,1}{\filledcell{\x}{\y}{rectColor}}}
    \foreach \x in {6,7}{\filledcell{\x}{0}{minusColor}}
    \filledcell{6}{1}{minusColor}
    \removedcell{7}{1}
    \draw[dashed,thick,gray] ({6*\cs},0) -- ({6*\cs},{2*\cs});
    \node[above] at ({3*\cs},{2*\cs}) {\small rect $6\times 2$};
    \node[above] at ({6.5*\cs},{2*\cs}) {\small $R^{-}(2,2)$};
  \end{tikzpicture}\end{center}""",

"tileable_4x_rectMinus_3kplus1": r"""
  Split a $4\times 3(k{-}1)$ full rectangle off the bottom; top is $R^{-}(4,4)$.
  Example $k=2$: $4\times 7$ minus corner.
  \begin{center}\begin{tikzpicture}
    \drawgrid{4}{7}
    \foreach \x in {0,1,2,3}{\foreach \y in {0,1,2}{\filledcell{\x}{\y}{rectColor}}}
    \foreach \x in {0,1,2,3}{\foreach \y in {3,4,5,6}{\filledcell{\x}{\y}{minusColor}}}
    \removedcell{3}{6}
    \draw[dashed,thick,gray] (0,{3*\cs}) -- ({4*\cs},{3*\cs});
    \node[right=2pt] at ({4*\cs},{1.5*\cs}) {\small rect $4\times 3$};
    \node[right=2pt] at ({4*\cs},{4.5*\cs}) {\small $R^{-}(4,4)$};
  \end{tikzpicture}\end{center}""",

"tileable_5x_3kplus2_minus": r"""
  Split a $5\times 3k$ full rectangle off the bottom; top is $R^{-}(5,2)$ or $R^{-}(5,5)$.
  Example $k=2$: $5\times 8$ minus corner.
  \begin{center}\begin{tikzpicture}
    \drawgrid{5}{8}
    \foreach \x in {0,1,2,3,4}{\foreach \y in {0,1,2,3,4,5}{\filledcell{\x}{\y}{rectColor}}}
    \foreach \x in {0,1,2,3,4}{\foreach \y in {6,7}{\filledcell{\x}{\y}{minusColor}}}
    \removedcell{4}{7}
    \draw[dashed,thick,gray] (0,{6*\cs}) -- ({5*\cs},{6*\cs});
    \node[right=2pt] at ({5*\cs},{3*\cs}) {\small rect $5\times 6$};
    \node[right=2pt] at ({5*\cs},{6.5*\cs}) {\small $R^{-}(5,2)$};
  \end{tikzpicture}\end{center}""",

"tileable_rectMinusCorner_mod2_jk_ge2": r"""
  For $j,k\ge 2$: split a $(3j{+}2)\times 3k$ full rectangle off the bottom;
  top is $R^{-}(3j{+}2,2)$. Example $j=k=2$: $8\times 8$ minus corner.
  \begin{center}\begin{tikzpicture}
    \drawgrid{8}{8}
    \foreach \x in {0,1,2,3,4,5,6,7}{\foreach \y in {0,1,2,3,4,5}{\filledcell{\x}{\y}{rectColor}}}
    \foreach \x in {0,1,2,3,4,5,6,7}{\foreach \y in {6,7}{\filledcell{\x}{\y}{minusColor}}}
    \removedcell{7}{7}
    \draw[dashed,thick,gray] (0,{6*\cs}) -- ({8*\cs},{6*\cs});
    \node at ({4*\cs},{3*\cs}) {\small rect $(3j{+}2)\times 3k$};
    \node at ({4*\cs},{7*\cs}) {\small $R^{-}(8,2)$};
  \end{tikzpicture}\end{center}""",

"tileable_rectMinusCorner_mod1_jk_ge": r"""
  For $n=3k{+}1$, $m=3j{+}1$, $j\ge 3$, $k\ge 1$: split a $(3k{+}1)\times 3(j{-}1)$
  full rectangle off the bottom; top is $R^{-}(3k{+}1,4)$.
  Example $j=3,k=1$: $4\times 10$ minus corner.
  \begin{center}\begin{tikzpicture}
    \drawgrid{4}{10}
    \foreach \x in {0,1,2,3}{\foreach \y in {0,1,2,3,4,5}{\filledcell{\x}{\y}{rectColor}}}
    \foreach \x in {0,1,2,3}{\foreach \y in {6,7,8,9}{\filledcell{\x}{\y}{minusColor}}}
    \removedcell{3}{9}
    \draw[dashed,thick,gray] (0,{6*\cs}) -- ({4*\cs},{6*\cs});
    \node[right=2pt] at ({4*\cs},{3*\cs}) {\small $(3k{+}1)\times 3(j{-}1)$};
    \node[right=2pt] at ({4*\cs},{7.5*\cs}) {\small $R^{-}(4,4)$};
  \end{tikzpicture}\end{center}""",

"tileable_rectangleMinus2Corner_3jplus2_3kplus1": r"""
  Decompose $R^{--}(3j{+}2,3k{+}1)$ into $R^{-}(3j{+}2,2)$ at the bottom,
  a $(3j)\times(3k{-}1)$ full rectangle at the top-left, and an L-tromino at the top-right.
  Example $j=1,k=1$: $R^{--}(5,4)$.
  \begin{center}\begin{tikzpicture}
    \drawgrid{5}{4}
    \foreach \x in {0,1,2,3}{\foreach \y in {0,1}{\filledcell{\x}{\y}{pieceAcolor}}}
    \filledcell{4}{0}{pieceAcolor}
    \foreach \x in {0,1,2}{\filledcell{\x}{2}{yellow!70}\filledcell{\x}{3}{yellow!70}}
    \filledcell{4}{1}{pieceBcolor}
    \filledcell{3}{2}{pieceBcolor}\filledcell{4}{2}{pieceBcolor}
    \removedcell{3}{3}\removedcell{4}{3}
    \draw[green!50!black,ultra thick]
      (0,0) -- ({4*\cs},0) -- ({4*\cs},\cs) -- ({5*\cs},\cs) -- ({5*\cs},{2*\cs})
      -- (0,{2*\cs}) -- cycle;
    \draw[yellow!70!black,ultra thick] (0,{2*\cs}) rectangle ({3*\cs},{4*\cs});
    \draw[red!60!black,ultra thick]
      ({4*\cs},\cs) -- ({5*\cs},\cs) -- ({5*\cs},{3*\cs}) -- ({4*\cs},{3*\cs})
      -- ({4*\cs},{2*\cs}) -- ({3*\cs},{2*\cs}) -- ({3*\cs},{3*\cs});
    \draw[red!60!black,ultra thick] ({3*\cs},{2*\cs}) -- ({4*\cs},{2*\cs});
    \node[below=2pt] at ({2*\cs},0) {\tiny Part~1: $R^{-}(5,2)$};
    \node[right=2pt] at ({5*\cs},{3*\cs}) {\tiny Part~3: tromino};
  \end{tikzpicture}\end{center}""",

"tileable_rectangleMinus2Corner_4_3kplus2": r"""
  Peel off an L-tromino at the top-left; remainder is a rotated $R^{-}(4,3k{+}1)$.
  Example $k=2$: $R^{--}(4,8)$.
  \begin{center}\begin{tikzpicture}
    \drawgrid{4}{8}
    \foreach \x in {0,1,2,3}{\foreach \y in {0,1,2,3,4,5}{\filledcell{\x}{\y}{piece2color}}}
    \filledcell{1}{6}{piece2color}\filledcell{2}{6}{piece2color}\filledcell{3}{6}{piece2color}
    \filledcell{0}{6}{piece1color}\filledcell{0}{7}{piece1color}\filledcell{1}{7}{piece1color}
    \removedcell{2}{7}\removedcell{3}{7}
    \draw[blue!70!black,ultra thick]
      (0,{6*\cs}) -- (\cs,{6*\cs}) -- (\cs,{7*\cs}) -- (0,{7*\cs}) -- cycle;
    \draw[blue!70!black,ultra thick]
      (0,{7*\cs}) -- ({2*\cs},{7*\cs}) -- ({2*\cs},{8*\cs}) -- (0,{8*\cs}) -- cycle;
    \draw[orange!80!black,ultra thick] (0,0) rectangle ({4*\cs},{6*\cs});
    \draw[orange!80!black,ultra thick] (\cs,{6*\cs}) rectangle ({4*\cs},{7*\cs});
    \node[left=2pt] at (0,{3*\cs}) {\tiny piece2: rot.\ $R^{-}(4,7)$};
    \node[left=2pt] at (0,{7.5*\cs}) {\tiny piece1: tromino};
  \end{tikzpicture}\end{center}""",

"tileable_rectangleMinus2Corner_3jplus1_3kplus2": r"""
  Three sub-cases for $R^{--}(3j{+}1,3k{+}2)$:

  \smallskip\noindent\textbf{(a) $j\ge 3$:} left strip $3(j{-}1)\times(3k{+}2)$ + right $R^{--}(4,3k{+}2)$.
  Example $j=3,k=1$: $R^{--}(10,5)$.
  \begin{center}\begin{tikzpicture}
    \drawgrid{10}{5}
    \foreach \x in {0,1,2,3,4,5}{\foreach \y in {0,1,2,3,4}{\filledcell{\x}{\y}{yellow!70}}}
    \foreach \x in {6,7,8,9}{\foreach \y in {0,1,2,3,4}{\filledcell{\x}{\y}{minusColor}}}
    \removedcell{8}{4}\removedcell{9}{4}
    \draw[dashed,thick,gray] ({6*\cs},0) -- ({6*\cs},{5*\cs});
    \node at ({3*\cs},{2.5*\cs}) {\small $3(j{-}1)\times(3k{+}2)$};
    \node at ({8*\cs},{2*\cs}) {\small $R^{--}(4,5)$};
  \end{tikzpicture}\end{center}

  \smallskip\noindent\textbf{(b) $j=2$, $k$ even:} left strip $3\times(3k{+}2)$ + right $R^{--}(4,3k{+}2)$.
  Example $j=2,k=2$: $R^{--}(7,8)$.
  \begin{center}\begin{tikzpicture}
    \drawgrid{7}{8}
    \foreach \x in {0,1,2}{\foreach \y in {0,1,2,3,4,5,6,7}{\filledcell{\x}{\y}{yellow!70}}}
    \foreach \x in {3,4,5,6}{\foreach \y in {0,1,2,3,4,5,6,7}{\filledcell{\x}{\y}{minusColor}}}
    \removedcell{5}{7}\removedcell{6}{7}
    \draw[dashed,thick,gray] ({3*\cs},0) -- ({3*\cs},{8*\cs});
    \node at ({1.5*\cs},{4*\cs}) {\small $3\times(3k{+}2)$};
    \node at ({5*\cs},{3.5*\cs}) {\small $R^{--}(4,8)$};
  \end{tikzpicture}\end{center}

  \smallskip\noindent\textbf{(c) $j=2$, $k$ odd:} pieces A ($\cong R^{--}(5,4)$), B (L-tromino), C ($3\times4$ rect).
  Example $j=2,k=1$: $R^{--}(7,5)$.
  \begin{center}\begin{tikzpicture}
    \drawgrid{7}{5}
    \foreach \x in {0,1,2,3}{\foreach \y in {0,1,2}{\filledcell{\x}{\y}{pieceAcolor}}}
    \foreach \x in {0,1,2}{\filledcell{\x}{3}{pieceAcolor}\filledcell{\x}{4}{pieceAcolor}}
    \filledcell{3}{3}{pieceBcolor}\filledcell{3}{4}{pieceBcolor}\filledcell{4}{4}{pieceBcolor}
    \foreach \x in {4,5,6}{\foreach \y in {0,1,2,3}{\filledcell{\x}{\y}{pieceCcolor}}}
    \removedcell{5}{4}\removedcell{6}{4}
    \draw[green!50!black,ultra thick] (0,0) rectangle ({4*\cs},{3*\cs});
    \draw[green!50!black,ultra thick] (0,{3*\cs}) rectangle ({3*\cs},{5*\cs});
    \draw[red!60!black,ultra thick]
      ({3*\cs},{3*\cs}) -- ({4*\cs},{3*\cs}) -- ({4*\cs},{4*\cs}) -- ({5*\cs},{4*\cs})
      -- ({5*\cs},{5*\cs}) -- ({3*\cs},{5*\cs}) -- cycle;
    \draw[purple!60!black,ultra thick] ({4*\cs},0) rectangle ({7*\cs},{4*\cs});
    \node at ({1.5*\cs},{1.5*\cs}) {\small A};
    \node at ({3.7*\cs},{4.2*\cs}) {\small B};
    \node at ({5.5*\cs},{2*\cs}) {\small C};
  \end{tikzpicture}\end{center}""",

}  # end FIGURE_INJECTIONS

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
        # Inject TikZ figure if one is registered for this declaration
        if name in FIGURE_INJECTIONS:
            lines.append(FIGURE_INJECTIONS[name])
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
