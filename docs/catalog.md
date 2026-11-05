# Catalogue (aide à la décision du propriétaire)

Décidé le 2026-11-05. Une page web publique, lisible sur téléphone (Galaxy Z Fold), qui montre
ce que le pipeline utilise et ce qu'il a produit, pour décider d'**ajouter ou retirer un
récitateur**, **garder ou écarter un fond**, et suivre le calendrier. Le catalogue **ne publie
rien** et **ne modifie rien** : il lit la configuration et l'état.

## Contraintes

- **Indépendant du publisher** : code à part (`src/quran_reels/catalog/` ou `tools/catalog/`),
  aucune modification des modules de publication, de rendu ou du calendrier, ni de `config/`.
  Lecture seule : `config/*.yaml`, `config/series/*.yaml`, `published.json` de la branche
  `state`, le cache des fonds (`.cache/`) s'il est restauré.
- **Aucun secret côté navigateur**, aucune donnée privée : la page est publique (le dépôt l'est).
  Aucun identifiant de jeton, aucun log brut.
- **Droits des médias** :
  - récitations : **lien vers la source** (lecture des MP3 d'EveryAyah depuis leur URL), jamais
    rehébergées sur le site ;
  - fonds Pexels/Pixabay : seulement un **aperçu léger** (quelques secondes en 360p, ou une
    planche d'images) avec auteur, licence et lien vers la page d'origine ;
  - scènes générées (les nôtres) : aperçu libre.

## Pages

1. **Récitateurs** : pour chacun, nom, producteur (ex. Complexe du Roi Fahd), statut
   (dans la rotation / retiré / candidat), note de droits de `project.yaml` (`rights`), historique
   des revendications connues (ex. retraits du 2026-11-05), nombre de vidéos publiées avec lui.
   **Même extrait pour tous** (une courte sourate, ex. 112 ou 1) pour comparer les voix.
   Section **Candidats** : récitations disponibles sur EveryAyah pas encore dans la liste.
2. **Fonds** : aperçu, `tags` (thèmes), source, auteur, licence, `note`, nombre d'utilisations
   et thème qui l'a choisi (manifestes). Les clips refusés restent listés avec la raison.
3. **Calendrier et séries** : les 14 prochains jours (même logique que
   `quran-reels calendar --days 14`), avancement de chaque série et file, prochaines images
   « Word of the day ».
4. **Publications** : derniers créneaux de `published.json`, liens Facebook/Instagram, statut
   TikTok, récitateur, fond, éléments retirés (`removed`).

## Agir depuis le téléphone

Chaque carte a des boutons qui ouvrent un **ticket GitHub prérempli**
(`https://github.com/mssnoussi92/quran-reels/issues/new?title=…&body=…&labels=catalog`) :
« Retirer ce fond », « Ajouter ce récitateur à la rotation », « Retirer ce récitateur »,
« Approuver / refuser ce clip candidat ». Le propriétaire valide le ticket ; une session de code
applique la modification en PR. Aucune écriture directe depuis la page.

## Construction et déploiement

- Commande `quran-reels catalog build` (ou script dédié) → dossier statique (HTML + `data.json`
  + aperçus).
- Workflow `catalog.yml` : après chaque push sur `main` qui touche `config/`, après chaque mise
  à jour de la branche `state`, une fois par jour, et à la demande. Il construit le catalogue
  (avec le réseau des runners) et déploie GitHub Pages **avec `docs/` + le catalogue**.
- GitHub Pages passe de « branche main /docs » à **« GitHub Actions »** (réglage à changer par
  le propriétaire au moment du premier déploiement). Tout `docs/` doit rester servi à la même
  adresse : CGU, confidentialité, pages TikTok et le fichier de vérification
  `tiktokL9p6iJLUFgCxLFBybxAfUuWqfqnLTuOp.txt`. Un échec de construction ne doit pas casser le
  site (ne pas déployer si la construction échoue).
- Adresse : `https://mssnoussi92.github.io/quran-reels/catalog/`.
