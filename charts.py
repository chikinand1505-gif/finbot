import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from typing import List, Dict

# ── Palette ──────────────────────────────────────────────────────────────────
COLORS = [
    "#6366F1", "#8B5CF6", "#EC4899", "#F59E0B",
    "#10B981", "#3B82F6", "#EF4444", "#14B8A6",
    "#F97316", "#84CC16", "#06B6D4", "#A855F7",
]
BG_COLOR = "#0F172A"
TEXT_COLOR = "#E2E8F0"
GRID_COLOR = "#1E293B"
INCOME_COLOR = "#10B981"
EXPENSE_COLOR = "#F43F5E"


def _apply_dark_style(fig, ax):
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    ax.tick_params(colors=TEXT_COLOR, labelsize=9)
    ax.spines["bottom"].set_color(GRID_COLOR)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID_COLOR)
    ax.yaxis.grid(True, color=GRID_COLOR, linewidth=0.8, linestyle="--")
    ax.set_axisbelow(True)


def generate_expense_chart(data: List[Dict], title: str) -> io.BytesIO:
    labels = [d["category"] for d in data]
    values = [d["total"] for d in data]
    total = sum(values)

    # Trim long category names
    short_labels = [l[:18] + "…" if len(l) > 20 else l for l in labels]

    fig, (ax_pie, ax_bar) = plt.subplots(1, 2, figsize=(12, 5))
    fig.patch.set_facecolor(BG_COLOR)

    # ── Pie chart ──
    ax_pie.set_facecolor(BG_COLOR)
    wedges, texts, autotexts = ax_pie.pie(
        values,
        labels=None,
        colors=COLORS[:len(values)],
        autopct=lambda p: f"{p:.1f}%" if p > 5 else "",
        startangle=140,
        pctdistance=0.75,
        wedgeprops=dict(linewidth=2, edgecolor=BG_COLOR),
    )
    for at in autotexts:
        at.set_color(TEXT_COLOR)
        at.set_fontsize(8)
        at.set_fontweight("bold")

    # Center total
    ax_pie.text(0, 0, f"{total:,.0f} ₽", ha="center", va="center",
                fontsize=12, fontweight="bold", color=TEXT_COLOR)

    # Legend
    legend_patches = [
        mpatches.Patch(color=COLORS[i], label=f"{short_labels[i]}")
        for i in range(len(labels))
    ]
    ax_pie.legend(handles=legend_patches, loc="lower center",
                  bbox_to_anchor=(0.5, -0.15), ncol=2,
                  fontsize=7, frameon=False, labelcolor=TEXT_COLOR)

    # ── Bar chart ──
    ax_bar.set_facecolor(BG_COLOR)
    y_pos = np.arange(len(labels))
    bars = ax_bar.barh(y_pos, values, color=COLORS[:len(values)],
                       height=0.6, edgecolor=BG_COLOR, linewidth=1.5)

    ax_bar.set_yticks(y_pos)
    ax_bar.set_yticklabels(short_labels, color=TEXT_COLOR, fontsize=8)
    ax_bar.tick_params(axis="x", colors=TEXT_COLOR, labelsize=8)
    ax_bar.spines["top"].set_visible(False)
    ax_bar.spines["right"].set_visible(False)
    ax_bar.spines["bottom"].set_color(GRID_COLOR)
    ax_bar.spines["left"].set_color(GRID_COLOR)
    ax_bar.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8, linestyle="--")
    ax_bar.set_axisbelow(True)
    ax_bar.invert_yaxis()

    # Value labels
    for bar, val in zip(bars, values):
        ax_bar.text(val + total * 0.01, bar.get_y() + bar.get_height() / 2,
                    f"{val:,.0f} ₽", va="center", ha="left",
                    color=TEXT_COLOR, fontsize=7.5)

    fig.suptitle(title, color=TEXT_COLOR, fontsize=14, fontweight="bold", y=1.01)
    plt.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    buf.seek(0)
    plt.close(fig)
    return buf


