"""Thread-safe, bounded, content-addressed image analysis for the desktop app.

The cache is process-local and keeps no private photos on disk. Originals are
never written. Callers may keep returned images, so the cache limit describes
retained cache bytes, not total process memory. All image arrays are read-only.
"""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from dataclasses import fields, is_dataclass, replace
import hashlib
import math
from pathlib import Path
import sys
from threading import RLock

import numpy as np

from framesense.core.compare import ImageComparison, compare_images
from framesense.core.loader import ImageData, load_image, validate_input_path
from framesense.core.regions import (
    Region,
    compute_region_stats,
    region_difference,
    validate_region,
)
from framesense.core.stats import ImageStats, compute_image_stats

ALGORITHM_VERSION = "colorlab-v2-rec709-hsl-lab-mean-distribution"


def _retained_bytes(value, seen=None) -> int:
    """Conservative retained-size estimate, including Python result containers."""
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    size = sys.getsizeof(value)
    if isinstance(value, np.ndarray):
        return size + (value.nbytes if not value.flags.owndata else 0)
    if is_dataclass(value):
        return size + sum(
            _retained_bytes(getattr(value, f.name), seen) for f in fields(value)
        )
    if isinstance(value, dict):
        return size + sum(
            _retained_bytes(k, seen) + _retained_bytes(v, seen)
            for k, v in value.items()
        )
    if isinstance(value, (list, tuple)):
        return size + sum(_retained_bytes(v, seen) for v in value)
    return size


class AnalysisService:
    """One shared service per application; safe for QThreadPool workers.

    Coordinates accepted by ``regions`` are original, EXIF-oriented pixel
    coordinates. They are mapped to the sampled analysis raster internally.
    A single lock also prevents simultaneous identical misses from decoding the
    same photo several times. UI work never runs inside this service.
    """

    def __init__(
        self,
        max_cache_bytes=128 * 1024 * 1024,
        analysis_max_side=1600,
        preview_max_side=1600,
        max_entries=24,
    ):
        if min(max_cache_bytes, analysis_max_side, preview_max_side, max_entries) < 1:
            raise ValueError("缓存容量、条目数和分析尺寸必须大于零")
        self.max_cache_bytes = int(max_cache_bytes)
        self.analysis_max_side = int(analysis_max_side)
        self.preview_max_side = int(preview_max_side)
        self.max_entries = int(max_entries)
        self._cache = OrderedDict()
        self._bytes = self._hits = self._misses = 0
        self._lock = RLock()

    def _get(self, key):
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        self._hits += 1
        self._cache.move_to_end(key)
        return entry[0]

    def _put(self, key, value):
        size = _retained_bytes(value) + _retained_bytes(key)
        if size > self.max_cache_bytes:
            return value
        old = self._cache.pop(key, None)
        if old is not None:
            self._bytes -= old[1]
        self._cache[key] = (value, size)
        self._bytes += size
        while self._bytes > self.max_cache_bytes or len(self._cache) > self.max_entries:
            _, (_, released) = self._cache.popitem(last=False)
            self._bytes -= released
        return value

    def _identity(self, image: ImageData):
        digest = image.file_sha256
        if not digest:
            digest = hashlib.sha256(
                np.ascontiguousarray(image.rgb).tobytes()
            ).hexdigest()
        return (
            ALGORITHM_VERSION,
            digest,
            image.width,
            image.height,
            image.rgb.shape,
            self.analysis_max_side,
            self.preview_max_side,
        )

    def load(self, path: str | Path) -> ImageData:
        path = validate_input_path(path)
        # Read content every time: replacement with identical size/mtime must
        # invalidate the cache as well. No path-only trust shortcut is used.
        with self._lock:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            key = (
                "image",
                ALGORITHM_VERSION,
                digest.hexdigest(),
                self.analysis_max_side,
                self.preview_max_side,
            )
            cached = self._get(key)
            if cached is not None:
                return (
                    cached
                    if cached.source_path == str(path)
                    else replace(cached, source_path=str(path))
                )
            image = load_image(
                path,
                max_side=self.analysis_max_side,
                preview_max_side=self.preview_max_side,
            )
            image.rgb.setflags(write=False)
            image.preview_rgb.setflags(write=False)
            # A file can be replaced between hashing and decoding. Cache only
            # under the bytes actually decoded, never under the earlier digest.
            actual_key = (
                "image",
                ALGORITHM_VERSION,
                image.file_sha256,
                self.analysis_max_side,
                self.preview_max_side,
            )
            return self._put(actual_key, image)

    def stats(self, image: ImageData) -> ImageStats:
        key = ("stats", self._identity(image), 1024)
        with self._lock:
            result = self._get(key)
            if result is None:
                result = compute_image_stats(image.rgb)
                result.width, result.height = image.width, image.height
                self._put(key, result)
            return deepcopy(result)

    def compare(self, reference: ImageData, source: ImageData) -> ImageComparison:
        key = ("compare", self._identity(reference), self._identity(source), 256)
        with self._lock:
            result = self._get(key)
            if result is None:
                result = self._put(key, compare_images(reference.rgb, source.rgb))
            return deepcopy(result)

    @staticmethod
    def _mapped_region(image: ImageData, region: Region):
        original = validate_region(region, (image.height, image.width))
        h, w = image.rgb.shape[:2]
        x, y = math.floor(original.x * w / image.width), math.floor(
            original.y * h / image.height
        )
        x2 = min(w, math.ceil((original.x + original.width) * w / image.width))
        y2 = min(h, math.ceil((original.y + original.height) * h / image.height))
        return original, Region(x, y, x2 - x, y2 - y)

    def regions(
        self,
        reference: ImageData,
        ref_region: Region,
        source: ImageData,
        source_region: Region,
    ) -> dict:
        original_ref, mapped_ref = self._mapped_region(reference, ref_region)
        original_source, mapped_source = self._mapped_region(source, source_region)
        key = (
            "regions",
            self._identity(reference),
            original_ref,
            self._identity(source),
            original_source,
            512,
        )
        with self._lock:
            result = self._get(key)
            if result is None:
                ref_stats = compute_region_stats(
                    reference.rgb, mapped_ref, min_pixels=1
                )
                src_stats = compute_region_stats(
                    source.rgb, mapped_source, min_pixels=1
                )
                result = region_difference(ref_stats, src_stats)
                result["reference_sample_count"] = ref_stats.sample_count
                result["source_sample_count"] = src_stats.sample_count
                result[
                    "note"
                ] += " 区域从原图坐标映射到分析预览，极小区域可能只覆盖少量采样像素。"
                self._put(key, result)
            return deepcopy(result)

    def clear(self):
        with self._lock:
            self._cache.clear()
            self._bytes = self._hits = self._misses = 0

    def cache_info(self):
        with self._lock:
            return {
                "entries": len(self._cache),
                "bytes": self._bytes,
                "max_cache_bytes": self.max_cache_bytes,
                "max_entries": self.max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "algorithm": ALGORITHM_VERSION,
            }
