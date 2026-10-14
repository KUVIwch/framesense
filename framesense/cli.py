"""FrameSense · Color Lab 离线命令行工具。"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from framesense.core.compare import compare_images
from framesense.core.loader import load_image
from framesense.core.regions import Region, compute_region_stats, region_difference
from framesense.core.stats import compute_image_stats
from framesense.guidance.engine import generate_guidance
from framesense.learning.session import (
    create_session,
    delete_session,
    get_session,
    list_sessions,
)


def _parse_region(text: str) -> Region:
    parts = [int(x) for x in text.split(",")]
    if len(parts) != 4:
        raise ValueError("区域格式应为 x,y,width,height")
    return Region(*parts)


def cmd_analyze(args: argparse.Namespace) -> int:
    ref = load_image(args.reference)
    src = load_image(args.source)
    ref_stats = compute_image_stats(ref.rgb)
    src_stats = compute_image_stats(src.rgb)
    comparison = compare_images(ref.rgb, src.rgb)

    region_diffs: list[dict] = []
    if args.region_ref and args.region_src:
        rr = compute_region_stats(ref.rgb, _parse_region(args.region_ref))
        sr = compute_region_stats(src.rgb, _parse_region(args.region_src))
        region_diffs = [region_difference(rr, sr)]

    guidance = generate_guidance(
        target_stats=ref_stats,
        source_stats=src_stats,
        region_diffs=region_diffs or None,
    )
    result = {
        "reference": asdict(ref_stats),
        "source": asdict(src_stats),
        "comparison": asdict(comparison),
        "regions": region_diffs,
        "guidance": guidance.model_dump(),
    }
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"已保存分析结果: {args.output}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_session(args: argparse.Namespace) -> int:
    if args.action == "create":
        sid = create_session(args.reference, args.source, mode=args.mode, title=args.title or "")
        print(sid)
        return 0
    if args.action == "list":
        for s in list_sessions(limit=args.limit):
            print(f"{s.id}\t{s.mode}\t{s.title or '-'}\t{s.reference_path}\t{s.source_path}")
        return 0
    if args.action == "get":
        s = get_session(args.id)
        if s is None:
            print("会话不存在", file=sys.stderr)
            return 1
        print(json.dumps(s.model_dump(), ensure_ascii=False, indent=2))
        return 0
    if args.action == "delete":
        return 0 if delete_session(args.id) else 1
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="framesense", description="FrameSense Color Lab 离线工具")
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="分析参考图与原片的差异并生成指导")
    p_analyze.add_argument("reference", help="参考图路径")
    p_analyze.add_argument("source", help="原片路径")
    p_analyze.add_argument("--region-ref", help="参考图区域 x,y,width,height")
    p_analyze.add_argument("--region-src", help="原片区域 x,y,width,height")
    p_analyze.add_argument("--output", help="输出 JSON 文件路径")

    p_session = sub.add_parser("session", help="学习会话管理")
    p_session.add_argument("action", choices=["create", "list", "get", "delete"])
    p_session.add_argument("--reference")
    p_session.add_argument("--source")
    p_session.add_argument("--mode", choices=["guided", "practice", "independent"], default="guided")
    p_session.add_argument("--title", default="")
    p_session.add_argument("--id", type=int)
    p_session.add_argument("--limit", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "analyze":
            return cmd_analyze(args)
        if args.command == "session":
            return cmd_session(args)
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
