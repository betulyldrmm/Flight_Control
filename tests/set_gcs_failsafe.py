"""
ArduPilot'un kendi GCS Failsafe parametrelerini ayarlar.
KTR: heartbeat kesilirse otomatik LAND moduna gecer.

DIKKAT (K3):
  FS_GCS_ENABLE = 5  ->  her zaman LAND. 1 DEGIL!
  1 = her zaman RTL; RTL konum ister, GPS'siz konfigurasyonda CALISMAZ.
  (Onceki surumde 1.0 yaziliydi; TEST_PLANI.md ile hizalandi.)

  SYSID_MYGCS = 254  ->  GCS failsafe SADECE Jetson'i (bizim heartbeat'i)
  izlesin. Mission Planner (255) bagli olsa bile maskeleememeli.
  connection.GCS_SYSID = 254 ile eslesir. Yeni surumlerde ad MAV_GCS_SYSID.
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
import time
from connection import connect
from pymavlink import mavutil

master = connect()


def set_param(name: str, value: float):
    print(f"{name} = {value} ayarlaniyor...")
    master.mav.param_set_send(
        master.target_system, master.target_component,
        name.encode('utf-8'), float(value),
        mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
    )
    time.sleep(1)


def read_param(name: str):
    master.mav.param_request_read_send(
        master.target_system, master.target_component, name.encode('utf-8'), -1
    )
    msg = master.recv_match(type='PARAM_VALUE', blocking=True, timeout=3)
    return msg.param_value if msg else None


# FS_GCS_ENABLE = 5 (LAND) -- 1 degil (1=RTL, GPS'siz calismaz)
set_param('FS_GCS_ENABLE', 5.0)

# SYSID_MYGCS = 254 (yeni surum: MAV_GCS_SYSID). Once eski adi dene, olmazsa yeni ad.
if read_param('SYSID_MYGCS') is not None:
    set_param('SYSID_MYGCS', 254)
    gcs_param = 'SYSID_MYGCS'
else:
    set_param('MAV_GCS_SYSID', 254)
    gcs_param = 'MAV_GCS_SYSID'

# Dogrula
print("\nDogrulama:")
for name in ('FS_GCS_ENABLE', gcs_param):
    val = read_param(name)
    print(f"  {name} = {val if val is not None else 'okunamadi'}")

print("\nBench testi: heartbeat gonderen scripti kill -9 ile oldur -> "
      "FC kendi kendine LAND'e gecmeli.")
