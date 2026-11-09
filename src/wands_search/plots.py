"""Shared chart and table style and helpers for notebooks and reports.

Charts and tables may be read outside the notebook, so each one must explain itself: its
title says what is measured and on which data, and a note defines any technical term.
"""

import html
import textwrap

import pandas as pd

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
# Third categorical slot. Below 3:1 contrast on SURFACE (2.74:1), so it is always paired with
# a distinct marker shape and a table of the same values.
SERIES_3 = "#1baf7a"
SERIES_COLORS = (SERIES_1, SERIES_2, SERIES_3)
SERIES_MARKERS = ("o", "s", "D")

TOKEN_DEFINITION = (
    "Token: a word from the text, computed by removing accents, lowercasing and splitting on "
    "anything that is not a letter or digit. Repeated words count once. "
    'Example: \'Fawkes 36" Blue-Vanity\' gives the tokens fawkes, 36, blue and vanity.'
)

WORDPIECE_DEFINITION = (
    "Wordpiece: a piece of text from the tokenizer of the embedding model (bge-small-en-v1.5), "
    "which splits rare words into known pieces and adds two special pieces to every input. "
    "Example: 'Fawkes 36\" Blue-Vanity' gives [CLS], fa, ##wk, ##es, 36, \", blue, -, vanity and [SEP] "
    "(10 wordpieces). The model reads at most 512 wordpieces."
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


def difference_plot(ax: Axes, labels: list[str], differences, lows, highs) -> None:
    """Horizontal points with 95% intervals for paired differences, with a reference line at 0.

    Intervals that exclude 0 are drawn in the primary series color; the others in a muted color.
    """
    positions = list(range(len(labels)))[::-1]
    for position, difference, low, high in zip(positions, differences, lows, highs):
        color = SERIES_1 if (low > 0 or high < 0) else MUTED_INK
        ax.plot([low, high], [position, position], color=color, linewidth=2)
        ax.plot([difference], [position], "o", color=color, markersize=6)
    ax.axvline(0, color=PRIMARY_INK, linewidth=1)
    ax.set_yticks(positions, labels)
    ax.grid(axis="y", visible=False)


def interval_dot_plot(ax: Axes, labels: list[str], systems: dict[str, tuple]) -> None:
    """One row per label and, in each row, one point with its 95% interval per system.

    ``systems`` maps a system name to ``(means, lows, highs)``, each aligned with ``labels``.
    Systems keep the fixed order of ``SERIES_COLORS`` and ``SERIES_MARKERS`` (color and shape),
    are offset vertically inside each row, and are named in the legend. The first label is
    drawn at the top.
    """
    if len(systems) > len(SERIES_COLORS):
        raise ValueError(f"at most {len(SERIES_COLORS)} systems")
    positions = list(range(len(labels)))[::-1]
    offsets = [0.0] if len(systems) == 1 else [0.25 - 0.5 * i / (len(systems) - 1) for i in range(len(systems))]
    for (name, (means, lows, highs)), color, marker, offset in zip(systems.items(), SERIES_COLORS, SERIES_MARKERS, offsets):
        for position, low, high in zip(positions, lows, highs):
            ax.plot([low, high], [position + offset] * 2, color=color, linewidth=2, solid_capstyle="round")
        ax.plot(list(means), [position + offset for position in positions], linestyle="none", marker=marker,
                markersize=7, color=color, markeredgecolor=SURFACE, markeredgewidth=1.5, label=name)
    ax.set_yticks(positions, labels)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=len(systems), frameon=False)


def system_interval_plot(ax: Axes, names: list[str], means, lows, highs, highlight: str | None = None) -> None:
    """One row per system with its mean and 95% interval, the first name at the top.

    ``highlight`` names one system drawn in the second series color, with a square marker,
    so it stays distinct without relying on color alone.
    """
    positions = list(range(len(names)))[::-1]
    for position, name, mean, low, high in zip(positions, names, means, lows, highs):
        chosen = name == highlight
        color = SERIES_2 if chosen else SERIES_1
        ax.plot([low, high], [position, position], color=color, linewidth=2, solid_capstyle="round")
        ax.plot([mean], [position], marker="s" if chosen else "o", markersize=7, color=color,
                markeredgecolor=SURFACE, markeredgewidth=1.5, linestyle="none")
    ax.set_yticks(positions, names)
    ax.grid(axis="y", visible=False)


def table(df: pd.DataFrame | pd.Series, title: str, note: str | None = None, precision: int = 1,
          max_text_length: int = 120):
    """Return a styled table with a title and an optional note, both shown above the rows.

    Floats are rounded to ``precision`` digits, numbers use a thousands separator and texts
    longer than ``max_text_length`` characters are cut, ending in "...".
    """
    frame = df.to_frame() if isinstance(df, pd.Series) else df

    def shorten(value):
        if isinstance(value, str) and len(value) > max_text_length:
            return value[: max_text_length - 3] + "..."
        return value

    frame = frame.map(shorten)
    caption = f"<b>{html.escape(title)}</b>"
    if note:
        caption += f"<br><span style='font-size:0.85em;color:{SECONDARY_INK}'>{html.escape(note)}</span>"
    return (
        frame.style
        .format(precision=precision, thousands=",", na_rep="null")
        .set_caption(caption)
        .set_table_styles([{"selector": "caption",
                            "props": [("caption-side", "top"), ("text-align", "left"), ("padding-bottom", "6px")]}])
    )
