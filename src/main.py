"""
Ana ucus kontrol dongusu.

    tracking verisi -> TrackingData -> PID -> failsafe -> MAVLink -> log

Kaynak secenekleri:
  --source fake    : simule hedef (donanim gerektirmez)
  --source socket  : Sercan'in tracking modulunden UDP/JSON
  --source stdin   : satir satir JSON (test icin)

Hedef secenekleri:
  --target sitl    : tcp:127.0.0.1:5760
  --target pixhawk : /dev/ttyTHS1 (Jetson uzerinde)
  --target none    : MAVLink yok, sadece PID + log (kuru calisma)
"""



import argparse
import json
import math
import signal
import sys
import time
from typing import Iterator, Optional

from src.camera import CAM_720P_40, CameraModel
from src.connection import connect, send_gcs_heartbeat, wait_ready
from src import flight_manager as fm
from src.failsafe import FailsafeMonitor, FailsafeState
from src.logger import FlightLogger
from src.pid_controller import TrackingController, ZERO_OUTPUT
from src.tracking_interface import TrackingData

FPS = 30
DT = 1.0 / FPS

# Secilecek lens. Grup karari bekleniyor; 70 FOV sartname kriterini saglamiyor.
# bkz. tests/camera_range_analysis.py
CAM: CameraModel = CAM_720P_40

_running = True


def _stop(signum, frame):
    global _running
    _running = False
    print("\nDurduruluyor...")


signal.signal(signal.SIGINT, _stop)


# ---------------------------------------------------------------
# Veri kaynaklari
# ---------------------------------------------------------------

def source_fake(frame_w: int = None, frame_h: int = None) -> Iterator[Optional[TrackingData]]:
    """Simule hedef: yatay + dikey sinus, 12-15. saniye arasi hedef kaybi."""
    frame_w = frame_w or CAM.w
    frame_h = frame_h or CAM.h
    i = 0
    t0 = time.time()
    next_t = t0

    while _running:
        t = time.time() - t0

        if 12.0 <= t < 15.0:
            yield TrackingData.lost(t, i)
        else:
            cx = frame_w / 2 + 0.23 * frame_w * math.sin(t * 0.8)
            cy = frame_h / 2 + 0.17 * frame_h * math.sin(t * 0.5)
            side = 90 + 20 * math.sin(t * 0.3)
            yield TrackingData.from_boxes(
                (cx - side / 2, cy - side / 2, side, side),
                t=t, frame_id=i, frame_w=frame_w, frame_h=frame_h)
        i += 1

        # Gercek 30 Hz tempo: islem suresini dusup kalan kadar uyu
        next_t += DT
        delay = next_t - time.time()
        if delay > 0:
            time.sleep(delay)
        else:
            next_t = time.time()   # geride kaldiysak sifirla, birikme olmasin


def source_stdin(frame_w: int = None, frame_h: int = None) -> Iterator[Optional[TrackingData]]:
    """Satir satir JSON oku."""
    frame_w = frame_w or CAM.w
    frame_h = frame_h or CAM.h

    for line in sys.stdin:
        if not _running:
            break
        line = line.strip()
        if not line:
            continue
        try:
            yield TrackingData.from_dict(json.loads(line), frame_w, frame_h)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Bozuk veri atlandi: {e}")
            yield None


def source_socket(host: str = "127.0.0.1", port: int = 5005,
                  frame_w: int = None, frame_h: int = None) -> Iterator[Optional[TrackingData]]:
    """UDP uzerinden JSON paket al (tracking modulu)."""
    import socket
    frame_w = frame_w or CAM.w
    frame_h = frame_h or CAM.h

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    # 0.1 sn: veri kesilse bile dongu >= 10 Hz doner.
    # (0.5 olsaydi log hizi 2 Hz'e duser, sartname >= 5 kayit/sn ister.)
    sock.settimeout(0.1)
    print(f"UDP dinleniyor: {host}:{port}")

    while _running:
        try:
            payload, _ = sock.recvfrom(4096)
            yield TrackingData.from_dict(json.loads(payload), frame_w, frame_h)
        except socket.timeout:
            yield None                    # veri yok -> failsafe gorecek
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Bozuk paket: {e}")
            yield None


SOURCES = {"fake": source_fake, "stdin": source_stdin, "socket": source_socket}

TARGETS = {
    # 5762 = SITL SERIAL1. 5760'i sim_vehicle'in baslattigi MAVProxy
    # tutar; oraya baglanirsak FC verisi bize gelmez.
    "sitl": "tcp:127.0.0.1:5762",
    "pixhawk": "/dev/ttyTHS1",
    "none": None,
}


# ---------------------------------------------------------------
# Ana dongu
# ---------------------------------------------------------------

