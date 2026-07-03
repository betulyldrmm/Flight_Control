"""
Failsafe mekanizmasi: Heartbeat/watchdog tabanli guvenlik sistemi.
Baglanti/sinyal kaybi durumunda drone'u otomatik LAND moduna gecirir.
"""
from pymavlink import mavutil
import time
import threading


class FailsafeMonitor:
    def __init__(self, master, timeout_seconds=3):
        """
        master: pymavlink baglantisi
        timeout_seconds: bu sure boyunca heartbeat gelmezse failsafe tetiklenir
        """
        self.master = master
        self.timeout_seconds = timeout_seconds
        self.last_heartbeat_time = time.time()
        self.running = False
        self.failsafe_triggered = False
        self._thread = None

    def _watch_loop(self):
        """Arka planda surekli calisan izleme dongusu."""
        while self.running:
            msg = self.master.recv_match(type='HEARTBEAT', blocking=False)
            if msg:
                self.last_heartbeat_time = time.time()

            elapsed = time.time() - self.last_heartbeat_time
            if elapsed > self.timeout_seconds and not self.failsafe_triggered:
                print(f"UYARI: {elapsed:.1f} saniyedir heartbeat yok! Failsafe tetikleniyor.")
                self._trigger_failsafe()

            time.sleep(0.2)

    def _trigger_failsafe(self):
        """Guvenli inis (LAND) komutunu gonder."""
        self.failsafe_triggered = True
        print("FAILSAFE: LAND komutu gonderiliyor...")
        try:
            self.master.mav.command_long_send(
                self.master.target_system, self.master.target_component,
                mavutil.mavlink.MAV_CMD_NAV_LAND, 0, 0, 0, 0, 0, 0, 0, 0
            )
            print("FAILSAFE: LAND komutu gonderildi.")
        except Exception as e:
            print(f"FAILSAFE HATA: LAND komutu gonderilemedi: {e}")

    def start(self):
        """Izlemeyi arka planda baslat."""
        self.running = True
        self.failsafe_triggered = False
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()
        print(f"Failsafe izleme baslatildi (timeout: {self.timeout_seconds}s)")

    def stop(self):
        """Izlemeyi durdur."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=1)
        print("Failsafe izleme durduruldu.")

    def reset_timer(self):
        """Heartbeat zamanini manuel sifirla (yeni komut gonderilince cagirilabilir)."""
        self.last_heartbeat_time = time.time()
