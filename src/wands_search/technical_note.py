"""Figures and PDF of the technical note (docs/nota_tecnica/).

The figures use the numbers registered in docs/EVALUATION.md (results history, reranker ablations,
latency) and in the error analysis of the validation set. They are copied here instead of being
recomputed, because the test set is run only once: recomputing it to draw a chart would be a second
run. Every constant names its source.

The note is written in Portuguese, so the text inside its figures is in Portuguese too (the exception
to the English rule of CONTRIBUTING.md). Figures are SVG with the text kept as text, drawn at the
width of one column of the PDF, so that they print sharp and with the font of the document.

Run ``uv run python -m wands_search.technical_note`` to redraw the figures and, when Google Chrome
is installed, print ``nota_tecnica.md`` to ``nota_tecnica.pdf``.
"""

import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import mistune  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from wands_search import plots  # noqa: E402

NOTE_DIR = Path(__file__).resolve().parents[2] / "docs" / "nota_tecnica"
FIGURE_WIDTH = 3.37  # inches: one column of the two-column A4 page (85.5 mm)
FIGURE_FORMAT = "svg"

# Colors of the default palette of plots.py, plus a white page surface (the PDF is white).
PAGE = "#ffffff"
BLUE, ORANGE = plots.SERIES_1, plots.SERIES_2
GREY, LIGHT_GREY = plots.MUTED_INK, plots.BASELINE
INK, SECONDARY = plots.PRIMARY_INK, plots.SECONDARY_INK
GRID = "#ebeae4"

NOTE_STYLE = {
    "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 7, "axes.titlesize": 7.6, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.titlepad": 6, "axes.labelsize": 6.8, "axes.labelcolor": SECONDARY,
    "xtick.labelsize": 6.6, "ytick.labelsize": 7.2, "xtick.color": GREY, "ytick.color": INK,
    "xtick.labelcolor": SECONDARY, "ytick.labelcolor": INK, "legend.fontsize": 6.8,
    "figure.facecolor": PAGE, "axes.facecolor": PAGE, "savefig.facecolor": PAGE,
    "svg.fonttype": "none", "axes.edgecolor": LIGHT_GREY, "axes.linewidth": 0.6,
    "grid.color": GRID, "grid.linewidth": 0.6, "xtick.major.width": 0.6, "xtick.major.size": 2.5,
    "ytick.major.size": 0, "legend.frameon": False, "legend.handletextpad": 0.4, "legend.columnspacing": 1.2,
}

# docs/EVALUATION.md, "Histórico de resultados": NDCG@10 (mean, 95% bootstrap interval).
# Validation of the selected system: final table of the reranker notebook, cited in EVALUATION.md.
SELECTED = "hybrid + reranker (escolhido)"
NDCG_AT_10 = {
    "BM25 (baseline)": {"validation": (0.620, 0.555, 0.687), "test": (0.717, 0.656, 0.769)},
    "semantic search": {"validation": (0.725, 0.668, 0.785), "test": (0.747, 0.691, 0.799)},
    "hybrid search": {"validation": (0.747, 0.690, 0.805), "test": (0.783, 0.724, 0.835)},
    "BM25 v2 + reranker": {"validation": (0.744, 0.682, 0.802), "test": (0.813, 0.758, 0.861)},
    "hybrid + reranker + cross-encoder": {"validation": (0.772, 0.720, 0.827), "test": (0.821, 0.770, 0.867)},
    SELECTED: {"validation": (0.776, 0.723, 0.831), "test": (0.824, 0.773, 0.870)},
}

