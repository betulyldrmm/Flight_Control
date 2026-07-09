import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.metrics import iou, frame_success, maneuver_success, logging_rate_ok


def test_iou_tam_ortusme():
    assert iou((0, 0, 100, 100), (0, 0, 100, 100)) == 1.0


def test_iou_hic_ortusmeme():
    assert iou((0, 0, 10, 10), (500, 500, 10, 10)) == 0.0


def test_iou_yarim_ortusme():
    # 100x100 kutular, 50 piksel kaymis -> kesisim 50x100=5000, birlesim 15000
    assert abs(iou((0, 0, 100, 100), (50, 0, 100, 100)) - 1/3) < 0.01


def test_kucuk_hedef_basarisiz():
    # 60x60 = 3600 < 4096 -> sartname sarti saglanmiyor
    kucuk = (0, 0, 60, 60)
    assert frame_success(kucuk, kucuk) is False


def test_yeterli_boyut_basarili():
    # 70x70 = 4900 > 4096
    buyuk = (0, 0, 70, 70)
    assert frame_success(buyuk, buyuk) is True


def test_manevra_esigi():
    assert maneuver_success([True] * 80 + [False] * 20) is True   # %80
    assert maneuver_success([True] * 79 + [False] * 21) is False  # %79


def test_loglama_hizi():
    assert logging_rate_ok([0.0, 0.2, 0.4, 0.6, 0.8]) is True      # 5 kayit
    assert logging_rate_ok([0.0, 0.25, 0.5, 0.75]) is False        # 4 kayit