"""
Ucus kontrol ve takip verisi loglama.

Yarisma Bilgilendirme Dokumani, Bolum 3:
  - "Sistem otonom moda gecirildigi andan itibaren saniye ve milisaniye
     cinsinden bir zaman sayaci (timestamp) baslatilmali ve bu zaman
     bilgisi goruntunun sag ust kosesine gomulmelidir."
  - "Elde edilen hedef tespit kutusu bilgileri, goruntu uzerindeki zaman
     damgasi ile senkronize sekilde kaydedilmelidir."
  - "Kaydedilen takip kutulari manevra suresi boyunca her saniye icin
     minimum 5 adet olmalidir."
  - "Formata uygun loglama yapmayan yarismacilar ilgili musabaka icin
     degerlendirmeye alinmayacaktir."

KRITIK: Zaman sayaci wall-clock degil, otonom moda gecisten itibaren
gecen suredir. start() cagrisi sayaci sifirlar.
"""

import csv
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TextIO

HEADER = [
    "t_ms",              # otonom moda gecisten itibaren gecen sure (ms)
    "frame_id",
    "durum",             # TAKIP | HEDEF_KAYIP | ARIYOR
    "bbox_x", "bbox_y", "bbox_w", "bbox_h",
    "bbox_px",           # w * h, sartname 4096 kontrolu icin
    "x_error", "y_error", "bbox_area",
    "confidence",
    "roll_cmd", "pitch_cmd", "yaw_cmd", "throttle_cmd",
    "in_deadband", "coasting", "searching",
    "flight_mode",
    "failsafe_active",
]


def _fmt(v, nd=4):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


@dataclass
class LogRow:
    t_ms: int
    frame_id: int
    durum: str
    bbox_x: Optional[float] = None
    bbox_y: Optional[float] = None
    bbox_w: Optional[float] = None
    bbox_h: Optional[float] = None
    bbox_px: Optional[float] = None
    x_error: Optional[float] = None
    y_error: Optional[float] = None
    bbox_area: Optional[float] = None
    confidence: Optional[float] = None
    roll_cmd: float = 0.0
    pitch_cmd: float = 0.0
    yaw_cmd: float = 0.0
    throttle_cmd: float = 0.0
    in_deadband: bool = False
    coasting: bool = False
    searching: bool = False
    flight_mode: str = ""
    failsafe_active: bool = False

    def to_list(self):
        return [
            self.t_ms, self.frame_id, self.durum,
            _fmt(self.bbox_x, 1), _fmt(self.bbox_y, 1),
            _fmt(self.bbox_w, 1), _fmt(self.bbox_h, 1),
            _fmt(self.bbox_px, 0),
            _fmt(self.x_error), _fmt(self.y_error), _fmt(self.bbox_area, 6),
            _fmt(self.confidence, 3),
            _fmt(self.roll_cmd), _fmt(self.pitch_cmd),
            _fmt(self.yaw_cmd), _fmt(self.throttle_cmd),
            _fmt(self.in_deadband), _fmt(self.coasting), _fmt(self.searching),
            self.flight_mode, _fmt(self.failsafe_active),
        ]


