@echo off
chcp 65001 >nul
title Bilgi Yarismasi
cd /d "%~dp0"
set "PYC="
where python >nul 2>nul && set "PYC=python"
if not defined PYC where py >nul 2>nul && set "PYC=py"
if not defined PYC (
  echo [HATA] Python bulunamadi. python.org adresinden kur ve "Add Python to PATH" kutusunu isaretle.
  pause
  exit /b 1
)
%PYC% -c "import wx" >nul 2>nul || (
  echo wxPython kuruluyor, lutfen bekleyin...
  %PYC% -m pip install wxPython
)
%PYC% -c "import accessible_output2" >nul 2>nul || (
  echo Ekran okuyucu destegi kuruluyor...
  %PYC% -m pip install accessible-output2
)
%PYC% bilgi_yarismasi.py
if errorlevel 1 pause
