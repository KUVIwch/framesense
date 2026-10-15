"""Content cache invariants, original-coordinate mapping and concurrent workers."""

from concurrent.futures import ThreadPoolExecutor
import os

import numpy as np
from PIL import Image
import pytest

from framesense.core.regions import Region
from framesense.core.service import AnalysisService


def save(path, color=(120, 80, 50), size=(160, 100)):
    Image.new("RGB", size, color).save(path)
    return path


def test_repeated_load_content_hit_and_readonly(tmp_path):
    service = AnalysisService()
    path = save(tmp_path / "中文照片.png")
    first = service.load(path)
    assert service.load(path) is first
    assert not first.rgb.flags.writeable
    assert service.cache_info()["hits"] == 1
    with pytest.raises(ValueError):
        first.rgb[0, 0] = 0


def test_content_change_invalidates_even_with_restored_timestamp(tmp_path):
    path = save(tmp_path / "photo.png")
    before_time = path.stat().st_mtime_ns
    service = AnalysisService()
    before = service.load(path)
    save(path, (50, 80, 120))
    os.utime(path, ns=(before_time, before_time))
    after = service.load(path)
    assert after.file_sha256 != before.file_sha256
    assert service.stats(after).mean_rgb != service.stats(before).mean_rgb


def test_content_dedup_keeps_current_path(tmp_path):
    first_path = save(tmp_path / "first.png")
    second_path = tmp_path / "second.png"
    second_path.write_bytes(first_path.read_bytes())
    service = AnalysisService()
    first, second = service.load(first_path), service.load(second_path)
    assert first.rgb is second.rgb
    assert second.source_path == str(second_path.resolve())


def test_results_are_defensive_copies(tmp_path):
    service = AnalysisService()
    image = service.load(save(tmp_path / "test.png"))
    result = service.stats(image)
    result.histogram[0] = -100
    assert service.stats(image).histogram[0] >= 0
    comparison = service.compare(image, image)
    comparison.mean_lab_delta_e = 100
    assert service.compare(image, image).mean_lab_delta_e == 0


def test_cache_lru_and_byte_bound_and_clear(tmp_path):
    service = AnalysisService(max_cache_bytes=7000, max_entries=2)
    for n in range(12):
        service.load(save(tmp_path / f"{n}.png", (n, 20, 30), (32, 32)))
        info = service.cache_info()
        assert info["entries"] <= 2
        assert info["bytes"] <= 7000
    service.clear()
    assert service.cache_info()["entries"] == 0
    assert service.cache_info()["bytes"] == 0


def test_oversized_item_is_not_retained(tmp_path):
    service = AnalysisService(max_cache_bytes=10)
    service.load(save(tmp_path / "photo.png"))
    assert service.cache_info()["entries"] == 0


def test_original_dimensions_and_region_coordinates(tmp_path):
    path = tmp_path / "wide.png"
    array = np.zeros((100, 400, 3), dtype=np.uint8)
    array[:, :200] = (200, 20, 20)
    array[:, 200:] = (20, 20, 200)
    Image.fromarray(array).save(path)
    service = AnalysisService(analysis_max_side=80, preview_max_side=160)
    image = service.load(path)
    assert (image.width, image.height) == (400, 100)
    assert image.rgb.shape == (20, 80, 3)
    assert image.preview_rgb.shape == (40, 160, 3)
    assert service.stats(image).width == 400
    left, right = Region(0, 0, 160, 100), Region(240, 0, 160, 100)
    difference = service.regions(image, left, image, right)
    assert difference["delta_e_cie76"] > 80
    assert difference["b_delta"] < -80
    assert difference["reference_sample_count"] <= 512**2
    with pytest.raises(ValueError):
        service.regions(image, Region(500, 0, 20, 20), image, right)


def test_concurrent_loads_do_not_duplicate_decode(tmp_path, monkeypatch):
    import framesense.core.service as module

    count = []
    real_load = module.load_image

    def counted(*args, **kwargs):
        count.append(1)
        return real_load(*args, **kwargs)

    monkeypatch.setattr(module, "load_image", counted)
    service = AnalysisService()
    path = save(tmp_path / "photo.png")
    with ThreadPoolExecutor(max_workers=4) as workers:
        images = list(workers.map(service.load, [path] * 8))
    assert len(count) == 1
    assert all(image is images[0] for image in images)


def test_invalid_settings():
    with pytest.raises(ValueError):
        AnalysisService(max_cache_bytes=0)
