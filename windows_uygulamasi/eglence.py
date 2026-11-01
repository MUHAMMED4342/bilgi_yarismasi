# -*- coding: utf-8 -*-
"""
Bilgi Yarışması - eğlence katmanı (arayüzden bağımsız, wx gerekmez).

Puanlama, seri, rütbeler, başarımlar, rekorlar, günlük seri, günün meydan okuması
ve "arkadaşa sor" jokeri burada durur. Böylece hem sade hem test edilebilir kalır.
"""
import datetime
import random

# ---------------------------------------------------------------- oyun modları
MODE_NAMES = {"klasik": "Klasik", "can": "Can modu", "gunluk": "Günün meydan okuması",
              "coklu": "Çok oyunculu"}
# mod: (soru sayısı, can)
MODE_RULES = {"klasik": (10, 1), "can": (15, 3), "gunluk": (10, 2)}
SPARE_QUESTIONS = 3  # "Soruyu değiştir" jokeri için yedek soru sayısı
PER_PLAYER = 5       # çok oyunculuda her oyuncunun cevaplayacağı soru
MAX_PLAYERS = 4

# ---------------------------------------------------------------- rütbeler
RANKS = [
    (0, "Çaylak"),
    (400, "Meraklı"),
    (1200, "Bilgiç"),
    (3000, "Uzman"),
    (6000, "Üstat"),
    (10000, "Bilge"),
    (16000, "Efsane"),
]


def rank_info(xp):
    """(rütbe adı, sonraki rütbe adı ya da None, sonrakine kalan puan, rütbe sırası)"""
    idx = 0
    for i, (need, _name) in enumerate(RANKS):
        if xp >= need:
            idx = i
    if idx + 1 < len(RANKS):
        return RANKS[idx][1], RANKS[idx + 1][1], RANKS[idx + 1][0] - xp, idx
    return RANKS[idx][1], None, 0, idx


# ---------------------------------------------------------------- tarih yardımcıları
def today_str(today=None):
    return (today or datetime.date.today()).isoformat()


def _to_date(s):
    try:
        return datetime.date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def daily_seed(today=None):
    d = today or datetime.date.today()
    return d.year * 10000 + d.month * 100 + d.day


class DailyRng:
    """Web sitesindeki eglence.js ile birebir aynı sayı üreteci (mulberry32) ve karıştırma.
    Günün meydan okumasında masaüstü ve site aynı soruları, aynı şık sırasıyla seçer."""

    def __init__(self, seed):
        self.a = seed & 0xFFFFFFFF

    def random(self):
        self.a = (self.a + 0x6D2B79F5) & 0xFFFFFFFF
        a = self.a
        t = ((a ^ (a >> 15)) * (1 | a)) & 0xFFFFFFFF
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & 0xFFFFFFFF)) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    def shuffle(self, a):
        for i in range(len(a) - 1, 0, -1):
            j = int(self.random() * (i + 1))
            a[i], a[j] = a[j], a[i]

    def sample(self, pool, k):
        a = list(pool)
        n = len(a)
        k = min(k, n)
        for i in range(k):
            j = i + int(self.random() * (n - i))
            a[i], a[j] = a[j], a[i]
        return a[:k]


# ---------------------------------------------------------------- profil
DEFAULT_PROFILE = {
    "xp": 0,            # toplam puan (rütbe buna göre)
    "oyun": 0,          # bitirilen oyun
    "dogru": 0,
    "soru": 0,
    "rekorlar": {},     # mod -> en yüksek puan
    "seri": 0,          # en uzun doğru serisi
    "gun_seri": 0,      # üst üste oynanan gün
    "son_gun": "",
    "gunluk_tarih": "",
    "gunluk_puan": 0,
    "kat": {},          # kategori -> [doğru, toplam]
    "basarim": [],
}


