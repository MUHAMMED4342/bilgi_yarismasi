# -*- coding: utf-8 -*-
"""Güncelleme denetimi ve kurulumu (arayüzden bağımsız, wx gerekmez). GitHub Sürümler (Releases) üzerinden çalışır.

Akış: son sürümü öğren -> zip'i indir (sağlama toplamı varsa doğrula) -> geçici klasöre aç ->
küçük bir .bat yardımcısı uygulama kapanınca dosyaları kopyalar ve uygulamayı yeniden açar.
Kullanıcı verisi ("veri" klasörü) zip'te olmadığı için dokunulmaz."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile

import surum

UA = "BilgiYarismasi-Guncelleme"
API_URL = "https://api.github.com/repos/%s/releases/latest" % surum.REPO
LATEST_PAGE = "https://github.com/%s/releases/latest" % surum.REPO
RELEASES_URL = "https://github.com/%s/releases" % surum.REPO
STAGE_NAME = "BilgiYarismasi_guncelleme"
CHUNK = 65536
TAG_RE = re.compile(r"^[A-Za-z0-9._-]{1,40}$")


class UpdateError(Exception):
    pass


class UpdateCancelled(UpdateError):
    pass


# ---------------------------------------------------------------- sürüm karşılaştırma
def parse_version(s):
    m = re.search(r"\d+(?:\.\d+)*", str(s or ""))
    return tuple(int(x) for x in m.group(0).split(".")) if m else ()


def _pad(a, b):
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)), b + (0,) * (n - len(b))


def compare(a, b):
    """-1, 0, 1 (a, b sürüm metni ya da tuple olabilir)"""
    a = parse_version(a) if not isinstance(a, tuple) else a
    b = parse_version(b) if not isinstance(b, tuple) else b
    a, b = _pad(a, b)
    return (a > b) - (a < b)


def is_newer(a, b):
    return compare(a, b) > 0


def vmax(a, b):
    return a if compare(a, b) >= 0 else b


def display_version(app_version, installed=""):
    cur = vmax(parse_version(app_version), parse_version(installed))
    return ".".join(str(x) for x in cur) or str(app_version)


def status(info, installed="", app_version=None):
    """'current' | 'outdated' | 'unknown' (denetlenemediyse)"""
    if not info:
        return "unknown"
    cur = vmax(parse_version(app_version or surum.APP_VERSION), parse_version(installed))
    return "outdated" if is_newer(info["version"], cur) else "current"


# ---------------------------------------------------------------- ortam
def is_frozen():
    return bool(getattr(sys, "frozen", False))


def _is_windows():
    return os.name == "nt"


def can_write(d):
    try:
        p = os.path.join(d, ".yazma_testi_guncelleme")
        with open(p, "w") as f:
            f.write("1")
        os.remove(p)
        return True
    except OSError:
        return False


def can_self_update(app_dir):
    """Yalnızca Windows'ta, paketlenmiş (exe) ve yazılabilir klasördeki kurulumlar kendini günceller.
    Python'dan çalıştırılan kaynak kod, geliştiricinin dosyalarının üzerine yazılmasın diye güncellenmez."""
    return _is_windows() and is_frozen() and can_write(app_dir)


# ---------------------------------------------------------------- son sürümü öğren
def _get(url, timeout, method="GET", accept="*/*"):
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": UA, "Accept": accept, "Cache-Control": "no-cache"})
    return urllib.request.urlopen(req, timeout=timeout)


def _from_api(timeout):
    try:
        with _get(API_URL, timeout, accept="application/vnd.github+json") as r:
            d = json.loads(r.read().decode("utf-8"))
        tag = str(d.get("tag_name") or "")
        ver = parse_version(tag)
        if not ver or not TAG_RE.match(tag):
            return None
        info = {"tag": tag, "version": ver, "notes": str(d.get("body") or "")[:1500],
                "url": "", "size": 0, "sha256": ""}
        for a in d.get("assets") or []:
            if a.get("name") == surum.ASSET_NAME:
                info["url"] = str(a.get("browser_download_url") or "")
                info["size"] = int(a.get("size") or 0)
                dg = str(a.get("digest") or "")
                if dg.startswith("sha256:"):
                    info["sha256"] = dg[7:].strip().lower()
        return info
    except Exception:
        return None


def _from_redirect(timeout):
    """API sınırına takılırsak: /releases/latest sayfası en son etikete yönlendirir."""
    for method in ("HEAD", "GET"):
        try:
            with _get(LATEST_PAGE, timeout, method=method) as r:
                final = r.geturl()
            m = re.search(r"/releases/tag/([^/?#]+)", final)
            if m:
                tag = urllib.parse.unquote(m.group(1))
                ver = parse_version(tag)
                if ver and TAG_RE.match(tag):
                    return {"tag": tag, "version": ver, "notes": "", "url": "", "size": 0, "sha256": ""}
        except Exception:
            continue
    return None


def check_latest(timeout=6.0):
    """{'tag','version','notes','url','size','sha256'} ya da None (denetlenemedi)."""
    return _from_api(timeout) or _from_redirect(timeout)


