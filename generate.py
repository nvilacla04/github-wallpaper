"""
Generate a GitHub contribution grid wallpaper for iPhone lock screen.
Pulls contributions via the GitHub GraphQL API and renders a PNG.
"""
import os
import sys
from datetime import date
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

# --- Config ----------------------------------------------------------------
CANVAS_W, CANVAS_H = 1290, 2796  # iPhone 15/16 Pro

# Layout — grid takes up most of the screen width
GRID_COLS = 21
SIDE_PADDING = 80                # left/right margin in pixels
GRID_TOP = 700                   # vertical start, below the clock

CELL_GAP_RATIO = 0.22            # gap as fraction of cell size
CELL_RADIUS_RATIO = 0.20         # rounded corners as fraction of cell size

# Dark theme: GitHub's actual dark-mode contribution colors
BG_COLOR = (0, 0, 0)
EMPTY_COLOR = (22, 27, 34)        # #161b22
LEVEL_COLORS = [
    (14, 68, 41),                 # #0e4429
    (0, 109, 50),                 # #006d32
    (38, 166, 65),                # #26a641
    (57, 211, 83),                # #39d353
]

# Footer text — uniform light grey/white
FOOTER_TEXT = (200, 200, 200)
LEGEND_TEXT = (140, 140, 140)


# --- GitHub API ------------------------------------------------------------
def fetch_contributions(username: str, token: str):
    today = date.today()
    year_start = f"{today.year}-01-01T00:00:00Z"
    year_end = today.isoformat() + "T23:59:59Z"

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """
    r = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": {
            "login": username, "from": year_start, "to": year_end
        }},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")

    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = []
    for week in cal["weeks"]:
        for d in week["contributionDays"]:
            days.append((d["date"], d["contributionCount"]))
    return days, cal["totalContributions"]


# --- Rendering -------------------------------------------------------------
def count_to_level(count: int, max_count: int) -> int:
    if count == 0:
        return 0
    if max_count <= 0:
        return 0
    ratio = count / max_count
    if ratio < 0.25:
        return 1
    if ratio < 0.5:
        return 2
    if ratio < 0.75:
        return 3
    return 4


def load_font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def render(days, total_contributions: int) -> Image.Image:
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    today = date.today()
    today_iso = today.isoformat()

    # Trim to today — don't render future days at all
    days_so_far = []
    for d, c in days:
        days_so_far.append((d, c))
        if d == today_iso:
            break

    n_days = len(days_so_far)
    if n_days == 0:
        return img

    # Compute cell size to fill the available width with the configured gap
    available_w = CANVAS_W - 2 * SIDE_PADDING
    cell_size = available_w / (GRID_COLS + (GRID_COLS - 1) * CELL_GAP_RATIO)
    cell_gap = cell_size * CELL_GAP_RATIO
    cell_radius = max(2, int(cell_size * CELL_RADIUS_RATIO))
    pitch = cell_size + cell_gap

    grid_w = GRID_COLS * cell_size + (GRID_COLS - 1) * cell_gap
    left = (CANVAS_W - grid_w) / 2

    counts = [c for _, c in days_so_far]
    max_count = max(counts) if counts else 0

    for i, (_, count) in enumerate(days_so_far):
        row = i // GRID_COLS
        col = i % GRID_COLS
        x0 = left + col * pitch
        y0 = GRID_TOP + row * pitch
        x1 = x0 + cell_size
        y1 = y0 + cell_size
        level = count_to_level(count, max_count)
        color = EMPTY_COLOR if level == 0 else LEVEL_COLORS[level - 1]
        draw.rounded_rectangle((x0, y0, x1, y1), radius=cell_radius, fill=color)

    # --- Footer text ------------------------------------------------------
    year_start = date(today.year, 1, 1)
    year_end = date(today.year, 12, 31)
    days_total = (year_end - year_start).days + 1
    days_passed = (today - year_start).days + 1
    days_left = days_total - days_passed
    pct = round(days_passed / days_total * 100)

    footer_y = CANVAS_H - 540
    f_small = load_font(40)

    # Top line
    line1 = f"{days_left}d left   ·   {pct}%"
    bbox = draw.textbbox((0, 0), line1, font=f_small)
    tw = bbox[2] - bbox[0]
    draw.text(((CANVAS_W - tw) // 2, footer_y), line1,
              font=f_small, fill=FOOTER_TEXT)

    # Legend
    legend_y = footer_y + 75
    legend_dot_size = 28
    legend_spacing = 44

    less_text = "Less"
    more_text = "More"
    less_w = draw.textbbox((0, 0), less_text, font=f_small)[2]
    more_w = draw.textbbox((0, 0), more_text, font=f_small)[2]
    legend_total_w = less_w + 24 + 5 * legend_spacing + 24 + more_w
    legend_x = (CANVAS_W - legend_total_w) // 2

    draw.text((legend_x, legend_y - 4), less_text, font=f_small, fill=LEGEND_TEXT)
    legend_x += less_w + 24

    for color in [EMPTY_COLOR] + list(LEVEL_COLORS):
        draw.rounded_rectangle(
            (legend_x, legend_y + 4,
             legend_x + legend_dot_size, legend_y + 4 + legend_dot_size),
            radius=6, fill=color,
        )
        legend_x += legend_spacing

    legend_x += 8
    draw.text((legend_x, legend_y - 4), more_text, font=f_small, fill=LEGEND_TEXT)

    # Bottom line
    line3 = f"Commits  ·  YTD: {total_contributions} Commits"
    bbox = draw.textbbox((0, 0), line3, font=f_small)
    tw = bbox[2] - bbox[0]
    draw.text(((CANVAS_W - tw) // 2, legend_y + 85), line3,
              font=f_small, fill=FOOTER_TEXT)

    return img


def main():
    username = os.environ["GH_USERNAME"]
    token = os.environ["GH_TOKEN"]

    print(f"Fetching contributions for {username}...", file=sys.stderr)
    days, total = fetch_contributions(username, token)
    print(f"Got {len(days)} days, {total} total contributions", file=sys.stderr)

    img = render(days, total)
    out = Path(__file__).parent / "wallpaper.png"
    img.save(out, "PNG", optimize=True)
    print(f"Wrote {out} ({out.stat().st_size} bytes)", file=sys.stderr)


if __name__ == "__main__":
    main()