# docs/EVALUATION.md, "Histórico de resultados": Capped Recall@100, Exact only (77 validation and
# 75 test queries with Exact). The rerankers keep the top 100 of their retrieval, so they have its value.
CAPPED_RECALL_AT_100 = {
    "BM25 (baseline)": {"validation": (0.702, 0.626, 0.778), "test": (0.703, 0.629, 0.773)},
    "BM25 v2": {"validation": (0.705, 0.628, 0.778), "test": (0.736, 0.666, 0.798)},
    "semantic search": {"validation": (0.678, 0.601, 0.751), "test": (0.712, 0.644, 0.778)},
    "hybrid search": {"validation": (0.714, 0.640, 0.784), "test": (0.760, 0.695, 0.820)},
}

# docs/EVALUATION.md, "Histórico de resultados", test set run (ms, p50 and p95), one CPU.
LATENCY_MS = {
    "BM25 (baseline)": {"retrieval": (0.9, 3.6), "ranking": (0.0, 0.0)},
    "hybrid search": {"retrieval": (9.0, 11.7), "ranking": (0.0, 0.0)},
    SELECTED: {"retrieval": (9.0, 11.7), "ranking": (27.1, 32.1)},
    "hybrid + reranker + cross-encoder": {"retrieval": (9.0, 11.7), "ranking": (376.8, 487.7)},
}
MACHINE = "laptop com Intel Core i9-9980HK, sem GPU"

# notebooks/07_error_analysis.ipynb (validation set, 97 queries): mean NDCG@10 of each level.
LOSS_LADDER = {
    "ordem perfeita": 1.0,
    "melhor ordem dos 100 candidatos": 0.933,
    "sistema escolhido": 0.776,
    "hybrid search sem reranker": 0.747,
}


def decimal_comma(digits: int) -> FuncFormatter:
    """Tick labels with a decimal comma, as in Portuguese."""
    return FuncFormatter(lambda value, _: f"{value:.{digits}f}".replace(".", ","))


