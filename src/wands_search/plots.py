"""Shared chart style and helpers for notebooks and reports.

Charts may be read outside the notebook, so each one must explain itself: its title
says what is measured and on which data, and a caption defines any technical term.
"""

import textwrap

import seaborn as sns
from matplotlib.axes import Axes
from matplotlib.figure import Figure

SURFACE = "#fcfcfb"
PRIMARY_INK = "#0b0b0b"
SECONDARY_INK = "#52514e"
MUTED_INK = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
SERIES_1 = "#2a78d6"
SERIES_2 = "#eb6834"

TOKEN_DEFINITION = (
    "Token: a word from the text, computed by removing accents, lowercasing and splitting on "
    "anything that is not a letter or digit. Repeated words count once. "
    'Example: \'Fawkes 36" Blue-Vanity\' gives the tokens fawkes, 36, blue and vanity.'
)


def apply_style() -> None:
    """Set the seaborn theme. The explicit surface keeps charts readable on dark editors."""
    sns.set_theme(
        style="whitegrid",
        rc={
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "figure.dpi": 110,
            "font.size": 10,
            "text.color": PRIMARY_INK,
            "axes.edgecolor": BASELINE,
            "axes.labelcolor": SECONDARY_INK,
            "axes.titlesize": 11,
            "axes.titlelocation": "left",
            "axes.titlecolor": PRIMARY_INK,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.axisbelow": True,
            "grid.color": GRIDLINE,
            "grid.linewidth": 0.8,
            "xtick.color": MUTED_INK,
            "ytick.color": MUTED_INK,
            "xtick.labelcolor": SECONDARY_INK,
            "ytick.labelcolor": SECONDARY_INK,
            "xtick.bottom": True,
            "legend.frameon": False,
        },
    )


def add_caption(fig: Figure, text: str, width: int = 120) -> None:
    """Add an explanatory note below the figure, wrapped to ``width`` characters."""
    fig.text(0.01, -0.01, textwrap.fill(text, width), va="top", ha="left", color=SECONDARY_INK, fontsize=9)


def reference_line(ax: Axes, x: float, label: str, y_fraction: float = 0.93, ha: str = "left") -> None:
    """Draw a labeled vertical reference line."""
    ax.axvline(x, color=PRIMARY_INK, linewidth=1.2)
    offset = 6 if ha == "left" else -6
    ax.annotate(label, xy=(x, y_fraction), xycoords=("data", "axes fraction"), xytext=(offset, 0),
                textcoords="offset points", ha=ha, color=PRIMARY_INK, fontsize=9)
