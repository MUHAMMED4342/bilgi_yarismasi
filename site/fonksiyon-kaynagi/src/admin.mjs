import { db, json, clip, ipOf, sleep, passwordOk, ID_RE, DAY,
         loadBans, saveBans, loadReports, saveReports, rlCount, rlHit, rlCleanup } from "./lib.mjs";

/* Yönetici işlemleri. Her istekte parola gönderilir (Netlify ortam değişkeni ADMIN_PASSWORD ile karşılaştırılır). */
export default async (req, context) => {
  if (req.method !== "POST") return json({ error: "yöntem" }, 405);
  let b; try { b = await req.json(); } catch (e) { return json({ error: "bozuk istek" }, 400); }
  const store = db(), ip = ipOf(req, context);
  const ok = passwordOk(b?.key);
  if (ok === null) return json({ error: "Yönetici parolası ayarlanmamış. Netlify'da ADMIN_PASSWORD ortam değişkenini tanımla." }, 503);
  if (await rlCount(store, "adm", ip) >= 8) return json({ error: "Çok fazla hatalı deneme. 15 dakika sonra tekrar dene." }, 429);
  if (!ok) { await rlHit(store, "adm", ip); await sleep(700); return json({ error: "Parola yanlış." }, 401); }

  let bans = await loadBans(store), reports = await loadReports(store);
  const act = b.action;
  if (act === "ban") {
    const id = String(b.id || "").trim().toLowerCase();
    if (!ID_RE.test(id)) return json({ error: "Kimlik 16 karakterlik harf-rakam (a-f, 0-9) olmalı." }, 400);
    const days = Math.max(0, Math.min(3650, Math.floor(+b.days || 0)));
    const entry = { id, name: clip(b.name, 20), reason: clip(b.reason, 200), t: Date.now(), until: days ? Date.now() + days * DAY : 0 };
    bans = bans.filter(x => x.id !== id).concat(entry);
    await saveBans(store, bans);
  } else if (act === "unban") {
    const id = String(b.id || "").trim().toLowerCase();
    bans = bans.filter(x => x.id !== id);
    await saveBans(store, bans);
  } else if (act === "dismiss") {
    if (b.target) reports = reports.filter(r => r.target.id !== b.target);
    else reports = reports.filter(r => r.rid !== b.rid);
    await saveReports(store, reports);
  } else if (act !== "list") {
    return json({ error: "Bilinmeyen işlem." }, 400);
  }
  if (act === "list" && Math.random() < 0.3) await rlCleanup(store);
  return json({ ok: true, bans: bans.slice().sort((a, c) => c.t - a.t), reports: reports.slice().sort((a, c) => c.t - a.t), t: Date.now() });
};
export const config = { path: "/api/admin" };
