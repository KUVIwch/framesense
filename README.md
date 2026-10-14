# FrameSense · Color Lab

FrameSense · Color Lab 是一个**离线优先的摄影仿色分析与学习工具**，运行在 Windows 桌面。

它解决一个问题：你有一张喜欢的摄影作品（参考图）和一张自己的原片，软件分析两者的**客观颜色与明暗差异**，给出可解释、可执行的调色指导，并支持练习与复盘。

核心理念：**不是让用户永远依赖工具，而是让用户从模仿开始，逐渐拥有独立判断颜色与影调的能力。**

## 为什么开发它

作者使用 Sony NEX-5N 拍照，长期被“照片差了一点感觉”困扰。市面上的修图软件和 AI 一键调色很多，但缺一个能帮助用户**理解差距、学会仿色**的工具。完整故事见 [docs/PROJECT_STORY.md](docs/PROJECT_STORY.md)。

## 当前真正支持的功能（不夸大）

- **双图导入**：参考作品 + 原片，支持 JPG、PNG；Sony ARW 通过 rawpy 解码为 sRGB（兼容性问题会明确报错，不伪造支持）。
- **色彩管理**：读取嵌入的 ICC 配置文件并转换到统一 sRGB 工作空间；缺失配置文件时按 sRGB 假设并标记。
- **客观分析**：亮度直方图、明暗比例、亮度百分位、对比度、饱和度/色度、主色、高光/暗部色偏、灰世界色偏估计。
- **双图差异**：直方图距离、平均 Lab 色差（ΔE76）、亮度差、色度差。
- **对应区域分析**：在两张图上分别选择矩形区域，计算区域均值色差（ΔE76 / ΔE00）与明暗差异。
- **调色指导引擎（离线规则）**：根据客观差异生成分步指导，包含观察、依据、目标、工具（Camera Raw / Photoshop）、操作方向、预期效果、副作用、调整后观察点；区分事实/推测/建议，不编造精确滑块数值。
- **三种学习模式**：引导模式（完整步骤）、练习模式（默认隐藏具体操作）、独立模式（隐藏操作，自行尝试）。
- **仿色复盘**：导入调色后的最终作品，对比其与参考图的 ΔE 是否比原片更接近。
- **学习会话**：保存参考图/原片/最终作品路径、区域、指导、笔记到本地 SQLite；路径失效时提示重新定位。
- **完全离线**：核心功能不依赖任何 API Key、不产生网络请求。

## 明确不做什么（当前版本）

- 不做完整修图器、不做 Photoshop 自动操控、不做在线账号、不做必须联网的 AI 分析。
- 更长远的方向见 [docs/ROADMAP.md](docs/ROADMAP.md)。

## 安装与运行（开发模式）

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m framesense.app
```

## 命令行（无界面环境）

```powershell
# 双图分析并生成指导 JSON
.venv\Scripts\python.exe -m framesense.cli analyze 参考图.jpg 原片.jpg --output result.json

# 学习会话管理
.venv\Scripts\python.exe -m framesense.cli session create --reference 参考图.jpg --source 原片.jpg
.venv\Scripts\python.exe -m framesense.cli session list
```

## 打包为可执行程序

见 [docs/BUILD.md](docs/BUILD.md)。

## 测试

```powershell
.venv\Scripts\python.exe -m pytest
```

## 项目结构

```
framesense/
  core/       图像加载 / 色彩管理 / 统计 / 双图对比 / 区域分析
  guidance/   调色指导引擎（结构化规则 + Pydantic 模型）
  learning/   学习会话持久化（SQLite）
  ui/         PySide6 桌面界面
  app.py      桌面入口
  cli.py      离线命令行工具
tests/        自动化测试
docs/         项目故事、决策、开发日志、路线图、构建说明
```

## 开发文档

- [项目故事](docs/PROJECT_STORY.md)
- [关键决策](docs/DECISIONS.md)
- [开发日志](docs/DEVLOG.md)
- [旧版 V0.1/V0.2 档案](docs/LEGACY_V0.1.md)
- [路线图](docs/ROADMAP.md)
- [构建说明](docs/BUILD.md)

## 已知问题与限制

- ARW 兼容性依赖 rawpy/LibRaw，个别机型可能失败；失败时会明确报错。
- 调色指导是规则引擎，覆盖常见曝光/色温/饱和度/区域差异场景，复杂艺术风格不一定能覆盖。
- 涉及滑块数值均为方向性起始范围，不是精确参数映射。
- 区域选择目前仅支持手动矩形区域。
