import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.camera import CameraModel, MIN_BBOX_SIDE_PX


def test_odak_uzakligi():
    cam = CameraModel(1280, 720, 70)
    assert abs(cam.focal_px - 914) < 2


def test_merkezdeki_hedef_kadraj_ortasinda():
    cam = CameraModel(1280, 720, 70)
    box = cam.project(5.0, 0.0, 0.0)
    x, y, w, h = box
    assert abs((x + w / 2) - 640) < 1
    assert abs((y + h / 2) - 360) < 1


def test_arkadaki_hedef_gorunmez():
    cam = CameraModel()
    assert cam.project(-1.0, 0.0, 0.0) is None


def test_uzaklastikca_kucuur():
    cam = CameraModel()
    assert cam.size_at(4.0) > cam.size_at(8.0)


def test_max_menzil_sartname_kriteri():
    """max_range_for_min_size mesafesinde bbox tam 64 px olmali."""
    cam = CameraModel(1280, 720, 70)
    d = cam.max_range_for_min_size()
    assert abs(cam.size_at(d) - MIN_BBOX_SIDE_PX) < 0.1


def test_mevcut_konfigurasyon_yetersiz():
    """70 FOV ile 6 metrede sartname kriteri saglanmiyor."""
    cam = CameraModel(1280, 720, 70)
    assert cam.size_at(6.0) < MIN_BBOX_SIDE_PX


def test_dar_fov_yeterli():
    """40 FOV ile 6 metrede kriter saglaniyor."""
    cam = CameraModel(1280, 720, 40)
    assert cam.size_at(6.0) > MIN_BBOX_SIDE_PX


def test_dikey_yari_fov():
    cam = CameraModel(1280, 720, 40)
    assert 11.0 < cam.vertical_half_fov_deg() < 12.5