def load_profile(cfg_dict):
    p = dict(DEFAULT_PROFILE)
    raw = cfg_dict.get("profil")
    if isinstance(raw, dict):
        p.update(raw)
    for key, typ in (("rekorlar", dict), ("kat", dict), ("basarim", list)):
        if not isinstance(p.get(key), typ):
            p[key] = typ()
    for key in ("xp", "oyun", "dogru", "soru", "seri", "gun_seri", "gunluk_puan"):
        try:
            p[key] = int(p[key])
        except (TypeError, ValueError):
            p[key] = 0
    cfg_dict["profil"] = p
    return p


def current_day_streak(p, today=None):
    """Bugün ya da dün oynadıysa seri sürüyor sayılır."""
    t = today or datetime.date.today()
    last = _to_date(p.get("son_gun"))
    if last is None:
        return 0
    if last in (t, t - datetime.timedelta(days=1)):
        return int(p.get("gun_seri", 0))
    return 0


def daily_played(p, today=None):
    return p.get("gunluk_tarih") == today_str(today)


# ---------------------------------------------------------------- puanlama
def score_question(elapsed, window, streak, half, friend, audience=False):
    """(temel, hız bonusu, seri bonusu, toplam)

    temel: 100; yarı yarıya -40, arkadaş -30, seyirci -20 (en az 30)
    hız:   0-50, cevap süresi pencereye göre ne kadar kısaysa o kadar çok
    seri:  2. doğrudan itibaren +10, en çok +60
    """
    base = max(30, 100 - (40 if half else 0) - (30 if friend else 0) - (20 if audience else 0))
    frac = max(0.0, 1.0 - elapsed / float(window)) if window else 0.0
    speed = int(round(50 * frac))
    bonus = 10 * min(max(streak - 1, 0), 6)
    return base, speed, bonus, base + speed + bonus


GOOD_LINES = ["Doğru cevap!", "Harika!", "Tam isabet!", "Bildin!", "Muhteşem!",
              "Çok iyi gidiyorsun!", "Şahane!", "Aferin!"]
BAD_LINES = ["Yanlış.", "Eyvah, yanlış.", "Olmadı, yanlış.", "Maalesef yanlış.", "Yazık, yanlış."]
TIMEOUT_LINES = ["Süre doldu.", "Zaman bitti.", "Eyvah, süre doldu."]
STREAK_LINES = {
    3: "Isınıyorsun! 3'lü seri.",
    5: "Ateş aldın! 5'li seri.",
    7: "Durdurulamıyorsun! 7'li seri.",
    10: "Efsane gidiyorsun! 10'lu seri.",
    15: "Bu artık rekor kokuyor! 15'li seri.",
}
STREAK_SOUND_AT = (3, 5, 7, 10, 15)


def streak_line(n):
    if n in STREAK_LINES:
        return STREAK_LINES[n]
    return "%d'li seri." % n if n >= 3 else ""


