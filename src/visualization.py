"""Fonctions de graphiques réutilisables et homogènes.

Chaque figure porte un titre, des axes nommés avec leur unité, une légende, la
période couverte et la source (BR-016). Les fonctions renvoient un objet
`matplotlib.figure.Figure` et n'appellent pas `plt.show()` : le notebook décide
de l'affichage, les tests n'affichent rien.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.figure import Figure

BASE_COLORS = {"WTI": "#1f4e79", "BTC_USD": "#c0504d", "SP500": "#2e7d32"}


def apply_style() -> None:
    """Applique un style Matplotlib sobre et lisible (grille, polices)."""
    plt.rcParams.update(
        {
            "figure.figsize": (11, 6),
            "axes.grid": True,
            "grid.alpha": 0.3,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "font.size": 10,
            "legend.frameon": False,
            "figure.autolayout": False,
        }
    )


def source_footer(fig: Figure, text: str) -> Figure:
    """Ajoute une mention de source et de période au bas de la figure."""
    fig.text(0.01, 0.005, text, fontsize=8, color="#555555", ha="left", va="bottom")
    return fig


def period_label(frame_or_index: pd.Index | pd.Series | pd.DataFrame) -> str:
    """Construit une mention `2020-01-02 → 2025-12-31` à partir d'un index."""
    index = getattr(frame_or_index, "index", frame_or_index)
    dates = pd.to_datetime(pd.Series(index)).dropna()
    if dates.empty:
        return "période inconnue"
    return f"{dates.min().date()} → {dates.max().date()}"


def plot_price(
    prices: pd.Series,
    *,
    asset: str,
    unit: str,
    provider: str,
    title: str | None = None,
) -> Figure:
    """Trace une série de prix brute dans son unité (les niveaux ne sont pas comparables)."""
    apply_style()
    fig, ax = plt.subplots()
    ax.plot(prices.index, prices.values, color=BASE_COLORS.get(asset), linewidth=1.4)
    ax.set_title(title or f"{asset} — prix de clôture ({unit})")
    ax.set_xlabel("Date")
    ax.set_ylabel(unit)
    ax.legend([asset], loc="upper left")
    fig.autofmt_xdate()
    return source_footer(
        fig,
        f"Source : {provider} — période {period_label(prices)} — "
        "valeurs manquantes non interpolées.",
    )


def plot_normalized_index(indices: pd.DataFrame, *, bases: dict[str, dict] | None = None) -> Figure:
    """Compare les indices base 100 des séries alignées."""
    apply_style()
    fig, ax = plt.subplots()
    for column in indices.columns:
        ax.plot(
            indices.index,
            indices[column],
            label=f"{column} (base 100)",
            color=BASE_COLORS.get(column),
            linewidth=1.4,
        )
    ax.axhline(100.0, color="#888888", linewidth=0.8, linestyle="--")
    ax.set_title("Évolution relative — indices normalisés base 100")
    ax.set_xlabel("Date")
    ax.set_ylabel("Indice (base 100)")
    ax.legend(loc="upper left")
    fig.autofmt_xdate()
    bases_text = ""
    if bases:
        bases_text = " — " + " ; ".join(
            f"{asset} base {base['base_value']:,.2f} au {base['base_date']}"
            for asset, base in bases.items()
        )
    return source_footer(
        fig,
        f"Calcul : prix_t / prix_base * 100 sur les dates communes{bases_text}.",
    )


def plot_returns(returns: pd.DataFrame) -> Figure:
    """Trace les rendements quotidiens alignés des trois séries."""
    apply_style()
    fig, ax = plt.subplots()
    for column in returns.columns:
        ax.plot(
            returns.index,
            returns.values,
            label=column,
            color=BASE_COLORS.get(column),
            linewidth=0.8,
            alpha=0.85,
        )
    ax.axhline(0.0, color="#888888", linewidth=0.8)
    ax.set_title("Rendements simples quotidiens (P_t / P_{t-1} - 1)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Rendement")
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    ax.legend(loc="upper left", ncol=3)
    fig.autofmt_xdate()
    return source_footer(
        fig,
        f"Rendements calculés sur dates communes, sans interpolation — {period_label(returns)}.",
    )


