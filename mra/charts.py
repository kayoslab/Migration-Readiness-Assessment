"""Report charts: static SVG, print-first, restrained corporate styling.

Colour jobs (never mixed): status = RED/AMBER/GREEN thresholds only (always with a text label),
diverging = disagree <-> agree around a grey neutral, sequential = one blue hue for counts.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

INK = "#1f2933"
INK_MUTED = "#6b7280"
RULE = "#d9dce1"
SURFACE = "#ffffff"
ACCENT = "#0b2545"

STATUS = {"RED": "#d03b3b", "AMBER": "#fab219", "GREEN": "#0ca30c"}
STATUS_TINT = {"RED": "#fbeaea", "AMBER": "#fef6e4", "GREEN": "#e8f5e8"}
LIKERT = ["#b8322f", "#ec9a8f", "#d9d8d4", "#86b6ef", "#256abf"]   # SD, D, N, A, SA
LIKERT_LABELS = ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"]
DIVERGING = LinearSegmentedColormap.from_list("mra_div", ["#b8322f", "#ec9a8f", "#f0efec", "#86b6ef", "#1c5cab"])
SEQUENTIAL = LinearSegmentedColormap.from_list("mra_seq", ["#f3f7fd", "#9ec5f4", "#3987e5", "#104281"])

WIDTH = 6.3  # inches, A4 text width with generous margins


def apply_style() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Source Sans 3", "Inter", "Helvetica Neue", "Arial", "DejaVu Sans"],
        "font.size": 8.5,
        "text.color": INK, "axes.labelcolor": INK_MUTED, "axes.edgecolor": RULE,
        "xtick.color": INK_MUTED, "ytick.color": INK, "axes.titlesize": 9,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": False, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "svg.fonttype": "path", "legend.frameon": False,
    })


def _save(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    return path


def _wrap(text: str, width: int) -> str:
    return "\n".join(textwrap.wrap(text, width)) or text


def domain_index_chart(summary: pd.DataFrame, rules, path: Path) -> Path:
    """Role-weighted index per domain with 95% interval against the agreed thresholds."""
    apply_style()
    data = summary.dropna(subset=["index"]).sort_values("index")
    fig, ax = plt.subplots(figsize=(WIDTH, 0.42 * len(data) + 0.8))
    lo, hi = 1.0, 5.0
    bands = [("RED", lo, rules.red_below), ("AMBER", rules.red_below, rules.green_from), ("GREEN", rules.green_from, hi)]
    for status, a, b in bands:
        ax.axvspan(a, b, color=STATUS_TINT[status], zorder=0, lw=0)
        ax.text((a + b) / 2, len(data) - 0.35, status.title(), ha="center", va="bottom",
                fontsize=7.5, color=INK_MUTED)
    y = np.arange(len(data))
    ax.hlines(y, data["ci_low"], data["ci_high"], color=ACCENT, lw=2, zorder=2, capstyle="round")
    ax.scatter(data["index"], y, s=46, color=ACCENT, edgecolor=SURFACE, linewidth=1.5, zorder=3)
    for yi, (_, row) in zip(y, data.iterrows()):
        flag = " (uncertain)" if row["uncertain"] else ""
        ax.text(hi + 0.08, yi, f"{row['index']:.2f}  {row['status']}{flag}", va="center", fontsize=8,
                color=INK, fontweight="bold" if row["status"] == "RED" else "normal")
    ax.set_yticks(y, [_wrap(g, 30) for g in data.index])
    ax.set_xlim(lo, hi)
    ax.set_ylim(-0.6, len(data) - 0.1)
    ax.set_xticks([1, 2, 3, 4, 5], ["1\nStrongly\ndisagree", "2", "3\nNeutral", "4", "5\nStrongly\nagree"])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Role-weighted index with 95% bootstrap interval")
    return _save(fig, path)


def role_heatmap(result, rules, path: Path) -> Path:
    """Role x domain scores. Cells that do not count towards the index are hatched and labelled."""
    apply_style()
    raw = result.role_raw_mean.T
    scored = result.role_mean.T
    n, items = result.role_n.T, result.role_items.T
    fig, ax = plt.subplots(figsize=(WIDTH, 0.5 * len(raw) + 0.9))
    ax.imshow(scored.to_numpy(dtype=float), cmap=DIVERGING, vmin=1, vmax=5, aspect="auto")
    for i, g in enumerate(raw.index):
        for j, r in enumerate(raw.columns):
            value, ok = raw.at[g, r], not np.isnan(scored.at[g, r])
            if items.at[g, r] == 0:
                ax.text(j, i, "not asked", ha="center", va="center", fontsize=7, color=INK_MUTED)
                continue
            if not ok:
                ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, hatch="////",
                                           edgecolor=RULE, lw=0))
                reason = f"{items.at[g, r]} item" + ("s" if items.at[g, r] != 1 else "") \
                    if items.at[g, r] < rules.min_role_items else f"n={n.at[g, r]}"
                ax.text(j, i, f"{value:.1f}\n({reason})", ha="center", va="center", fontsize=7,
                        color=INK_MUTED, style="italic")
                continue
            dark = value < 1.8 or value > 4.2
            ax.text(j, i, f"{value:.1f}", ha="center", va="center", fontsize=9, fontweight="bold",
                    color=SURFACE if dark else INK)
    ax.set_xticks(range(len(raw.columns)), [f"{r}\n(n={int(result.role_n.loc[r].max())})" for r in raw.columns])
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(raw.index)), [_wrap(g, 30) for g in raw.index])
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-0.5, len(raw.columns)), minor=True)
    ax.set_yticks(np.arange(-0.5, len(raw.index)), minor=True)
    ax.grid(which="minor", color=SURFACE, lw=2)
    ax.tick_params(which="minor", length=0)
    return _save(fig, path)


def likert_chart(items: pd.DataFrame, path: Path, wrap: int = 62) -> Path:
    """Diverging stacked bars: disagreement left of zero, agreement right, neutral split in the middle."""
    apply_style()
    data = items.iloc[::-1]
    counts = data[[f"n_{k}" for k in range(1, 6)]].to_numpy(dtype=float)
    share = counts / counts.sum(1, keepdims=True)
    left = -(share[:, 0] + share[:, 1] + share[:, 2] / 2)
    fig, ax = plt.subplots(figsize=(WIDTH, 0.4 * len(data) + 0.9))
    y = np.arange(len(data))
    for k in range(5):
        ax.barh(y, share[:, k], left=left, color=LIKERT[k], height=0.62, edgecolor=SURFACE, lw=1,
                label=LIKERT_LABELS[k])
        left = left + share[:, k]
    ax.axvline(0, color=INK_MUTED, lw=0.8)
    labels = [_wrap(f"{q}", wrap) for q in data["question"]]
    ax.set_yticks(y, labels, fontsize=7.5)
    for yi, (_, row) in zip(y, data.iterrows()):
        ax.text(1.02, yi, f"{row['score']:.1f}", va="center", fontsize=8, transform=ax.get_yaxis_transform())
    ax.text(1.02, len(data) - 0.3, "Score", fontsize=7, color=INK_MUTED, transform=ax.get_yaxis_transform())
    ax.set_xlim(-1, 1)
    ax.set_xticks([-1, -0.5, 0, 0.5, 1], ["100%", "50%", "0", "50%", "100%"])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.legend(ncol=5, loc="lower center", bbox_to_anchor=(0.35, 1.0), fontsize=7, handlelength=1, columnspacing=1)
    return _save(fig, path)


def stance_chart(by_role: pd.DataFrame, path: Path) -> Path:
    """Share of coded answers per stance, per role (LLM analysis)."""
    apply_style()
    order = [("opposes_change", "Opposes change", LIKERT[0]), ("mixed", "Mixed", LIKERT[1]),
             ("neutral", "No stance", LIKERT[2]), ("supports_change", "Supports change", LIKERT[4])]
    data = by_role.iloc[::-1]
    fig, ax = plt.subplots(figsize=(WIDTH, 0.42 * len(data) + 0.8))
    left = np.zeros(len(data))
    y = np.arange(len(data))
    for key, label, color in order:
        values = data[key].to_numpy() if key in data else np.zeros(len(data))
        ax.barh(y, values, left=left, color=color, height=0.6, edgecolor=SURFACE, lw=1, label=label)
        left += values
    ax.set_yticks(y, [f"{r} (n={int(n)})" for r, n in zip(data.index, data["n"])])
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1], ["0%", "25%", "50%", "75%", "100%"])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.legend(ncol=4, loc="lower center", bbox_to_anchor=(0.45, 1.0), fontsize=7, handlelength=1)
    return _save(fig, path)


def theme_heatmap(theme_share: pd.DataFrame, path: Path, top: int = 10) -> Path:
    """Share of each group's answers that mention a theme."""
    apply_style()
    data = theme_share.head(top)
    fig, ax = plt.subplots(figsize=(WIDTH, 0.36 * len(data) + 0.8))
    ax.imshow(data.to_numpy(dtype=float), cmap=SEQUENTIAL, aspect="auto")
    vmax = max(data.to_numpy().max(), 0.01)
    for i in range(len(data)):
        for j in range(data.shape[1]):
            v = data.iat[i, j]
            ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=8,
                    color=SURFACE if v > 0.6 * vmax else INK)
    ax.set_xticks(range(data.shape[1]), data.columns)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(data)), data.index)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    return _save(fig, path)
