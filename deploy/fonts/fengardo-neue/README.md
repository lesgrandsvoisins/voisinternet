# Fengardo Neue — identité visuelle Les Grands Voisins

Police du logotype officiel (voir aussi `core/static/core/fonts/FengardoNeue-*.woff2`
pour la version web). Recompilée depuis les sources UFO d'origine
([github.com/loicsander/Fengardo-Redux](https://github.com/loicsander/Fengardo-Redux),
licence MIT, Loïc Sander) plutôt que reprise telle quelle du site en production, pour
corriger :

- un « F » entièrement absent de l'italique (glyphe présent mais jamais référencé dans
  la table `cmap` du fichier d'origine) ;
- l'absence de graisse grasse italique (jamais dessinée par le projet d'origine :
  approximée ici en inclinant tous les glyphes de la graisse grasse droite) ;
- des métadonnées `OS/2`/`head`/`name` incohérentes (la graisse grasse portait le bit
  « Regular » de `fsSelection` au lieu du bit « Bold », un nom complet contenant un
  résidu de nom de fichier interne « alpha », un nom PostScript avec une espace —
  invalide selon la spécification). Ces incohérences sont invisibles dans un navigateur
  (CSS `@font-face` fixe `font-weight`/`font-style` explicitement) mais peuvent perturber
  des outils qui lisent les métadonnées internes de la police, dont XeLaTeX/LuaLaTeX.

## Utiliser avec XeLaTeX ou LuaLaTeX (`fontspec`)

```latex
\usepackage{fontspec}
\setmainfont{Fengardo Neue}[
  Path = fonts/fengardo-neue/,
  Extension = .ttf,
  UprightFont = *-Regular,
  BoldFont = *-Bold,
  ItalicFont = *-Italic,
  BoldItalicFont = *-BoldItalic,
]
```

(pdfLaTeX ne peut pas charger de police TrueType/OpenType directement — XeLaTeX ou
LuaLaTeX sont nécessaires.)

## Licence

MIT (Loïc Sander, 2014) — voir la licence complète du projet Fengardo-Redux.
