@echo off
setlocal enableextensions
title Bilgi Yarismasi - EXE olusturucu (32 bit)
cd /d "%~dp0"

rem ===== AYARLAR =====
rem ONEFILE=0 : klasor (hizli acilir, onerilen)   ONEFILE=1 : tek exe (acilista biraz yavas)
set "ONEFILE=0"
rem 32 bit Python otomatik bulunamazsa buraya tam yolunu yazabilirsin. Ornek: C:\Python311-32\python.exe
set "PY32="
rem ====================

for %%F in (bilgi_yarismasi.py eglence.py yasak.py yasal.py online.py online_ui.py) do (
  if not exist "%%F" (
    echo [HATA] %%F bulunamadi. Tum .py dosyalari bu bat dosyasiyla ayni klasorde olmali.
    pause & exit /b 1
  )
)

rem --- 32 bit Python'u bul ---
if not defined PY32 (
  py -3-32 -c "import sys" >nul 2>nul && set "PY32=py -3-32"
)
if not defined PY32 (
  echo [HATA] 32 bit Python bulunamadi.
  echo python.org adresinden "Windows installer (32-bit)" surumunu kur. Python 3.11 32 bit onerilir
  echo ^(wxPython'un 32 bit hazir paketi bu surumde bulunur^). Kurarken "py launcher" kutusu isaretli olsun.
  echo Ya da bu dosyayi acip PY32 satirina python.exe yolunu yaz.
  pause & exit /b 1
)

%PY32% -c "import struct,sys; sys.exit(0 if struct.calcsize('P')*8==32 else 1)"
if errorlevel 1 (
  echo [HATA] Secilen Python 32 bit degil. Lutfen 32 bit kurulum kullan.
  pause & exit /b 1
)
for /f "delims=" %%V in ('%PY32% -c "import sys;print(sys.version.split()[0])"') do set "PYVER=%%V"
echo 32 bit Python bulundu: %PYVER%

rem --- sanal ortam ---
if not exist ".venv32\Scripts\python.exe" (
  echo Sanal ortam olusturuluyor...
  %PY32% -m venv .venv32
  if errorlevel 1 ( echo [HATA] Sanal ortam olusturulamadi. & pause & exit /b 1 )
)
set "VP=.venv32\Scripts\python.exe"

echo Paketler kuruluyor, lutfen bekle...
"%VP%" -m pip install --upgrade pip >nul 2>nul
"%VP%" -m pip install --only-binary=:all: wxPython
if errorlevel 1 (
  echo [HATA] wxPython 32 bit paketi kurulamadi. Python 3.11 32 bit kullanmayi dene.
  pause & exit /b 1
)
"%VP%" -m pip install pyinstaller
if errorlevel 1 ( echo [HATA] pyinstaller kurulamadi. & pause & exit /b 1 )
"%VP%" -m pip install paho-mqtt >nul 2>nul
set "AO="
"%VP%" -m pip install accessible-output2
if errorlevel 1 (
  echo [UYARI] accessible-output2 kurulamadi. Ekran okuyucu konusmasi yerine SAPI/odak yontemi kullanilacak.
) else (
  set "AO=--collect-all accessible_output2 --collect-all libloader --collect-all platform_utils"
)

set "MODE=--onedir"
if "%ONEFILE%"=="1" set "MODE=--onefile"

echo EXE olusturuluyor...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
"%VP%" -m PyInstaller --noconfirm --clean --windowed %MODE% --name BilgiYarismasi %AO% --hidden-import paho.mqtt.client bilgi_yarismasi.py
if errorlevel 1 ( echo [HATA] PyInstaller basarisiz oldu. & pause & exit /b 1 )

rem --- tasinabilir paket ---
set "OUT=dist\BilgiYarismasi"
if "%ONEFILE%"=="1" (
  mkdir "%OUT%" 2>nul
  move /y "dist\BilgiYarismasi.exe" "%OUT%\" >nul
)
if exist questions.json copy /y questions.json "%OUT%\" >nul
> "%OUT%\OKU.txt" echo Bilgi Yarismasi - tasinabilir surum. Klasoru istedigin yere kopyala, BilgiYarismasi.exe dosyasini ac. Ayarlar ve sesler "veri" klasorunde saklanir.

echo ZIP hazirlaniyor...
"%VP%" -c "import shutil; shutil.make_archive('BilgiYarismasi_tasinabilir','zip','dist','BilgiYarismasi')"
if errorlevel 1 ( echo [HATA] ZIP olusturulamadi. & pause & exit /b 1 )

echo.
echo TAMAM: %~dp0BilgiYarismasi_tasinabilir.zip
echo Klasor surumu: %~dp0%OUT%
pause