def comma(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _clean_axes(ax: Axes) -> None:
    """Hairline vertical grid, a bottom baseline and no other frame."""
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    ax.set_axisbelow(True)


def _align_titles(fig: Figure, pads: dict | None = None) -> None:
    """Redraw every panel title from the left edge of the figure (by default it starts after the tick labels).

    Call it after ``tight_layout``: the title set with ``set_title`` reserves the space, and is then
    replaced by a text at the same height that starts at the left edge. ``pads`` gives the title pad
    (points) of the axes that do not use the default one.
    """
    pads = pads or {}
    for ax in fig.axes:
        title = ax.get_title(loc="left")
        if not title:
            continue
        pad = pads.get(ax, NOTE_STYLE["axes.titlepad"])
        label = ax.set_title(title, loc="left", pad=pad)
        y = label.get_position()[1]
        offset = label.get_transform()
        ax.set_title("", loc="left", pad=pad)
        ax.text(_left_edge(ax), y, title, transform=offset, ha="left", va="baseline",
                fontsize=NOTE_STYLE["axes.titlesize"], fontweight="bold", color=INK)


def _left_edge(ax: Axes) -> float:
    """The left edge of the figure in the axes coordinates of ``ax``."""
    box = ax.get_position()
    return -box.x0 / box.width


def _note(fig: Figure, text: str, width: int = 82) -> None:
    """The explanation under the chart, in the secondary ink."""
    fig.text(0.0, 0.0, textwrap.fill(text, width), va="top", ha="left", color=SECONDARY, fontsize=6.2,
             linespacing=1.35, transform=fig.transFigure)


def _save(fig: Figure, path: Path) -> None:
    fig.savefig(path, format=FIGURE_FORMAT, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


def _mean_bars(ax: Axes, results: dict, highlight: str | None = None) -> None:
    """One pair of bars per system: the validation and test set means, each labeled with its value."""
    names = list(results)
    positions = list(range(len(names)))[::-1]
    for position, name in zip(positions, names):
        for split, color, offset in (("validation", BLUE, 0.19), ("test", ORANGE, -0.19)):
            mean = results[name][split][0]
            ax.barh(position + offset, mean, height=0.36, color=color, edgecolor=PAGE, linewidth=0.6)
            ax.annotate(comma(mean), xy=(mean, position + offset), xytext=(2.5, 0), textcoords="offset points",
                        va="center", fontsize=6.2, color=INK,
                        fontweight="bold" if name == highlight else "normal")
    ax.set_yticks(positions, names)
    if highlight in names:
        ax.get_yticklabels()[names.index(highlight)].set_fontweight("bold")
    ax.set_ylim(-0.6, len(names) - 0.4)
    ax.set_xlim(0, 1.0)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.xaxis.set_major_formatter(decimal_comma(1))
    _clean_axes(ax)


def quality_figure(path: Path) -> None:
    """Mean NDCG@10 of every system and mean Capped Recall@100 of every retrieval, validation and test set."""
    fig, axes = plt.subplots(2, 1, figsize=(FIGURE_WIDTH, 4.0), height_ratios=[6, 4])
    _mean_bars(axes[0], NDCG_AT_10, highlight=SELECTED)
    axes[0].set_title("Qualidade da ordem: NDCG@10 de cada sistema")
    axes[0].set_xlabel("NDCG@10 médio (0 a 1, maior é melhor)")
    _mean_bars(axes[1], CAPPED_RECALL_AT_100)
    axes[1].set_title("Cobertura do retrieval: Capped Recall@100")
    axes[1].set_xlabel("Capped Recall@100 médio (0 a 1, maior é melhor)")
    handles = [Patch(color=BLUE, label="validation set (97 queries)"),
               Patch(color=ORANGE, label="test set (95 queries)")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.0, 1.05), ncol=2, borderaxespad=0)
    fig.tight_layout(h_pad=1.6)
    _align_titles(fig)
    _note(fig, "O validation set escolheu o sistema; o test set rodou uma única vez, depois da escolha. "
               "Capped Recall@100: fração dos produtos Exact que chegam aos 100 candidatos (só queries com "
               "algum Exact: 77 e 75). Um reranker tem a cobertura do seu retrieval.")
    _save(fig, path)


def latency_figure(path: Path) -> None:
    """Median latency of one search, split into retrieval and ranking."""
    fig, ax = plt.subplots(figsize=(FIGURE_WIDTH, 1.55))
    names = list(LATENCY_MS)
    positions = list(range(len(names)))[::-1]
    for position, name in zip(positions, names):
        retrieval_p50 = LATENCY_MS[name]["retrieval"][0]
        ranking_p50 = LATENCY_MS[name]["ranking"][0]
        ax.barh(position, retrieval_p50, color=BLUE, height=0.56)
        if ranking_p50:
            ax.barh(position, ranking_p50, left=retrieval_p50, color=ORANGE, height=0.56,
                    edgecolor=PAGE, linewidth=0.8)
        total = retrieval_p50 + ranking_p50
        ax.annotate(f"{comma(total, 1 if total < 10 else 0)} ms", xy=(total, position), xytext=(3, 0),
                    textcoords="offset points", va="center", fontsize=6.6, color=INK)
    ax.set_yticks(positions, names)
    ax.get_yticklabels()[names.index(SELECTED)].set_fontweight("bold")
    ax.set_xlim(0, 430)
    ax.set_ylim(-0.6, len(names) - 0.4)
    ax.set_xlabel("Tempo mediano (p50) de uma busca, em ms")
    ax.set_title("Latência de uma busca")
    _clean_axes(ax)
    handles = [Patch(color=BLUE, label="retrieval"), Patch(color=ORANGE, label="ranking")]
    ax.legend(handles=handles, loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2, borderaxespad=0.3)
    fig.tight_layout()
    _align_titles(fig)
    p95 = "; ".join(f"{name}, {comma(values['retrieval'][1], 1)}"
                    + (f" + {comma(values['ranking'][1], 1)}" if values["ranking"][1] else "") + " ms"
                    for name, values in LATENCY_MS.items())
    _note(fig, f"Execução do test set (95 queries), {MACHINE}, um processo. p95 (95% das buscas levam até), "
               f"retrieval + ranking: {p95}.")
    _save(fig, path)


def error_analysis_figure(path: Path) -> None:
    """Where the NDCG@10 loss of the selected system comes from: retrieval or ranking, validation set."""
    fig, ax = plt.subplots(figsize=(FIGURE_WIDTH, 1.55))
    ladder = list(LOSS_LADDER)
    positions = list(range(len(ladder)))[::-1]
    colors = [LIGHT_GREY, BLUE, ORANGE, GREY]
    ax.barh(positions, list(LOSS_LADDER.values()), color=colors, height=0.56)
    for position, value in zip(positions, LOSS_LADDER.values()):
        ax.annotate(comma(value), xy=(value, position), xytext=(3, 0), textcoords="offset points",
                    va="center", fontsize=6.6, color=INK)
    ax.set_yticks(positions, ladder)
    ax.set_xlim(0, 1.12)
    ax.set_ylim(-0.6, len(ladder) - 0.4)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.xaxis.set_major_formatter(decimal_comma(1))
    ax.set_xlabel("NDCG@10 médio")
    ax.set_title("Retrieval perde 0,067; ranking perde 0,156")
    _clean_axes(ax)
    fig.tight_layout()
    _align_titles(fig)
    _note(fig, "97 queries do validation set. Melhor ordem dos 100 candidatos: os candidatos da hybrid search "
               "ordenados pelo label (Exact primeiro), o teto de qualquer reranker.")
    _save(fig, path)


FIGURES = {
    f"quality.{FIGURE_FORMAT}": quality_figure,
    f"latency.{FIGURE_FORMAT}": latency_figure,
    f"error_analysis.{FIGURE_FORMAT}": error_analysis_figure,
}


def build_figures(figure_dir: Path) -> list[Path]:
    """Draw every figure of the note into ``figure_dir`` and return their paths."""
    figure_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    with plt.rc_context(NOTE_STYLE):
        for name, draw in FIGURES.items():
            draw(figure_dir / name)
            paths.append(figure_dir / name)
    return paths


def markdown_to_html(markdown_text: str, css: str, title: str) -> str:
    """A standalone HTML page from the Markdown of the note (raw HTML blocks are kept)."""
    body = mistune.create_markdown(escape=False, plugins=["table"])(markdown_text)
    return (f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>{title}</title>"
            f"<style>{css}</style></head><body>{body}</body></html>")


CHROME_CANDIDATES = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "chromium", "chromium-browser",
)


