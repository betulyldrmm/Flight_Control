"""Resmi teslim formati (tespit_kaydi.csv) birim testleri."""
import csv
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.resmi_kayit import (CSV_BASLIK, ResmiKayit, bindirme_metni,
                             goruntu_adi)


def test_goruntu_adi_formati():
    assert goruntu_adi(0, 0) == "kare_000000_zaman_000000000.jpg"
    assert goruntu_adi(1452, 48400, "png") == "kare_001452_zaman_000048400.png"


def test_gecersiz_uzanti():
    with pytest.raises(ValueError):
        goruntu_adi(0, 0, "gif")


def test_bindirme_metni_zorunlu_alanlar():
    m = bindirme_metni(1452, 48400, otonom=1)
    assert "kare_no: 001452" in m
    assert "zaman_damgasi_ms: 000048400" in m
    assert "OTONOM: 1" in m


def test_csv_baslik_ve_satirlar(tmp_path):
    p = tmp_path / "tespit_kaydi.csv"
    with ResmiKayit(str(p)) as rk:
        ad1 = rk.kaydet(0, 0, otonom=1, bbox=(812, 431, 72, 72), guven=0.91)
        ad2 = rk.kaydet(1, 33, otonom=1, bbox=None)          # tespit yok

    rows = list(csv.reader(open(p, encoding="utf-8")))
    assert rows[0] == CSV_BASLIK
    assert rows[1][2] == ad1 == "kare_000000_zaman_000000000.jpg"
    # tespit yok satiri: gorunur=0, kutular 0, guven 0.00
    assert rows[2][4] == "0"
    assert rows[2][5:9] == ["0", "0", "0", "0"]
    assert rows[2][9] == "0.00"
    assert ad2.startswith("kare_000001")


def test_zaman_geriye_gidemez(tmp_path):
    p = tmp_path / "t.csv"
    rk = ResmiKayit(str(p))
    rk.kaydet(0, 100, 1, bbox=(1, 1, 10, 10), guven=0.5)
    ad = rk.kaydet(1, 100, 1, bbox=(1, 1, 10, 10), guven=0.5)  # ayni zaman
    rk.kapat()
    assert "zaman_000000101" in ad                              # +1 ms kaydirildi


def test_kare_no_artan_olmali(tmp_path):
    rk = ResmiKayit(str(tmp_path / "t.csv"))
    rk.kaydet(5, 100, 1, bbox=None)
    with pytest.raises(ValueError):
        rk.kaydet(5, 200, 1, bbox=None)
    rk.kapat()


def test_kutu_sinira_kirpilir(tmp_path):
    p = tmp_path / "t.csv"
    with ResmiKayit(str(p)) as rk:
        rk.kaydet(0, 0, 1, bbox=(1250, 700, 100, 100),
                  frame_w=1280, frame_h=720, guven=0.9)
    r = list(csv.reader(open(p, encoding="utf-8")))[1]
    x, y, w, h = (float(v) for v in r[5:9])
    assert x + w <= 1280 and y + h <= 720


def test_dogrulayici_temiz_paketi_gecirir(tmp_path):
    """Uretilen paket, dogrulayicidan hatasiz gecmeli (uctan uca)."""
    paket = tmp_path / "TAKIM_TEST_DENEME_01"
    goruntu = paket / "goruntu"
    goruntu.mkdir(parents=True)

    with ResmiKayit(str(paket / "tespit_kaydi.csv")) as rk:
        t = 0
        for i in range(30):                      # 3 sn, 10 Hz
            bbox = (100 + i, 200, 80, 80) if i % 7 else None
            ad = rk.kaydet(i, t, otonom=1, bbox=bbox, guven=0.9)
            (goruntu / ad).write_bytes(b"fake")  # sahte goruntu dosyasi
            t += 100

    sys.path.insert(0, os.path.dirname(__file__))
    import paket_dogrula
    paket_dogrula.hatalar.clear()
    paket_dogrula.uyarilar.clear()
    assert paket_dogrula.dogrula(str(paket)), paket_dogrula.hatalar
