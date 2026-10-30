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
import matplotlib.patches  # noqa: E402
import matplotlib.ticker  # noqa: E402
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


# ====================================================================================== v3 decision exhibits

CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#6250d6", "#008300", "#e34948"]
NEUTRAL = "#c9cbcf"


def outcome_colours(outcome_ids: list[str]) -> dict[str, str]:
    """Fixed colour per outcome, in rule order — identity never depends on rank."""
    return {o: CATEGORICAL[i % len(CATEGORICAL)] for i, o in enumerate(outcome_ids)}


def outcome_probability_chart(distribution: dict, labels: dict, leading: str | None, confidence: float, path: Path) -> Path:
    apply_style()
    items = [(k, v) for k, v in distribution.items() if v > 0]
    items.sort(key=lambda kv: kv[1])
    fig, ax = plt.subplots(figsize=(WIDTH, 0.38 * len(items) + 0.7))
    y = np.arange(len(items))
    colours = [ACCENT if k == leading else NEUTRAL for k, _ in items]
    ax.barh(y, [v for _, v in items], color=colours, height=0.55)
    for yi, (k, v) in zip(y, items):
        ax.text(v + 0.01, yi, f"{v:.0%}", va="center", fontsize=8, color=INK)
    ax.axvline(confidence, color=INK_MUTED, lw=0.8, ls="--")
    ax.text(confidence, len(items) - 0.4, f" confidence required ({confidence:.0%})", fontsize=7, color=INK_MUTED, va="bottom")
    ax.set_yticks(y, [_wrap(labels.get(k, k.replace("_", " ")), 42) for k, _ in items])
    ax.set_xlim(0, 1.08)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1], ["0%", "25%", "50%", "75%", "100%"])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Share of bootstrap draws in which each path applies")
    return _save(fig, path)


def need_capability_map(need: np.ndarray, capability: np.ndarray, path: Path,
                        need_cuts=(2.5, 3.5), capability_cut=3.5, distributed: bool = False) -> Path:
    """Bootstrap cloud of (need, capability floor) over the main architecture regions."""
    apply_style()
    fig, ax = plt.subplots(figsize=(WIDTH, 3.6))
    lo, hi = 1, 5
    middle = "Consolidate or realign services" if distributed else "Restructure within the system"
    regions = [((lo, need_cuts[0]), (lo, hi), "Keep and improve practices", "#f3f7fd"),
               ((need_cuts[0], need_cuts[1]), (lo, hi), middle, "#f4f5f7"),
               ((need_cuts[1], hi), (lo, capability_cut), None, "#f4f5f7"),
               ((need_cuts[1], hi), (capability_cut, hi), "Decomposition possible\n(if gates, data and cost allow)", "#e8f5e8")]
    for (x0, x1), (y0, y1), label, colour in regions:
        ax.add_patch(plt.Rectangle((x0, y0), x1 - x0, y1 - y0, color=colour, lw=0, zorder=0))
        if label:
            ax.text(x0 + 0.08, y1 - 0.12, _wrap(label, 22), fontsize=7.5, color=INK_MUTED, va="top")
    ok = ~(np.isnan(need) | np.isnan(capability))
    ax.scatter(need[ok][1:], capability[ok][1:], s=6, color=ACCENT, alpha=0.12, lw=0, zorder=2)
    ax.scatter(need[0], capability[0], s=60, color=ACCENT, edgecolor=SURFACE, lw=1.5, zorder=3)
    for x in need_cuts:
        ax.axvline(x, color=RULE, lw=0.8)
    ax.axhline(capability_cut, color=RULE, lw=0.8, xmin=(need_cuts[0] - lo) / (hi - lo))
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("Need for change (1–5): coupling, blast radius, business impact, cognitive load")
    ax.set_ylabel("Weakest capability (1–5)")
    return _save(fig, path)


