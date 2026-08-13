"""
Great Economic Convergence — animated GDP-per-capita (PPP) convergence

Concept:
  < $20,000 PPP GDP per capita: 6.5% annual growth
  $20,000–$40,000:             4.5%
  $40,000–$80,000:             2.5%
  >= $80,000:                   0.5%

The growth rate is recalculated every year, so a country automatically
moves into a slower band after crossing a threshold.

Default:
  Base year: 2026
  End year:  2100
  Countries: population > 100 million
  Data source: World Bank API
  Output: great_economic_convergence.gif

Dependencies:
  pip install pandas requests matplotlib pillow
"""

import io
import requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter

BASE_YEAR = 2026
TARGET_YEAR = 2100
MIN_POPULATION = 100_000_000

OUTPUT_FILE = "great_economic_convergence.gif"


# Midpoints of the user's proposed growth bands.
def growth_rate(gdp_pc):
    if gdp_pc < 20_000:
        return 0.065
    elif gdp_pc < 40_000:
        return 0.045
    elif gdp_pc < 80_000:
        return 0.025
    else:
        return 0.005


def wb_indicator(indicator, year):
    url = (
        f"https://api.worldbank.org/v2/country/all/indicator/"
        f"{indicator}?date={year}&format=json&per_page=400"
    )
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    data = r.json()[1]
    return pd.DataFrame(
        [
            {"iso3": x["countryiso3code"], "value": x["value"]}
            for x in data
            if x["countryiso3code"]
        ]
    )


def wb_countries():
    url = "https://api.worldbank.org/v2/country?format=json&per_page=400"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    data = r.json()[1]
    return pd.DataFrame(
        [
            {
                "iso3": x["id"],
                "country": x["name"],
                "region": x["region"]["value"],
            }
            for x in data
            if x["region"]["value"] != "Aggregates"
        ]
    )


def load_data():
    # PPP GDP per capita, current international dollars.
    gdp = wb_indicator("NY.GDP.PCAP.PP.CD", BASE_YEAR)
    pop = wb_indicator("SP.POP.TOTL", BASE_YEAR)
    countries = wb_countries()

    df = countries.merge(gdp, on="iso3", how="inner", suffixes=("", "_gdp"))
    df = df.merge(pop, on="iso3", how="inner", suffixes=("", "_pop"))

    df = df.rename(columns={"value_gdp": "gdp_pc", "value": "population"})
    df["gdp_pc"] = pd.to_numeric(df["gdp_pc"], errors="coerce")
    df["population"] = pd.to_numeric(df["population"], errors="coerce")

    df = df.dropna(subset=["gdp_pc", "population"])
    df = df[df["population"] >= MIN_POPULATION].copy()

    return (
        df[["iso3", "country", "gdp_pc", "population"]]
        .sort_values("gdp_pc")
        .reset_index(drop=True)
    )


def simulate(df):
    years = np.arange(BASE_YEAR, TARGET_YEAR + 1)
    values = {}

    values[BASE_YEAR] = df["gdp_pc"].to_numpy(dtype=float)

    for year in years[1:]:
        previous = values[year - 1]
        rates = np.array([growth_rate(x) for x in previous])
        values[year] = previous * (1.0 + rates)

    return years, values


def make_animation(df, years, values):
    fig, ax = plt.subplots(figsize=(16, 9))

    # Fixed scale keeps the visual comparison stable through time.
    max_value = max(float(values[y].max()) for y in years)
    x_max = max(120_000, max_value * 1.08)

    # Country labels are annotated on every frame.
    y_positions = np.arange(len(df))

    bars = ax.barh(y_positions, values[BASE_YEAR], height=0.72)

    ax.set_xlim(0, x_max)
    ax.set_ylim(-1, len(df))
    ax.set_yticks(y_positions)
    ax.set_yticklabels(df["country"])
    ax.invert_yaxis()

    ax.set_xlabel("GDP per capita (PPP, current international $)")
    ax.set_title(
        f"The Great Economic Convergence — {BASE_YEAR}",
        fontsize=20,
        fontweight="bold",
    )

    # Growth-band thresholds.
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

        # Remove old value labels.
        for txt in list(ax.texts):
            if getattr(txt, "_country_value_label", False):
                txt.remove()

        for y, value in zip(y_positions, current):
            rate = growth_rate(value)
            label = ax.text(
                value,
                y,
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

    print(f"Saving animation to: {OUTPUT_FILE}")
    anim.save(
        OUTPUT_FILE,
        writer=PillowWriter(fps=10),
        dpi=120,
    )
    plt.close(fig)
    print("Done.")


def main():
    print("Downloading World Bank data...")
    df = load_data()

    if df.empty:
        raise RuntimeError(
            "No countries met the population/data filters. "
            "Check the World Bank API response."
        )

    print(f"Countries included: {len(df)}")
    print(df[["country", "gdp_pc", "population"]].to_string(index=False))

    print("Simulating convergence...")
    years, values = simulate(df)

    print("Rendering GIF...")
    make_animation(df, years, values)


if __name__ == "__main__":
    main()
