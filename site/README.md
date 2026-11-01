# Bilgi Yarışması — Web Sitesi

Netlify'a bu klasörü yükle (`netlify.toml` hazır). Ban sistemi için **Netlify Functions** gerekir, bu yüzden aşağıdaki "Yönetici paneli kurulumu" bölümünü oku.

## Dosyalar
- `index.html` — giriş sayfası (tarayıcıdan oyna / Windows uygulamasını indir)
- `index2.html` — oyun (tek başına, günlük meydan okuma, çok oyunculu, online düello)
- `eglence.js` — puan, rütbe, başarım, arkadaşa sor, seyirciye sor, günlük meydan okuma mantığı
- `admin.html` — **yönetici paneli** (parola korumalı, arama motorlarına kapalı)
- `gizlilik.html`, `kosullar.html` — Gizlilik Politikası ve Kullanım Şartları
- `netlify/functions/` — ban listesi, bildirim ve yönetici işlemleri (`bans.mjs`, `report.mjs`, `admin.mjs`; tek dosyaya paketlenmiş, ek kurulum gerekmez)
- `fonksiyon-kaynagi/` — o fonksiyonların okunabilir kaynağı ve testi (yayın için gerekmez)
- `questions.json` — soru havuzu (masaüstü uygulaması da bu dosyayı sitenin adresinden çeker)
- `stil.css`, `iletisim.html`, `tesekkur.html` — ortak stil ve iletişim sayfaları
- `bilgi_yarisi.zip` — Windows uygulaması (giriş sayfasındaki indirme bağlantısı)
- `baslat.bat` — siteyi bilgisayarında denemek için yerel sunucu (ban sistemi yerelde çalışmaz)
- `prompt.txt` — yapay zekâya yeni soru yazdırma talimatı

## Yönetici paneli kurulumu
1. Netlify'da siteni aç: **Site configuration → Environment variables → Add a variable**.
2. Anahtar `ADMIN_PASSWORD`, değer olarak uzun ve tahmin edilmesi zor bir parola yaz. Kimseyle paylaşma.
3. Siteyi yeniden yayınla (değişken yeni yayından sonra geçerli olur).
4. `https://bilgiarena.netlify.app/admin.html` adresine git, parolayla gir.

Panelde ne yapılır:
- **Bildirimler:** oyuncuların "Rakibi bildir" ile gönderdikleri şikâyetler, aynı oyuncuya gelenler gruplanır. "Yasakla…" ile süre (1/7/30 gün ya da kalıcı) seçersin. Bildirimler 90 gün sonra kendiliğinden silinir.
- **Yasaklılar:** aktif yasaklar; "Yasağı kaldır" ile geri alınır. Süreli yasaklar kendiliğinden biter.
- **Kimlikle yasakla:** bir oyuncunun 16 karakterlik oyuncu kimliğini biliyorsan doğrudan yasaklarsın. Oyuncular kimliklerini online ad ekranında görür (itiraz için bunu iletirler).

Parola 8 kez yanlış girilirse o IP 15 dakika kilitlenir.

## Ban sistemi nasıl çalışır, sınırları nelerdir
- Her cihaz rastgele bir **oyuncu kimliği** üretir (web: tarayıcı depolaması, masaüstü: ayar dosyası). Yasak bu kimliğe bağlıdır.
- Online başlamadan önce istemci `/api/bans` listesini ister. Yasaklıysa online'a giremez; tek başına ve çok oyunculu modlar açık kalır. Rakibin yasaklı olduğu eşleşmeler de iptal edilir.
- Sistem yalnızca **resmî site ve uygulama sürümleri** için bağlayıcıdır. Kimliğini sıfırlayan (tarayıcı verisini silen / ayar dosyasını silen) ya da değiştirilmiş istemci kullanan biri yasağı aşabilir; bunu Kullanım Şartları ihlali sayarız ama teknik olarak tamamen engelleyemeyiz. Online altyapı halka açık MQTT sunucularıdır, bizim sunucumuz değildir.
- Ban sunucusuna ulaşılamazsa herkesin online'ı engellenmesin diye oyun serbest bırakılır.
- Kimliksiz eski sürüm istemciler yasaklanamaz.

## Gizlilik ve şartlar
`gizlilik.html` ve `kosullar.html` hizmetin gerçekte yaptığı veri işlemeyi anlatır (yerel veriler, halka açık MQTT, bildirim/yasak kayıtları, Web3Forms, Netlify, Google Fonts). Hizmete yeni bir veri toplama özelliği eklersen bu metinleri de güncelle. Metinler hukuki danışmanlık yerine geçmez; yayınlamadan önce gözden geçirmeni öneririz.

## Fonksiyonları değiştirmek istersen
```
cd fonksiyon-kaynagi
npm install
npm test        # sahte depolamayla testler
npm run build   # ../netlify/functions içine tek dosya olarak paketler
```

Online düello, masaüstü uygulamasıyla aynı MQTT kanalını kullanır; ikisi birbiriyle eşleşir.