def tco_chart(ratios: dict[str, tuple[float, float, float]], labels: dict, path: Path) -> Path:
    """Cost of each option relative to the current setup: point and 90% range."""
    apply_style()
    items = sorted(ratios.items(), key=lambda kv: kv[1][1])
    fig, ax = plt.subplots(figsize=(WIDTH, 0.42 * len(items) + 0.9))
    y = np.arange(len(items))
    for yi, (k, (p5, mid, p95)) in zip(y, items):
        ax.hlines(yi, p5, p95, color=ACCENT, lw=2, capstyle="round")
        ax.scatter(mid, yi, s=46, color=ACCENT, edgecolor=SURFACE, lw=1.5, zorder=3)
        ax.text(max(p95, mid) + 0.04, yi, f"{mid:.2f}", va="center", fontsize=8)
    ax.axvline(1.0, color=INK_MUTED, lw=0.8)
    ax.axvline(0.85, color=INK_MUTED, lw=0.8, ls="--")
    ax.text(1.0, len(items) - 0.35, " same cost", fontsize=7, color=INK_MUTED)
    ax.text(0.85, len(items) - 0.35, "15% cheaper ", fontsize=7, color=INK_MUTED, ha="right")
    ax.set_yticks(y, [_wrap(labels.get(k, k), 40) for k, _ in items])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    right = max(1.3, max(v[2] for _, v in items) + 0.25)
    ax.set_xlim(max(0, min(v[0] for _, v in items) - 0.15), right)
    ax.set_xlabel("5-year cost relative to the current setup (net present value; 90% range)")
    return _save(fig, path)


def tornado_chart(rows: list[dict], label_for, path: Path, top: int = 7) -> Path:
    apply_style()
    base = rows[0]["base"]
    data = rows[1:top + 1][::-1]
    fig, ax = plt.subplots(figsize=(WIDTH, 0.36 * len(data) + 0.8))
    y = np.arange(len(data))
    for yi, r in zip(y, data):
        lo, hi = sorted((r["low"], r["high"]))
        ax.barh(yi, hi - lo, left=lo, color=NEUTRAL, height=0.55)
    ax.axvline(base, color=ACCENT, lw=1.2)
    ax.set_yticks(y, [_wrap(label_for(r["input"]), 48) for r in data], fontsize=7.5)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Cost relative to an improved current setup, each input at its low and high estimate")
    return _save(fig, path)


def divergence_chart(rows: list[dict], path: Path) -> Path:
    """Measured value (fact band) against perception (survey) for diverging sub-areas."""
    apply_style()
    fig, ax = plt.subplots(figsize=(WIDTH, 0.42 * len(rows) + 0.9))
    y = np.arange(len(rows))
    for yi, r in zip(y, rows):
        ax.plot([r["fact"], r["survey"]], [yi, yi], color=RULE, lw=2, zorder=1)
        ax.scatter(r["fact"], yi, s=46, color=ACCENT, zorder=2, label="Measured" if yi == 0 else None)
        ax.scatter(r["survey"], yi, s=46, color=SURFACE, edgecolor=ACCENT, lw=1.5, zorder=2,
                   label="Perceived" if yi == 0 else None)
    ax.set_yticks(y, [_wrap(r["label"], 40) for r in rows])
    ax.set_xlim(1, 5)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2, fontsize=7.5)
    ax.set_xlabel("Score (1–5)")
    return _save(fig, path)


def preference_chart(by_group: dict, order: list[str], labels: dict, path: Path) -> Path:
    """100% stacked bars of preferred direction per group, colours fixed per outcome."""
    apply_style()
    groups = list(by_group)[::-1]
    colours = outcome_colours(order)
    fig, ax = plt.subplots(figsize=(WIDTH, 0.42 * len(groups) + 1.2))
    left = np.zeros(len(groups))
    y = np.arange(len(groups))
    for o in order + ["no_direction"]:
        values = np.array([by_group[g].get(o, 0.0) for g in groups])
        if not values.any():
            continue
        ax.barh(y, values, left=left, height=0.6, color=colours.get(o, NEUTRAL), edgecolor=SURFACE, lw=1,
                label=_wrap(labels.get(o, "No preference / don't know"), 30))
        left += values
    ax.set_yticks(y, groups)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.5, 1], ["0%", "50%", "100%"])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, fontsize=7, handlelength=1)
    return _save(fig, path)


