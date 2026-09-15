#!/usr/bin/env python3
"""
Corrige les fichiers d'export Ghost dont le frontmatter YAML est invalide : le
champ `excerpt:` a été rempli avec le corps entier du billet, sur plusieurs
lignes brutes, sans la syntaxe de bloc littéral YAML. Reformate en
`excerpt: |` suivi des lignes du texte indentées de deux espaces, jusqu'à la
ligne `slug:` qui suit.

Usage : python3 fix_excerpt.py [fichier.md ...]
Sans argument, traite tous les *.md du dossier.
"""
import glob
import sys


def fix_file(path):
    with open(path, encoding="utf-8") as f:
        lines = f.readlines()

    if not lines or lines[0].rstrip("\n") != "---":
        return False

    try:
        end = next(i for i in range(1, len(lines)) if lines[i].rstrip("\n") == "---")
    except StopIteration:
        return False

    frontmatter = lines[1:end]
    excerpt_i = next((i for i, l in enumerate(frontmatter) if l.startswith("excerpt:")), None)
    slug_i = next((i for i, l in enumerate(frontmatter) if l.startswith("slug:")), None)
    if excerpt_i is None or slug_i is None or slug_i <= excerpt_i + 1:
        return False  # déjà sur une seule ligne, ou format inattendu : on ne touche pas

    first_line = frontmatter[excerpt_i][len("excerpt:"):].strip()
    body_lines = [l.rstrip("\n") for l in frontmatter[excerpt_i + 1:slug_i]]
    # Ligne(s) vide(s) juste avant `slug:` : un artefact du bug, pas du texte.
    while body_lines and not body_lines[-1]:
        body_lines.pop()

    new_excerpt = ["excerpt: |\n"]
    for line in [first_line, *body_lines]:
        new_excerpt.append(f"  {line}\n" if line else "\n")

    new_lines = lines[:1] + frontmatter[:excerpt_i] + new_excerpt + frontmatter[slug_i:] + lines[end:]

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    return True


def main(paths):
    changed = [p for p in paths if fix_file(p)]
    for p in changed:
        print(f"corrigé : {p}")
    print(f"{len(changed)}/{len(paths)} fichier(s) modifié(s)")


if __name__ == "__main__":
    main(sys.argv[1:] or sorted(glob.glob("deploy/ghost-export/*.md")))
