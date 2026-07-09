import sys, os, csv
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.logger import FlightLogger, HEADER
from src.tracking_interface import TrackingData
from src.pid_controller import TrackingController


def test_baslik_ve_satir_yazilir(tmp_path):
    lg = FlightLogger(str(tmp_path)).start(t0=0.0)
    d = TrackingData.from_boxes((100, 200, 80, 80), t=0.0, frame_id=1)
    ctrl = TrackingController()
    out = ctrl.compute(d, dt=0.033)
    lg.log(d, out, flight_mode="GUIDED_NOGPS", t_ms=0)
    lg.close()

    with open(lg.path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == HEADER
    assert len(rows) == 2
    assert rows[1][2] == "TAKIP"


def test_zaman_otonom_moddan_baslar(tmp_path):
    lg = FlightLogger(str(tmp_path)).start(t0=1000.0)
    assert lg.elapsed_ms(now=1000.0) == 0
    assert lg.elapsed_ms(now=1002.5) == 2500
    lg.close()


def test_overlay_formati():
    assert FlightLogger.overlay_text(0) == "0.000"
    assert FlightLogger.overlay_text(2500) == "2.500"
    assert FlightLogger.overlay_text(65042) == "65.042"


def test_hedef_kayip_satiri(tmp_path):
    lg = FlightLogger(str(tmp_path)).start(t0=0.0)
    lost = TrackingData.lost(timestamp=1.0, frame_id=7)
    row = lg.log(lost, None, t_ms=1000)
    lg.close()
    assert row.durum == "HEDEF_KAYIP"
    assert row.bbox_x is None


def test_loglama_hizi_kontrolu(tmp_path):
    lg = FlightLogger(str(tmp_path)).start(t0=0.0)
    d = TrackingData.from_boxes((100, 200, 80, 80), t=0.0)
    for i in range(30):                       # 30 Hz, 1 saniye
        lg.log(d, None, t_ms=int(i * 1000 / 30))
    lg.close()
    assert lg.rate_ok(min_hz=5) is True


def test_yetersiz_hiz_yakalanir(tmp_path):
    lg = FlightLogger(str(tmp_path)).start(t0=0.0)
    d = TrackingData.from_boxes((100, 200, 80, 80), t=0.0)
    for i in range(4):                        # saniyede sadece 4 kayit
        lg.log(d, None, t_ms=i * 250)
    lg.close()
    assert lg.rate_ok(min_hz=5) is False
    
def test_kismi_son_saniye_yok_sayilir(tmp_path):
    """Son saniye kismi ise loglama hizi yine yeterli sayilmali."""
    lg = FlightLogger(str(tmp_path)).start(t0=0.0)
    d = TrackingData.from_boxes((100, 200, 80, 80), t=0.0)
    for i in range(30):                    # tam 1. saniye: 30 kayit
        lg.log(d, None, t_ms=int(i * 1000 / 30))
    for i in range(30):                    # tam 2. saniye
        lg.log(d, None, t_ms=1000 + int(i * 1000 / 30))
    for i in range(2):                     # 3. saniye: sadece 2 kayit (kismi)
        lg.log(d, None, t_ms=2000 + i * 33)
    lg.close()
    assert lg.rate_ok(min_hz=5) is True