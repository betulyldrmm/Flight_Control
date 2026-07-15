import sys, os, time, collections
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pymavlink import mavutil
from src import flight_manager as fm

# 5760'i MAVProxy tutuyor (sim_vehicle.py otomatik baslatiyor).
# Bize dogrudan FC baglantisi lazim -> SERIAL1 = 5762.
ADDR = sys.argv[1] if len(sys.argv) > 1 else "tcp:127.0.0.1:5762"

m = mavutil.mavlink_connection(ADDR)
hb = m.wait_heartbeat(timeout=10)
if hb is None:
    print(f"HATA: heartbeat yok ({ADDR}). SITL calisiyor mu?")
    sys.exit(1)
print(f"heartbeat ok ({ADDR}), sistem {m.target_system}")
if m.target_system == 0:
    print("UYARI: sistem 0 -> gecerli arac heartbeat'i degil!")

fm.request_streams(m, rate_hz=10)
time.sleep(1)

c = collections.Counter()
t0 = time.time()
while time.time() - t0 < 5.0:
    msg = m.recv_match(blocking=True, timeout=1)
    if msg:
        c[msg.get_type()] += 1

print(f"\n5 saniyede {sum(c.values())} mesaj, {len(c)} tip:\n")
for k, v in c.most_common(20):
    print(f"  {k:<28} {v}")

for want in ("ATTITUDE", "LOCAL_POSITION_NED", "GLOBAL_POSITION_INT"):
    print(f"\n{want}: {'VAR' if c[want] else 'YOK'}")