def stakes_heatmap(by_group: dict, order: list[str], labels: dict, path: Path) -> Path:
    """Mean expected effect of each option on respondents' own roles and skills (−1 harms … +1 helps)."""
    apply_style()
    groups = list(by_group)
    cols = [o for o in order if any(o in by_group[g] for g in groups)]
    data = np.array([[by_group[g].get(o, np.nan) for o in cols] for g in groups])
    fig, ax = plt.subplots(figsize=(WIDTH, 0.4 * len(groups) + 1.2))
    ax.imshow(np.nan_to_num(data), cmap=DIVERGING, vmin=-1, vmax=1, aspect="auto")
    for i in range(len(groups)):
        for j in range(len(cols)):
            v = data[i, j]
            ax.text(j, i, "–" if np.isnan(v) else f"{v:+.1f}", ha="center", va="center", fontsize=8,
                    color=SURFACE if not np.isnan(v) and abs(v) > 0.6 else INK)
    ax.set_xticks(range(len(cols)), [_wrap(labels.get(o, o), 16) for o in cols], fontsize=7)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(groups)), groups)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    return _save(fig, path)


def group_matrix_heatmap(matrix: pd.DataFrame, counts: pd.DataFrame, min_n: int, path: Path) -> Path:
    """Each group's view of each sub-area (1–5); cells with fewer than `min_n` respondents are hatched."""
    apply_style()
    fig, ax = plt.subplots(figsize=(WIDTH, 0.3 * len(matrix) + 1.0))
    values = matrix.to_numpy(dtype=float)
    shown = np.where(counts.to_numpy() >= min_n, values, np.nan)
    ax.imshow(shown, cmap=DIVERGING, vmin=1, vmax=5, aspect="auto")
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            v, n = values[i, j], counts.iat[i, j]
            if np.isnan(v):
                continue
            if n < min_n:
                ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False, hatch="////", edgecolor=RULE, lw=0))
                ax.text(j, i, f"n={n}", ha="center", va="center", fontsize=6.5, color=INK_MUTED, style="italic")
            else:
                ax.text(j, i, f"{v:.1f}", ha="center", va="center", fontsize=7.5,
                        color=SURFACE if v < 1.8 or v > 4.2 else INK)
    ax.set_xticks(range(matrix.shape[1]), matrix.columns, fontsize=8)
    ax.xaxis.tick_top()
    ax.set_yticks(range(matrix.shape[0]), [_wrap(s, 48) for s in matrix.index], fontsize=7)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-0.5, matrix.shape[1]), minor=True)
    ax.set_yticks(np.arange(-0.5, matrix.shape[0]), minor=True)
    ax.grid(which="minor", color=SURFACE, lw=1.5)
    ax.tick_params(which="minor", length=0)
    return _save(fig, path)


def score_distribution_chart(items: list[dict], path: Path) -> Path:
    """Weakest statements: share of answers scoring low (1–2), middle (3) and high (4–5), split around the middle."""
    apply_style()
    data = items[::-1]
    labels = [_wrap(it["text"], 72) for it in data]
    lines = max(label.count("\n") + 1 for label in labels)
    fig, ax = plt.subplots(figsize=(WIDTH, (0.2 + 0.16 * lines) * len(data) + 0.9))
    y = np.arange(len(data))
    for yi, it in zip(y, data):
        left = -(it["low"] + it["mid"] / 2)
        for share, colour, label in ((it["low"], LIKERT[0], "Low (1–2)"), (it["mid"], LIKERT[2], "Middle (3)"),
                                     (it["high"], LIKERT[4], "High (4–5)")):
            ax.barh(yi, share, left=left, color=colour, height=0.6, edgecolor=SURFACE, lw=1,
                    label=label if yi == 0 else None)
            left += share
        ax.text(1.02, yi, f"{it['score']:.1f}", va="center", fontsize=8, transform=ax.get_yaxis_transform())
    ax.axvline(0, color=INK_MUTED, lw=0.8)
    ax.set_yticks(y, labels, fontsize=7)
    ax.set_xlim(-1, 1)
    ax.set_xticks([-1, -0.5, 0, 0.5, 1], ["100%", "50%", "0", "50%", "100%"])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.35, 1.0), fontsize=7, handlelength=1)
    return _save(fig, path)


