"""
ArduPilot'un kendi GCS Failsafe parametresini ayarlar.
KTR'de tarif edildigi gibi: heartbeat kesilirse otomatik Land moduna gecer.
"""
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
import time
from connection import connect
from pymavlink import mavutil

master = connect()

# FS_GCS_ENABLE: 1 = etkin, Land moduna gec
print("FS_GCS_ENABLE parametresi ayarlaniyor...")
master.mav.param_set_send(
    master.target_system, master.target_component,
    b'FS_GCS_ENABLE', 1.0, mavutil.mavlink.MAV_PARAM_TYPE_REAL32
)
time.sleep(1)

# Dogrula
master.mav.param_request_read_send(
    master.target_system, master.target_component, b'FS_GCS_ENABLE', -1
)
msg = master.recv_match(type='PARAM_VALUE', blocking=True, timeout=3)
print(f"Dogrulandi: FS_GCS_ENABLE = {msg.param_value if msg else 'okunamadi'}")