def find_chrome() -> str | None:
    for candidate in CHROME_CANDIDATES:
        if Path(candidate).exists() or shutil.which(candidate):
            return candidate
    return None


def render_pdf(note_dir: Path = NOTE_DIR) -> Path | None:
    """Print ``nota_tecnica.md`` to ``nota_tecnica.pdf`` with headless Chrome; None without Chrome."""
    chrome = find_chrome()
    if chrome is None:
        return None
    html_text = markdown_to_html((note_dir / "nota_tecnica.md").read_text(), (note_dir / "style.css").read_text(),
                                 "Nota técnica")
    pdf_path = note_dir / "nota_tecnica.pdf"
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=note_dir, delete=False) as page:
        page.write(html_text)
    try:
        subprocess.run([chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={pdf_path}", Path(page.name).as_uri()],
                       check=True, capture_output=True, timeout=120)
    finally:
        Path(page.name).unlink()
    return pdf_path


def main() -> None:
    for path in build_figures(NOTE_DIR / "figures"):
        print("figure:", path.relative_to(NOTE_DIR.parents[1]))
    pdf_path = render_pdf()
    print("pdf:", pdf_path.relative_to(NOTE_DIR.parents[1]) if pdf_path else "Google Chrome not found, PDF not built")


if __name__ == "__main__":
    main()
