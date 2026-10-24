# Cooking annotation dataset

[繁體中文](#繁體中文)

Human annotations and their images for retraining the cooking recognition models. Images are copied without recompression. Image files are addressed by SHA-256 and shared between records, so repeated references do not duplicate images.

## Contents

- `classification/samples.jsonl`: 15,631 human-reviewed point samples. The 15,627 confirmed samples have one of 31 labels, including background. The remaining four are `uncertain`, have `split: excluded`, and are excluded from training.
- `classification/splits/`: the original train, validation and development-test sample IDs. IDs, labels, crop hashes and split assignments match the frozen dataset used to train the released point classifiers.
- `labels.json`: output-class order, stable English label IDs and Traditional Chinese names.
- `images/`: original crop PNGs, point-context images, board references and available legacy review images. Files are grouped by hash prefix.
- `image-index.jsonl`: image path, SHA-256, size and dimensions.
- `legacy/point_reviews.jsonl`: 327 earlier point reviews, already included in the primary classification dataset. `current_sample_ids` links them to current samples. Do not append them again as additional training examples.
- `legacy/click_reviews.jsonl`: 67 earlier click reviews, including visible/actual food, point safety and occlusion judgments. Available verified frames are included; unavailable before/after images are explicitly null. These are not independent training examples by default.
- `segmentation/`: preserved board proposals and 17 human question responses. Original confirmation flags remain intact. `reviewed: true` does not mean human confirmation. The polygons have not been established as a fully human-verified segmentation ground truth; review them before training a segmentation model.
- `training-config.json`, `training_policy.py`: input conventions, optimization settings and validation-based continuation policy.
- `manifest.json`, `statistics.json`: file integrity information and dataset coverage.

Latest active labels are exported. Withdrawn label history, local SQLite settings, synchronization accounts and model guesses are not exported as ground truth. Missing auxiliary review images are recorded explicitly. Game images and artwork remain the property of their respective rights holders.

## Validate

From the repository root:

```powershell
python -m pip install Pillow
python annotations/validate_dataset.py
```

The validator checks hashes, image readability, references, label validity and split leakage. It fails if the same source game or identical crop appears in different classification splits.

## Retrain a classifier

Install the PyTorch build appropriate for the training machine and the versions in `requirements-training.txt`, preferably in a separate virtual environment. These training dependencies are separate from the player runtime.

```powershell
python -m pip install -r annotations/requirements-training.txt
python annotations/train_classifier.py --architecture resnet18 --output outputs/retraining/resnet18
```

Supported architectures: `resnet18`, `resnet34`, `resnet50`, `resnet101`, `resnet152`. Default initialization is torchvision ImageNet1K V1; downloading its weights requires network access. `--initialization random` starts without pretrained weights and is a different experiment.

Inputs match the existing point classifiers: original 64×64 crops, OpenCV linear resize to 96×96, BGR channel order, CHW float32 divided by 255. Do not apply RGB conversion or ImageNet mean/std normalization when reproducing these inputs. Training uses horizontal flips, brightness scaling, weighted cross-entropy, AdamW and the recorded learning-rate schedule.

By default, training runs for at least 60 and at most 200 epochs. After the minimum, it stops when the three-epoch mean validation macro recall has not improved by 0.002 for 30 epochs. `--max-epochs` can set a lower cap. Best-checkpoint selection uses raw validation macro recall, with fewer mistakes at confidence ≥0.995 breaking ties. The development-test split is evaluated only after selection; it is an existing development benchmark, not a newly collected final holdout.

`best.pt`, `last.pt`, `history.json` and `result.json` are written to the output directory. Each invocation starts a fresh model and optimizer. Ctrl+C preserves checkpoints from completed epochs; the example does not automatically resume a previous run. The example preserves data and preprocessing conventions, but does not guarantee bitwise-identical weights across hardware or framework versions. No training starts when downloading or validating this dataset.

Point coordinates are in the canonical 1536×864 game frame. Classification board/context images are visual references; use `crop` as the classifier input. Legacy records retain native points and scale when available. Segmentation polygons use the coordinate system of their associated board image; they must not be mixed with canonical game coordinates.

Keep source games together if changing splits. Do not mix legacy duplicates, context images or unconfirmed polygons into another split and report the result as an independent test.

## 繁體中文

這個資料夾包含料理辨識的人工標註及對應圖片，供重新訓練與評估使用。圖片直接複製，沒有重新壓縮；以SHA-256共用相同圖片。

- 分類資料共15,631筆人工判讀，其中15,627筆可用於訓練、4筆為「不確定」。模型輸出共31類，包含背景；不確定不是模型類別。
- 保留正式點位分類器訓練時使用的樣本ID、標籤、裁片雜湊及訓練／驗證／開發測試切分。
- 早期327筆點位標註已包含於主資料，請勿再次加入而造成重複或跨集合洩漏。
- 保留67筆歷史點擊判讀及17筆棋盤人工問答。缺少的輔助前後畫面明確記為null；現存判讀畫面一併提供。
- 棋盤輪廓保留原確認狀態。`reviewed: true`不等於人工確認，不能把這些自動輪廓直接視為已完成的人工分割標籤。

在儲存庫根目錄執行上方驗證及訓練指令即可。訓練需另裝PyTorch環境，不會增加玩家版依賴。範例支援ResNet18／34／50／101／152，預設採ImageNet1K V1初始化，每次執行從新模型與新最佳化器開始。

輸入為原始64×64裁片，線性縮放至96×96，以BGR、CHW、float32除以255處理；不要額外轉RGB或套用ImageNet平均值／標準差。訓練至少60輪、最多200輪，依三輪平滑後的驗證macro recall判斷是否繼續；連續30輪沒有0.002的改善便停止。最佳模型依原始驗證macro recall選擇，開發測試集只在選完後評估。

「不確定」、已撤銷歷史與模型猜測不會混入有效訓練標籤。本機路徑、同步帳號及SQLite設定未包含在公開資料內。遊戲畫面與美術素材的權利歸各自權利人所有。