def download_url(info):
    if info.get("url"):
        return info["url"]
    return "https://github.com/%s/releases/download/%s/%s" % (
        surum.REPO, urllib.parse.quote(info["tag"]), surum.ASSET_NAME)


# ---------------------------------------------------------------- indirme ve açma
def stage_dir():
    return os.path.join(tempfile.gettempdir(), STAGE_NAME)


def prepare_stage():
    d = stage_dir()
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d, exist_ok=True)
    return d


def cleanup_stage():
    """Önceki güncellemeden kalan büyük dosyaları sil (kayıt dosyası kalır)."""
    d = stage_dir()
    shutil.rmtree(os.path.join(d, "yeni"), ignore_errors=True)
    try:
        os.remove(os.path.join(d, "paket.zip"))
    except OSError:
        pass


def download(url, dest, progress=None, timeout=20.0, sha256="", cancel=None, size_hint=0):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    h = hashlib.sha256()
    got = 0
    with urllib.request.urlopen(req, timeout=timeout) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0) or size_hint
        while True:
            if cancel and cancel():
                raise UpdateCancelled("İptal edildi.")
            chunk = r.read(CHUNK)
            if not chunk:
                break
            f.write(chunk)
            h.update(chunk)
            got += len(chunk)
            if progress:
                progress(got, total)
    if sha256 and h.hexdigest() != sha256.lower():
        raise UpdateError("İndirilen dosya doğrulanamadı (sağlama toplamı uyuşmuyor).")
    return got


def extract(zip_path, stage):
    """Zip'i stage\\yeni içine açar, uygulama dosyalarının bulunduğu klasörü döndürür."""
    dest = os.path.join(stage, "yeni")
    shutil.rmtree(dest, ignore_errors=True)
    try:
        z = zipfile.ZipFile(zip_path)
    except zipfile.BadZipFile:
        raise UpdateError("İndirilen zip dosyası bozuk.")
    with z:
        bad = z.testzip()
        if bad:
            raise UpdateError("Zip bozuk: %s" % bad)
        root = os.path.realpath(dest)
        for n in z.namelist():
            t = os.path.realpath(os.path.join(dest, n))
            if t != root and not t.startswith(root + os.sep):
                raise UpdateError("Güvensiz dosya yolu: %s" % n)
        z.extractall(dest)
    for dp, _dn, fn in os.walk(dest):
        if surum.EXE_NAME in fn:
            return dp
    raise UpdateError("Zip içinde %s bulunamadı." % surum.EXE_NAME)


# ---------------------------------------------------------------- kurulum (Windows)
# Yalnızca ASCII: yollar ortam değişkenleriyle geçer, böylece Türkçe karakterli kullanıcı adları sorun çıkarmaz.
BAT = """@echo off
setlocal
set "N=0"
>>"%BY_LOG%" echo [%date% %time%] guncelleme basladi: %BY_TAG%
:bekle
tasklist /FI "PID eq %BY_PID%" /NH 2>nul | find /i "%BY_EXE%" >nul
if errorlevel 1 goto kopyala
set /a N+=1
if %N% GEQ 90 goto kopyala
ping 127.0.0.1 -n 2 >nul
goto bekle
:kopyala
ping 127.0.0.1 -n 2 >nul
robocopy "%BY_SRC%" "%BY_APP%" /E /IS /IT /R:10 /W:2 /NFL /NDL /NJH /NJS /NP >>"%BY_LOG%" 2>&1
if errorlevel 8 goto hata
>>"%BY_LOG%" echo [%date% %time%] kopyalama tamam
cd /d "%BY_APP%"
start "" "%BY_APP%\\%BY_EXE%" --guncellendi=%BY_TAG%
goto bitis
:hata
>>"%BY_LOG%" echo [%date% %time%] HATA: kopyalama basarisiz
cd /d "%BY_APP%"
start "" "%BY_APP%\\%BY_EXE%"
:bitis
endlocal
"""


def apply_frozen(src_dir, app_dir, tag, stage, pid=None, popen=None):
    """Yardımcı .bat'ı başlatır. Çağıran, hemen ardından uygulamayı kapatmalıdır."""
    if not _is_windows():
        raise UpdateError("Otomatik kurulum yalnızca Windows'ta çalışır.")
    if not TAG_RE.match(tag or ""):
        raise UpdateError("Geçersiz sürüm etiketi.")
    bat = os.path.join(stage, "uygula.bat")
    with open(bat, "w", encoding="ascii", newline="\r\n") as f:
        f.write(BAT)
    env = dict(os.environ)
    env.update(BY_APP=os.path.normpath(app_dir), BY_SRC=os.path.normpath(src_dir), BY_EXE=surum.EXE_NAME,
               BY_PID=str(pid or os.getpid()), BY_TAG=tag, BY_LOG=os.path.join(stage, "guncelleme.log"))
    popen = popen or subprocess.Popen
    # CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    popen(["cmd.exe", "/d", "/c", "call", bat], env=env, cwd=stage, stdin=subprocess.DEVNULL,
          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
          creationflags=0x08000000 | 0x00000200)
    return bat