def roadmap_chart(roadmap: dict, path: Path) -> Path:
    """Indicative sequencing: one lane per workstream, review points as vertical rules, migration with its high estimate."""
    apply_style()
    lanes: dict[str, dict] = {}
    for b in roadmap["bars"]:
        lane = lanes.setdefault(b["workstream"], {"start": b["start"], "end": b["end"], "high": b["end_high"], "n": 0})
        lane["start"], lane["end"] = min(lane["start"], b["start"]), max(lane["end"], b["end"])
        lane["high"] = max(filter(None, [lane["high"], b["end_high"]]), default=None)
        lane["n"] += 1
    names = list(lanes)[::-1]
    horizon = roadmap["horizon"]
    fig, ax = plt.subplots(figsize=(WIDTH, 0.42 * len(names) + 1.0))
    for yi, name in enumerate(names):
        lane = lanes[name]
        ax.barh(yi, lane["end"] - lane["start"], left=lane["start"], height=0.5, color=ACCENT)
        if lane["high"] and lane["high"] > lane["end"]:
            ax.barh(yi, lane["high"] - lane["end"], left=lane["end"], height=0.5, color=SURFACE, edgecolor=ACCENT,
                    hatch="////", lw=0.8)
        count = f"{lane['n']} action{'s' if lane['n'] > 1 else ''}" if "migration" not in name.lower() else "likely – high estimate"
        ax.text((lane["high"] or lane["end"]) + 0.2, yi, count, va="center", fontsize=7.5, color=INK_MUTED)
    for i, g in enumerate(roadmap["gates"], 1):
        ax.axvline(g["month"], color=INK_MUTED, lw=0.8, ls="--")
        ax.text(g["month"], len(names) - 0.25, f"C{i}", ha="center", va="bottom", fontsize=7.5, color=INK_MUTED)
    ax.set_yticks(range(len(names)), [_wrap(n, 32) for n in names])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, horizon + 3)
    ax.set_ylim(-0.6, len(names) + 0.1)
    ax.set_xticks(range(0, horizon + 1, 3))
    ax.set_xlabel("Months from the decision (indicative)")
    return _save(fig, path)


def stakeholder_chart(rows: list[dict], path: Path) -> Path:
    """Support for the recommended paths (x) against influence (y); quadrant names are approaches, not verdicts."""
    apply_style()
    level = {"low": 1, "medium": 2, "high": 3}
    fig, ax = plt.subplots(figsize=(WIDTH, 3.2))
    ax.axvline(0.5, color=RULE, lw=0.8)
    ax.axhline(2.5, color=RULE, lw=0.8)
    for x, y, text, ha in [(0.02, 3.45, "Engage closely", "left"), (0.98, 3.45, "Involve as sponsors", "right"),
                           (0.02, 0.55, "Inform and listen", "left"), (0.98, 0.55, "Keep informed and involved", "right")]:
        ax.text(x, y, text, fontsize=7.5, color=INK_MUTED, ha=ha, va="center")
    for lvl in (1, 2, 3):                                 # spread groups that sit close together on one level
        same = sorted((r for r in rows if level[r["influence"]] == lvl), key=lambda r: r["support"])
        offsets, run = [], 0
        for i, r in enumerate(same):
            run = run + 1 if i and r["support"] - same[i - 1]["support"] < 0.1 else 0
            offsets.append((0, 0.22, -0.22, 0.44)[run % 4])
        for r, dy in zip(same, offsets):
            ax.scatter(r["support"], lvl + dy, s=60, color=ACCENT, edgecolor=SURFACE, lw=1.5, zorder=3, clip_on=False)
            ax.text(r["support"] + 0.025, lvl + dy, r["group"], fontsize=8, color=INK, va="center")
    ax.set_xlim(0, 1)
    ax.set_ylim(0.3, 3.7)
    ax.set_yticks([1, 2, 3], ["Low", "Medium", "High"])
    ax.set_ylabel("Influence on the decision")
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    ax.set_xlabel("Respondents preferring the recommended path (or its interim step), averaged over decisions")
    return _save(fig, path)


def benchmark_chart(rows: list[dict], path: Path) -> Path:
    """Each delivery measure on DORA's 0–10 scale: industry average ± one standard deviation, and this organisation."""
    apply_style()
    rows = [r for r in rows][::-1]
    fig, ax = plt.subplots(figsize=(WIDTH, 0.5 * len(rows) + 1.0))
    for yi, r in enumerate(rows):
        lo, hi = max(0, r["industry_mean"] - r["industry_sd"]), min(10, r["industry_mean"] + r["industry_sd"])
        ax.barh(yi, hi - lo, left=lo, height=0.42, color=RULE)
        ax.plot([r["industry_mean"]] * 2, [yi - 0.21, yi + 0.21], color=INK_MUTED, lw=1.5)
        if r["score"] is not None:
            ax.scatter(r["score"], yi, s=60, color=ACCENT, edgecolor=SURFACE, lw=1.5, zorder=3, clip_on=False)
        else:
            ax.text(0.1, yi, "not measured", va="center", fontsize=7.5, color=INK_MUTED)
    ax.set_yticks(range(len(rows)), [_wrap(r["label"], 26) for r in rows])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, 10.2)
    ax.set_xticks(range(0, 11, 2))
    ax.set_xlabel("DORA score (0–10, higher is better)")
    handles = [plt.Line2D([], [], marker="o", ls="", color=ACCENT, markersize=7, label="This organisation"),
               plt.Line2D([], [], color=INK_MUTED, lw=1.5, label="Industry average"),
               matplotlib.patches.Patch(color=RULE, label="± one standard deviation")]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False, fontsize=7.5)
    return _save(fig, path)


