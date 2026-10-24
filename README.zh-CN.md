# Hololive Dreams Auto Collect Cooking — 1.1.0

[English](README.md) · [繁體中文](README.zh-TW.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Indonesian](README.id.md) · [简体中文](README.zh-CN.md)

Windows版《hololive Dreams》拼配厨房的自动料理程序。通过游戏画面识别食材，以普通鼠标输入选取食物，并在结算后继续下一局。

## 下载

前往 [GitHub Releases](https://github.com/harrykuang-dev/Hololive-Dreams-Collect-Cooking-Auto/releases/tag/v1.1.0)，下载 `Collect-Cooking-Auto-v1.1.0-win64.7z`。用7-Zip解压，再运行解压文件夹中的 `Collect-Cooking-Auto-v1.1.0.exe`。

请保留EXE旁的 `_internal` 文件夹。已包含Python、推理库及五份模型权重。`SHA256SUMS.txt`用于核对下载文件；`models.zip`供源码使用。GitHub自动生成的源码ZIP需要另外安装依赖和模型。

## 功能

- 识别食谱食材、剩余需求及槽位，规划目标拾取、三消清理与抖盘。
- 提供「**标准**」（ResNet18）与「**进阶**」（ResNet101）。标准运算需求较低，进阶适合性能较充足的电脑。
- 模型加载与游戏开始分开，加载的点位分类器同时验证按需补充候选。
- 可设置目标局数，完成一局后自动继续，达标后停止。
- 支持英文、繁体中文、日文、韩文、印尼文及简体中文，语言选择应用于程序界面。
- 提供自定义快捷键、运行记录及可选的本地开发者诊断模式。

## 使用方法

1. 打开游戏，进入拼配厨房。
2. 运行EXE，选择程序语言和识别模型，输入正整数目标局数；首次使用默认5局。
3. 点击「**加载模型**」，等待显示模型已加载。
4. 点击「**开始**」后，程序会尝试还原游戏窗口并切到前台，也可在游戏中按 **F8**。若Windows阻止切换，请手动切回游戏，并保持画面无遮挡。
5. **F8**暂停／继续，**Esc**或「**停止**」结束运行。切换焦点会暂停输入，切回游戏按F8继续。切换模型前先停止，再选择并加载另一个模型。

点击快捷键框后，按下要使用的按键或Ctrl／Alt／Shift组合键。未完成输入就离开输入框时，保留原设置；设置会保存供下次使用。

## 使用条件与限制

适用于Windows 10／11 x64及Windows版游戏。游戏客户区需保持16:9，保持屏幕开启及游戏可见。单一完整版包含全部推理库及一份共用FP32 ONNX模型。兼容NVIDIA GPU自动使用TensorRT，其他受支持的DirectX 12 GPU使用DirectML，最后回退CPU。CPU或性能较低的GPU可能无法通过点击时效检查。

解压后的便携文件夹约2.9 GB，另需预留下载文件及解压空间。界面中的已完成局数表示批次进度，料理数和成绩以游戏结算画面为准。食材移动、遮挡、电脑性能及游戏更新都可能影响识别。

## 技术实现

### 画面捕获与处理

[捕获模块](outputs/kitchen-bot/async_recording.py)以独立线程通过Windows GDI获取游戏客户区画面，请求频率为每秒20帧，持续发布近期画面供识别，不等待视频编码。[识别流程](outputs/kitchen-bot/perception.py)将画面统一到1536×864，再对448×280的桌面裁片进行分割。点位按实际缩放和顶部偏移换算回游戏坐标。

### 食材识别与模型共享

主表面分割模型生成可见食材区域，所选点位分类器检查点击位置周围的64×64裁片，缩放到96×96后推理。共享的图标分类器读取食谱和槽位，数字模板及固定UI图形判断需求数量和游戏阶段。

当主路径准备等待或抖盘时，[补充定位器](outputs/kitchen-bot/supplemental_food.py)按需寻找洋葱、炸虾及金枪鱼罐头候选，再交给已加载的点位分类器验证。程序只加载所选的标准或进阶点位分类器。详见 [模型说明](docs/model-options.md)。

### 规划与抖盘间隔

[规划器](outputs/kitchen-bot/planner.py)跨帧保存食谱、槽位估计、待确认拾取及近期失败点，优先处理目标食材与完成三消，并根据需求数量变化及可见槽位获取反馈。两次实际按下抖盘至少间隔5秒，且需在近期画面确认按钮可用。

### 移动验证与续局

[光流跟踪](outputs/kitchen-bot/motion.py)在发送点击前估计局部位移，[新画面复核](outputs/kitchen-bot/latest_click.py)检查订单、游戏阶段，以及观测点与预测点的食材类别。跟踪失败后，可通过受限的局部重新定位重试所需食材。[会话控制](outputs/kitchen-bot/session_flow.py)识别右下角续局按钮，从结算与菜单继续下一局。

## 异常反馈与开发者模式

识别、点击或续局异常，可在 [GitHub Issues](https://github.com/harrykuang-dev/Hololive-Dreams-Collect-Cooking-Auto/issues)提交反馈。先勾选「**开发者模式**」再重现问题，程序会在本地保存识别结果、点击时序、游戏截图及性能摘要。开启后会增加性能负担，资料不会自动上传。

点击旁边的 `?` 可查看并打开诊断文件夹：

```text
%LOCALAPPDATA%\CollectCookingAuto\sessions\
```

每次运行结束后会生成以日期时间命名的ZIP。反馈时请提供程序版本、所选模型、游戏语言、分辨率、Windows显示缩放、问题描述及诊断ZIP。

开发者模式以JSONL永久保留每局确认后的分数、完成料理数、点击、决策、等待原因及耗时。结算截图与普通截图共同按容量淘汰较早图片；图片是否仍保留以 `image-index.json` 为准。无法确认的结算数字标为null并保留原因。每个诊断ZIP硬上限20 MB；若纯文本也超限，会分成多个ZIP，完整文本原文件仍保留在本机。

## 源码与许可说明

源码启动、构建及测试见 [开发说明](docs/DEVELOPMENT.md)，其他内容见 [版本记录](docs/VERSION_HISTORY.md)、[模型说明](docs/model-options.md)及 [游戏用词](docs/GAME_TERMS.md)。

人工标注图片、标签、固定数据划分及重新训练说明见 [annotations](annotations/README.md#繁體中文)。

第三方许可保留于 [third-party](third-party/README.md)。游戏名称与美术素材的权利归各自权利人所有。
