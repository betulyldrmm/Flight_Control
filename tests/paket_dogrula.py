"""
Teslim paketi dogrulayici - Ek Dokuman V1.1 "Ek-C Kontrol Listesi".

Hakem degerlendirme yazilimindan ONCE bizim yakalamamiz gereken tum
format hatalarini denetler. Teslimden once MUTLAKA calistirin.

Kullanim:
    python tests/paket_dogrula.py TAKIM_XXX_DENEME_01/
    (klasor icinde goruntu/ ve tespit_kaydi.csv olmali)
"""
import csv
import os
import re
import sys

BASLIK = ["kare_no", "zaman_damgasi_ms", "goruntu_adi", "otonom_mod",
          "hedef_gorunur", "kutu_x", "kutu_y", "kutu_genislik",
          "kutu_yukseklik", "guven_skoru"]
AD_DESENI = re.compile(r"^kare_(\d{6})_zaman_(\d{9})\.(png|jpg|jpeg)$")

hatalar = []
uyarilar = []


def hata(m):
    hatalar.append(m)


def uyari(m):
    uyarilar.append(m)


def dogrula(paket: str) -> bool:
    csv_yolu = os.path.join(paket, "tespit_kaydi.csv")
    goruntu_dizin = os.path.join(paket, "goruntu")

    # -- Kritik yapi ------------------------------------------------------
    if not os.path.isfile(csv_yolu):
        hata("KRITIK: tespit_kaydi.csv yok")
    if not os.path.isdir(goruntu_dizin):
        hata("KRITIK: goruntu/ klasoru yok")
    if hatalar:
        return False

    dosyalar = set(os.listdir(goruntu_dizin))
    for d in sorted(dosyalar):
        if not AD_DESENI.match(d):
            hata(f"Gecersiz goruntu adi: {d}")

    # -- CSV --------------------------------------------------------------
    with open(csv_yolu, encoding="utf-8-sig", newline="") as f:
        ham = f.read()
    if "\n\n" in ham.replace("\r", "") or ham.rstrip("\n").split("\n")[-1] == "":
        hata("CSV icinde bos satir var")

    satirlar = list(csv.reader(ham.splitlines()))
    if not satirlar:
        hata("KRITIK: CSV bos")
        return False
    if satirlar[0] != BASLIK:
        hata(f"KRITIK: baslik hatali!\n  beklenen: {','.join(BASLIK)}\n"
             f"  bulunan : {','.join(satirlar[0])}")
        return False

    onceki_kare = -1
    onceki_zaman = -1
    csv_adlari = set()
    zaman_kovalari = {}

    for i, s in enumerate(satirlar[1:], start=2):
        if len(s) != len(BASLIK):
            hata(f"satir {i}: {len(s)} alan var, {len(BASLIK)} olmali")
            continue
        try:
            kare = int(s[0]); zaman = int(s[1]); ad = s[2]
            otonom = int(s[3]); gorunur = int(s[4])
            x, y, w, h = (float(v) for v in s[5:9])
            guven = float(s[9])
        except ValueError as e:
            hata(f"satir {i}: sayi cevrilemedi ({e})")
            continue

        if kare <= onceki_kare:
            hata(f"satir {i}: kare_no artan degil ({kare} <= {onceki_kare})")
        if zaman <= onceki_zaman:
            hata(f"satir {i}: zaman_damgasi_ms artan degil ({zaman} <= {onceki_zaman})")
        onceki_kare, onceki_zaman = kare, zaman

        m = AD_DESENI.match(ad)
        if not m:
            hata(f"satir {i}: goruntu_adi formati hatali: {ad}")
        else:
            if int(m.group(1)) != kare or int(m.group(2)) != zaman:
                hata(f"satir {i}: dosya adindaki kare/zaman CSV ile uyusmuyor: {ad}")
        if ad not in dosyalar:
            hata(f"satir {i}: goruntu/ icinde dosya yok: {ad}")
        if ad in csv_adlari:
            hata(f"satir {i}: ayni goruntu_adi iki kez: {ad}")
        csv_adlari.add(ad)

        if otonom not in (0, 1):
            hata(f"satir {i}: otonom_mod 0/1 olmali: {otonom}")
        if gorunur not in (0, 1):
            hata(f"satir {i}: hedef_gorunur 0/1 olmali: {gorunur}")

        if gorunur == 0:
            if any(v != 0 for v in (x, y, w, h)) or guven != 0.0:
                hata(f"satir {i}: hedef_gorunur=0 iken kutu/guven 0 olmali")
        else:
            if w <= 0 or h <= 0:
                hata(f"satir {i}: hedef_gorunur=1 iken kutu boyutu pozitif olmali")
        if not (0.0 <= guven <= 1.0):
            hata(f"satir {i}: guven_skoru 0-1 disi: {guven}")
        if w < 0 or h < 0:
            hata(f"satir {i}: negatif kutu boyutu")

        # 5 Hz kontrolu (otonom moddaki tespit kutulari)
        if otonom == 1 and gorunur == 1:
            zaman_kovalari.setdefault(zaman // 1000, 0)
            zaman_kovalari[zaman // 1000] += 1

    # CSV'de olmayan goruntu dosyalari
    fazla = dosyalar - csv_adlari
    for d in sorted(fazla):
        uyari(f"goruntu/ icinde CSV'de gecmeyen dosya: {d}")

    # 5 Hz (ilk/son saniye kismi olabilir, haric)
    kovalar = sorted(zaman_kovalari)
    for k in kovalar[1:-1]:
        if zaman_kovalari[k] < 5:
            uyari(f"saniye {k}: yalnizca {zaman_kovalari[k]} tespit kutusu (< 5 Hz)")

    return not hatalar


def main():
    if len(sys.argv) != 2:
        sys.exit("Kullanim: python tests/paket_dogrula.py <paket_klasoru>")
    paket = sys.argv[1]
    ok = dogrula(paket)

    print(f"\n=== Teslim paketi dogrulama: {paket} ===")
    for h in hatalar:
        print(f"  [HATA]  {h}")
    for u in uyarilar:
        print(f"  [UYARI] {u}")
    if ok and not uyarilar:
        print("  Tum kontroller GECTI. Paket teslime hazir.")
    elif ok:
        print(f"  Format GECERLI, ancak {len(uyarilar)} uyari var.")
    else:
        print(f"  {len(hatalar)} HATA - bu paket degerlendirme disi kalabilir!")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
