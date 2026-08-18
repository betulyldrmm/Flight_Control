"""
Ucus kontrol koduna UDP ile tespit kutusu gonderir.

FORMAT — src/tracking_interface.TrackingData.from_dict ile BIREBIR uyumlu
(Format A / bbox). Ucus kontrol bu paketi 127.0.0.1:5005'te dinler.

  Hedef gorunurken:
    {"durum":"TAKIP","bbox":{"x":..,"y":..,"w":..,"h":..},
     "guven_skoru":0.91,"timestamp":1.23,"frame_id":45}
  Hedef yokken:
    {"durum":"HEDEF_KAYIP","timestamp":1.30,"frame_id":46}

DIKKAT: alan adlari degistirilmemeli; ucus kontrol tarafi bunlari bekler.
"""

import json
import socket
from typing import Optional, Tuple

Box = Tuple[float, float, float, float]


class FlightControlSender:
    def __init__(self, host: str = "127.0.0.1", port: int = 5005):
        self.addr = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, durum: str, timestamp: float, frame_id: int,
             bbox: Optional[Box] = None, guven: Optional[float] = None):
        """Tek bir kare icin paket olustur ve gonder."""
        if durum == "TAKIP" and bbox is not None:
            x, y, w, h = bbox
            paket = {
                "durum": "TAKIP",
                "bbox": {"x": round(float(x), 1), "y": round(float(y), 1),
                         "w": round(float(w), 1), "h": round(float(h), 1)},
                "guven_skoru": round(float(guven), 3) if guven is not None else 0.0,
                "timestamp": round(float(timestamp), 3),
                "frame_id": int(frame_id),
            }
        else:
            # Hedef yok / kayip: kutu gonderilmez (ucus kontrol tarafi coasting/arama yapar)
            paket = {
                "durum": durum if durum in ("HEDEF_KAYIP", "ARIYOR") else "HEDEF_KAYIP",
                "timestamp": round(float(timestamp), 3),
                "frame_id": int(frame_id),
            }
        self.sock.sendto(json.dumps(paket).encode("utf-8"), self.addr)
        return paket

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass
