<picture>
  <source media="(prefers-color-scheme: dark)" srcset="framesense/assets/readme-wordmark-dark.svg">
  <img src="framesense/assets/readme-wordmark-light.svg" width="340" alt="FrameSense Color Lab">
</picture>

# FrameSense · Color Lab

一张参考作品，一张自己的原片。先看影调与颜色差在哪里，再到 Camera Raw 里试调，最后带着结果回来比较。

FrameSense 是离线的 Windows 仿色学习工具。它提供测量、试调方向和练习记录，让你逐渐形成自己的判断。当前版本为 **0.3.0-preview**，仍需真实摄影素材与更多屏幕环境试用。

## 一次练习

1. 把参考作品和原片拖到对应画布，或点「放入」选择文件。
2. 滚轮缩放、拖动平移；「联动查看」按相对倍率与位置同步。
3. Shift 拖动框选两块含义相近的区域，例如同样的肤色、墙面或天空。
4. 点「看看差在哪」，从影调、色度与区域关系挑一两个重点。
5. 在 Camera Raw / Photoshop 调整；导出 Markdown 清单可边做边看。
6. 放入调后作品，切换原片、成片或参考叠图，再写下值得保留的变化。

引导模式显示完整解释；练习模式先隐藏操作，点提示再展开；独立模式保留自己的观察空间。切换模式不丢照片、区域或笔记。

## 这一版实际做了什么

- 原创取景框与色彩切片标识，深浅两套主题，照片优先的可调整三栏工作台。
- JPG / PNG / Sony ARW 只读加载，应用 EXIF 方向，读取 ICC 并转换到 sRGB。无配置与损坏配置会明确标记。
- 后台加载、分析与区域取样；可以取消，过时结果不会替换当前工作台。正在执行的原生解码不能中途强杀。
- 内容哈希与算法版本作缓存键，默认上限 128 MiB / 24 条；缓存不落盘，原图不改动。
- 亮度分布、三段影调、HSL 饱和度、Lab 色度、主色和对应区域 ΔE00。不同尺寸、不同构图可做全局分布比较。
- 可解释的离线调色规则，区分测量、经验与建议。不会从 JPEG 唯一反推作者参数。
- 本地 SQLite 练习记录、目标、笔记、区域、结果与查看状态；原子草稿与切换前恢复；丢失路径可重新定位。

全局平均颜色 ΔE 不是风格分数，也不是照片好坏评分。场景内容、构图、拍摄光线都会影响统计；尽量同时比较对应区域。

## 运行

需要 Python 3.11 或更新版本；本轮实际验证环境为 Windows、Python 3.14.5。

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m framesense.app
```

本机已构建的预览包在 `outputs/windows-0.3.0-preview/FrameSenseColorLab/`。双击其中的 exe；请保留相邻的 `_internal` 文件夹。它不需要 API Key 或网络。构建方法见 [BUILD](docs/BUILD.md)。

## 常用操作

| 操作 | 按键 |
| --- | --- |
| 放入参考 / 原片 | Ctrl+O / Ctrl+Shift+O |
| 保存练习 / 导出清单 | Ctrl+S / Ctrl+E |
| 分析 / 收起观察栏 | Ctrl+Enter / Ctrl+B |
| 适合窗口 / 放大缩小 | 画布内 F / +、− |
| 区域 / 平移工具 | 画布内 R / V |
| 临时框选 / 清除区域 | Shift 拖动 / Esc |
| 调整区域 | 方向键移动，Ctrl+方向键改变大小 |
| 撤销区域选择 | Alt+Backspace |

## 验证与测量

```powershell
.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=work/test-run
.venv\Scripts\python.exe tools/benchmark.py --mode optimized --output work/performance/rerun.json
.venv\Scripts\python.exe tools/render_workbench.py
```

24 MP 合成 JPG 核心工作流实测由 9.079 秒 / 1482.4 MiB 降至 1.852 秒 / 206.1 MiB。有限分辨率近似、首次导入和文件缓存都会影响结果，详见 [性能测量](docs/PERFORMANCE.md)，不能据此宣称 GUI 帧率。

## 文档与边界

[项目故事](docs/PROJECT_STORY.md) · [设计系统](docs/DESIGN_SYSTEM.md) · [交互取舍](docs/UX_DECISIONS.md) · [审查](docs/AUDIT.md) · [开发日志](docs/DEVLOG.md) · [验收记录](docs/QA.md) · [路线图](docs/ROADMAP.md)

原型基线保存在 `baseline-colorlab-20261014`；早期 Streamlit 版本保存在 `v0.1-streamlit`。当前数据只在本机 `data/`，构建程序使用 exe 旁的 `data/`，源码与打包程序的记录相互独立。

仍需验证：真实 Sony ARW、不同相机/广色域 ICC、大 PNG 峰值、不同 DPI 真机观感。预览图的极小区域精度有限；规则无法判断人物语义或替代创作意图。不提供完整 RAW 显影或 Photoshop 自动控制。
