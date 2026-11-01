import { getStore } from "@netlify/blobs";
import { createHash, timingSafeEqual } from "node:crypto";

export const DAY = 86400000;
export const REPORT_TTL = 90 * DAY;          // bildirimler 90 gün sonra silinir
export const RL_WIN = { rep: 10 * 60000, adm: 15 * 60000 };
export const ID_RE = /^[a-f0-9]{16}$/;
export const KINDS = ["hakaret", "hile", "isim", "spam", "diger"];

export function db() {
  return globalThis.__BY_TEST_STORE__ || getStore({ name: "bilgi-yarismasi", consistency: "strong" });
}
export const json = (obj, status = 200) => new Response(JSON.stringify(obj), {
  status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
});
export const clip = (s, n) => String(s ?? "").replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim().slice(0, n);
export function ipOf(req, context) {
  return (context && context.ip) || req.headers.get("x-nf-client-connection-ip") ||
    (req.headers.get("x-forwarded-for") || "").split(",")[0].trim() || "?";
}
const ipHash = ip => createHash("sha256").update("by|" + ip).digest("hex").slice(0, 24);
export async function readJson(store, key, def) {
  try { const v = await store.get(key, { type: "json" }); return v ?? def; } catch (e) { return def; }
}

/* ---- yasaklar ---- */
export async function loadBans(store) {
  const d = await readJson(store, "bans", { list: [] });
  const now = Date.now();
  return (Array.isArray(d.list) ? d.list : []).filter(b => b && ID_RE.test(b.id) && (!b.until || b.until > now));
}
export const saveBans = (store, list) => store.setJSON("bans", { list: list.slice(-5000) });

/* ---- bildirimler ---- */
export async function loadReports(store) {
  const d = await readJson(store, "reports", { list: [] });
  const min = Date.now() - REPORT_TTL;
  return (Array.isArray(d.list) ? d.list : []).filter(r => r && r.t > min);
}
export const saveReports = (store, list) => store.setJSON("reports", { list: list.slice(-500) });

/* ---- hız sınırı (IP yalnızca özet olarak, kısa süreli kovalarda tutulur) ---- */
const rlKey = (name, ip) => `rl-${name}-${ipHash(ip)}-${Math.floor(Date.now() / RL_WIN[name])}`;
export async function rlCount(store, name, ip) { return (await readJson(store, rlKey(name, ip), { n: 0 })).n; }
export async function rlHit(store, name, ip) {
  const k = rlKey(name, ip);
  const cur = await readJson(store, k, { n: 0 });
  await store.setJSON(k, { n: cur.n + 1 });
  return cur.n + 1;
}
export async function rlCleanup(store) {
  try {
    const { blobs } = await store.list({ prefix: "rl-" });
    const now = Date.now();
    for (const b of blobs) {
      const m = b.key.match(/^rl-([a-z]+)-[a-f0-9]+-(\d+)$/);
      if (m && RL_WIN[m[1]] && (+m[2] + 2) * RL_WIN[m[1]] < now) await store.delete(b.key);
    }
  } catch (e) { /* önemli değil */ }
}

/* ---- yönetici parolası: Netlify ortam değişkeni ADMIN_PASSWORD ---- */
export function passwordOk(given) {
  let real = "";
  try { real = (globalThis.Netlify && Netlify.env && Netlify.env.get("ADMIN_PASSWORD")) || ""; } catch (e) {}
  real = real || process.env.ADMIN_PASSWORD || "";
  if (!real) return null;
  const h = s => createHash("sha256").update(String(s ?? "")).digest();
  return timingSafeEqual(h(given), h(real));
}
export const sleep = ms => new Promise(r => setTimeout(r, ms));
