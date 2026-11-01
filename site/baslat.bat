@echo off
chcp 65001 >nul
title Bilgi Yarismasi - yerel sunucu
cd /d "%~dp0"
where python >nul 2>nul || (echo [HATA] Python bulunamadi. & pause & exit /b 1)
echo Tarayicida http://localhost:8000/index.html adresini ac. Kapatmak icin bu pencereyi kapat.
start "" http://localhost:8000/index.html
python -m http.server 8000
