# -*- coding: utf-8 -*-
"""Oyuncu kimliği, yasak listesi ve rakip bildirimi (sitedeki /api uçlarıyla konuşur)."""
import json
import re
import time
import urllib.error
import urllib.request
import uuid

from yasal import SITE_URL

BANS_URL = SITE_URL + "/api/bans"
REPORT_URL = SITE_URL + "/api/report"
UA = "BilgiYarismasi-Windows"
PID_RE = re.compile(r"^[a-f0-9]{16}$")
KINDS = [("hakaret", "Hakaret / küfür"), ("hile", "Hile"), ("isim", "Uygunsuz isim"),
         ("spam", "Spam"), ("diger", "Diğer")]


def new_pid():
    return uuid.uuid4().hex[:16]


def valid_pid(p):
    return isinstance(p, str) and bool(PID_RE.match(p))


def fetch_bans(timeout=5.0):
    """(başarılı, {kimlik: bitiş_ms}). Sunucuya ulaşılamazsa (False, {}) döner ve kimse engellenmez."""
    try:
        req = urllib.request.Request("%s?t=%d" % (BANS_URL, int(time.time())),
                                     headers={"User-Agent": UA, "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
        now = time.time() * 1000
        out = {}
        for b in d.get("bans", []):
            pid, until = b.get("id"), int(b.get("until") or 0)
            if valid_pid(pid) and (not until or until > now):
                out[pid] = until
        return True, out
    except Exception:
        return False, {}


def send_report(reporter, target_id, target_name, kind, reason, timeout=8.0):
    """(başarılı, hata_metni)"""
    body = json.dumps({"reporter": reporter, "target": {"id": target_id, "name": target_name},
                       "kind": kind, "reason": reason}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(REPORT_URL, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout):
            return True, ""
    except urllib.error.HTTPError as e:
        try:
            return False, json.loads(e.read().decode("utf-8")).get("error", "Hata %d" % e.code)
        except Exception:
            return False, "Hata %d" % e.code
    except Exception:
        return False, "Bağlantı kurulamadı."