# ---------------------------------------------------------------- arkadaşa sor
# (ad, açılış cümlesi, iyi bildiği kategoriler, zayıf olduğu kategoriler)
FRIENDS = [
    ("Kankan Mehmet", "Ooo sürpriz telefon! Dur bir bakayım.",
     {"Spor", "Müzik", "Sinema"}, {"Edebiyat", "Felsefe ve Mantık", "Matematik"}),
    ("Teyzem", "Aman yavrum, ben bunu televizyonda görmüştüm!",
     {"Yemek ve Mutfak", "Tıp ve Sağlık", "Dil ve Kültür"}, {"Teknoloji", "Matematik", "Astronomi"}),
    ("Dayım", "Ben bu işlerden anlarım, dinle beni.",
     {"Tarih", "Coğrafya", "Ekonomi", "Hukuk ve Siyaset"}, {"Sanat", "Müzik", "Teknoloji"}),
    ("Komşu Fatma Abla", "Çayı koymuştum ama neyse, hemen söyleyeyim.",
     {"Yemek ve Mutfak", "Doğa", "Dil ve Kültür"}, {"Teknoloji", "Hukuk ve Siyaset", "Matematik"}),
    ("Kuzenim Ece", "Aaa tam dün bunu okumuştum!",
     {"Sanat", "Edebiyat", "Psikoloji", "Sinema"}, {"Spor", "Ekonomi"}),
    ("Arkadaşım Burak", "Alo, müsaitim, söyle bakalım.",
     {"Teknoloji", "Bilim", "Keşifler ve İcatlar"}, {"Edebiyat", "Sanat"}),
    ("Öğretmenim Ayşe Hanım", "Bak şimdi evladım, dikkatle dinle.",
     {"Edebiyat", "Tarih", "Dil ve Kültür", "Mitoloji"}, {"Spor", "Teknoloji"}),
    ("Ablam Zeynep", "Hayırdır, yine mi yarışma? Neyse, sor bakalım.",
     {"Tıp ve Sağlık", "Psikoloji", "Doğa"}, {"Ekonomi", "Hukuk ve Siyaset"}),
    ("İş arkadaşım Murat", "Toplantıdayım ama iki dakikam var.",
     {"Ekonomi", "Teknoloji", "Hukuk ve Siyaset"}, {"Doğa", "Mitoloji"}),
    ("Babam", "Hah, aradığın iyi oldu, bunu biliyorum galiba.",
     {"Tarih", "Coğrafya", "Spor", "Arkeoloji"}, {"Teknoloji", "Sinema"}),
    ("Annem", "Canım benim, hemen düşünüyorum.",
     {"Yemek ve Mutfak", "Müzik", "Tıp ve Sağlık"}, {"Teknoloji", "Matematik"}),
    ("Eski sınıf arkadaşım Cem", "Vay be, kaç yıl oldu! Hadi sor bakalım.",
     {"Matematik", "Astronomi", "Felsefe ve Mantık", "Bilim"}, {"Yemek ve Mutfak", "Spor"}),
]
# (temel doğru bilme olasılığı, ağırlık)
CONFIDENCE = [(0.82, 3), (0.68, 4), (0.5, 3)]


def _confidence_words(prob):
    if prob >= 0.85:
        return "Yüzde doksan eminim."
    if prob >= 0.65:
        return "Yüzde yetmiş eminim."
    if prob >= 0.5:
        return "Yarı yarıya eminim."
    return "Pek emin değilim ama içime öyle doğdu."


def friend_hint(right_idx, available, rng=None, category=""):
    """Arkadaşın önerdiği şıkkı seçer. Kategori uzmanlığı olasılığı değiştirir."""
    r = rng or random
    name, intro, strong, weak = r.choice(FRIENDS)
    prob = r.choices([c[0] for c in CONFIDENCE], weights=[c[1] for c in CONFIDENCE])[0]
    note = ""
    if category in strong:
        prob = min(0.97, prob + 0.12)
        note = "Bu benim alanım!"
    elif category in weak:
        prob = max(0.3, prob - 0.15)
        note = "Bu konuda pek iyi değilimdir ama bir deneyeyim."
    wrong = [k for k in available if k != right_idx]
    knows = (r.random() < prob) or not wrong
    idx = right_idx if knows else r.choice(wrong)
    return {"name": name, "intro": intro, "note": note, "level": _confidence_words(prob),
            "idx": idx, "right": idx == right_idx}


# ---------------------------------------------------------------- seyirci jokeri
def audience_poll(right_idx, available, rng=None):
    """Elenmemiş şıklar için yüzdeler (toplam 100). Seyirci çoğu zaman haklıdır, bazen yanılır."""
    r = rng or random
    avail = list(available)
    if right_idx not in avail:
        avail.append(right_idx)
    k = len(avail)
    if k == 1:
        return {right_idx: 100}
    lead = r.uniform(0.55, 0.88) if k == 2 else r.uniform(0.45, 0.80)
    misled = r.random() < 0.15
    top = r.choice([a for a in avail if a != right_idx]) if misled else right_idx
    others = [a for a in avail if a != top]
    rest = 1.0 - lead
    w = [r.random() + 0.15 for _ in others]
    shares = {top: lead}
    for a, x in zip(others, w):
        shares[a] = rest * x / sum(w)
    if max(shares[a] for a in others) > lead * 0.9:  # lider gerçekten lider kalsın
        for a in others:
            shares[a] = rest / len(others)
    raw = {a: shares[a] * 100 for a in avail}
    out = {a: int(v) for a, v in raw.items()}
    left = 100 - sum(out.values())
    for a in sorted(avail, key=lambda a: raw[a] - out[a], reverse=True)[:left]:
        out[a] += 1
    return out


