// Fonksiyonları bağımlılıklarıyla birlikte tek dosyaya paketler (sürükle-bırak yüklemede de çalışsın diye).
import { build } from "esbuild";
for (const f of ["bans", "report", "admin"]) {
  await build({
    entryPoints: [`src/${f}.mjs`], outfile: `../netlify/functions/${f}.mjs`,
    bundle: true, format: "esm", platform: "node", target: "node18", minify: false, legalComments: "none",
  });
  console.log("paketlendi:", f);
}
