// Audit d'accessibilité automatique (axe-core, règles WCAG 2.0/2.1/2.2 A et AA + bonnes pratiques) de pages clés, en clair/sombre
// et en 1280/390 px. Lecture seule. Nécessite Node et Playwright ; axe-core s'installe à part (rien n'est ajouté au site) :
//     mkdir /tmp/axe && cd /tmp/axe && npm install axe-core
//     BASE=http://127.0.0.1:8000 SESSION=<cookie sessionid d'un compte> NODE_PATH=<dossier node_modules global> node tools/audit_accessibilite.js
// Sortie : le nombre de violations et le détail dans /tmp/axe-results.json (règle, page, mode, exemples).
const { chromium } = require('playwright');
const fs = require('fs');
const axeSrc = fs.readFileSync(process.env.AXE || '/tmp/axe/node_modules/axe-core/axe.min.js', 'utf8');
const BASE = process.env.BASE || 'http://127.0.0.1:8000';
const SESSION = process.env.SESSION || '';
const pages = (process.env.PAGES || '/fr/,/ar/,/en/,/fr/account/,/fr/account/raccourcis/,/fr/account/parcours/,/fr/account/groupes/,/fr/agenda/,/fr/annuaire/,/fr/blog/,/fr/contact/,/fr/grandsvoisins/,/fr/outils/,/fr/recherche/?q=blog,/fr/etiquettes/,/fr/annuaire/mes-fiches/,/fr/agenda/mes-evenements/').split(',');
(async () => {
  const b = await chromium.launch(); const res = [];
  for (const scheme of ['light', 'dark']) for (const w of [1280, 390]) {
    const ctx = await b.newContext({ viewport: { width: w, height: 900 }, colorScheme: scheme });
    if (SESSION) await ctx.addCookies([{ name: 'sessionid', value: SESSION, url: BASE }]);
    const pg = await ctx.newPage();
    for (const p of pages) {
      try {
        const r = await pg.goto(BASE + p, { waitUntil: 'load' });
        await pg.evaluate(axeSrc);
        const out = await pg.evaluate(async () => await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] } }));
        for (const v of out.violations) res.push({ scheme, w, page: p, status: r.status(), id: v.id, impact: v.impact, help: v.help, n: v.nodes.length, ex: v.nodes.slice(0, 2).map(n => n.target.join(' ')) });
      } catch (e) { res.push({ scheme, w, page: p, id: 'ERREUR', help: String(e).slice(0, 120) }); }
    }
    await ctx.close();
  }
  fs.writeFileSync('/tmp/axe-results.json', JSON.stringify(res, null, 1));
  console.log('violations :', res.length);
  await b.close();
})();
