# Bilgi Yarışması — Windows (wxPython) Uygulaması

Ekran okuyucu uyumlu masaüstü sürümü. Tek başına oyun + online düello (sitedeki oyuncularla eşleşir).

## Neler var?
- **Üç mod:** Klasik (10 soru, ilk yanlışta biter), Can modu (15 soru, 3 can) ve **Günün Meydan Okuması** (her gün herkes için aynı 10 soru, 2 can).
- **Kategori seçimi** ve isteğe bağlı süre.
- **Puan sistemi:** her doğru 100 puan + hız bonusu (en çok 50) + seri bonusu (en çok 60).
- **Dört joker:** J yarı yarıya, **F arkadaşa sor** (12 farklı kişi; her birinin uzman olduğu konular var, her zaman haklı çıkmazlar), **A seyirciye sor** (yüzdelik oylar), **S soruyu değiştir**.
- **Çok oyunculu (2-4 kişi, aynı bilgisayarda):** sırayla oynanır, herkes 5 soru cevaplar, herkesin kendi jokerleri var; sıra değişince ekran okuyucu kimin sırası olduğunu söyler.
- **Rütbeler:** Çaylak → Meraklı → Bilgiç → Uzman → Üstat → Bilge → Efsane.
- **13 başarım**, rekorlar, günlük seri ve kategori istatistikleri (ana menü → Profilim).
- Yeni sesler: seri, rekor, başarım, telefon, soru değiştirme.
- Oyun içi kısayollar: 1-4, C, T, P, J, F, A, S, Esc.

## Çalıştırma
`calistir.bat` — gerekli paketleri kurar ve uygulamayı açar.

## Taşınabilir EXE (32 bit)
`exe_olustur.bat` — 32 bit Python (3.11 önerilir) ile `BilgiYarismasi_tasinabilir.zip` üretir.

## Güvenlik ve gizlilik
- Ana menüde **Gizlilik Politikası** ve **Kullanım Şartları** ekranları var (metin kutusunda okunur, isteyen sitede açabilir).
- Online oynamadan önce şartlar bir kez onaylatılır.
- Her kurulum rastgele bir **oyuncu kimliği** üretir (ayar dosyasında saklanır). Yönetici bir kimliği yasaklarsa o cihaz online'a giremez; tek başına, günlük ve çok oyunculu modlar çalışmaya devam eder.
- Online ekranlarda **B** tuşuyla (ya da sonuç ekranındaki düğmeyle) rakip bildirilir.

## Dosyalar
- `bilgi_yarismasi.py` — ana uygulama ve arayüz
- `eglence.py` — puan, rütbe, başarım, günlük meydan okuma, arkadaş jokeri (arayüzden bağımsız)
- `yasak.py` — oyuncu kimliği, yasak listesi kontrolü ve rakip bildirimi (sitedeki /api uçlarıyla konuşur)
- `yasal.py` — Gizlilik Politikası ve Kullanım Şartları metinleri (siteyle aynı içerik)
- `online.py` — MQTT taşıyıcı, eşleşme, düello kuralları
- `online_ui.py` — online ekranları
- `questions.json` — internet yokken kullanılan yedek soru havuzu (normalde sitenin adresinden çekilir)
- `requirements.txt` — paketler

Günün meydan okuması, web sitesiyle birebir aynı soruları seçer.

Sorular her oyunda `https://bilgiarena.netlify.app/questions.json` adresinden yenilenir.
