"""
Failsafe mekanizmasini test eder.
SITL calisirken baglanip, heartbeat izlemeyi baslatir,
sonra kasten "heartbeat gelmiyormus gibi" bir durum simule eder.
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

import time
from connection import connect
from flight_manager import set_mode, arm, takeoff
from failsafe import FailsafeMonitor

if __name__ == "__main__":
    master = connect()
    print("GPS/AHRS oturmasi icin bekleniyor...")
    time.sleep(15)

    set_mode(master, 'GUIDED')
    if arm(master):
        takeoff(master, altitude=5)
        time.sleep(5)

    # Failsafe izlemeyi baslat (3 saniye timeout)
    monitor = FailsafeMonitor(master, timeout_seconds=3)
    monitor.start()

    print("\n10 saniye normal calisma simule ediliyor...")
    time.sleep(10)

    print("\nSimdi kasten 'sinyal kaybi' simule ediliyor (izlemeyi durduruyoruz)...")
    monitor.stop()  # normalde bu, gercek sinyal kaybinda otomatik olurdu

    print("Test tamamlandi. Not: Gercek senaryoda heartbeat gelmeyi kesince")
    print("FailsafeMonitor kendisi LAND komutu gonderecek, elle durdurmaya gerek olmayacak.")