LEAD_TIME_BUCKETS = ["Coordination between teams", "Waiting on process", "Review, build and tests", "No single main cause"]


def lead_time_chart(by_group: dict, path: Path) -> Path:
    """Where lead time goes, as each group sees it: 100% stacked bars in fixed bucket order and colours."""
    apply_style()
    groups = list(by_group)[::-1]
    colours = dict(zip(LEAD_TIME_BUCKETS, [CATEGORICAL[0], CATEGORICAL[1], CATEGORICAL[2], NEUTRAL]))
    fig, ax = plt.subplots(figsize=(WIDTH, 0.42 * len(groups) + 1.2))
    left = np.zeros(len(groups))
    y = np.arange(len(groups))
    for b in LEAD_TIME_BUCKETS:
        values = np.array([by_group[g].get(b, 0.0) for g in groups])
        if not values.any():
            continue
        ax.barh(y, values, left=left, height=0.6, color=colours[b], edgecolor=SURFACE, lw=1, label=b)
        for yi, (x0, v) in enumerate(zip(left, values)):
            if v >= 0.12:
                ax.text(x0 + v / 2, yi, f"{v:.0%}", ha="center", va="center", fontsize=7.5, color=SURFACE)
        left += values
    ax.set_yticks(y, groups)
    ax.set_xlim(0, 1)
    ax.set_xticks([0, 0.5, 1], ["0%", "50%", "100%"])
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=4, fontsize=7, handlelength=1)
    return _save(fig, path)


def sourcing_map(parts: list[dict], commodity_below: float, coverage_at_least: float, path: Path) -> Path:
    """Each candidate part: how much it sets the organisation apart (x) against how much a product covers (y),
    with 90% ranges; the shaded corner is where replacing it can apply (if buying is also cheaper)."""
    apply_style()
    fig, ax = plt.subplots(figsize=(WIDTH, 3.4))
    ax.add_patch(plt.Rectangle((1, coverage_at_least), commodity_below - 1, 100 - coverage_at_least,
                               color="#f3f7fd", lw=0, zorder=0))
    ax.text(1.06, coverage_at_least + 1, "Replacing can apply (if buying is also cheaper)", fontsize=7.5,
            color=INK_MUTED, va="bottom")
    ax.text(4.94, coverage_at_least - 1, "Keep building", fontsize=7.5, color=INK_MUTED, va="top", ha="right")
    ax.axvline(commodity_below, color=RULE, lw=0.8)
    ax.axhline(coverage_at_least, color=RULE, lw=0.8)
    for p in parts:
        if p.get("differentiation") is None:
            continue
        x, y = p["differentiation"], p["coverage"]
        (x0, x1), (y0, y1) = p["differentiation_range"], p["coverage_range"]
        ax.plot([x0, x1], [y, y], color=ACCENT, lw=1.2, alpha=0.6, zorder=2)
        ax.plot([x, x], [y0, y1], color=ACCENT, lw=1.2, alpha=0.6, zorder=2)
        ax.scatter(x, y, s=60, color=ACCENT, edgecolor=SURFACE, lw=1.5, zorder=3)
        ax.text(x + 0.06, y + 1.5, p["name"], fontsize=8, color=INK)
    ax.set_xlim(1, 5)
    ax.set_ylim(max(0, min([p["coverage_range"][0] for p in parts if p.get("coverage") is not None] + [50]) - 5), 100)
    ax.set_xlabel("How much the part sets the organisation apart (1–5, business-facing groups)")
    ax.set_ylabel("Requirements a product\nmeets as is (%)")
    return _save(fig, path)
