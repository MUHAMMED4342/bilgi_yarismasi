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

## Güncelleme sistemi
- Uygulama açılırken GitHub'dan en son sürüme bakar. Yeni sürüm varsa **kendiliğinden indirir, kurar ve yeniden açılır** (ilerleme ekran okuyucuya okunur; Esc ya da İptal et ile vazgeçilir).
- **Eski sürümle online oynanamaz.** Online ekranına girince ya da eşleşme başlatınca sürüm denetlenir; eskiyse "Online için güncelleme gerekli" ekranı açılır. Tek başına, günlük meydan okuma ve çok oyunculu modlar eski sürümle de çalışır.
- GitHub'a ulaşılamıyorsa (internet yoksa) herkes engellenmesin diye online serbest bırakılır.
- Ana menüde **Güncellemeleri denetle** düğmesi ve Oyun menüsünde **Güncellemeleri açılışta otomatik kur** anahtarı var. Otomatik kurulum kapalıyken de eski sürümle online oynanamaz.
- Otomatik kurulum yalnızca paketlenmiş **exe** için (Windows) çalışır; `calistir.bat` ile Python'dan çalışan kaynak kod kendi dosyalarını değiştirmez, sadece haber verir.
- Kullanıcı verileri (`veri` klasörü: ayarlar, profil, oyuncu kimliği) güncellemede korunur.
- Bir güncelleme iki kez art arda kurulamazsa otomatik deneme durur ve "Sürümler sayfasından elle indir" denir.

### Yeni sürüm nasıl yayınlanır
1. `surum.py` içindeki `APP_VERSION` değerini artır (örn. `"1.0.1"`).
2. `exe_olustur.bat` ile EXE zip'ini üret (sonunda hangi etiketi kullanacağını yazar).
3. GitHub → Releases → Create a new release. **Etiket (tag) tam olarak `v` + sürüm** olmalı (örn. `v1.0.1`). `BilgiYarismasi_tasinabilir.zip` dosyasını adını değiştirmeden ekle, Publish release de.
4. Kullanıcılar uygulamayı açınca yeni sürümü kendiliğinden alır; eski sürüm online'a giremez.

Not: Güncelleme sistemi bu sürümle (1.0.0) birlikte gelir; daha eski bir kurulumu kullananlar bir kez elle yeni zip'i indirmeli.

## Güvenlik ve gizlilik
- Ana menüde **Gizlilik Politikası** ve **Kullanım Şartları** ekranları var (metin kutusunda okunur, isteyen sitede açabilir).
- Online oynamadan önce şartlar bir kez onaylatılır.
- Her kurulum rastgele bir **oyuncu kimliği** üretir (ayar dosyasında saklanır). Yönetici bir kimliği yasaklarsa o cihaz online'a giremez; tek başına, günlük ve çok oyunculu modlar çalışmaya devam eder.
- Online ekranlarda **B** tuşuyla (ya da sonuç ekranındaki düğmeyle) rakip bildirilir.

## Dosyalar
- `bilgi_yarismasi.py` — ana uygulama ve arayüz
- `eglence.py` — puan, rütbe, başarım, günlük meydan okuma, arkadaş jokeri (arayüzden bağımsız)
- `surum.py` — uygulama sürümü (yeni sürüm çıkarırken ilk burayı artır)
- `guncelle.py` — güncelleme denetimi ve kurulumu (GitHub Releases üzerinden)
- `yasak.py` — oyuncu kimliği, yasak listesi kontrolü ve rakip bildirimi (sitedeki /api uçlarıyla konuşur)
- `yasal.py` — Gizlilik Politikası ve Kullanım Şartları metinleri (siteyle aynı içerik)
- `online.py` — MQTT taşıyıcı, eşleşme, düello kuralları
- `online_ui.py` — online ekranları
- `questions.json` — internet yokken kullanılan yedek soru havuzu (normalde GitHub'daki `site/questions.json` dosyasından çekilir)
- `requirements.txt` — paketler

Günün meydan okuması, web sitesiyle birebir aynı soruları seçer.

Sorular her oyunda `https://raw.githubusercontent.com/MUHAMMED4342/bilgi_yarismasi/master/site/questions.json` adresinden yenilenir (Netlify'dan çekilmez). Soru eklemek için GitHub'daki bu dosyayı güncellemen yeterli; uygulama ve site birkaç dakika içinde yeni soruları alır.

Not: Yasak listesi ve rakip bildirimi (`yasak.py`) Netlify'daki siteye bağlanır; sorular ise yalnızca GitHub'dan gelir.
