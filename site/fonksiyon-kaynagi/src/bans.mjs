import { db, json, loadBans } from "./lib.mjs";

/* Herkese açık: yalnızca yasaklı kimlikler ve bitiş zamanı. İsim ve neden asla yayınlanmaz. */
export default async (req) => {
  if (req.method !== "GET") return json({ error: "yöntem" }, 405);
  const bans = (await loadBans(db())).map(b => ({ id: b.id, until: b.until || 0 }));
  return json({ bans, t: Date.now() });
};
export const config = { path: "/api/bans" };
