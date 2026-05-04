"""
Generate a GitHub contribution grid wallpaper for iPhone lock screen.
Pulls contributions via the GitHub GraphQL API and renders a PNG.
"""
import os
import sys
from datetime import date, datetime
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

# --- Config ----------------------------------------------------------------
CANVAS_W, CANVAS_H = 1290, 2796  # iPhone 15/16 Pro

# Grid placement: positioned in the upper-middle band so it sits below the
# clock and above the bottom widgets on the lock screen.
GRID_TOP = 900
GRID_LEFT_MARGIN = 130  # auto-centered, but used as a min margin

DOT_RADIUS = 14
DOT_SPACING = 36  # center-to-center

# Dark theme: GitHub's actual dark-mode contribution colors
BG_COLOR = (0, 0, 0)
EMPTY_COLOR = (22, 27, 34)        # #161b22
LEVEL_COLORS = [
    (14, 68, 41),                  # #0e4429
    (0, 109, 50),                  # #006d32
    (38, 166, 65),                 # #26a641
    (57, 211, 83),                 # #39d353
]

# Footer text colors (muted red/orange like screenshot)
FOOTER_RED = (220, 80, 60)
FOOTER_GREEN = (57, 211, 83)
FOOTER_GREY = (140, 140, 140)


# --- GitHub API ------------------------------------------------------------
def fetch_contributions(username: str, token: str):
    """Return list of (date, count) for the current calendar year."""
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
    """Map contribution count to 0-4 (0 = empty)."""
    if count == 0:
        return 0
    # GitHub's bucketing is roughly quartile-based on the user's own max
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
    """Try to load a real font, fall back to default."""
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


def draw_dot(draw: ImageDraw.ImageDraw, cx: int, cy: int, color):
    draw.ellipse(
        (cx - DOT_RADIUS, cy - DOT_RADIUS, cx + DOT_RADIUS, cy + DOT_RADIUS),
        fill=color,
    )


def render(days, total_contributions: int) -> Image.Image:
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Pad the days list to a full year (366 to be safe) so future days
    # render as empty dots — grid stays the same size all year, only the
    # filled portion grows over time.
    today = date.today()
    year_start = date(today.year, 1, 1)
    year_end = date(today.year, 12, 31)
    days_total = (year_end - year_start).days + 1

    today_iso = today.isoformat()
    today_idx = next(
        (i for i, (d, _) in enumerate(days) if d == today_iso), len(days) - 1
    )

    while len(days) < days_total:
        days.append(("", 0))

    # 21 columns to match the screenshot's aspect ratio
    cols = 21
    rows = (len(days) + cols - 1) // cols

    grid_w = cols * DOT_SPACING
    left = (CANVAS_W - grid_w) // 2 + DOT_RADIUS

    # Use only the filled-in days for max calculation
    counts = [c for _, c in days[:today_idx + 1]]
    max_count = max(counts) if counts else 0

    for i, (day_str, count) in enumerate(days):
        row = i // cols
        col = i % cols
        cx = left + col * DOT_SPACING
        cy = GRID_TOP + row * DOT_SPACING
        # Future days always empty
        if i > today_idx:
            color = EMPTY_COLOR
        else:
            level = count_to_level(count, max_count)
            color = EMPTY_COLOR if level == 0 else LEVEL_COLORS[level - 1]
        draw_dot(draw, cx, cy, color)

    # --- Footer text ------------------------------------------------------
    today = date.today()
    year_start = date(today.year, 1, 1)
    year_end = date(today.year, 12, 31)
    days_total = (year_end - year_start).days + 1
    days_passed = (today - year_start).days + 1
    days_left = days_total - days_passed
    pct = round(days_passed / days_total * 100)

    # Position above the bottom lock-screen widget area (flashlight/camera)
    footer_y = CANVAS_H - 540

    f_small = load_font(36)
    f_med = load_font(40, bold=True)

    # Top line: "268d left   26%"
    line1 = f"{days_left}d left   ·   {pct}%"
    bbox = draw.textbbox((0, 0), line1, font=f_small)
    tw = bbox[2] - bbox[0]
    draw.text(((CANVAS_W - tw) // 2, footer_y), line1,
              font=f_small, fill=FOOTER_RED)

    # Legend: "Less ▢▢▣▣▤ More"
    legend_y = footer_y + 70
    legend_dot_r = 14
    legend_spacing = 42
    legend_total_w = 5 * legend_spacing + 200
    legend_x = (CANVAS_W - legend_total_w) // 2

    less_text = "Less"
    bbox = draw.textbbox((0, 0), less_text, font=f_small)
    draw.text((legend_x, legend_y - 4), less_text, font=f_small, fill=FOOTER_GREY)
    legend_x += bbox[2] - bbox[0] + 24

    legend_colors = [EMPTY_COLOR] + list(LEVEL_COLORS)
    for color in legend_colors:
        draw.ellipse(
            (legend_x, legend_y + 4,
             legend_x + legend_dot_r * 2, legend_y + 4 + legend_dot_r * 2),
            fill=color,
        )
        legend_x += legend_spacing

    legend_x += 8
    draw.text((legend_x, legend_y - 4), "More", font=f_small, fill=FOOTER_GREY)

    # Bottom line: "Commits · YTD: N Commits"
    line3 = f"Commits  ·  YTD: {total_contributions} Commits"
    bbox = draw.textbbox((0, 0), line3, font=f_small)
    tw = bbox[2] - bbox[0]
    draw.text(((CANVAS_W - tw) // 2, legend_y + 80), line3,
              font=f_small, fill=FOOTER_RED)

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
