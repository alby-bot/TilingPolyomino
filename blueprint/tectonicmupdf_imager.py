"""
plasTeX imager: tectonic (PDF compiler) + pymupdf (PDF → PNG renderer).

Drop-in replacement for gspdfpng when pdflatex/ghostscript are unavailable.
Requires: tectonic (at ~/.local/bin/tectonic) and pymupdf (pip install pymupdf).
"""
import os
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional

from plasTeX.Imagers import Imager as _Imager

import shutil as _shutil
_TECTONIC_CANDIDATES = [
    os.path.expanduser('~/.local/bin/tectonic'),
    '/usr/local/bin/tectonic',
    '/usr/bin/tectonic',
]
TECTONIC = (
    _shutil.which('tectonic') or
    next((p for p in _TECTONIC_CANDIDATES if os.path.exists(p)), 'tectonic')
)
DPI = 144  # render at 2× screen DPI for crisp images


class TectonicMuPDF(_Imager):
    """Imager that uses tectonic to compile LaTeX and pymupdf to render PDF pages."""

    fileExtension = '.png'
    compiler = TECTONIC

    # Packages that are leanblueprint/plasTeX-specific and must NOT appear in
    # the standalone image document (tectonic won't find them).
    STRIP_PACKAGES = {
        'blueprint', 'plastexdepgraph', 'plastexshowmore',
        'hyperref', 'cleveref',
    }

    def verify(self):
        """Check that tectonic and pymupdf are both available."""
        if not os.path.exists(TECTONIC):
            return False
        try:
            import fitz  # noqa: F401
            return True
        except ImportError:
            return False

    # Regex patterns for lines we WANT to keep in the image preamble
    KEEP_PATTERNS = [
        r'\\documentclass',
        r'\\usepackage\s*(\[.*?\])?\s*\{(amsmath|amssymb|tikz|xcolor|subcaption|graphicx)\b',
        r'\\usetikzlibrary',
        r'\\newcommand',
        r'\\renewcommand',
        r'\\providecommand',
        r'\\def\\',
        r'\\definecolor',
        r'\\colorlet',
        r'\\pgfkeys',
        r'\\tikzset',
        r'%',     # comments — harmless
    ]

    # Minimal hardcoded preamble for standalone TikZ image compilation.
    # This avoids all plasTeX source-mangling issues (definecolor returns ""
    # from its source property; blueprint.sty doesn't exist for tectonic).
    TIKZ_PREAMBLE = r"""
\documentclass{article}
\usepackage{amsmath,amssymb}
\usepackage{tikz}
\usepackage{xcolor}
\usetikzlibrary{patterns,arrows.meta}
% ── polyomino cell macros ──
\newcommand{\cs}{0.50}
\newcommand{\filledcell}[3]{%
  \fill[#3] (#1*\cs,#2*\cs) rectangle ({(#1+1)*\cs},{(#2+1)*\cs});}
\newcommand{\removedcell}[2]{%
  \fill[gray!40] (#1*\cs,#2*\cs) rectangle ({(#1+1)*\cs},{(#2+1)*\cs});
  \draw[red!70!black,very thick]
    ({#1*\cs+0.05},{#2*\cs+0.05}) -- ({(#1+1)*\cs-0.05},{(#2+1)*\cs-0.05});
  \draw[red!70!black,very thick]
    ({(#1+1)*\cs-0.05},{#2*\cs+0.05}) -- ({#1*\cs+0.05},{(#2+1)*\cs-0.05});}
\newcommand{\drawgrid}[2]{%
  \draw[gray!40,thin] (0,0) grid ({#1*\cs},{#2*\cs});
  \draw[black,thick] (0,0) rectangle ({#1*\cs},{#2*\cs});}
% ── colors ──
\definecolor{tcolor1}{HTML}{8ECAE6}
\definecolor{tcolor2}{HTML}{FCA311}
\definecolor{tcolor3}{HTML}{06D6A0}
\definecolor{tcolor4}{HTML}{EF476F}
\definecolor{tcolor5}{HTML}{9B5DE5}
\definecolor{tcolor6}{HTML}{FFD166}
\definecolor{piece1color}{HTML}{8ECAE6}
\definecolor{piece2color}{HTML}{FCA311}
\definecolor{pieceAcolor}{HTML}{83C5BE}
\definecolor{pieceBcolor}{HTML}{E56B6F}
\definecolor{pieceCcolor}{HTML}{B5179E}
\definecolor{rectColor}{HTML}{FFDDA0}
\definecolor{minusColor}{HTML}{B3D8F5}
"""

    def writePreamble(self, document):
        """
        Write a minimal hardcoded TikZ preamble instead of using the plasTeX
        document preamble (which strips definecolor, includes blueprint.sty, etc.).
        Then add the standard plasTeX imager registration macros.
        """
        self.source.write(self.TIKZ_PREAMBLE)
        # plasTeX imager registration — must follow the \documentclass line
        self.source.write('\\makeatletter\\oddsidemargin -0.25in\\evensidemargin -0.25in\n')
        self.source.write(r'''
\newwrite\imager@log
\immediate\openout\imager@log=images.csv
\@ifundefined{plasTeXimage}{%
\newenvironment{plasTeXimage}[2]{%
\vfil\break\plasTeXregister%
\thispagestyle{empty}\def\@eqnnum{}\def\tagform@{\@gobble}%
\write\imager@log{\arabic{page},#1,#2}%
\ignorespaces}{}}{}
'''
        )
        self.source.write(r'''
\@ifundefined{plasTeXregister}{%
\def\plasTeXregister{\parindent=-0.5in\ifhmode\hrule%
\else\vrule\fi height 2pt depth 0pt %
width 2pt\hskip2pt}}{}
'''
        )
        # Write plasTeX's standard imager registration macros
        self.source.write('\\makeatletter\\oddsidemargin -0.25in\\evensidemargin -0.25in\n')
        self.source.write(r'''
\newwrite\imager@log
\immediate\openout\imager@log=images.csv
\@ifundefined{plasTeXimage}{%
\newenvironment{plasTeXimage}[2]{%
\vfil\break\plasTeXregister%
\thispagestyle{empty}\def\@eqnnum{}\def\tagform@{\@gobble}%
\write\imager@log{\arabic{page},#1,#2}%
\ignorespaces}{}}{}
'''
        )
        self.source.write(r'''
\@ifundefined{plasTeXregister}{%
\def\plasTeXregister{\parindent=-0.5in\ifhmode\hrule%
\else\vrule\fi height 2pt depth 0pt %
width 2pt\hskip2pt}}{}
'''
        )

    def compileLatex(self, texinputs=''):
        """Compile images.tex with tectonic."""
        env = os.environ.copy()
        env['TEXINPUTS'] = texinputs
        # tectonic is called as: tectonic <file.tex>
        # It writes <file.pdf> in the same directory.
        result = subprocess.run(
            [TECTONIC, '--outfmt', 'pdf', self.tmpFile.name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                'tectonic compilation failed:\n' + result.stdout.decode(errors='replace')
            )

    def executeConverter(self, outfile: Optional[str] = None) -> List[Tuple[str, str]]:
        """Render each PDF page to PNG using pymupdf, guided by images.csv."""
        import fitz

        if outfile is None:
            outfile = self.tmpFile.with_suffix('.pdf').name

        doc = fitz.open(outfile)
        mat = fitz.Matrix(DPI / 72, DPI / 72)  # scale from 72 dpi baseline

        images: List[Tuple[str, str]] = []
        with open('images.csv') as fh:
            for line in fh.readlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.split(',')
                page_no, dest = parts[0], parts[1]
                page_idx = int(page_no) - 1  # fitz is 0-indexed
                filename = f'img{page_no}.png'
                page = doc[page_idx]
                pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)
                pix.save(filename)
                images.append((filename, dest.rstrip()))

        doc.close()
        return images


Imager = TectonicMuPDF