# ---------------------------------------------------------------- çok oyunculu isimler
def clean_names(raw):
    """Boş isimlere 'Oyuncu N' verir, aynı isimleri ayırır."""
    out = []
    for i, nm in enumerate(raw):
        nm = " ".join(str(nm or "").split())[:20] or "Oyuncu %d" % (i + 1)
        base, n = nm, 2
        while nm.lower() in [x.lower() for x in out]:
            nm = "%s %d" % (base, n)
            n += 1
        out.append(nm)
    return out


# ---------------------------------------------------------------- başarımlar
# c: oyun özeti, p: profil
ACHIEVEMENTS = [
    ("ilk", "İlk Adım", "İlk oyununu bitir.",
     lambda c, p: p["oyun"] >= 1),
    ("kusursuz", "Kusursuz", "Hiç yanlış yapmadan en az 10 soruluk bir oyunu bitir.",
     lambda c, p: c["n"] >= 10 and c["correct"] == c["n"]),
    ("jokersiz", "Jokersiz Kahraman", "Hiç joker kullanmadan hatasız bir oyun bitir.",
     lambda c, p: c["n"] >= 10 and c["correct"] == c["n"] and c["jokers"] == 0),
    ("seri7", "Ateş Hattı", "Üst üste 7 soru bil.",
     lambda c, p: c["best_streak"] >= 7),
    ("simsek", "Şimşek", "Bir soruyu 4 saniyeden kısa sürede doğru bil.",
     lambda c, p: c["fastest"] is not None and c["fastest"] < 4),
    ("son_saniye", "Son Saniye", "Süreli oyunda son 2 saniyede doğru cevap ver.",
     lambda c, p: c["last_sec"]),
    ("sagduyu", "Kendine Güvenen", "Arkadaşının yanlış yönlendirdiği bir soruyu yine de doğru bil.",
     lambda c, p: c["fooled_right"]),
    ("gunluk", "Günün Kahramanı", "Günün meydan okumasında en az 7 soru bil.",
     lambda c, p: c["mode"] == "gunluk" and c["correct"] >= 7),
    ("maraton", "Maratoncu", "Can modunda 15 sorunun hepsini bitir.",
     lambda c, p: c["mode"] == "can" and c["finished"]),
    ("bin", "Bin Puan", "Tek oyunda 1000 puan topla.",
     lambda c, p: c["score"] >= 1000),
    ("muddavim", "Müdavim", "10 oyun bitir.",
     lambda c, p: p["oyun"] >= 10),
    ("aliskanlik", "Alışkanlık", "3 gün üst üste oyna.",
     lambda c, p: p["gun_seri"] >= 3),
    ("usta", "Alanında Usta", "Aynı kategoride toplam 20 doğru cevap ver.",
     lambda c, p: any(v[0] >= 20 for v in p["kat"].values())),
]


