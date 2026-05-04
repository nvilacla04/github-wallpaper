# GitHub Contribution Wallpaper

Auto-generates an iPhone lock-screen wallpaper showing your GitHub year-to-date contribution grid, hosted free on GitHub Actions.

## Setup

### 1. Create the repo

Make a new **public** repo on GitHub (must be public so the raw PNG URL is accessible without auth) and push these files to it.

### 2. Create a Personal Access Token

The `GITHUB_TOKEN` available inside Actions can read public events but **cannot read private contribution data**. To include private repos in the count, create a classic PAT:

1. https://github.com/settings/tokens/new
2. Scope: `read:user` (and `repo` if you want private contributions counted)
3. Copy the token

### 3. Add it as a secret

Repo → Settings → Secrets and variables → Actions → New repository secret
- Name: `GH_PAT`
- Value: your token

### 4. Run it once

Actions tab → "Update wallpaper" → "Run workflow". After ~30s you should see `wallpaper.png` committed to the repo.

The raw URL will be:
```
https://raw.githubusercontent.com/<your-username>/<repo-name>/main/wallpaper.png
```

Open it in your phone browser to verify it looks right.

### 5. iOS Shortcut

Open Shortcuts → Automation → New → Time of Day → 6:00 AM → Run Immediately.

Add actions:
1. **Get Contents of URL** → paste the raw URL above
2. **Set Wallpaper** → use "Contents of URL", lock screen, "Show Preview" off (if your iOS version allows)

> Note: iOS 16+ may force a confirmation dialog. There's no clean workaround — just tap through, or check current status of `Set Wallpaper` permissions for your iOS version.

## Customization

Edit `generate.py`:
- `CANVAS_W`, `CANVAS_H` — change for different iPhone models
- `GRID_TOP` — vertical position of the grid
- `LEVEL_COLORS` — change the green palette
- `cols` inside `render()` — grid width (currently 21)

## Local testing

```bash
pip install Pillow requests
GH_USERNAME=your-username GH_TOKEN=ghp_xxx python generate.py
open wallpaper.png
```
