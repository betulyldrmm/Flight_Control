import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.pid_controller import TrackingController
from src.tracking_interface import TrackingData


def make_data(x_err, y_err, area=0.0075):
    return TrackingData(durum="TAKIP", timestamp=0.0,
                        x_error=x_err, y_error=y_err, bbox_area=area,
                        bbox_px=area * 1280 * 720, guven_skoru=0.9)


def test_deadband_komut_uretmez():
    c = TrackingController()
    out = c.compute(make_data(0.10, -0.15), dt=0.033)
    assert out.in_deadband is True
    assert out.yaw_rate == 0.0
    assert out.pitch == 0.0


def test_deadband_disinda_komut_uretir():
    c = TrackingController()
    out = c.compute(make_data(0.60, 0.0), dt=0.033)
    assert out.yaw_rate > 0          # hedef sagda -> saga don
    assert out.in_deadband is False


def test_roll_yaw_ile_ayni_yonde():
    c = TrackingController()
    out = c.compute(make_data(0.80, 0.0), dt=0.033)
    assert out.roll > 0
    assert abs(out.roll) <= abs(out.yaw_rate)


def test_limitler_asilmiyor():
    c = TrackingController()
    for _ in range(200):
        out = c.compute(make_data(1.0, 1.0, area=0.0001), dt=0.033)
    assert -0.5 <= out.yaw_rate <= 0.5
    assert -0.4 <= out.pitch <= 0.4
    assert -0.3 <= out.roll <= 0.3
    assert -0.3 <= out.throttle <= 0.3


def test_hedef_kucukse_yaklas():
    c = TrackingController()
    out = c.compute(make_data(0.0, 0.0, area=0.001), dt=0.033)
    assert out.throttle > 0


def test_hedef_kayipsa_sifir_komut():
    c = TrackingController()
    lost = TrackingData.lost(timestamp=1.0)
    out = c.compute(lost, dt=0.033)
    assert out.as_tuple() == (0.0, 0.0, 0.0, 0.0)