def generate_balance_chart(data: List[Dict]) -> io.BytesIO:
    months = [d["month"] for d in data]
    incomes = [d["income"] for d in data]
    expenses = [d["expense"] for d in data]
    net = [i - e for i, e in zip(incomes, expenses)]

    x = np.arange(len(months))
    width = 0.35

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), gridspec_kw={"height_ratios": [3, 1]})
    fig.patch.set_facecolor(BG_COLOR)

    # ── Grouped bars ──
    ax1.set_facecolor(BG_COLOR)
    bars1 = ax1.bar(x - width/2, incomes, width, label="Доходы",
                    color=INCOME_COLOR, alpha=0.85, edgecolor=BG_COLOR)
    bars2 = ax1.bar(x + width/2, expenses, width, label="Расходы",
                    color=EXPENSE_COLOR, alpha=0.85, edgecolor=BG_COLOR)

    ax1.set_xticks(x)
    ax1.set_xticklabels(months, color=TEXT_COLOR, fontsize=9)
    ax1.tick_params(axis="y", colors=TEXT_COLOR, labelsize=9)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.spines["bottom"].set_color(GRID_COLOR)
    ax1.spines["left"].set_color(GRID_COLOR)
    ax1.yaxis.grid(True, color=GRID_COLOR, linewidth=0.8, linestyle="--")
    ax1.set_axisbelow(True)
    ax1.legend(frameon=False, labelcolor=TEXT_COLOR, fontsize=9)
    ax1.set_title("История доходов и расходов", color=TEXT_COLOR, fontsize=13, fontweight="bold")

    # ── Net line ──
    ax2.set_facecolor(BG_COLOR)
    colors_net = [INCOME_COLOR if v >= 0 else EXPENSE_COLOR for v in net]
    ax2.bar(x, net, color=colors_net, alpha=0.9, edgecolor=BG_COLOR)
    ax2.axhline(0, color=GRID_COLOR, linewidth=1)
    ax2.set_xticks(x)
    ax2.set_xticklabels(months, color=TEXT_COLOR, fontsize=9)
    ax2.tick_params(axis="y", colors=TEXT_COLOR, labelsize=8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.spines["bottom"].set_color(GRID_COLOR)
    ax2.spines["left"].set_color(GRID_COLOR)
    ax2.set_title("Чистый баланс по месяцам", color=TEXT_COLOR, fontsize=10, pad=8)

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    buf.seek(0)
    plt.close(fig)
    return buf


def generate_goals_chart(goals: List[Dict]) -> io.BytesIO:
    names = [g["name"][:20] + "…" if len(g["name"]) > 22 else g["name"] for g in goals]
    targets = [float(g["target_amount"]) for g in goals]
    currents = [float(g["current_amount"]) for g in goals]
    percentages = [min(c / t * 100, 100) for c, t in zip(currents, targets)]

    fig, ax = plt.subplots(figsize=(10, max(3, len(goals) * 1.1)))
    fig.patch.set_facecolor(BG_COLOR)
    ax.set_facecolor(BG_COLOR)

    y = np.arange(len(goals))
    bar_h = 0.5

    # Background bars (full)
    ax.barh(y, [100] * len(goals), bar_h, color=GRID_COLOR, edgecolor=BG_COLOR)
    # Progress bars
    bar_colors = [INCOME_COLOR if p >= 100 else COLORS[i % len(COLORS)] for i, p in enumerate(percentages)]
    ax.barh(y, percentages, bar_h, color=bar_colors, edgecolor=BG_COLOR, alpha=0.9)

    ax.set_xlim(0, 110)
    ax.set_yticks(y)
    ax.set_yticklabels(names, color=TEXT_COLOR, fontsize=9)
    ax.tick_params(axis="x", colors=TEXT_COLOR, labelsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_color(GRID_COLOR)
    ax.spines["left"].set_color(GRID_COLOR)
    ax.xaxis.grid(True, color=GRID_COLOR, linewidth=0.6, linestyle="--")
    ax.set_axisbelow(True)
    ax.set_xlabel("% выполнения", color=TEXT_COLOR, fontsize=9)

    # Annotations
    for i, (p, curr, tgt) in enumerate(zip(percentages, currents, targets)):
        label = f"{curr:,.0f} / {tgt:,.0f} ₽ ({p:.0f}%)"
        ax.text(min(p, 100) + 1, i, label, va="center", ha="left",
                color=TEXT_COLOR, fontsize=8)

    ax.set_title("Прогресс финансовых целей", color=TEXT_COLOR,
                 fontsize=13, fontweight="bold", pad=12)

    plt.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    buf.seek(0)
    plt.close(fig)
    return buf