def apply_result(p, c, today=None):
    """Bitmiş oyunu profile işler. Değişiklikleri özetleyen bir sözlük döndürür."""
    t = today or datetime.date.today()
    t_str = t.isoformat()
    old_rank = rank_info(p["xp"])[3]
    mode = c["mode"]

    p["oyun"] += 1
    p["dogru"] += c["correct"]
    p["soru"] += c["answered"]
    p["xp"] += c["score"]

    old_record = int(p["rekorlar"].get(mode, 0))
    new_record = c["score"] > old_record
    if new_record:
        p["rekorlar"][mode] = c["score"]

    new_streak_record = c["best_streak"] > p["seri"]
    if new_streak_record:
        p["seri"] = c["best_streak"]

    last = _to_date(p.get("son_gun"))
    if last == t:
        pass
    elif last == t - datetime.timedelta(days=1):
        p["gun_seri"] += 1
    else:
        p["gun_seri"] = 1
    p["son_gun"] = t_str

    if mode == "gunluk":
        if p.get("gunluk_tarih") == t_str:
            p["gunluk_puan"] = max(p["gunluk_puan"], c["score"])
        else:
            p["gunluk_tarih"], p["gunluk_puan"] = t_str, c["score"]

    for cat, (ok, tot) in c["cats"].items():
        v = p["kat"].setdefault(cat, [0, 0])
        v[0] += ok
        v[1] += tot

    new_ach = []
    for aid, name, desc, test in ACHIEVEMENTS:
        if aid not in p["basarim"] and test(c, p):
            p["basarim"].append(aid)
            new_ach.append((name, desc))

    name, _next, _left, idx = rank_info(p["xp"])
    return {
        "old_record": old_record,
        "new_record": new_record and c["score"] > 0,
        "new_streak_record": new_streak_record and c["best_streak"] >= 3,
        "new_rank": name if idx > old_rank else None,
        "new_ach": new_ach,
        "day_streak": p["gun_seri"],
    }


# ---------------------------------------------------------------- metinler
def rank_line(p):
    name, nxt, left, _i = rank_info(p["xp"])
    if nxt:
        return "Rütben: %s, %d puan. %s rütbesine %d puan kaldı." % (name, p["xp"], nxt, left)
    return "Rütben: %s, %d puan. En yüksek rütbedesin!" % (name, p["xp"])


def stats_text(p, today=None):
    lines = [rank_line(p)]
    if p["oyun"]:
        pct = int(round(100.0 * p["dogru"] / p["soru"])) if p["soru"] else 0
        lines.append("Bitirilen oyun: %d. Doğru cevap: %d / %d (yüzde %d)." %
                     (p["oyun"], p["dogru"], p["soru"], pct))
    else:
        lines.append("Henüz oyun bitirmedin.")
    recs = [("%s %d" % (MODE_NAMES[m], p["rekorlar"][m])) for m in ("klasik", "can", "gunluk")
            if p["rekorlar"].get(m)]
    lines.append("Rekorlar: %s." % ", ".join(recs) if recs else "Henüz rekorun yok.")
    lines.append("En uzun doğru serisi: %d." % p["seri"])
    ds = current_day_streak(p, today)
    lines.append("Üst üste oynanan gün: %d." % ds if ds else "Günlük serin şu an yok. Bugün oyna, başlat!")
    if daily_played(p, today):
        lines.append("Bugünün meydan okumasından %d puan aldın." % p["gunluk_puan"])
    else:
        lines.append("Günün meydan okuması seni bekliyor.")
    cats = [(c, v[0], v[1]) for c, v in p["kat"].items() if v[1] >= 5]
    if cats:
        best = max(cats, key=lambda x: (x[1] / float(x[2]), x[2]))
        worst = min(cats, key=lambda x: (x[1] / float(x[2]), -x[2]))
        lines.append("En iyi kategorin: %s (%d / %d doğru)." % (best[0], best[1], best[2]))
        if worst[0] != best[0]:
            lines.append("Çalışman gereken kategori: %s (%d / %d doğru)." % (worst[0], worst[1], worst[2]))
    return "\n".join(lines)


def achievements_text(p):
    got = [(n, d) for a, n, d, _t in ACHIEVEMENTS if a in p["basarim"]]
    lock = [(n, d) for a, n, d, _t in ACHIEVEMENTS if a not in p["basarim"]]
    out = ["Kazanılan başarımlar: %d / %d" % (len(got), len(ACHIEVEMENTS))]
    if got:
        out += ["- %s: %s" % x for x in got]
    if lock:
        out += ["", "Henüz kazanılmayanlar:"] + ["- %s: %s" % x for x in lock]
    return "\n".join(out)
