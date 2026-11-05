"""Pre-filled GitHub issues: the catalogue's only way to act (docs/catalog.md).

Each button opens github.com/<repo>/issues/new with a title, a body and the label `catalog`.
The owner reads it, edits it if needed and submits it; a code session then applies the change
in a pull request. Nothing is written from the page.
"""

from __future__ import annotations

from urllib.parse import urlencode

REPO = "mssnoussi92/quran-reels"
SITE = "https://mssnoussi92.github.io/quran-reels/catalog/"
LABEL = "catalog"
FOOTER = ("\n\n---\nOuvert depuis le catalogue ({where}). Une session de code applique la "
          "décision en PR ; rien n'est modifié tant que la PR n'est pas fusionnée.")


def url(title: str, body: str, anchor: str = "", repo: str = REPO) -> str:
    where = SITE + (f"#{anchor}" if anchor else "")
    query = urlencode({"title": title, "body": body.strip() + FOOTER.format(where=where),
                       "labels": LABEL})
    return f"https://github.com/{repo}/issues/new?{query}"


def _lines(facts: dict[str, object]) -> str:
    return "\n".join(f"- {k} : {v}" for k, v in facts.items() if v not in (None, "", [], 0))


def remove_reciter(name: str, label: str, facts: dict[str, object]) -> str:
    return url(f"Catalogue : retirer {label} de la rotation",
               f"Décision : **retirer {label}** (`{name}`) de `content.rotation.reciters` "
               "(config/project.yaml). Il reste dans la liste des récitateurs.\n\n"
               f"{_lines(facts)}\n\nRaison : ", f"rec-{name}")


def add_reciter(name: str, label: str, facts: dict[str, object]) -> str:
    return url(f"Catalogue : ajouter {label} à la rotation",
               f"Décision : **ajouter {label}** (`{name}`) à `content.rotation.reciters` "
               "(config/project.yaml).\n\n"
               "Avant : découpes vérifiées des passages à venir (workflow `prepare`), essai "
               "sur Facebook seul puis Instagram (règle 6 de CLAUDE.md).\n\n"
               f"{_lines(facts)}\n\nRaison : ", f"rec-{name}")


def add_candidate(folder: str, label: str, facts: dict[str, object]) -> str:
    return url(f"Catalogue : ajouter {label} (EveryAyah) à la rotation",
               f"Décision : **ajouter {label}** depuis EveryAyah, dossier `{folder}`, à "
               "`content.reciters` puis à `content.rotation.reciters` (config/project.yaml).\n\n"
               "Avant : vérifier la provenance et les droits de l'enregistrement, essai sur "
               "Facebook seul puis Instagram (règle 6 de CLAUDE.md).\n\n"
               f"{_lines(facts)}\n\nRaison : ", "candidates")


def remove_background(bg_id: str, facts: dict[str, object]) -> str:
    return url(f"Catalogue : retirer le fond {bg_id}",
               f"Décision : **retirer le fond** `{bg_id}` de `config/backgrounds.yaml` (il "
               "passe dans la liste des refusés du catalogue, avec la raison).\n\n"
               f"{_lines(facts)}\n\nRaison : ", f"bg-{bg_id}")


def clip_decision(approve: bool, clip_id: str, facts: dict[str, object]) -> str:
    verb = "approuver" if approve else "refuser"
    what = ("**approuver** ce clip : l'ajouter à `config/backgrounds.yaml` (`source: pixabay`, "
            "`pixabay_id`, `author`, `page`, `tags`, `note`) après le contrôle image par image "
            "(ni personnes, ni animaux, ni texte)." if approve else
            "**refuser** ce clip : il rejoint la liste des refusés du catalogue, avec la raison.")
    return url(f"Catalogue : {verb} le clip candidat {clip_id}",
               f"Décision : {what}\n\n{_lines(facts)}\n\nRaison : ", f"clip-{clip_id}")
