"""Reproducible offline core benchmark; synthetic photos, isolated workers.

Run with the project's Python: tools/benchmark.py --mode baseline --output work/baseline.json
Run before/after in the same environment. Peak is the OS process high water mark,
not Python's allocation tracker. No GUI frame-rate claims are made here.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.environ.get("FRAMESENSE_BENCHMARK_SOURCE_ROOT", str(ROOT)))


def peak_memory_bytes():
    if os.name == "nt":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "PeakWorkingSetSize",
                    "WorkingSetSize",
                    "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage",
                    "QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage",
                    "PagefileUsage",
                    "PeakPagefileUsage",
                )
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(Counters),
            wintypes.DWORD,
        ]
        if not psapi.GetProcessMemoryInfo(
            kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(counters.PeakWorkingSetSize)
    import resource

    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def worker(path, mode):
    start = time.perf_counter()
    from framesense.core.loader import load_image
    from framesense.core.stats import compute_image_stats
    from framesense.core.compare import compare_images
    from framesense.core.regions import Region, compute_region_stats, region_difference

    imported = time.perf_counter()
    if mode == "baseline":
        image = load_image(path)
        loaded = time.perf_counter()
        stats = compute_image_stats(image.rgb)
        analyzed = time.perf_counter()
        comparison = compare_images(image.rgb, image.rgb)
        compared = time.perf_counter()
        region = Region(0, 0, image.width // 2, image.height // 2)
        selected = compute_region_stats(image.rgb, region)
        region_difference(selected, selected)
        regional = time.perf_counter()
        repeated_image = load_image(path)
        compute_image_stats(repeated_image.rgb)
        warm = time.perf_counter()
        cache = None
    else:
        from framesense.core.service import AnalysisService

        service = AnalysisService()
        image = service.load(path)
        loaded = time.perf_counter()
        stats = service.stats(image)
        analyzed = time.perf_counter()
        comparison = service.compare(image, image)
        compared = time.perf_counter()
        region = Region(0, 0, image.width // 2, image.height // 2)
        service.regions(image, region, image, region)
        regional = time.perf_counter()
        repeated_image = service.load(path)
        service.stats(repeated_image)
        warm = time.perf_counter()
        cache = service.cache_info()
    return {
        "file": Path(path).name,
        "width": image.width,
        "height": image.height,
        "analysis_shape": list(image.rgb.shape),
        "import_s": imported - start,
        "load_s": loaded - imported,
        "stats_s": analyzed - loaded,
        "compare_s": compared - analyzed,
        "region_s": regional - compared,
        "repeat_load_stats_s": warm - regional,
        "total_s": warm - start,
        "peak_memory_bytes": peak_memory_bytes(),
        "cache": cache,
        "mean_brightness": stats.mean_brightness,
        "self_delta_e": comparison.mean_lab_delta_e,
    }


def make_fixtures(directory):
    import numpy as np
    from PIL import Image

    directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for width, height in ((640, 480), (4912, 3264), (6000, 4000)):
        path = directory / f"synthetic-{width}x{height}.jpg"
        if not path.exists():
            # Bounded deterministic rows; gradients, bright/dark and colored areas.
            pixels = np.empty((height, width, 3), dtype=np.uint8)
            x = np.arange(width, dtype=np.uint32)
            for y in range(height):
                pixels[y, :, 0] = (x * 255 // width + y * 31 // height) % 256
                pixels[y, :, 1] = (x * 103 // width + y * 151 // height) % 256
                pixels[y, :, 2] = (x * 67 // width + y * 189 // height) % 256
            Image.fromarray(pixels).save(path, quality=92)
        paths.append(path)
    return paths


def export_baseline(ref):
    """Read historical core files without switching or modifying the checkout."""
    destination = ROOT / "work/performance/baseline-source"
    files = (
        "framesense/__init__.py",
        "framesense/core/__init__.py",
        "framesense/core/color.py",
        "framesense/core/loader.py",
        "framesense/core/stats.py",
        "framesense/core/compare.py",
        "framesense/core/regions.py",
    )
    for name in files:
        result = subprocess.run(
            ["git", "show", f"{ref}:{name}"], cwd=ROOT, capture_output=True, check=True
        )
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result.stdout)
    return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=("baseline", "optimized"), default="optimized"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "work/performance/optimized.json"
    )
    parser.add_argument("--worker", type=Path)
    parser.add_argument("--baseline-ref", default="baseline-colorlab-20261014")
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker, args.mode)))
        return
    rows = []
    environment = os.environ.copy()
    if args.mode == "baseline":
        environment["FRAMESENSE_BENCHMARK_SOURCE_ROOT"] = str(
            export_baseline(args.baseline_ref)
        )
    for path in make_fixtures(ROOT / "work/performance/fixtures"):
        started = time.perf_counter()
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--mode",
                args.mode,
                "--worker",
                str(path),
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=True,
            timeout=240,
        )
        row = json.loads(result.stdout)
        row["process_wall_s"] = time.perf_counter() - started
        rows.append(row)
        print(
            f"{path.name}: {row['total_s']:.3f}s, peak {row['peak_memory_bytes'] / 1048576:.1f} MiB",
            flush=True,
        )
    payload = {
        "mode": args.mode,
        "python": sys.version,
        "platform": platform.platform(),
        "baseline_ref": args.baseline_ref if args.mode == "baseline" else None,
        "processor": platform.processor(),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "fixture": "deterministic synthetic JPG gradients, quality 92; no private photos",
        "measurements": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
