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
from matplotlib.animation import FuncAnimation, PillowWriter, FFMpegWriter

BASE_YEAR = 2024
TARGET_YEAR = 2100

DATA_FILE = Path(__file__).with_name("great_economic_convergence_data_2024.csv")
OUTPUT_GIF_FILE = Path(__file__).with_name("great_economic_convergence.gif")
OUTPUT_MP4_FILE = Path(__file__).with_name("great_economic_convergence.mp4")


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
    plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=(16, 9), facecolor="#0e1117")
    ax.set_facecolor("#161b22")

    y = np.arange(len(df))
    
    # Dynamic threshold line calculations:
    # Each boundary threshold simulates year-by-year using growth_rate(val).
    # As the $20K boundary grows past $20K, its growth rate dynamically steps down
    # (6.5% -> 4.5% -> 2.5% -> 0.5%) so boundaries converge without overtaking.
    threshold_configs = [
        {"base": 20_000, "name": "Boundary 1", "color": "#2ecc71"},
        {"base": 40_000, "name": "Boundary 2", "color": "#3498db"},
        {"base": 80_000, "name": "Boundary 3", "color": "#f1c40f"},
    ]

    threshold_values = {}
    for cfg in threshold_configs:
        vals = [float(cfg["base"])]
        curr = float(cfg["base"])
        for _ in range(len(years) - 1):
            rate = growth_rate(curr)
            curr = curr * (1 + rate)
            vals.append(curr)
        threshold_values[cfg["base"]] = vals

    # Helper function to get color based on current position relative to moving vertical lines (th1, th2, th3)
    def get_bar_color(value, th1, th2, th3):
        if value < th1:
            return "#2ecc71"  # Emerald Green (6.5% tier, behind vertical line 1)
        if value < th2:
            return "#3498db"  # Bright Blue (4.5% tier, between line 1 and line 2)
        if value < th3:
            return "#f1c40f"  # Warm Gold (2.5% tier, between line 2 and line 3)
        return "#e74c3c"      # Coral Red (0.5% tier, past line 3)

    initial_th1 = threshold_values[20_000][0]
    initial_th2 = threshold_values[40_000][0]
    initial_th3 = threshold_values[80_000][0]
    initial_colors = [get_bar_color(v, initial_th1, initial_th2, initial_th3) for v in values[BASE_YEAR]]
    bars = ax.barh(y, values[BASE_YEAR], height=0.72, color=initial_colors, edgecolor="none", alpha=0.9)

    max_value = max(float(values[year].max()) for year in years)
    ax.set_xlim(0, max(120_000, max_value * 1.12))
    ax.set_ylim(-0.8, len(df) - 0.2)
    ax.set_yticks(y)
    ax.set_yticklabels(df["country"], fontsize=10, fontweight="bold", color="#e6edf3")
    ax.invert_yaxis()

    ax.set_xlabel("GDP per capita (PPP, current international $)", fontsize=12, fontweight="bold", color="#8b949e", labelpad=10)
    ax.tick_params(colors="#8b949e", labelsize=10)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#30363d")
    ax.spines["bottom"].set_color("#30363d")

    # Gridlines
    ax.xaxis.grid(True, linestyle=":", alpha=0.3, color="#8b949e")
    ax.set_axisbelow(True)

    # Create regional income classification text headers
    # Region 1: [0, th1] -> "Poor"
    # Region 2: [th1, th2] -> "Middle Income"
    # Region 3: [th2, th3] -> "Developed"
    # Region 4: [th3, xmax] -> "Ultra Developed"
    region_defs = [
        {"name": "Poor", "color": "#2ecc71"},
        {"name": "Middle Income", "color": "#3498db"},
        {"name": "Developed", "color": "#f1c40f"},
        {"name": "Ultra Developed", "color": "#e74c3c"},
    ]
    region_texts = []
    for rdef in region_defs:
        txt = ax.text(
            0,
            1.02,
            rdef["name"].upper(),
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="bottom",
            fontsize=11,
            color=rdef["color"],
            fontweight="bold",
            alpha=0.85,
        )
        region_texts.append((rdef, txt))

    # Create line and text objects for dynamic thresholds
    threshold_lines = []
    threshold_texts = []
    for cfg in threshold_configs:
        init_val = threshold_values[cfg["base"]][0]
        init_rate = growth_rate(init_val)
        line = ax.axvline(init_val, linestyle="--", linewidth=1.5, color=cfg["color"], alpha=0.6)
        txt = ax.text(
            init_val,
            -0.02,
            f"${init_val / 1000:.1f}K ({init_rate * 100:.1f}%)",
            transform=ax.get_xaxis_transform(),
            ha="center",
            va="bottom",
            fontsize=8.5,
            color=cfg["color"],
            fontweight="bold",
        )
        threshold_lines.append((cfg, line))
        threshold_texts.append((cfg, txt))

    def update(frame):
        year = int(years[frame])
        current = values[year]

        # Current positions of dynamic vertical lines in this frame
        th1 = threshold_values[20_000][frame]
        th2 = threshold_values[40_000][frame]
        th3 = threshold_values[80_000][frame]
        xmax = ax.get_xlim()[1]

        for bar, value in zip(bars, current):
            bar.set_width(value)
            bar.set_color(get_bar_color(value, th1, th2, th3))

        # Update region header positions and dynamic font scaling
        regions_bounds = [
            (0, th1),
            (th1, th2),
            (th2, th3),
            (th3, xmax),
        ]

        for idx, (left, right) in enumerate(regions_bounds):
            width = right - left
            center = left + (width / 2.0)
            rdef, txt = region_texts[idx]
            txt.set_x(center)
            
            # Dynamically adjust font size if region compresses below width threshold
            # Approx character width fitting in plot data units
            text_len = len(rdef["name"])
            approx_char_width = max_value * 0.015
            needed_width = text_len * approx_char_width
            if width < needed_width:
                scaled_size = max(6.5, 11 * (width / needed_width))
            else:
                scaled_size = 11
            txt.set_fontsize(scaled_size)

        # Update dynamic threshold line positions, colors, and label text
        for idx, (cfg, line) in enumerate(threshold_lines):
            curr_th = threshold_values[cfg["base"]][frame]
            curr_rate = growth_rate(curr_th)
            curr_color = get_bar_color(curr_th, th1, th2, th3)
            
            line.set_xdata([curr_th, curr_th])
            line.set_color(curr_color)
            
            _, txt = threshold_texts[idx]
            txt.set_x(curr_th)
            txt.set_color(curr_color)
            txt.set_text(f"${curr_th / 1000:.1f}K ({curr_rate * 100:.1f}%)")

        ax.set_title(
            f"The Great Economic Convergence — {year}",
            fontsize=22,
            fontweight="bold",
            color="#ffffff",
            pad=45,
        )

        for txt in list(ax.texts):
            if getattr(txt, "_country_value_label", False):
                txt.remove()

        for ypos, value in zip(y, current):
            rate = growth_rate(value)
            label = ax.text(
                value + (max_value * 0.008),
                ypos,
                f"${value:,.0f} ({rate * 100:.1f}%)",
                va="center",
                fontsize=9,
                fontweight="bold",
                color="#e6edf3",
            )
            label._country_value_label = True

        return bars

    # Slowed down speed: interval 500ms (2 frames per second / 0.5s per year for deliberate viewing)
    anim = FuncAnimation(
        fig,
        update,
        frames=len(years),
        interval=500,
        blit=False,
        repeat=True,
    )

    print("Displaying animation...")
    plt.show()

    print(f"Saving GIF: {OUTPUT_GIF_FILE}")
    anim.save(
        OUTPUT_GIF_FILE,
        writer=PillowWriter(fps=2),
        dpi=120,
    )

    print(f"Saving MP4: {OUTPUT_MP4_FILE}")
    saved_mp4 = False
    
    # Try finding ffmpeg executable path dynamically if not on system PATH
    ffmpeg_exe = None
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    if ffmpeg_exe:
        plt.rcParams['animation.ffmpeg_path'] = ffmpeg_exe

    try:
        anim.save(
            OUTPUT_MP4_FILE,
            writer=FFMpegWriter(fps=2, extra_args=['-vcodec', 'libx264']),
            dpi=120,
        )
        saved_mp4 = True
        print("MP4 saved successfully using matplotlib FFMpegWriter.")
    except Exception as e:
        # Fallback to imageio if FFMpegWriter fails
        try:
            import imageio
            reader = imageio.get_reader(OUTPUT_GIF_FILE)
            fps = reader.get_meta_data().get('fps', 2)
            writer = imageio.get_writer(OUTPUT_MP4_FILE, fps=fps)
            for frame in reader:
                writer.append_data(frame)
            writer.close()
            reader.close()
            saved_mp4 = True
            print("MP4 converted and saved successfully from GIF using imageio.")
        except Exception as e2:
            print(f"Could not save MP4: {e}")
            print("Note: To enable MP4 export natively, install FFmpeg on your system or run: pip install imageio[ffmpeg]")

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
