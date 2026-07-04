import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
import time
from connection import connect
from pymavlink import mavutil

master = connect()

params = {
    'EK3_SRC1_POSXY': 0,
    'EK3_SRC1_VELXY': 5,
    'EK3_SRC1_POSZ': 1,
    'EK3_SRC1_YAW': 1,
}

for name, value in params.items():
    print(f"{name} = {value} olarak ayarlaniyor...")
    master.mav.param_set_send(
        master.target_system, master.target_component,
        name.encode('utf-8'), float(value), mavutil.mavlink.MAV_PARAM_TYPE_REAL32
    )
    time.sleep(0.5)

print("\nDogrulama yapiliyor...")
time.sleep(1)
for name in params.keys():
    master.mav.param_request_read_send(
        master.target_system, master.target_component, name.encode('utf-8'), -1
    )
    msg = master.recv_match(type='PARAM_VALUE', blocking=True, timeout=3)
    if msg:
        print(f"Dogrulandi: {msg.param_id.strip()} = {msg.param_value}")
