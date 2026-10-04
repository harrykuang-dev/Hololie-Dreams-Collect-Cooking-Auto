# Hololie-Dreams-Collect-Cooking-Auto

[English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

An experimental, local Windows auto-player for **Collect Cooking** in hololive DREAMS. The game is called **拼配厨房** in Simplified Chinese and **食材妙厨房** in Traditional Chinese. The repository name preserves the requested spelling, `Hololie-Dreams-Collect-Cooking-Auto`.

The gameplay baseline is **`e323dd962ed18ef1`**, the latest version tested over five games. It uses screenshots, neural image recognition, a persistent match-three planner, optical flow, and native mouse input. There is no language-model call in the gameplay loop, game-memory reading, process injection, or modification of game files.

## Portable Windows release (v0.2.0)

Download the complete portable archive from [Releases](https://github.com/harrykuang-dev/Hololie-Dreams-Collect-Cooking-Auto/releases/tag/v0.2.0), extract it, then double-click `Collect-Cooking-Auto-v0.2.0.exe` inside the extracted folder. Keep `_internal` beside the EXE. Python, installation and separate model downloads are unnecessary. CUDA libraries and all checkpoints are bundled; NVIDIA GPU inference is retained, with CPU fallback. If the archive is split into `.7z.001`, `.7z.002`, etc., download all parts into the same folder and extract `.001` using 7-Zip.

The light Windows interface follows [Hololive-Dreams-Fishing-Auto](https://github.com/harrykuang-dev/Hololive-Dreams-Fishing-Auto). Choose English/Simplified/Traditional Chinese, enter a positive game count and optionally enable video recording. Click **Start** to prepare models, then return to the game and press the start/pause shortcut (default **F8**). Pressing the shortcut while the app is idle loads models and starts automatically if the game remains foreground. The stop shortcut (default **Esc**) or **Stop** ends the batch. Click a shortcut field and press a new key or Ctrl/Alt/Shift combination; overlapping shortcuts are rejected. Shortcuts can be changed while idle. Closing the launcher requests a graceful stop and waits for the worker.

Settings and logs are saved in `%LOCALAPPDATA%/CollectCookingAuto`. Video is off by default; capture stays at 20 FPS. The completed-game count indicates batch progress, not a verified dish count. Source users can run `pythonw gui.py`; `Launch.cmd` uses the same frontend. Shortcut helpers are reused under the fishing project's MIT license; attribution is in [third-party/README.md](third-party/README.md).

This release packages the previous gameplay logic with launcher/control changes. The five-game results below describe the original runtime, not a new benchmark of v0.2.0. Current package fingerprints are in [docs/packaged-runtime.json](docs/packaged-runtime.json); historical test fingerprints remain unchanged. Build using `pip install -r requirements-build.txt` and `./build.ps1` after installing models; use a CUDA-enabled torch build to retain GPU support. The frontend and model inference run in separate processes; a local stop signal is checked before clicks and during transitions.

## Status and actual results

| Fixed-version batch | Completed dishes in five games | Mean | Median | Range | Endings |
| --- | --- | ---: | ---: | --- | --- |
| Best recorded batch, `18e2ddb6c76d8c2f` | 11, 8, 9, 8, 9 | **9.0** | 9 | 8–11 | Five timeouts |
| Latest tested gameplay, `e323dd962ed18ef1` | 10, 8, 6, 7, 9 | **8.0** | 8 | 6–10 | Four timeouts, one tray overflow |

Every listed result was checked against the game's final result screen; these are not just internal planner counters. The development target, five games averaging at least **9.79 dishes** (an integer total of at least 49), has **not** been achieved. A single ten-dish game is not evidence of consistent ten-dish performance. These random batches do not establish that the newer version improves or worsens the baseline. Sanitized results and fingerprints are in [docs/verified-batches.json](docs/verified-batches.json) and [docs/tested-runtime.json](docs/tested-runtime.json).

The latest version retains the best batch's learned weights and primary planner. It adds timing diagnostics, rate-limited lossless failure-frame pairs, and a guarded local re-detection fallback. In its five-game batch, that fallback dispatched four food clicks; three had a subsequent target-counter decrease before another food input, and one remained unconfirmed. That is supporting feedback, not proof of the exact object selected by the game's collider.

## Install

Tested environment: Windows, Python **3.13**, PyTorch **2.8.0+cu128**, torchvision **0.23.0+cu128**, and an NVIDIA RTX 4070 Laptop GPU. CPU inference is supported by device selection, but equivalent gameplay speed/results have not been validated. The implementation assumes the observed 16:9 game layout; arbitrary aspect ratios, UI changes, and all translations have not been verified.

From the repository root, in PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
gh release download v0.1.0 --repo harrykuang-dev/Hololie-Dreams-Collect-Cooking-Auto --pattern models.zip --dir downloads
.\.venv\Scripts\python.exe tools\install_models.py downloads\models.zip
.\.venv\Scripts\python.exe tools\check_runtime.py
```

The package pins match the tested Python packages; the default PyTorch wheel selected by your package index may differ in CUDA support. The runtime automatically chooses CUDA when available, otherwise CPU. `gh` is only used to download the model archive: alternatively download `models.zip` from [Releases](https://github.com/harrykuang-dev/Hololie-Dreams-Collect-Cooking-Auto/releases/tag/v0.1.0) in a browser and pass its local path to the installer. Weights are release assets, not large Git blobs. The installer checks the archive and every checkpoint against SHA-256 before installation.

## Run

1. Open Collect Cooking and choose **SCORE ATTACK**. Ordinary mode also has a timer and is not the ten-dish evaluation mode.
2. Double-click `Launch.cmd`, or run `.\.venv\Scripts\pythonw.exe gui.py`.
3. Enter a positive game count, click **Start**, wait for **Ready**, return to the game and press **F8**. The player can advance from its result screen, kitchen menu, or Order screen using fixed-layout buttons.
4. Keep the game in the foreground and avoid concurrent mouse/keyboard use. **F8** pauses/resumes; **Escape** stops. Switching focus pauses gameplay input; return to the game and press F8 to resume.
5. Review the saved result screen and logs after each batch. This is a development player, not a guaranteed unattended ten-dish solution.

Equivalent CLI entry:

```powershell
.\.venv\Scripts\python.exe outputs\kitchen-bot\standalone.py --point-model ../kitchen-labeler/point-classifier-human.pt --games 5 --fps 20
```

The GUI selects the human-trained point model automatically when installed. Direct CLI use must specify that model as above to reproduce the tested version; the historical default `point-classifier.pt` is different. `--seconds` limits each gameplay run (default 300); `--diagnostic-lossless-interval` controls the minimum interval between failed-tracking PNG pairs (default 2 seconds). `--replay PATH` analyzes an existing image without creating the desktop input/capture adapter; replay does not validate real clicks.

## Technical implementation

### Capture and coordinates

`standalone.py` captures the Windows game client area using **GDI**, calls **SendInput** for mouse clicks, and polls F8/Escape locally. Capture and MP4 encoding run in a background thread at requested **20 FPS**, separately from inference. Frame publication uses a condition variable. Captured frames are normalized to **1536×864**; native coordinates use the measured scale and top offset. The board is cropped at `(318,175)–(1215,735)` and resized to **448×280** for semantic segmentation. Desktop input is guarded by game focus.

20 FPS is the requested capture rate, not a promise of twenty decisions per second. Host capture-start and mouse-dispatch timestamps are measured; they are not Unity exposure or input-receipt timestamps.

### Recognition

- **Visible-surface segmentation:** `segmenter.py` defines a small U-Net-style encoder/decoder (24/48/96/160 channels, skip connections), producing **31 classes: 30 foods plus background**. Connected components identify visible patches. A confidence-weighted distance transform chooses an interior candidate point, rather than a bounding-box center that may land on an overlapping ingredient.
- **Appearance classification:** `icon_classifier.py` uses **ResNet18**, a 31-class head, and 96×96 input crops. One checkpoint reads recipe/tray icons and object context; the human-trained point checkpoint verifies a **64×64 canonical crop around the exact proposed click point**. Its softmax score is a gate, not a calibrated probability of click success.
- **Order/state reading:** digit templates and color/component tests read order number, remaining counts, and completion checkmarks. Fixed UI artwork detects order overlays, dish completion, results, curtains, and overflow. Dish-completion detection uses corner ornaments rather than translated dish text; this reduces language dependence without proving every language/layout works.
- **Transparent containers:** the baseline prefers the colored lid of the bean-sprout jar instead of treating its transparent body as a clickable surface.

Training began with synthetic views rendered from locally extracted ingredient meshes/textures, then used real screenshots and human point/polygon labels. Game meshes, the full extraction, and the private annotation/training corpus are **not included**. The release provides trained checkpoints, not a complete reproducible training dataset. Later difficult-food retraining candidates that failed old-class retention checks were rejected; they are not silently deployed here. Only the small ingredient icon set required by the existing template fallback and UI/digit templates are included.

### Planning and click verification

`planner.py` retains the recipe, order, seven-slot tray estimate, pending input, rejected locations, and shuffle state between decisions. It prefers required ingredients and completing already collected pairs. Required pickups are checked through remaining-counter changes; rendered tray observations correct inventory estimates. When targets are hidden, shuffle readiness is read from the rendered button rather than assuming a cooldown. High-confidence non-target triples can free space when there is sufficient room. This feedback can still be ambiguous during animation.

`motion.py` tracks a 3×3 point grid with pyramidal **Lucas–Kanade optical flow** and forward/backward consistency checks. It rejects insufficient tracks, inconsistent movement, stale frame gaps, excessive prediction, or out-of-bounds points. A nearly unchanged flat patch can be treated as stationary. Prediction includes capture age, cursor settling, and a render allowance. `latest_click.py` checks phase/order and classifies **both the observed and predicted point** in the latest frame. Crowded trays and selected narrow/clearing picks use stricter gates. Limited follow-up clicks retain their own fresh-frame checks.

`supplemental_food.py` adds separate human-surface models for **onion/shrimp/tuna**, only when the original route has no food action. It preserves the original approved route and requires strong agreement again on a fresh frame.

### Latest local re-detection fallback

`guarded_local_relocation.py` runs only after the primary latest-frame food check returns `wait`. It tries the **first rejected required primary food**, not a non-target clearing pick or the separate supplement route. `local_relocation.py` re-segments an aligned **160×160 ROI at the original board pixel scale**. Crop-edge components, small/weak patches, distant points, and transparent bean-sprout jars are excluded.

The candidate must pass a copy of the original planner, including its recent bad-point history. After inference, the fallback explicitly requests **another capture**, requires unchanged phase/order/counters/tray, applies the original flow limits, and requires **≥0.995 point-class agreement** at both observed and predicted locations. It checks a **150 ms host frame-age cap** through verification and before dispatch, and disables follow-up clicks for this route. Native cursor movement adds further time after the pre-dispatch check; the cap is not an exact game-frame freshness guarantee.

## Files, models, and diagnostics

| Path | Purpose |
| --- | --- |
| `outputs/kitchen-bot/standalone.py` | Capture/input loop, fixed-version batches, logging |
| `perception.py`, `segmenter.py`, `icon_classifier.py` | Surface, point, recipe and tray recognition |
| `planner.py`, `shuffle_state.py` | Persistent match-three decisions and shuffle gating |
| `motion.py`, `motion_click.py`, `latest_click.py` | Track, predict and validate food clicks |
| `supplemental_food.py` | Separate difficult-food fallback |
| `local_relocation.py`, `guarded_local_relocation.py` | Latest guarded local re-detection |
| `outputs/kitchen-assets/textures/` | Minimal ingredient icons used by template matching |
| `models-manifest.json` | Release checkpoint paths, sizes and SHA-256 |
| `tests/` | Offline coordinate and state/timestamp rejection checks |

Installed active weights: `segmenter-adapted.pt`, `icon-classifier.pt`, `segmenter-positive-surfaces.pt`, `point-classifier-human-paired.pt`, and `outputs/kitchen-labeler/point-classifier-human.pt`. The archive also includes historical `segmenter.pt` and `point-classifier.pt` fallbacks. `render_samples.py`, `vision.py`, and `worker.py` are retained historical/support modules; the synthetic renderer requires the separate local 3D asset corpus. The standalone player does **not** require Codex or Computer Use.

Launcher runs save under `%LOCALAPPDATA%/CollectCookingAuto/launch-…/runs/`; direct CLI runs default to `outputs/kitchen-bot/runs/`. Diagnostics include decision images, `final.jpg`, JSONL and summaries. MP4 is optional in the GUI (off by default); direct CLI recording defaults to on. Private runs and annotation data are excluded from the public repository.

Offline checks:

```powershell
.\.venv\Scripts\python.exe tests\test_local_relocation_coordinates.py
.\.venv\Scripts\python.exe tests\test_guarded_local_relocation.py
```

These checks exercise coordinate mapping, crop boundaries, primary-action preservation, stale capture rejection, inventory/state changes, tracking rejection, and strict point confirmation. They do not replace actual five-game testing. Remaining issues include occlusion/collider mismatch, recognition that looks correct before dispatch but does not pick the intended object, and slow/failed tracking of some foods. Current recordings lack a complete per-video-frame capture timestamp index; precise dispatch-to-video alignment is a proposed diagnostic improvement, not an implemented feature.

This is an independent experimental project, not an official hololive DREAMS product. Game names and artwork belong to their respective owners.
