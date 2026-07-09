import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.failsafe import FailsafeMonitor, FailsafeState


class FakeMaster:
    target_system = 1
    target_component = 1
    def recv_match(self, **kw):
        return None


def make_fs(**kw):
    fs = FailsafeMonitor(FakeMaster(), **kw)
    return fs


def test_normal_durum():
    fs = make_fs()
    st = fs.update(data_received=True, target_detected=True, now=0.0)
    assert st == FailsafeState.NORMAL
    assert fs.active is False


def test_hedef_kaybi_hover():
    fs = make_fs(target_lost_hover=1.5)
    fs.update(True, True, now=0.0)
    st = fs.update(True, False, now=2.0)        # 2 sn hedef yok
    assert st == FailsafeState.TARGET_LOST
    assert fs.should_hover() is True
    assert fs.should_land(now=2.0) is False     # LAND cok erken


def test_hedef_kaybi_uzun_surerse_land():
    fs = make_fs(target_lost_hover=1.5, target_lost_land=15.0)
    fs.update(True, True, now=0.0)
    fs.update(True, False, now=20.0)
    assert fs.should_land(now=20.0) is True


def test_veri_kesilirse_data_timeout():
    fs = make_fs(data_timeout=1.0)
    fs.update(True, True, now=0.0)
    st = fs.update(data_received=False, target_detected=False, now=2.0)
    assert st == FailsafeState.DATA_TIMEOUT
    assert fs.should_hover() is True


def test_heartbeat_kesilirse_link_lost():
    fs = make_fs(link_timeout=3.0)
    fs.update(True, True, now=0.0)
    fs.last_heartbeat = 0.0
    st = fs.update(True, True, now=5.0)
    assert st == FailsafeState.LINK_LOST
    assert fs.should_land(now=5.0) is True


def test_oncelik_sirasi():
    """Baglanti kaybi, hedef kaybindan onceliklidir."""
    fs = make_fs()
    fs.last_heartbeat = 0.0
    st = fs.update(data_received=False, target_detected=False, now=10.0)
    assert st == FailsafeState.LINK_LOST