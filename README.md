# Hololive Dreams Auto Collect Cooking — 1.1.0

[English](README.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Indonesian](README.id.md) · [简体中文](README.zh-CN.md)

A cooking program for Collect Cooking in the Windows version of *hololive Dreams*. It recognizes ingredients from the game screen, selects food through ordinary mouse input, and continues with another game after the result screen.

## Download

Open [GitHub Releases](https://github.com/harrykuang-dev/Hololive-Dreams-Collect-Cooking-Auto/releases/tag/v1.1.0) and download every `Collect-Cooking-Auto-v1.1.0-win64.7z.*` part into the same folder. Extract `.7z.001` with 7-Zip, then run `Collect-Cooking-Auto-v1.1.0.exe` inside the extracted folder.

Keep `_internal` beside the EXE. Python, the inference libraries and all five model checkpoints are included. `SHA256SUMS.txt` verifies the downloads; `models.zip` is for source users. GitHub's source ZIP requires installing dependencies and models separately.

## Features

- Recognizes recipe ingredients, remaining quantities and tray contents, then plans ingredient picks, clearing triples and plate shuffles.
- Two recognition options: **Standard** (ResNet18) and **Advanced** (ResNet101). Standard has lower computing requirements; Advanced suits more powerful PCs.
- Model loading and gameplay start are separate. The loaded point classifier also verifies on-demand supplemental candidates.
- Configurable game target, with automatic continuation after a completed game.
- Six interface languages: English, Traditional Chinese, Japanese, Korean, Indonesian and Simplified Chinese. The language choice applies to the program interface.
- Custom shortcuts, activity log and optional local developer diagnostics.

## Usage

1. Open the game and enter Collect Cooking.
2. Run the EXE, choose a program language and recognition model, and enter a positive game target. The initial target is five games.
3. Click **Load model** and wait for the ready message.
4. Click **Start** to have the program attempt to restore and bring the game to the foreground, or press **F8** in the game. If Windows blocks the switch, return to the game manually. Keep its window unobstructed.
5. **F8** pauses/resumes; **Esc** or **Stop** ends the run. A focus change pauses input; return to the game and press F8 to resume. Stop before selecting and loading another model.

Click a shortcut field, then press the desired key or Ctrl/Alt/Shift combination. Leaving the field without completing a shortcut preserves the previous setting. Settings are saved for the next launch.

## Requirements and limitations

Requires Windows 10/11 x64 and the Windows game client. Use a 16:9 client area; keep the display on and the game visible. One complete package includes all inference libraries and one shared set of FP32 ONNX models. Compatible NVIDIA GPUs automatically use TensorRT; other supported DirectX 12 GPUs use DirectML, with CPU as the final fallback. CPU or low-performance GPUs may not meet the click timing requirements.

The extracted portable folder uses about 2.9 GB; allow additional space for the downloaded archive and extraction. The completed-game counter shows batch progress. Read dish counts and scores from the game's result screen. Motion, occlusion, computer performance and game updates can affect recognition.

## Technical implementation

### Capture and image processing

The [capture module](outputs/kitchen-bot/async_recording.py) acquires the game client area through Windows GDI on an independent thread, requesting 20 frames per second. It publishes recent frames to recognition without waiting for video encoding. The [recognition pipeline](outputs/kitchen-bot/perception.py) normalizes images to 1536×864 and segments a 448×280 board crop. Click coordinates are mapped back through the measured scale and vertical offset.

### Ingredient recognition and model sharing

The main surface segmenter proposes visible ingredient regions. The selected point classifier checks a 64×64 crop around each click, resized to 96×96 for inference. A shared icon classifier reads recipe and tray contents; digit templates and fixed UI artwork provide quantities and screen state.

When the main route would wait or shuffle, the [supplemental locator](outputs/kitchen-bot/supplemental_food.py) can propose onion, fried-shrimp and tuna-can candidates. These use the already loaded point classifier for verification. Only the selected Standard or Advanced point classifier is loaded. See [model details](docs/model-options.md).

### Planning and shuffle timing

The [planner](outputs/kitchen-bot/planner.py) retains the recipe, tray estimate, pending picks and rejected locations between frames. It prioritizes required ingredients and completing triples. Target-counter changes and visible tray contents provide feedback. Shuffles require at least five seconds between actual button presses and a ready button in a recent frame.

### Motion validation and continuation

[Optical flow](outputs/kitchen-bot/motion.py) tracks local movement before dispatch. [Fresh-frame verification](outputs/kitchen-bot/latest_click.py) checks the order, screen state and food class at observed and predicted points. A guarded local relocation can retry a required ingredient after failed tracking. [Session control](outputs/kitchen-bot/session_flow.py) recognizes the bottom-right continuation button to move from results and menus to the next game.

## Bug reports and developer mode

Report recognition, clicking or continuation problems through [GitHub Issues](https://github.com/harrykuang-dev/Hololive-Dreams-Collect-Cooking-Auto/issues). Enable **Developer mode** before reproducing the problem. It saves recognition results, click timing, game screenshots and performance summaries locally. Enabling it adds processing overhead; data is not uploaded automatically.

Click the adjacent `?` to view and open the diagnostics folder:

```text
%LOCALAPPDATA%\CollectCookingAuto\sessions\
```

A dated ZIP is created when the run ends. Include the program version, selected model, game language, resolution, Windows display scaling, problem description and diagnostic ZIP.

Developer mode permanently retains every round’s verified score, dish count, click events, decisions, wait reasons and timings in JSONL files. Result screenshots and ordinary screenshots share oldest-first capacity eviction; `image-index.json` lists retained images. Unconfirmed result numbers remain null with an explanation. Each diagnostic ZIP has a hard limit of 20 MB. Text-only overflow is split into multiple ZIPs, while complete original text files remain on disk.

## Source and notices

Source startup, building and tests are in the [development guide](docs/DEVELOPMENT.md). The [version history](docs/VERSION_HISTORY.md), [model details](docs/model-options.md) and [game terminology](docs/GAME_TERMS.md) provide further reference.

Third-party notices are in [third-party](third-party/README.md). Game names and artwork belong to their respective rights holders.