def run(source_name: str, target_name: str,
        takeoff_alt: float = 5.0, duration: Optional[float] = None,
        desired_distance: float = 4.0, log_dir: str = "logs"):

    print(f"Kamera: {CAM}")
    print(f"Hedef takip mesafesi: {desired_distance} m "
          f"(bu mesafede bbox {CAM.size_at(desired_distance):.0f} px)")

    master = None
    if TARGETS[target_name] is not None:
        master = connect(TARGETS[target_name])
        fm.request_streams(master, rate_hz=10)
        time.sleep(1)

    ctrl = TrackingController(cam=CAM, desired_distance_m=desired_distance)
    logger = FlightLogger(log_dir).start()
    fs = FailsafeMonitor(master) if master else None

    if master:
        if not wait_ready(master, timeout=20.0):
            print("UYARI: pre-arm saglik biti dogrulanamadi, devam ediliyor.")
        fm.set_mode(master, "GUIDED_NOGPS")
        if not fm.arm(master):
            print("Arm edilemedi, cikiliyor.")
            logger.close()
            return

        print(f"Kalkis: {takeoff_alt} m")
        t0 = time.time()
        last_hb = 0.0
        last_alt = None
        while _running and time.time() - t0 < 12.0:
            alt = fm.get_altitude(master, timeout=0.05)
            if alt is not None:
                last_alt = alt
            # Karari son BILINEN irtifaya gore ver; tek bir bos okuma
            # kalkisi kesmesin
            if last_alt is not None and last_alt >= takeoff_alt:
                print(f"Kalkis tamam: {last_alt:.1f} m")
                break
            if last_alt is None and time.time() - t0 > 6.0:
                print("Irtifa hic okunamadi, sure limitiyle kalkis kesildi.")
                break
            if time.time() - last_hb > 1.0:
                send_gcs_heartbeat(master)
                last_hb = time.time()
            fm.send_attitude_target(master, thrust=0.70)
            time.sleep(0.05)
        else:
            print(f"Kalkis suresi doldu (son irtifa: "
                  f"{last_alt:.1f} m)" if last_alt is not None
                  else "Kalkis suresi doldu (irtifa okunamadi)")

    # Arm + kalkis dakikalarca surmus olabilir; failsafe saatlerini
    # simdi sifirla, yoksa dongunun ilk turunda sahte LINK_LOST olusur.
    if fs:
        fs.reset()

    print("\nOtonom takip basladi. Ctrl+C ile durdur.\n")
    src = SOURCES[source_name]()
    loop_t0 = time.time()
    last_report = 0.0
    last_hb = 0.0
    prev_t = None

    for data in src:
        if not _running:
            break
        if duration and time.time() - loop_t0 > duration:
            break

        # GCS heartbeat (FS_GCS_ENABLE=1 icin zorunlu, ~1 Hz)
        if master and time.time() - last_hb > 1.0:
            send_gcs_heartbeat(master)
            last_hb = time.time()

        data_received = data is not None
        target_ok = data_received and data.is_valid()

        # 1) Failsafe degerlendirmesi
        state = FailsafeState.NORMAL
        if fs:
            fs.poll_heartbeat()
            state = fs.update(data_received, target_ok)

            if fs.should_land():
                fs.trigger_land()
                break

        # 2) Kontrol (dt olculur; kaynak yavassa sabit DT yanlis olur)
        now_t = time.time()
        dt = DT if prev_t is None else min(max(now_t - prev_t, 0.001), 0.2)
        prev_t = now_t

        if not data_received:
            # Veri gelmedi: kayip frame olarak isle -> coasting devreye girer
            data = TrackingData.lost(time.time() - loop_t0)
        out = ctrl.compute(data, dt=dt)

        if fs and fs.should_hover():
            # Coasting'e her durumda izin ver. Aramaya yalnizca hedef
            # kaybinda izin ver; veri kesintisinde (DATA_TIMEOUT) korle
            # donmek tehlikeli -> hover.
            keep = out.coasting or (
                out.searching and state == FailsafeState.TARGET_LOST)
            if not keep:
                out = ZERO_OUTPUT

        # 3) Komut
        if master and not (fs and fs.land_sent):
            fm.send_control_output(master, out)

        # 4) Log
        logger.log(data, out,
                   flight_mode=state.value if fs else "SIM",
                   failsafe_active=bool(fs and fs.active))

        # 5) Durum raporu
        now = time.time() - loop_t0
        if now - last_report > 2.0:
            last_report = now
            bbox = f"{data.bbox_px:.0f}px" if data.bbox_px else "yok"
            att = fm.get_attitude(master, timeout=0.1) if master else None
            yaw_s = f"arac_yaw={math.degrees(att[2]):+6.1f}" if att else ""
            print(f"t={now:5.1f}s  {data.durum:<12} bbox={bbox:>8}  "
                  f"yaw_cmd={out.yaw_rate:+.3f} thr={out.throttle:+.3f}  "
                  f"{yaw_s}  {fs.status() if fs else ''}")

    # Kapanis
    if master:
        if not (fs and fs.land_sent):
            print("\nIniyor...")
            fm.land(master)
        fm.wait_landed(master)

    logger.close()
    print("\n" + logger.rate_report())


def main():
    p = argparse.ArgumentParser(description="FPV Drone Izleme - Ucus Kontrol")
    p.add_argument("--source", choices=SOURCES, default="fake")
    p.add_argument("--target", choices=TARGETS, default="none")
    p.add_argument("--alt", type=float, default=5.0)
    p.add_argument("--dist", type=float, default=4.0,
                   help="hedef takip mesafesi (m)")
    p.add_argument("--duration", type=float, default=None,
                   help="saniye; verilmezse Ctrl+C'ye kadar")
    args = p.parse_args()

    run(args.source, args.target, args.alt, args.duration, args.dist)


if __name__ == "__main__":
    main()