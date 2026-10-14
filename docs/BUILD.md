# 构建 Windows 可执行程序

## 前置条件

- 已安装项目依赖：`pip install -r requirements.txt`
- 已安装 PyInstaller（requirements.txt 已包含）

## 构建命令

在项目根目录执行：

```powershell
.venv\Scripts\pyinstaller --noconfirm --clean --windowed --name FrameSenseColorLab framesense/app.py
```

产物位于 `dist/FrameSenseColorLab/`，主程序为 `FrameSenseColorLab.exe`。

## 说明与注意事项

- PySide6 体积较大，打包产物可能达到 200MB 以上。
- 本程序不需要 PySide6 WebEngine；如果希望减小体积，可以在 PyInstaller 配置中排除 `PySide6.QtWebEngine*` 模块。
- 杀毒软件可能对 PyInstaller 产物误报，这是常见问题。
- `dist/`、`build/`、`*.spec` 已加入 `.gitignore`，不会进入 Git。

## 验证

构建完成后，直接运行 `dist\FrameSenseColorLab\FrameSenseColorLab.exe`。如果没有 GUI 环境，可先运行：

```powershell
.venv\Scripts\python.exe -m framesense.cli analyze 参考图.jpg 原片.jpg
```

确认分析核心正常。
