"""
GCS failsafe SITL testi - TAM OTOMATIK.

Akis:
  baglan -> arm -> kalkis -> 15 sn hover -> heartbeat/komut KESILIR
  (Jetson cokmesi simulasyonu) -> FC'nin kendi kendine LAND'e gecmesi
  beklenir -> sonuc PASS/FAIL olarak yazilir.

On kosullar (SITL'de MAVProxy uzerinden):
  param set FS_GCS_ENABLE 5      (LAND)
  param set MAV_GCS_SYSID 254    (eski ad: SYSID_MYGCS)
FS_GCS_TIMEOUT varsayilan 5 sn.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.connection import connect, send_gcs_heartbeat, wait_ready
from src import flight_manager as fm

ADDR = sys.argv[1] if len(sys.argv) > 1 else "tcp:127.0.0.1:5762"
HOVER_S = 15.0
BEKLEME_S = 30.0     # failsafe icin ust sinir (FS_GCS_TIMEOUT=5 + pay)

m = connect(ADDR)
fm.request_streams(m, rate_hz=10)
wait_ready(m, timeout=20)

if not fm.set_mode(m, "GUIDED_NOGPS"):
    sys.exit("Mod degistirilemedi.")
if not fm.arm(m):
    sys.exit("Arm olmadi.")

print("Kalkis (8 sn)...")
t0 = time.time()
last_hb = 0.0
while time.time() - t0 < 8.0:
    if time.time() - last_hb > 1.0:
        send_gcs_heartbeat(m)
        last_hb = time.time()
    fm.send_attitude_target(m, thrust=0.70)
    time.sleep(0.05)

print(f"Hover ({HOVER_S:.0f} sn)...")
t0 = time.time()
while time.time() - t0 < HOVER_S:
    if time.time() - last_hb > 1.0:
        send_gcs_heartbeat(m)
        last_hb = time.time()
    fm.send_attitude_target(m)
    time.sleep(0.05)

print("\n" + "=" * 60)
print("HEARTBEAT VE KOMUTLAR KESILDI (Jetson cokmesi simulasyonu).")
print(f"FC'nin ~5 sn icinde LAND'e gecmesi bekleniyor...")
print("=" * 60 + "\n")

land_id = m.mode_mapping().get("LAND")
kesinti_t0 = time.time()

while time.time() - kesinti_t0 < BEKLEME_S:
    hb = m.recv_match(type="HEARTBEAT", blocking=True, timeout=1)
    if hb is None or hb.get_srcSystem() != m.target_system:
        continue
    gecen = time.time() - kesinti_t0
    if hb.custom_mode == land_id:
        print(f"[PASS] FC {gecen:.1f} sn sonra kendi kendine LAND'e gecti.")
        print("GCS failsafe DOGRULANDI. Inisi izlemek icin bekleniyor...")
        fm.wait_landed(m, timeout=60)
        sys.exit(0)

print(f"[FAIL] {BEKLEME_S:.0f} sn gecti, FC LAND'e GECMEDI.")
print("Kontrol: FS_GCS_ENABLE=5 ve MAV_GCS_SYSID=254 ayarli mi?")
sys.exit(1)