def plot_return_distribution(returns: pd.DataFrame, *, bins: int = 80) -> Figure:
    """Compare les distributions de rendement."""
    apply_style()
    fig, ax = plt.subplots()
    for column in returns.columns:
        values = pd.to_numeric(returns[column], errors="coerce").dropna()
        ax.hist(
            values,
            bins=bins,
            density=True,
            histtype="step",
            linewidth=1.4,
            color=BASE_COLORS.get(column),
            label=f"{column} (n={len(values)})",
        )
    ax.set_title("Distribution des rendements simples")
    ax.set_xlabel("Rendement")
    ax.set_ylabel("Densité")
    ax.xaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    ax.legend()
    return source_footer(fig, f"Densités estimées sur {len(returns)} dates communes alignées.")


def plot_rolling_volatility(volatilities: pd.DataFrame, *, window: int) -> Figure:
    """Trace la volatilité annualisée en fenêtre glissante."""
    apply_style()
    fig, ax = plt.subplots()
    for column in volatilities.columns:
        ax.plot(
            volatilities.index,
            volatilities[column],
            label=column,
            color=BASE_COLORS.get(column),
            linewidth=1.2,
        )
    ax.set_title(f"Volatilité annualisée — fenêtre glissante de {window} observations")
    ax.set_xlabel("Date")
    ax.set_ylabel("Volatilité annualisée")
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    ax.legend(loc="upper left", ncol=3)
    fig.autofmt_xdate()
    return source_footer(
        fig,
        f"Écart-type d'échantillon × √252 — les {window - 1} premières dates n'ont pas de valeur.",
    )


def plot_drawdown(drawdowns: pd.DataFrame) -> Figure:
    """Trace le drawdown de chaque série (base 100 alignée)."""
    apply_style()
    fig, ax = plt.subplots()
    for column in drawdowns.columns:
        ax.plot(
            drawdowns.index,
            drawdowns[column],
            label=column,
            color=BASE_COLORS.get(column),
            linewidth=1.2,
        )
        trough_date = drawdowns[column].idxmin()
        ax.scatter(
            [trough_date],
            [drawdowns[column].min()],
            color=BASE_COLORS.get(column),
            s=22,
            zorder=3,
        )
    ax.set_title("Drawdown depuis le plus haut historique (indice base 100)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Drawdown")
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:.0%}")
    ax.legend(loc="lower left", ncol=3)
    fig.autofmt_xdate()
    return source_footer(
        fig, "Creux maximaux marqués par un point — calcul : indice / plus haut historique - 1."
    )


def plot_correlation_heatmap(correlation: pd.DataFrame, *, n_observations: int) -> Figure:
    """Affiche la matrice de corrélation de Pearson des rendements alignés."""
    apply_style()
    fig, ax = plt.subplots()
    image = ax.imshow(correlation.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(correlation.columns)), correlation.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(correlation.index)), correlation.index)
    for i in range(len(correlation.index)):
        for j in range(len(correlation.columns)):
            ax.text(
                j,
                i,
                f"{correlation.values[i, j]:.2f}",
                ha="center",
                va="center",
                fontsize=10,
                color="black",
            )
    ax.grid(False)
    ax.set_title("Corrélation de Pearson des rendements simples alignés")
    fig.colorbar(image, ax=ax, fraction=0.046, label="coefficient de corrélation")
    return source_footer(
        fig,
        f"{n_observations} observations appariées par série — "
        "la corrélation n'établit pas une causalité.",
    )


def plot_base_reference(bases: dict[str, dict], *, units: dict[str, str]) -> Figure:
    """Figure didactique : rappel de la date et de la valeur de base de chaque série."""
    apply_style()
    fig, ax = plt.subplots(figsize=(8, 2.8))
    ax.axis("off")
    lines = [
        f"{asset} : base {base['base_value']:,.4f} {units.get(asset, '')} "
        f"au {base['base_date']} → indice 100"
        for asset, base in bases.items()
    ]
    ax.set_title("Référence de normalisation (indice base 100)", pad=12)
    ax.text(0.02, 0.85, "\n".join(f"- {line}" for line in lines), fontsize=10, va="top")
    return source_footer(fig, "Source : calcul interne du pipeline (base = première date commune).")


def save_figure(fig: Figure, path: str | Path) -> Path:
    """Enregistre une figure sur disque et la ferme."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return target
