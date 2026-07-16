"""
RESMI TESLIM FORMATI
Kaynak: "FPV Drone Izleme - Goruntu ve Tespit Kutusu Kayit Formati
Ek Dokumani" V1.1 Taslak (01.07.2026).

Bu modul uc seyi standartlastirir:
  1. tespit_kaydi.csv  - zorunlu sema, birebir baslik sirasi
  2. goruntu dosya adi - kare_<6 hane>_zaman_<9 hane>.<uzanti>
  3. bindirme metni    - sag ust kose: zaman, kare_no, OTONOM

ONEMLI GOREV DAGILIMI:
  Goruntu karelerini diske KAYDEDEN taraf (goruntu isleme / Sercan)
  bu modulu kullanmali; cunku CSV'deki goruntu_adi ile diskteki dosya
  birebir ayni olmak zorunda. Ucus kontrol tarafi kendi ic logunu
  (logger.py) tutmaya devam eder; o hakem teslimi DEGILDIR.

KURALLAR (dokumandan):
  - Baslik satiri birebir: kare_no,zaman_damgasi_ms,goruntu_adi,
    otonom_mod,hedef_gorunur,kutu_x,kutu_y,kutu_genislik,
    kutu_yukseklik,guven_skoru
  - UTF-8, virgul ayirici, ondalik nokta, bos satir yok, yorum yok.
  - kare_no artan ve benzersiz; zaman_damgasi_ms geriye gitmez ve
    ayni deger iki karede kullanilamaz.
  - hedef_gorunur=0 iken: kutu alanlari 0, guven_skoru 0.00.
  - hedef_gorunur=1 iken: genislik/yukseklik pozitif olmali.
  - Kutu goruntu sinirlari disina tasarsa kare gecersiz sayilir;
    bu yuzden yazarken sinira kirpilir (clamp).
"""

import csv
import os
from typing import Optional, Tuple

CSV_BASLIK = [
    "kare_no", "zaman_damgasi_ms", "goruntu_adi", "otonom_mod",
    "hedef_gorunur", "kutu_x", "kutu_y", "kutu_genislik",
    "kutu_yukseklik", "guven_skoru",
]

GECERLI_UZANTILAR = ("png", "jpg", "jpeg")


def goruntu_adi(kare_no: int, zaman_ms: int, uzanti: str = "jpg") -> str:
    """kare_000123_zaman_000004100.jpg"""
    uzanti = uzanti.lower().lstrip(".")
    if uzanti not in GECERLI_UZANTILAR:
        raise ValueError(f"Gecersiz uzanti: {uzanti} (izinli: {GECERLI_UZANTILAR})")
    if kare_no < 0 or zaman_ms < 0:
        raise ValueError("kare_no ve zaman_ms negatif olamaz")
    return f"kare_{kare_no:06d}_zaman_{zaman_ms:09d}.{uzanti}"


def bindirme_metni(kare_no: int, zaman_ms: int, otonom: int = 1) -> str:
    """
    Goruntunun sag ust kosesine basilacak metin (dokuman Bolum 6).
    Yari saydam koyu arka plan + beyaz metin onerilir.
    """
    return (f"zaman_damgasi_ms: {zaman_ms:09d}\n"
            f"kare_no: {kare_no:06d}\n"
            f"OTONOM: {otonom}")


class ResmiKayit:
    """
    tespit_kaydi.csv yazicisi.

    Kullanim (goruntu isleme dongusunde her karede):
        rk = ResmiKayit("teslim/tespit_kaydi.csv")
        ad = rk.kaydet(kare_no=i, zaman_ms=t_ms, otonom=1,
                       bbox=(x, y, w, h), guven=0.91,
                       frame_w=1280, frame_h=720)
        # goruntuyu 'teslim/goruntu/<ad>' olarak kaydet (bindirmeyle)
        ...
        rk.kapat()
    """

    def __init__(self, path: str = "tespit_kaydi.csv"):
        d = os.path.dirname(path)
        if d:
            os.makedirs(d, exist_ok=True)
        self.path = path
        # newline="" -> csv modulu kendi satir sonunu koyar, bos satir olmaz
        self._f = open(path, "w", newline="", encoding="utf-8")
        self._w = csv.writer(self._f)
        self._w.writerow(CSV_BASLIK)
        self._son_kare = -1
        self._son_zaman = -1
        self.satir_sayisi = 0

    def kaydet(self, kare_no: int, zaman_ms: int, otonom: int,
               bbox: Optional[Tuple[float, float, float, float]] = None,
               guven: Optional[float] = None,
               frame_w: int = 1280, frame_h: int = 720,
               uzanti: str = "jpg") -> str:
        """
        Bir kare icin satir yazar; goruntu dosya adini dondurur.
        bbox None ise 'tespit yok' satiri yazilir (Bolum 11).
        """
        kare_no = int(kare_no)
        zaman_ms = int(zaman_ms)

        if kare_no <= self._son_kare:
            raise ValueError(f"kare_no artan olmali: {kare_no} <= {self._son_kare}")
        if zaman_ms <= self._son_zaman:
            # zaman geriye gidemez / ayni olamaz -> 1 ms ileri kaydir
            zaman_ms = self._son_zaman + 1

        ad = goruntu_adi(kare_no, zaman_ms, uzanti)

        if bbox is None:
            # Bolum 11: tespit yok satiri
            satir = [kare_no, zaman_ms, ad, int(bool(otonom)), 0,
                     0, 0, 0, 0, "0.00"]
        else:
            x, y, w, h = (float(v) for v in bbox)
            if w <= 0 or h <= 0:
                raise ValueError("hedef_gorunur=1 iken kutu boyutu pozitif olmali")
            # Sinira kirp (tasan kutu kareyi gecersiz kilar)
            x = min(max(x, 0.0), frame_w - 1.0)
            y = min(max(y, 0.0), frame_h - 1.0)
            w = min(w, frame_w - x)
            h = min(h, frame_h - y)
            g = 0.0 if guven is None else min(max(float(guven), 0.0), 1.0)
            satir = [kare_no, zaman_ms, ad, int(bool(otonom)), 1,
                     f"{x:.1f}", f"{y:.1f}", f"{w:.1f}", f"{h:.1f}",
                     f"{g:.2f}"]

        self._w.writerow(satir)
        self._son_kare = kare_no
        self._son_zaman = zaman_ms
        self.satir_sayisi += 1
        return ad

    def kapat(self):
        if self._f:
            self._f.close()
            self._f = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.kapat()
