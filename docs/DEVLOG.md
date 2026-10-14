# 开发日志

## 2026-10-10 前后：项目萌芽

想法来自 Sony NEX-5N 的日常拍摄：照片“差了点感觉”，想找工具帮忙分析调色方向。

## 2026-10-13：V0.1 Streamlit 原型

- 实现 JPG/PNG/ARW 读取、EXIF、直方图、颜色统计。
- 接入云知声 MaaS（U2 Flash），实现结构化调色方案。
- SQLite 历史 + Markdown 导出。
- 89 项 pytest 通过；至少一次真实模型调用成功。

**遇到的问题：**

- 云知声 U2 Flash 响应慢，30 秒超时直接失败。把超时提高到 300 秒、设置 max_tokens=4000、关闭 `response_format` 后成功。
- 起初误把用户 Key 当 OpenAI 官方 Key，返回 401；改为云知声端点后正常。
- Windows 控制台中文乱码：对 stdout/stderr 做 UTF-8 重配置。
- pytest 的 Windows 临时目录出现权限错误（WinError 5），改用项目内 `--basetemp` 规避。根因未彻底定位。
- Streamlit 长驻进程缓存旧模块，改代码后必须重启；增加代码更新提示。
- UI 测试发现一个真实 bug：Mock 模式下侧边栏“模型模板”仍会用 .env 里的 Key 构造真实客户端，导致误发付费请求；已修复。

## 2026-10-14：产品转向，开始桌面重构

- 重新审视产品方向：不做大而全的修图软件，聚焦仿色学习。
- 初始化 Git 仓库，把 V0.1/V0.2 旧版保存为基线并打标签 `v0.1-streamlit`。
- 安装 PySide6、colour-science、PyInstaller。
- 开始搭建 `framesense/core`（加载、色彩管理、统计、双图对比、区域分析）、`framesense/guidance`（调色指导引擎）、`framesense/learning`（学习会话）。

## 后续阶段

- 阶段 B：色彩分析核心 + 测试。
- 阶段 C：调色教学引擎 + 测试。
- 阶段 D：PySide6 桌面界面。
- 阶段 E：仿色复盘与学习历史。
- 阶段 F：全量测试、文档、打包。
- 阶段 G：GitHub 提交与推送。

本日志会按实际进度继续补充。

## 2026-10-14：断网后继续

- 补完学习会话测试（7 项）。
- 新增离线 CLI（`framesense.cli`）与 PySide6 桌面 UI（`framesense/ui`、`framesense/app.py`）。
- UI 支持：双图导入、缩放/平移/矩形区域选择、直方图与主色样本、三模式指导展示、学习笔记、会话保存/加载、最终作品复盘对比。
- 新增 CLI 测试与 UI 冒烟测试（离屏渲染）。
- 当前测试：51 项通过。
- 下一步：README/BUILD 文档、PyInstaller 打包尝试、GitHub 推送（gh 未安装，需用户授权）。

## 2026-10-14：打包与 GitHub 归档完成

- PyInstaller 打包成功：`dist/FrameSenseColorLab/FrameSenseColorLab.exe`，并完成启动验证（进程正常存活）。
- 使用 Windows 凭据管理器中的 GitHub 凭据，创建公开仓库 `KUVIwch/framesense` 并推送全部提交。
- 最终全量测试：51 项通过。
- 本地与远程 `main` 分支 HEAD 一致（`e861b2b`）。

## 断网检查点：2026-10-14（暂停前状态）

**已完成并提交：**

- 阶段 A：初始化 Git；旧版 V0.1/V0.2 存档（tag `v0.1-streamlit`）；docs 历史文档。
- 阶段 B：离线核心 `framesense/core`（色彩管理/加载/统计/区域/双图对比），31 项测试通过。
- 阶段 C：调色教学引擎 `framesense/guidance`，5 项测试通过。
- 已提交 commit：`chore: archive ...`、`docs: record framesense project history`、`refactor: establish color lab architecture`、`feat: add grading guidance engine`。

**当前未提交（已创建、编译通过）：**

- `framesense/learning/`：学习会话 SQLite 持久化（models + session），**测试尚未编写**。

**下一步待完成：**

1. 补 `tests/learning/` 学习会话测试。
2. 阶段 D：PySide6 桌面 UI（`framesense/ui/`：主窗口、图像视图、直方图/颜色样本控件）。
3. 阶段 E：仿色复盘（导入最终作品、对比、标记有意差异）。
4. 阶段 F：全量测试、README、BUILD 文档、PyInstaller 打包尝试。
5. 阶段 G：GitHub 提交与推送（gh CLI 未安装、未认证，需要用户授权后处理）。

**当前测试状态**：36 项通过（31 core + 5 guidance）；learning 测试待补。
