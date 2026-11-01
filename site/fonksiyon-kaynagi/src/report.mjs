import { db, json, clip, ipOf, ID_RE, KINDS, loadReports, saveReports, rlCount, rlHit, rlCleanup } from "./lib.mjs";

/* Oyuncular rakibi bildirir. Yönetici panelinde görünür; kimse otomatik yasaklanmaz. */
export default async (req, context) => {
  if (req.method !== "POST") return json({ error: "yöntem" }, 405);
  let b; try { b = await req.json(); } catch (e) { return json({ error: "bozuk istek" }, 400); }
  const store = db(), ip = ipOf(req, context);
  const tid = typeof b?.target?.id === "string" && ID_RE.test(b.target.id) ? b.target.id : "";
  const tname = clip(b?.target?.name, 20);
  if (!tid && !tname) return json({ error: "Bildirilen oyuncu belirtilmemiş." }, 400);
  if (await rlCount(store, "rep", ip) >= 5) return json({ error: "Çok fazla bildirim. Biraz sonra tekrar dene." }, 429);
  const rid = typeof b?.reporter === "string" && ID_RE.test(b.reporter) ? b.reporter : "";
  const kind = KINDS.includes(b?.kind) ? b.kind : "diger";
  const reason = clip(b?.reason, 300);
  const list = await loadReports(store);
  const now = Date.now();
  // Aynı kişi aynı oyuncuyu 1 saat içinde tekrar bildirirse yeni kayıt açılmaz.
  if (!(rid && tid && list.some(r => r.reporter === rid && r.target.id === tid && now - r.t < 3600000))) {
    list.push({ rid: now.toString(36) + Math.random().toString(36).slice(2, 7), t: now, kind, reason,
                reporter: rid, target: { id: tid, name: tname } });
    await saveReports(store, list);
  }
  await rlHit(store, "rep", ip);
  if (Math.random() < 0.1) await rlCleanup(store);
  return json({ ok: true });
};
export const config = { path: "/api/report" };
