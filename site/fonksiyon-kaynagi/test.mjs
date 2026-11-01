// Sahte depolama ile fonksiyon testi: npm test
const mem = new Map();
globalThis.__BY_TEST_STORE__ = {
  async get(k) { return mem.has(k) ? JSON.parse(mem.get(k)) : null; },
  async setJSON(k, v) { mem.set(k, JSON.stringify(v)); },
  async delete(k) { mem.delete(k); },
  async list({ prefix }) { return { blobs: [...mem.keys()].filter(k => k.startsWith(prefix)).map(key => ({ key })) }; },
};
process.env.ADMIN_PASSWORD = "gizli-parola";
const bans = (await import("./src/bans.mjs")).default;
const report = (await import("./src/report.mjs")).default;
const admin = (await import("./src/admin.mjs")).default;
let n = 0; const ok = (c, m) => { n++; if (!c) { console.log("BAŞARISIZ:", m); process.exitCode = 1; } };
const post = (h, body, ip = "1.1.1.1") => h(new Request("http://x/api", { method: "POST", body: JSON.stringify(body) }), { ip });
const A = id => "a".repeat(16 - id.length) + id;
const get = async () => (await (await bans(new Request("http://x/api/bans"))).json());

ok((await get()).bans.length === 0, "başta ban yok");
// yönetici: yanlış parola
let r = await post(admin, { key: "yanlış", action: "list" }); ok(r.status === 401, "yanlış parola 401");
r = await post(admin, { key: "gizli-parola", action: "list" }); ok(r.status === 200, "doğru parola");
// bildirim
const T = "1234567890abcdef", R = "fedcba0987654321";
r = await post(report, { reporter: R, target: { id: T, name: "Kötü Ali" }, kind: "hakaret", reason: "küfür etti\n\n   çok" }, "2.2.2.2");
ok(r.status === 200, "bildirim alındı");
await post(report, { reporter: R, target: { id: T, name: "Kötü Ali" }, kind: "hakaret", reason: "tekrar" }, "2.2.2.2");
let list = await (await post(admin, { key: "gizli-parola", action: "list" })).json();
ok(list.reports.length === 1 && list.reports[0].reason === "küfür etti çok", "bildirim temizlendi ve tekrar sayılmadı");
r = await post(report, { target: { id: "zzz", name: "" } }, "3.3.3.3"); ok(r.status === 400, "geçersiz hedef");
// hız sınırı
for (let i = 0; i < 6; i++) r = await post(report, { target: { id: "", name: "x" + i } }, "9.9.9.9");
ok(r.status === 429, "bildirim hız sınırı");
// ban
r = await post(admin, { key: "gizli-parola", action: "ban", id: T, name: "Kötü Ali", reason: "küfür", days: 7 });
list = await r.json(); ok(list.bans.length === 1 && list.bans[0].until > Date.now(), "ban eklendi");
let pub = await get(); ok(pub.bans.length === 1 && pub.bans[0].id === T && !("name" in pub.bans[0]) && !("reason" in pub.bans[0]), "herkese açık liste sadece kimlik içerir");
r = await post(admin, { key: "gizli-parola", action: "ban", id: "KISA" }); ok(r.status === 400, "geçersiz kimlik reddedildi");
// süresi dolan ban listede görünmez
mem.set("bans", JSON.stringify({ list: [{ id: T, name: "", reason: "", t: 1, until: Date.now() - 1000 }] }));
ok((await get()).bans.length === 0, "süresi dolan ban görünmez");
// kalıcı ban + kaldırma
await post(admin, { key: "gizli-parola", action: "ban", id: T.toUpperCase(), days: 0 });
pub = await get(); ok(pub.bans[0].until === 0, "kalıcı ban");
await post(admin, { key: "gizli-parola", action: "unban", id: T }); ok((await get()).bans.length === 0, "ban kaldırıldı");
// bildirimi sil
await post(admin, { key: "gizli-parola", action: "dismiss", target: T });
list = await (await post(admin, { key: "gizli-parola", action: "list" })).json(); ok(!list.reports.some(r => r.target.id === T), "bildirim silindi");
// kaba kuvvet engeli
let last; for (let i = 0; i < 9; i++) last = await post(admin, { key: "x" + i, action: "list" }, "7.7.7.7");
ok(last.status === 429, "8 hatadan sonra kilit");
r = await post(admin, { key: "gizli-parola", action: "list" }, "7.7.7.7"); ok(r.status === 429, "kilitliyken doğru parola da reddedilir");
// parola ayarlanmamışsa
delete process.env.ADMIN_PASSWORD; r = await post(admin, { key: "x", action: "list" }, "8.8.8.8"); ok(r.status === 503, "parola yoksa 503");
r = await bans(new Request("http://x/api/bans", { method: "POST" })); ok(r.status === 405, "bans POST kabul etmez");
console.log("fonksiyon testleri tamam:", n, "kontrol");
