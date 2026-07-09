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

from src.connection import connect
from src import flight_manager as fm
from src.failsafe import FailsafeMonitor, FailsafeState
from src.logger import FlightLogger
from src.pid_controller import TrackingController, ZERO_OUTPUT
from src.tracking_interface import TrackingData

FPS = 30
DT = 1.0 / FPS

_running = True


def _stop(signum, frame):
    global _running
    _running = False
    print("\nDurduruluyor...")


signal.signal(signal.SIGINT, _stop)


# ---------------------------------------------------------------
# Veri kaynaklari
# ---------------------------------------------------------------

def source_fake(frame_w=1280, frame_h=720) -> Iterator[Optional[TrackingData]]:
    """Simule hedef: yatay sinus + arada hedef kaybi."""
    i = 0
    t0 = time.time()
    while _running:
        t = time.time() - t0

        # 12-15. saniye arasi hedef kayip
        if 12.0 <= t < 15.0:
            yield TrackingData.lost(t, i)
        else:
            cx = frame_w / 2 + 300 * math.sin(t * 0.8)
            cy = frame_h / 2 + 120 * math.sin(t * 0.5)
            side = 90 + 20 * math.sin(t * 0.3)
            yield TrackingData.from_boxes(
                (cx - side / 2, cy - side / 2, side, side),
                t=t, frame_id=i, frame_w=frame_w, frame_h=frame_h)
        i += 1
        time.sleep(DT)


def source_stdin(frame_w=1280, frame_h=720) -> Iterator[Optional[TrackingData]]:
    """Satir satir JSON oku."""
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


def source_socket(host="127.0.0.1", port=5005,
                  frame_w=1280, frame_h=720) -> Iterator[Optional[TrackingData]]:
    """UDP uzerinden JSON paket al (Sercan'in tracking modulu)."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    sock.settimeout(0.5)
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
    "sitl": "tcp:127.0.0.1:5760",
    "pixhawk": "/dev/ttyTHS1",
    "none": None,
}

# ---------------------------------------------------------------
# Ana dongu
# ---------------------------------------------------------------

def run(source_name: str, target_name: str,
        takeoff_alt: float = 5.0, duration: Optional[float] = None,
        log_dir: str = "logs"):

    master = None
    if TARGETS[target_name] is not None:
        master = connect(TARGETS[target_name])
        fm.request_streams(master, rate_hz=10)
        time.sleep(1)

    ctrl = TrackingController(desired_distance_m=4.0)
    logger = FlightLogger(log_dir).start()
    fs = FailsafeMonitor(master) if master else None

    if master:
        fm.set_mode(master, "GUIDED_NOGPS")
        if not fm.arm(master):
            print("Arm edilemedi, cikiliyor.")
            logger.close()
            return

        print(f"Kalkis: {takeoff_alt} m")
        t0 = time.time()
        while time.time() - t0 < 6.0 and _running:
            fm.send_attitude_target(master, thrust=0.70)
            time.sleep(0.05)

    print("\nOtonom takip basladi. Ctrl+C ile durdur.\n")
    src = SOURCES[source_name]()
    loop_t0 = time.time()
    last_report = 0.0

    for data in src:
        if not _running:
            break
        if duration and time.time() - loop_t0 > duration:
            break

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

        # 2) Kontrol
        if data_received:
            out = ctrl.compute(data, dt=DT)
        else:
            out = ZERO_OUTPUT
            data = TrackingData.lost(time.time() - loop_t0)

        if fs and fs.should_hover() and not out.coasting:
            out = ZERO_OUTPUT

        # 3) Komut
        if master and not (fs and fs.land_sent):
            fm.send_control_output(master, out)

        # 4) Log
        logger.log(data, out,
                   flight_mode=state.value if fs else "SIM",
                   failsafe_active=bool(fs and fs.active))

        # 5) Durum
        now = time.time() - loop_t0
        if now - last_report > 2.0:
            last_report = now
            bbox = f"{data.bbox_px:.0f}px" if data.bbox_px else "yok"
            print(f"t={now:5.1f}s  {data.durum:<12} bbox={bbox:>7}  "
                  f"yaw={out.yaw_rate:+.3f} thr={out.throttle:+.3f}  "
                  f"{fs.status() if fs else ''}")

    # Kapanis
    if master and not (fs and fs.land_sent):
        print("\nIniyor...")
        fm.land(master)

    logger.close()
    print("\n" + logger.rate_report())


def main():
    p = argparse.ArgumentParser(description="FPV Drone Izleme - Ucus Kontrol")
    p.add_argument("--source", choices=SOURCES, default="fake")
    p.add_argument("--target", choices=TARGETS, default="none")
    p.add_argument("--alt", type=float, default=5.0)
    p.add_argument("--duration", type=float, default=None,
                   help="saniye; verilmezse Ctrl+C'ye kadar")
    args = p.parse_args()

    run(args.source, args.target, args.alt, args.duration)


if __name__ == "__main__":
    main()