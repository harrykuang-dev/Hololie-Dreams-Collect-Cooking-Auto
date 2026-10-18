# 開發說明

## 環境

使用Windows x64與Python 3.13。套件版本列於 `requirements.txt`，建置依賴列於 `requirements-build.txt`。CUDA可用時自動使用GPU，否則使用CPU。

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
```

需使用NVIDIA GPU時，依 [PyTorch官方版本安裝表](https://pytorch.org/get-started/previous-versions/#v280)安裝與本版對應的CUDA套件：

```powershell
.\.venv\Scripts\python.exe -m pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cu128
```

## 安裝模型

從v1.0.0 Release下載 `models.zip`，保留原檔名與壓縮包內路徑：

```powershell
gh release download v1.0.0 --repo harrykuang-dev/Hololie-Dreams-Collect-Cooking-Auto --pattern models.zip --dir downloads
.\.venv\Scripts\python.exe tools\install_models.py downloads\models.zip
.\.venv\Scripts\python.exe tools\check_runtime.py
```

安裝程式會先核對壓縮包及五個權重的SHA-256、檔案大小與允許路徑，再寫入缺少的檔案。若既有權重不同，先將該檔移至備份位置，再執行安裝。

| 權重 | 用途 |
| --- | --- |
| `outputs/kitchen-bot/segmenter-adapted.pt` | 主食材表面分割 |
| `outputs/kitchen-bot/icon-classifier.pt` | 食譜、槽位及外觀分類 |
| `outputs/kitchen-bot/segmenter-positive-surfaces.pt` | 按需補充分割 |
| `outputs/kitchen-labeler/point-classifier-resnet18.pt` | 標準點位分類器 |
| `outputs/kitchen-labeler/point-classifier-resnet101.pt` | 進階點位分類器 |

模型檔案位於Release附件，Git只保存安裝清單與指紋。

## 啟動與建置

```powershell
.\.venv\Scripts\pythonw.exe gui.py
```

建置時先啟用上述虛擬環境，確保PowerShell中的 `python` 指向已安裝CUDA套件的環境，再執行：

```powershell
.\.venv\Scripts\Activate.ps1
.\build.ps1
```

產物為 `dist/Collect-Cooking-Auto-v1.0.0/`。EXE與 `_internal` 需一起保留。建置腳本會複製README、文件、模型清單及第三方授權。

## 測試

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
.\.venv\Scripts\python.exe tools\check_runtime.py
```

測試涵蓋載入與開始分離、快捷鍵、Num Lock／Alt狀態、停止信號、診斷容量、座標換算、移動驗證與槽位變化。測試中的遊戲輸入介面使用替代物件。

封裝程式可只載入與暖機模型，核對後退出：

```powershell
.\Collect-Cooking-Auto-v1.0.0.exe --worker --model resnet18 --check-model-only --games 1 --output .\model-check\runs --control-file .\model-check\stop
```

將 `resnet18` 改成 `resnet101` 可核對進階模型。此命令不建立遊戲擷取或輸入介面，結果寫入 `model-check/model-check.json`。

## 診斷格式

GUI開發者模式在正常停止或例外結束後產生ZIP，上限20,000,000位元組。內容包含：

- `diagnostic.json`：版本、模型、環境、動作與等待原因統計、各食材累計分析耗時及刪減計數。
- `trace.jsonl`：近期辨識、規劃與耗時紀錄，容量上限4 MB。
- `inputs.jsonl`：近期輸入、補點及過場紀錄，容量上限1 MB。
- `image-index.json`：原畫面參照、JPEG路徑、原尺寸與儲存尺寸。
- `screenshots/`：近期採樣畫面、失敗追蹤畫面及結算畫面，最多100張、合計10 MB。
- `metadata/`：逐局摘要、執行檔案與模型指紋、擷取效能摘要。
- `launcher-tail.txt`：近期啟動紀錄。

截圖最長邊1536像素，以JPEG壓縮。一般畫面最多每2秒保留一張；三類畫面分別輪替，避免長批次只剩結算畫面。詳細內容以 `outputs/kitchen-bot/diagnostic_store.py` 的容量設定為準。診斷包不包含權重、原始碼副本或設定檔；Windows帳號路徑會替換為匿名參照。

一般模式不保存詳細截圖或辨識紀錄，結束後移除該次暫存資料。強制結束程序前尚未打包的記憶體紀錄無法恢復。

開發用直接CLI保留完整記錄入口：

```powershell
.\.venv\Scripts\python.exe outputs\kitchen-bot\standalone.py --point-model ../kitchen-labeler/point-classifier-resnet18.pt --games 5
```

此入口預設保存原生尺寸錄影及完整逐幀資料，容量需求與GUI診斷包不同。
