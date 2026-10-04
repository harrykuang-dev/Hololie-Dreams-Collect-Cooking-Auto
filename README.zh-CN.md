# Hololie-Dreams-Collect-Cooking-Auto

[English](README.md) · [简体中文](README.zh-CN.md) · [繁體中文](README.zh-TW.md)

hololive DREAMS 小游戏 **Collect Cooking** 的 Windows 本地自动游玩实验程序。游戏简体名称为 **拼配厨房**，繁体名称为 **食材妙厨房**。仓库名称保留指定拼写 `Hololie-Dreams-Collect-Cooking-Auto`。

料理逻辑基于最新经过五局实战测试的 **`e323dd962ed18ef1`**。程序结合截图、神经网络图像识别、持续保存状态的三消规划、光流追踪和本地鼠标输入。游戏循环不调用语言模型，不读取游戏内存，不注入游戏进程，也不修改游戏文件。

## Windows 便携版（v0.2.0）

从 [Release](https://github.com/harrykuang-dev/Hololie-Dreams-Collect-Cooking-Auto/releases/tag/v0.2.0) 下载完整便携包，解压后双击文件夹中的 `Collect-Cooking-Auto-v0.2.0.exe`。保留旁边的 `_internal` 文件夹。已包含 Python 运行环境、CUDA 库与全部模型，无需另装 Python 或下载模型。保留 NVIDIA GPU 推理并支持 CPU 回退。如果发布包分为 `.7z.001`、`.7z.002` 等，请下载所有分卷到同一文件夹，再用 7-Zip 解压 `.001`。

前端参考 [Hololive-Dreams-Fishing-Auto](https://github.com/harrykuang-dev/Hololive-Dreams-Fishing-Auto) 的浅色 Windows 布局。支持英／简／繁三种界面语言，局数自行填写正整数，录像默认关闭。点击「开始」加载模型，再切回游戏按开始／暂停键（默认 **F8**）。在程序待命时直接按该热键，会加载模型并在游戏仍位于前台时自动开始。「停止」按钮或停止键（默认 **Esc**）结束整批。点击热键输入框后按新的按键，可带 Ctrl／Alt／Shift；拒绝重叠的热键，运行时不能修改。关闭前端会请求正常停止并等待工作进程退出。

设置与日志保存在 `%LOCALAPPDATA%/CollectCookingAuto`。关闭录像仍保持 20 FPS 截图。已完成局数表示批次进度，并非已核验料理数。源码可用 `pythonw gui.py` 或 `Launch.cmd` 启动相同前端。快捷键辅助代码按钓鱼项目的 MIT 许可复用，来源见 [third-party/README.md](third-party/README.md)。

本次加入前端、打包与控制功能，沿用此前已测料理逻辑。下方五局成绩属于原实测版，并非 v0.2.0 的新实战成绩。当前包指纹见 [docs/packaged-runtime.json](docs/packaged-runtime.json)，历史指纹保留原值。安装模型后，使用 `pip install -r requirements-build.txt` 与 `./build.ps1` 打包；需使用支持 CUDA 的 torch 环境以保留 GPU 功能。前端与模型推理分进程运行，停止请求通过本地控制文件传递，并在点击前及过场期间检查。

## 当前状态与真实成绩

| 固定版本五局 | 每局完成料理数 | 平均 | 中位数 | 范围 | 结束原因 |
| --- | --- | ---: | ---: | --- | --- |
| 最佳记录版 `18e2ddb6c76d8c2f` | 11、8、9、8、9 | **9.0** | 9 | 8–11 | 五局时间到 |
| 最新实测料理版 `e323dd962ed18ef1` | 10、8、6、7、9 | **8.0** | 8 | 6–10 | 四局时间到、一局爆槽 |

上述成绩逐局核对了游戏结算画面，并非仅采用程序内部计数。开发目标是五局平均至少 **9.79 道**，即整数总和至少 49；**尚未达成**。单局十道不代表稳定每局十道。两批随机五局也不能证明新版本改善或导致退步。去除个人路径后的数据见 [docs/verified-batches.json](docs/verified-batches.json)，已测运行版指纹见 [docs/tested-runtime.json](docs/tested-runtime.json)。

最新版本沿用最佳记录版的模型权重与主规划器，新增时序诊断、限频无损失败画面，以及局部重新定位补充路径。该路径在五局中实际点击四次，三次在下一个食材输入前观察到目标需求减少，一次尚未确认。这只是反馈证据，不能证明游戏碰撞系统实际选中了哪个物体。

## 安装

已测环境：Windows、Python **3.13**、PyTorch **2.8.0+cu128**、torchvision **0.23.0+cu128**、RTX 4070 Laptop GPU。程序可自动选择 CPU，但尚未验证 CPU 下能获得同等实时速度和游戏成绩。实现依赖已观察到的 16:9 游戏布局，任意宽高比、UI 改版和所有语言布局均未验证。

在仓库根目录打开 PowerShell：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
gh release download v0.1.0 --repo harrykuang-dev/Hololie-Dreams-Collect-Cooking-Auto --pattern models.zip --dir downloads
.\.venv\Scripts\python.exe tools\install_models.py downloads\models.zip
.\.venv\Scripts\python.exe tools\check_runtime.py
```

依赖版本对应实测 Python 环境；默认包源提供的 PyTorch 安装包，其 CUDA 支持可能不同。检测到可用 CUDA 就使用 GPU，否则使用 CPU。`gh` 仅用于下载权重，也可以在浏览器中从 [Release](https://github.com/harrykuang-dev/Hololie-Dreams-Collect-Cooking-Auto/releases/tag/v0.1.0) 下载 `models.zip`，再把本地路径交给安装脚本。模型放在 Release 附件，不放进 Git 大文件历史。安装脚本在写入前检查整个压缩包与各模型的 SHA-256。

## 运行

1. 进入 **Collect Cooking／拼配厨房**，选择 **SCORE ATTACK**。普通模式也计时，不是十道料理的验证模式。
2. 双击根目录 `Launch.cmd`，或运行 `.\.venv\Scripts\pythonw.exe gui.py`。
3. 自行填写正整数局数，点击 **Start**，等待 **Ready**，切回游戏按 **F8**。可从小游戏结算、厨房菜单或 Order 画面开始，程序按固定布局推进下一步。
4. 保持游戏在前台，测试中避免同时操作鼠标键盘。**F8** 暂停／恢复，**Escape** 停止。切换焦点会暂停游戏输入，回到游戏按 F8 恢复。
5. 测试结束后核对结算截图与日志。这是开发实验版本，不保证无人值守完成十道。

等价命令行入口：

```powershell
.\.venv\Scripts\python.exe outputs\kitchen-bot\standalone.py --point-model ../kitchen-labeler/point-classifier-human.pt --games 5 --fps 20
```

GUI 在权重安装后自动选择人工标注点位模型。直接用命令行时，必须像上面一样指定它，才能复现已测版本；历史默认 `point-classifier.pt` 是另一个模型。`--seconds` 限制每局运行时间，默认 300 秒；`--diagnostic-lossless-interval` 是失败追踪 PNG 对的最短保存间隔，默认 2 秒。`--replay PATH` 离线分析已有图片，不创建桌面捕获／输入适配器；回放不能证明实际点击成功。

## 技术细节与实现方式

### 截图与坐标

`standalone.py` 通过 Windows **GDI** 截取游戏客户区，通过 **SendInput** 点击鼠标，在本机读取 F8／Escape。截图与 MP4 编码在后台线程按请求 **20 FPS** 执行，与神经网络推理分离，使用条件变量发布新帧。图像统一到 **1536×864**，用实际比例和顶部偏移换算回客户区坐标。桌面区域裁切为 `(318,175)–(1215,735)`，缩放为 **448×280** 后分割。输入前检查游戏焦点。

20 FPS 指请求截图率，不代表每秒决策 20 次。记录的捕获开始与鼠标派发时间是主机时间，不是 Unity 图像曝光或收到输入的精确时间。

### 图像识别

- **可见表面分割**：`segmenter.py` 是小型 U-Net 风格编码／解码网络，通道 24/48/96/160，有跳跃连接，输出 **30 种食材＋背景，共 31 类**。连通区域提取可见片段，通过置信度加权的距离变换选内部位置，减少外框中心落在其他遮挡食材上的情况。
- **外观分类**：`icon_classifier.py` 使用 **ResNet18** 和 31 类分类头，输入 96×96。图标模型读食谱、槽位与外框上下文；人工标注点位模型检查点击中心周围的 **64×64 标准画面裁切**。Softmax 分数是筛选门槛，并不是校准后的点击成功概率。
- **订单与状态**：数字模板、颜色及连通区域读订单编号、剩余数量和完成勾。固定 UI 图形区分订单过场、料理完成、结算、帷幕及爆槽。完成过场使用角落装饰检测，减少对翻译文字的依赖，但没有证明所有语言／布局都适用。
- **透明容器**：豆芽罐优先寻找彩色瓶盖，避免把透明罐身当作可靠可点击表面。

早期训练使用本地解包食材模型／贴图生成合成视角，随后用真实画面和人工中心／轮廓标注训练。仓库**不包含**完整解包、3D 模型及私有训练标注集；Release 提供已训练权重，并非完整可复现训练数据集。后来困难食材的训练候选未通过旧类别保留检查，已被拒绝，没有混入当前部署。仅附带现有模板回退所需的小型食材图标集及 UI／数字模板。

### 三消规划与点击验证

`planner.py` 跨帧保存食谱、订单、七格槽位估计、待确认点击、近期失败位置与抖盘状态。优先目标食材以及补齐已有两件的三消组；目标拾取用需求数量减少确认，渲染槽位观察校正库存。找不到目标时从按钮画面判断抖盘是否可用，不只依赖固定冷却时间。有足够空间及高信心同类三件时，也可清理非目标食材。动画期间这些反馈仍可能不明确。

`motion.py` 以 3×3 点网格进行金字塔 **Lucas–Kanade 光流**，检查正反向一致性；追踪点不足、运动不一致、帧间隔过旧、外推太远或落点越界就拒绝。几乎不变的平坦图块可视为静止。外推计入画面年龄、游标定位等待与渲染余量。`latest_click.py` 检查新画面的阶段／订单，并同时分类**观测点和预测落点**。拥挤槽位、部分窄区域与非目标清槽动作采用更严格门槛。有限的追加点击也有各自的新帧验证。

`supplemental_food.py` 在原路没有食材动作时，用另一组人工表面模型补充 **洋葱／炸虾／鲔鱼罐**，保留原路已批准动作，新画面中仍须强一致性复核。

### 最新局部重新定位路径

`guarded_local_relocation.py` 仅在原最新帧食材检查返回 `wait` 后启用。只尝试**第一个被拒绝的所需主路径食材**，不替非目标清槽或独立 supplement 路径重新定位。`local_relocation.py` 在原有桌面像素尺度上重新分割对齐的 **160×160 ROI**，排除碰裁切边缘、小／弱区域、距离过远点及透明豆芽罐。

候选必须经过原规划器的副本，包括近期失败点记录。推理结束后再明确取得**另一帧**，确认阶段、订单、需求数量及槽位不变，保持原光流和位移上限，并要求观测／预测点分类均 **≥0.995**。验证过程中及输入派发前检查 **150ms 主机画面年龄上限**；此路径禁用追加点击。派发前检查之后仍有鼠标移动等待，因此该上限并不保证游戏中的精确画面新鲜度。

## 文件、权重与诊断

| 文件／路径 | 职责 |
| --- | --- |
| `outputs/kitchen-bot/standalone.py` | 本机截图／输入、自定义局数与日志 |
| `perception.py`、`segmenter.py`、`icon_classifier.py` | 表面、点位、食谱与槽位识别 |
| `planner.py`、`shuffle_state.py` | 三消状态管理与抖盘门控 |
| `motion.py`、`motion_click.py`、`latest_click.py` | 追踪、外推与复核 |
| `supplemental_food.py` | 困难食材独立补充 |
| `local_relocation.py`、`guarded_local_relocation.py` | 最新局部重新定位 |
| `outputs/kitchen-assets/textures/` | 模板匹配使用的最小食材图标集 |
| `models-manifest.json` | 权重路径、大小与 SHA-256 |
| `tests/` | 离线坐标与状态／时间拒绝检查 |

当前启用权重：`segmenter-adapted.pt`、`icon-classifier.pt`、`segmenter-positive-surfaces.pt`、`point-classifier-human-paired.pt`，以及 `outputs/kitchen-labeler/point-classifier-human.pt`。压缩包还保留历史 `segmenter.pt` 和 `point-classifier.pt`。`render_samples.py`、`vision.py`、`worker.py` 为保留的历史／支持模块；合成渲染器需另备本地 3D 资源。独立版运行**不依赖 Codex 或 Computer Use**。

前端运行记录保存在 `%LOCALAPPDATA%/CollectCookingAuto/launch-…/runs/`；直接 CLI 默认写入 `outputs/kitchen-bot/runs/`。包括决策截图、`final.jpg`、JSONL 与摘要。前端录像默认关闭，可以开启；直接 CLI 默认开启录像。私人测试与标注资料不发布。

离线验证：

```powershell
.\.venv\Scripts\python.exe tests\test_local_relocation_coordinates.py
.\.venv\Scripts\python.exe tests\test_guarded_local_relocation.py
```

检查涵盖坐标换算、裁切边界、原批准动作保留、过旧帧拒绝、槽位／状态变化、追踪失败与严格点位复核。它们不能替代实战五局。剩余问题包括遮挡／碰撞不一致、点击前看起来识别正确但未拾取预期物体，以及部分食材追踪缓慢或失败。现有录像缺少完整逐视频帧的捕获时间索引；精确对齐鼠标派发与录像是建议的后续诊断，尚未实现。

本项目为独立实验项目，并非 hololive DREAMS 官方产品。游戏名称与美术素材归各自权利人所有。
