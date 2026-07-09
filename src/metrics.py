"""
Sartname basari kriterlerini olcen modul.

Yarisma Bilgilendirme Dokumani, Bolum 3:
  - Hedef, tespit karesi icinde 64x64 (4096) pikselden buyuk alan kaplamali.
  - Bir frame basarili sayilir: takip kutusu ile referans kutu IoU >= %30.
  - Bir manevra basarili sayilir: frame'lerin >= %80'i basarili.
  - Kaydedilen takip kutulari: her saniye icin minimum 5 adet.
"""

from typing import Iterable, Optional, Sequence, Tuple

Box = Tuple[float, float, float, float]  # (x, y, w, h)

MIN_BBOX_PX = 4096      # 64 x 64
MIN_IOU = 0.30          # frame basari esigi
MIN_FRAME_RATIO = 0.80  # manevra basari esigi
MIN_LOG_RATE_HZ = 5     # saniyede minimum kayit


def iou(box_a: Box, box_b: Box) -> float:
    """Iki bounding box arasindaki kesisim/birlesim oranini dondurur."""
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b

    ax2, ay2 = ax + aw, ay + ah
    bx2, by2 = bx + bw, by + bh

    inter_x1 = max(ax, bx)
    inter_y1 = max(ay, by)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    inter = inter_w * inter_h

    if inter <= 0.0:
        return 0.0

    union = (aw * ah) + (bw * bh) - inter
    return inter / union if union > 0 else 0.0


def frame_success(tracked: Optional[Box], reference: Optional[Box]) -> bool:
    """
    Tek bir frame icin basari kontrolu.
    Iki sart birlikte saglanmali:
      1. Referans hedef en az 4096 piksel alan kapliyor mu?
      2. Takip kutusu referans ile en az %30 kesisiyor mu?
    """
    if tracked is None or reference is None:
        return False

    ref_area = reference[2] * reference[3]
    if ref_area < MIN_BBOX_PX:
        return False

    return iou(tracked, reference) >= MIN_IOU


def maneuver_success(results: Sequence[bool]) -> bool:
    """Frame basari listesinden manevra basarisini hesaplar."""
    if not results:
        return False
    return (sum(results) / len(results)) >= MIN_FRAME_RATIO


def success_ratio(results: Sequence[bool]) -> float:
    """Basarili frame orani. Raporlama icin."""
    return sum(results) / len(results) if results else 0.0


def logging_rate_ok(timestamps_s: Sequence[float]) -> bool:
    """
    Her tam saniye diliminde en az MIN_LOG_RATE_HZ kayit var mi?
    timestamps_s: saniye cinsinden, otonom moda gecisten itibaren.
    """
    if not timestamps_s:
        return False

    buckets = {}
    for t in timestamps_s:
        sec = int(t)
        buckets[sec] = buckets.get(sec, 0) + 1

    return all(count >= MIN_LOG_RATE_HZ for count in buckets.values())


class ManeuverEvaluator:
    """
    Bir manevra istasyonu boyunca frame sonuclarini biriktirir.
    Manevra bitiminde ozet dondurur.
    """

    def __init__(self, name: str):
        self.name = name
        self.results: list[bool] = []
        self.timestamps: list[float] = []
        self.ious: list[float] = []

    def add(self, tracked: Optional[Box], reference: Optional[Box], t: float):
        ok = frame_success(tracked, reference)
        self.results.append(ok)
        self.timestamps.append(t)
        if tracked and reference:
            self.ious.append(iou(tracked, reference))
        else:
            self.ious.append(0.0)

    def summary(self) -> dict:
        return {
            "manevra": self.name,
            "toplam_frame": len(self.results),
            "basarili_frame": sum(self.results),
            "basari_orani": round(success_ratio(self.results), 4),
            "ortalama_iou": round(sum(self.ious) / len(self.ious), 4) if self.ious else 0.0,
            "manevra_basarili": maneuver_success(self.results),
            "loglama_yeterli": logging_rate_ok(self.timestamps),
        }

    def report(self) -> str:
        s = self.summary()
        durum = "BASARILI" if s["manevra_basarili"] else "BASARISIZ"
        oran = s["basari_orani"] * 100
        esik = MIN_FRAME_RATIO * 100
        log_durum = "yeterli" if s["loglama_yeterli"] else "YETERSIZ"

        satirlar = [
            f"[{s['manevra']}] {durum}",
            f"  Frame: {s['basarili_frame']}/{s['toplam_frame']} (%{oran:.1f}, esik %{esik:.0f})",
            f"  Ortalama IoU: {s['ortalama_iou']:.3f} (esik {MIN_IOU})",
            f"  Loglama hizi: {log_durum} (>= {MIN_LOG_RATE_HZ} kayit/sn)",
        ]
        return "\n".join(satirlar)