"""命令行入口。"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from framesense import __version__
from framesense.ai.base import create_analyzer
from framesense.analyzer import DEFAULT_THRESHOLD, analyze_sequence
from framesense.config import VALID_AI_MODES, load_config
from framesense.io_utils import list_image_files
from framesense.report import save_json, save_markdown

DEMO_DEFAULT_DIR = Path("outputs") / "demo_frames"
REPORT_DEFAULT_DIR = Path("outputs") / "reports"


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="framesense",
        description="FrameSense V0.1 帧序列分析工具",
    )
    parser.add_argument("--version", action="version", version=f"FrameSense {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="分析单个图片或一个目录中的帧序列")
    p_analyze.add_argument("path", help="图片文件或包含帧序列的目录")
    p_analyze.add_argument("--output-dir", default=str(REPORT_DEFAULT_DIR), help="报告输出目录")
    p_analyze.add_argument(
        "--ai-mode",
        choices=sorted(VALID_AI_MODES),
        default=None,
        help="AI 模式（默认 mock，不产生网络调用）",
    )
    p_analyze.add_argument("--recursive", action="store_true", help="递归扫描子目录")
    p_analyze.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help="关键帧切换阈值 0~1",
    )
    p_analyze.add_argument(
        "--format",
        choices=["json", "markdown", "both"],
        default="both",
        help="报告格式",
    )

    p_info = sub.add_parser("info", help="显示单张图片基本信息")
    p_info.add_argument("path")

    p_demo = sub.add_parser("demo", help="生成一组合成演示帧并执行 Mock 分析")
    p_demo.add_argument("--output-dir", default=str(DEMO_DEFAULT_DIR))
    p_demo.add_argument("--frames", type=int, default=6)
    p_demo.add_argument("--width", type=int, default=320)
    p_demo.add_argument("--height", type=int, default=180)
    return parser


def cmd_info(args: argparse.Namespace) -> int:
    from framesense.features import file_size_bytes, load_image, validate_image_path

    p = validate_image_path(args.path)
    img = load_image(p)
    print(f"文件: {p}")
    print(f"尺寸: {img.width} x {img.height}")
    print(f"模式: {img.mode}")
    print(f"格式: {p.suffix.lstrip('.').upper()}")
    print(f"大小: {file_size_bytes(p)} 字节")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """生成合成演示帧（纯本地绘图，不涉及真实照片）。"""
    from PIL import Image, ImageDraw

    out_dir = Path(args.output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    n = max(2, args.frames)
    width, height = args.width, args.height
    created: list[Path] = []
    for i in range(n):
        img = Image.new("RGB", (width, height), (30, 30, 40))
        draw = ImageDraw.Draw(img)
        for y in range(height):
            color = (30 + int(20 * y / height), 30 + int(10 * y / height), 40 + int(30 * y / height))
            draw.line([(0, y), (width, y)], fill=color)
        cx = int(width * (0.2 + 0.6 * i / max(1, n - 1)))
        cy = int(height * 0.5)
        r = int(height * 0.18)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(200 + (i * 10) % 55, 100, 180))
        path = out_dir / f"frame_{i:03d}.png"
        img.save(path, format="PNG")
        created.append(path)
    print(f"已生成 {len(created)} 帧到: {out_dir}")
    return run_analyze(
        path=out_dir,
        output_dir=out_dir / "report",
        ai_mode="mock",
        recursive=False,
        threshold=DEFAULT_THRESHOLD,
        formats=("both",),
    )


def cmd_analyze(args: argparse.Namespace) -> int:
    return run_analyze(
        path=args.path,
        output_dir=args.output_dir,
        ai_mode=args.ai_mode,
        recursive=args.recursive,
        threshold=args.threshold,
        formats=(args.format,),
    )


def run_analyze(
    path: str,
    output_dir: str | Path,
    ai_mode: str | None,
    recursive: bool,
    threshold: float,
    formats: tuple[str, ...],
) -> int:
    """执行序列分析并保存报告。"""
    paths = list_image_files(path, recursive=recursive)
    if not paths:
        print(f"错误：未找到支持的图片文件: {path}", file=sys.stderr)
        return 2
    if not 0.0 <= threshold <= 1.0:
        print("错误：threshold 必须在 0~1 之间", file=sys.stderr)
        return 2

    config = load_config(ai_mode=ai_mode)
    try:
        analyzer = create_analyzer(config.ai_mode, config)
    except ValueError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    source = Path(path).expanduser().resolve()
    report = analyze_sequence(
        paths,
        ai_analyzer=analyzer,
        threshold=threshold,
        ai_mode=config.ai_mode,
        source_path=str(source),
    )

    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    saved: list[Path] = []
    for fmt in formats:
        if fmt in ("json", "both"):
            saved.append(save_json(report, out_dir / f"framesense_report_{stamp}.json"))
        if fmt in ("markdown", "both"):
            saved.append(save_markdown(report, out_dir / f"framesense_report_{stamp}.md"))

    print(f"分析完成：{report.total_frames} 帧，关键帧 {report.keyframe_indices}")
    print(f"报告已保存：{', '.join(str(s) for s in saved)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    # 统一 UTF-8 输出，避免 Windows 控制台代码页导致中文乱码
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            return cmd_analyze(args)
        if args.command == "info":
            return cmd_info(args)
        if args.command == "demo":
            return cmd_demo(args)
    except KeyboardInterrupt:
        print("已取消", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
