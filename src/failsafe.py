"""
Failsafe: baglanti, veri ve hedef kaybi durumlarinin yonetimi.

UC AYRI KATMAN:

  1. FC baglantisi (Pixhawk heartbeat kesildi)
     -> LAND. Pixhawk'a komut gonderemiyoruz, ama gonderebiliyorsak
        LAND'e gecmesini istiyoruz.

  2. Tracking verisi kesildi (Jetson/goruntu isleme takildi)
     -> Once hover (sifir komut), sonra LAND.

  3. Hedef kayip (tracking calisiyor ama hedefi goremiyor)
     -> LAND DEGIL. Kisa sureli coasting (PID'de), sonra hover/arama modu.
        Hedef kaybi bir ariza degil, normal bir durum.

NOT: Bu katman yardimci bir guvenlik agidir. ASIL guvenlik ArduPilot'un
kendi failsafe parametreleridir:
    FS_GCS_ENABLE = 1       (GCS heartbeat kesilince LAND)
    FS_OPTIONS              (davranis secimi)
    BATT_FS_LOW_ACT         (batarya failsafe)
KTR: "MAVLink heartbeat sinyali kesildiginde aracin otomatik olarak
Land moduna gecmesi hedeflenmistir."
"""

import time
from enum import Enum
from typing import Optional


class FailsafeState(Enum):
    NORMAL = "NORMAL"
    TARGET_LOST = "TARGET_LOST"     # hedef yok, ucus devam
    DATA_TIMEOUT = "DATA_TIMEOUT"   # tracking verisi gelmiyor
    LINK_LOST = "LINK_LOST"         # FC heartbeat yok
    LANDING = "LANDING"             # LAND komutu gonderildi


class FailsafeMonitor:
    """
    Thread kullanmaz. main.py her dongude update() cagirir.

    Kullanim:
        fs = FailsafeMonitor(master)
        ...
        state = fs.update(data_received=True, target_detected=data.is_valid())
        if fs.should_hover():
            out = ZERO_OUTPUT
        if fs.should_land():
            fs.trigger_land()
    """

    def __init__(self, master,
                 link_timeout: float = 3.0,
                 data_timeout: float = 1.0,
                 target_lost_hover: float = 1.5,
                 target_lost_land: float = 15.0):
        self.master = master
        self.link_timeout = link_timeout
        self.data_timeout = data_timeout
        self.target_lost_hover = target_lost_hover
        self.target_lost_land = target_lost_land

        now = time.time()
        self.last_heartbeat = now
        self.last_data = now
        self.last_target = now

        self.state = FailsafeState.NORMAL
        self.land_sent = False

    # -- guncelleme ------------------------------------------------------

    def poll_heartbeat(self) -> bool:
        """
        FC baglantisinin canli olup olmadigini kontrol eder (bloklamaz).

        NOT: Sadece HEARTBEAT'e bakmak kirilgandir; ana dongudeki diger
        recv_match cagrilari (orn. get_attitude) heartbeat mesajini
        tuketebilir. FC'den gelen HERHANGI bir mesaj baglantinin canli
        oldugunun kanitidir.
        """
        alive = False
        while True:
            msg = self.master.recv_match(blocking=False)
            if msg is None:
                break
            if msg.get_type() != "BAD_DATA":
                alive = True
        if alive:
            self.last_heartbeat = time.time()
        return alive

    def update(self, data_received: bool, target_detected: bool,
               now: Optional[float] = None) -> FailsafeState:
        """
        data_received: tracking modulunden bu donguda veri geldi mi
        target_detected: gelen veride hedef var mi
        """
        now = now if now is not None else time.time()

        if data_received:
            self.last_data = now
        if target_detected:
            self.last_target = now

        # Oncelik sirasi: baglanti > veri > hedef
        if now - self.last_heartbeat > self.link_timeout:
            self.state = FailsafeState.LINK_LOST
        elif now - self.last_data > self.data_timeout:
            self.state = FailsafeState.DATA_TIMEOUT
        elif now - self.last_target > self.target_lost_hover:
            self.state = FailsafeState.TARGET_LOST
        else:
            self.state = FailsafeState.NORMAL

        if self.land_sent:
            self.state = FailsafeState.LANDING

        return self.state

    # -- kararlar --------------------------------------------------------

    def should_hover(self) -> bool:
        """Sifir komut gonderilmeli mi?"""
        return self.state in (FailsafeState.TARGET_LOST,
                              FailsafeState.DATA_TIMEOUT)

    def should_land(self, now: Optional[float] = None) -> bool:
        """LAND'e gecilmeli mi?"""
        if self.land_sent:
            return False
        now = now if now is not None else time.time()

        if self.state == FailsafeState.LINK_LOST:
            return True
        if self.state == FailsafeState.DATA_TIMEOUT:
            return now - self.last_data > self.data_timeout * 5
        if self.state == FailsafeState.TARGET_LOST:
            return now - self.last_target > self.target_lost_land
        return False

    @property
    def active(self) -> bool:
        return self.state != FailsafeState.NORMAL

    # -- eylem -----------------------------------------------------------

    def trigger_land(self) -> bool:
        """LAND moduna gecir. Bir kez calisir."""
        if self.land_sent:
            return True

        from src.flight_manager import set_mode
        print(f"FAILSAFE [{self.state.value}]: LAND moduna geciliyor")
        try:
            ok = set_mode(self.master, "LAND", timeout=3.0)
            self.land_sent = True
            self.state = FailsafeState.LANDING
            return ok
        except Exception as e:
            print(f"FAILSAFE HATA: LAND gonderilemedi: {e}")
            return False

    def reset(self):
        now = time.time()
        self.last_heartbeat = now
        self.last_data = now
        self.last_target = now
        self.state = FailsafeState.NORMAL
        self.land_sent = False

    def status(self) -> str:
        now = time.time()
        return (f"[{self.state.value}] "
                f"hb {now - self.last_heartbeat:.1f}s, "
                f"veri {now - self.last_data:.1f}s, "
                f"hedef {now - self.last_target:.1f}s")