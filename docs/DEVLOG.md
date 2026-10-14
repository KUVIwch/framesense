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
