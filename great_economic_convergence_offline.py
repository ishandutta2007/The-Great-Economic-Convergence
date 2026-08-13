"""
Great Economic Convergence — OFFLINE version.

This script does NOT access the Internet.
It imports the starting dataset from:
    great_economic_convergence_data_2024.csv

Starting GDP-per-capita data:
    World Bank WDI, 2024, GDP per capita, PPP (current international $)

Growth assumptions:
    < $20K       -> 6.5%
    $20K-$40K    -> 4.5%
    $40K-$80K    -> 2.5%
    >= $80K      -> 0.5%

The growth band is recalculated every year, so countries automatically
move to slower bands as they cross the thresholds.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

BASE_YEAR = 2024
TARGET_YEAR = 2100

DATA_FILE = Path(__file__).with_name("great_economic_convergence_data_2024.csv")
OUTPUT_FILE = Path(__file__).with_name("great_economic_convergence.gif")


def growth_rate(gdp_pc):
    if gdp_pc < 20_000:
        return 0.065
    if gdp_pc < 40_000:
        return 0.045
    if gdp_pc < 80_000:
        return 0.025
    return 0.005


def load_data():
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Could not find offline data file:\n{DATA_FILE}\n\n"
            "Keep the CSV in the same directory as this Python script."
        )

    df = pd.read_csv(DATA_FILE)

    required = {"country", "iso3", "gdp_pc_ppp_2024", "population_2024"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in CSV: {sorted(missing)}")

    df = df.dropna(subset=["gdp_pc_ppp_2024"]).copy()
    df["gdp_pc"] = pd.to_numeric(df["gdp_pc_ppp_2024"])
    df["population"] = pd.to_numeric(df["population_2024"])

    return df.sort_values("gdp_pc").reset_index(drop=True)


def simulate(df):
    years = np.arange(BASE_YEAR, TARGET_YEAR + 1)

    values = {BASE_YEAR: df["gdp_pc"].to_numpy(dtype=float)}

    for year in years[1:]:
        previous = values[year - 1]
        rates = np.array([growth_rate(x) for x in previous])
        values[year] = previous * (1 + rates)

    return years, values


def make_animation(df, years, values):
    fig, ax = plt.subplots(figsize=(16, 9))

    y = np.arange(len(df))
    bars = ax.barh(y, values[BASE_YEAR], height=0.72)

    max_value = max(float(values[year].max()) for year in years)
    ax.set_xlim(0, max(120_000, max_value * 1.10))
    ax.set_ylim(-1, len(df))
    ax.set_yticks(y)
    ax.set_yticklabels(df["country"])
    ax.invert_yaxis()

    ax.set_xlabel("GDP per capita (PPP, current international $)")
    ax.set_title(
        f"The Great Economic Convergence — {BASE_YEAR}",
        fontsize=20,
        fontweight="bold",
    )

    for threshold in [20_000, 40_000, 80_000]:
        ax.axvline(threshold, linestyle="--", linewidth=1.2)
        ax.text(
            threshold,
            1.01,
            f"${threshold / 1000:.0f}K",
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="bottom",
        )

    def update(frame):
        year = int(years[frame])
        current = values[year]

        for bar, value in zip(bars, current):
            bar.set_width(value)

        ax.set_title(
            f"The Great Economic Convergence — {year}",
            fontsize=20,
            fontweight="bold",
        )

        for txt in list(ax.texts):
            if getattr(txt, "_country_value_label", False):
                txt.remove()

        for ypos, value in zip(y, current):
            rate = growth_rate(value)
            label = ax.text(
                value,
                ypos,
                f"  ${value:,.0f}  ({rate * 100:.1f}%)",
                va="center",
                fontsize=8.5,
            )
            label._country_value_label = True

        return bars

    anim = FuncAnimation(
        fig,
        update,
        frames=len(years),
        interval=100,
        blit=False,
        repeat=True,
    )

    print("Displaying animation...")
    plt.show()

    print(f"Saving: {OUTPUT_FILE}")
    anim.save(
        OUTPUT_FILE,
        writer=PillowWriter(fps=10),
        dpi=120,
    )
    plt.close(fig)
    print("Finished.")


def main():
    print(f"Loading OFFLINE data: {DATA_FILE}")
    df = load_data()

    print(f"Countries: {len(df)}")
    print(df[["country", "gdp_pc", "population"]].to_string(index=False))

    years, values = simulate(df)
    make_animation(df, years, values)


if __name__ == "__main__":
    main()
