"""Arama modu (hedef kaybinda yaw taramasi) birim testleri."""

from src.pid_controller import TrackingController
from src.tracking_interface import TrackingData

DT = 1 / 30


def _valid(x=0.4, y=0.0, area=0.01):
    return TrackingData(durum="TAKIP", timestamp=0.0,
                        x_error=x, y_error=y, bbox_area=area)


def _lost():
    return TrackingData.lost(0.0)


def test_coast_sonra_arama_saga():
    c = TrackingController(reference_area=0.01, coast_frames=3)
    c.compute(_valid(x=0.4), dt=DT)          # hedef sagda goruldu

    outs = [c.compute(_lost(), dt=DT) for _ in range(3)]
    assert all(o.coasting for o in outs)

    o = c.compute(_lost(), dt=DT)            # coast bitti -> arama
    assert o.searching and not o.coasting
    assert o.yaw_rate > 0                    # saga tarama
    assert o.pitch == 0.0 and o.roll == 0.0 and o.throttle == 0.0


def test_arama_sola():
    c = TrackingController(reference_area=0.01, coast_frames=1)
    c.compute(_valid(x=-0.4), dt=DT)         # hedef solda goruldu
    c.compute(_lost(), dt=DT)                # coast
    o = c.compute(_lost(), dt=DT)
    assert o.searching and o.yaw_rate < 0


def test_yeniden_yakalama_temiz_baslar():
    c = TrackingController(reference_area=0.01, coast_frames=1)
    c.compute(_valid(x=0.4), dt=DT)
    for _ in range(10):
        c.compute(_lost(), dt=DT)
    assert c.pid_yaw.integral == 0.0         # aramaya gecerken resetlendi

    o = c.compute(_valid(x=0.2), dt=DT)
    assert not o.searching and not o.coasting
    assert c.lost_frames == 0


def test_arama_hizi_limitte():
    c = TrackingController(reference_area=0.01, coast_frames=1,
                           search_yaw_rate=0.12)
    c.compute(_valid(x=0.4), dt=DT)
    c.compute(_lost(), dt=DT)
    o = c.compute(_lost(), dt=DT)
    assert abs(o.yaw_rate) == 0.12           # sabit, yavas tarama