class FlightLogger:
    """
    Kullanim:
        logger = FlightLogger("logs")
        logger.start()                       # otonom moda gecis ani
        ...
        logger.log(data, out, mode="GUIDED_NOGPS")
        ...
        logger.close()
        print(logger.rate_report())
    """

    def __init__(self, log_dir: str = "logs", prefix: str = "flight"):
        os.makedirs(log_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = os.path.join(log_dir, f"{prefix}_{stamp}.csv")
        self._f: Optional[TextIO] = None
        self._w = None
        self._t0: Optional[float] = None
        self.rows = 0
        self._timestamps_ms = []
        self._last_flush = 0.0

    # -- yasam dongusu ---------------------------------------------------

    def start(self, t0: Optional[float] = None):
        """Otonom moda gecis ani. Zaman sayacini sifirlar, dosyayi acar."""
        self._t0 = t0 if t0 is not None else time.time()
        self._f = open(self.path, "w", newline="", encoding="utf-8")
        self._w = csv.writer(self._f)
        self._w.writerow(HEADER)
        return self

    def close(self):
        if self._f:
            self._f.close()
            self._f = None
            self._w = None

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.close()

    # -- zaman -----------------------------------------------------------

    def elapsed_ms(self, now: Optional[float] = None) -> int:
        """Otonom moda gecisten itibaren gecen sure (ms)."""
        if self._t0 is None:
            raise RuntimeError("FlightLogger.start() cagrilmadi")
        now = now if now is not None else time.time()
        return int(round((now - self._t0) * 1000.0))

    @staticmethod
    def overlay_text(t_ms: int) -> str:
        """
        Goruntunun sag ust kosesine gomulecek zaman damgasi.
        Format: SS.mmm (saniye.milisaniye)
        """
        return f"{t_ms // 1000}.{t_ms % 1000:03d}"

    # -- kayit -----------------------------------------------------------

    def log(self, data, out=None, *,
            flight_mode: str = "",
            failsafe_active: bool = False,
            t_ms: Optional[int] = None) -> LogRow:
        """
        data: TrackingData
        out:  ControlOutput (None ise komutlar sifir yazilir)
        t_ms: verilmezse gercek zamandan hesaplanir (simulasyonda ver)
        """
        if self._w is None:
            raise RuntimeError("FlightLogger.start() cagrilmadi")

        if t_ms is None:
            t_ms = self.elapsed_ms()

        bx = by = bw = bh = None
        if data.bbox is not None:
            bx, by, bw, bh = data.bbox

        row = LogRow(
            t_ms=t_ms,
            frame_id=data.frame_id,
            durum=data.durum,
            bbox_x=bx, bbox_y=by, bbox_w=bw, bbox_h=bh,
            bbox_px=data.bbox_px,
            x_error=data.x_error,
            y_error=data.y_error,
            bbox_area=data.bbox_area,
            confidence=data.guven_skoru,
            roll_cmd=out.roll if out else 0.0,
            pitch_cmd=out.pitch if out else 0.0,
            yaw_cmd=out.yaw_rate if out else 0.0,
            throttle_cmd=out.throttle if out else 0.0,
            in_deadband=out.in_deadband if out else False,
            coasting=getattr(out, "coasting", False) if out else False,
            searching=getattr(out, "searching", False) if out else False,
            flight_mode=flight_mode,
            failsafe_active=failsafe_active,
        )

        self._w.writerow(row.to_list())
        # Her satirda flush diske takilip donguyu durdurabiliyor
        # (Windows'ta 2+ sn'lik duraklamalar gozlendi). 0.5 sn'de bir
        # flush, kirim durumunda en fazla yarim saniyelik veri kaybi.
        now = time.time()
        if now - self._last_flush > 0.5:
            self._f.flush()
            self._last_flush = now
        self.rows += 1
        self._timestamps_ms.append(t_ms)
        return row

    # -- dogrulama -------------------------------------------------------

    def rate_ok(self, min_hz: int = 5) -> bool:
        """
        Her tam saniye diliminde en az min_hz kayit var mi?
        Ilk ve son dilim kismi olabilecegi icin haric tutulur.
        """
        if not self._timestamps_ms:
            return False

        buckets = {}
        for t in self._timestamps_ms:
            buckets[t // 1000] = buckets.get(t // 1000, 0) + 1

        keys = sorted(buckets)
        if len(keys) <= 2:
            return all(buckets[k] >= min_hz for k in keys)
        return all(buckets[k] >= min_hz for k in keys[1:-1])
    
    def rate_report(self, min_hz: int = 5) -> str:
        if not self._timestamps_ms:
            return "Hic kayit yok."
        dur_s = (self._timestamps_ms[-1] - self._timestamps_ms[0]) / 1000.0
        hz = self.rows / dur_s if dur_s > 0 else 0.0
        ok = "YETERLI" if self.rate_ok(min_hz) else "YETERSIZ"
        return (f"{self.path}\n"
                f"  {self.rows} kayit, {dur_s:.1f} sn, ortalama {hz:.1f} Hz\n"
                f"  Sartname (>= {min_hz} kayit/sn): {ok}")