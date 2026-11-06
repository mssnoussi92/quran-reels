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

## Mise en œuvre (2026-11-05)

- Code : `src/quran_reels/catalog/` (`reciters.py`, `backgrounds.py`, `schedule.py`, `posts.py`,
  `previews.py`, `issues.py`, `page.py`, gabarit et script dans `site/`). Il appelle les
  fonctions du pipeline (`selector.calendar.preview`, `reciters.choose`,
  `images.select.upcoming`, `sources.backgrounds.choose`) sur des copies de l'état et n'écrit
  que dans son dossier de sortie. Seul ajout ailleurs : la sous-commande dans `cli.py`.
- `quran-reels catalog build --state state-branch --out _site/catalog` → `index.html` (rendu
  côté serveur, lisible sans JavaScript), `data.json`, `catalog.css`, `catalog.js`,
  `previews/`. Options : `--previous` (le `data.json` déployé), `--clip-candidates` (le
  `candidates.json` de `backgrounds-search`), `--manifests`, `--no-previews`, `--days`.
- **Récitateurs** : extrait commun = sourate 112 avec sa basmala, lu depuis la source
  (EveryAyah : `bismillah` ou `001001` puis `112001…112004` ; mp3quran.net et archive.org : le
  fichier de la sourate 112). Candidats : `everyayah.com/data/recitations.js`, une carte par
  récitateur et style (débits regroupés), traductions et lectures Warsh écartées ; un nom
  déjà dans la liste (Ghamadi, Menshawi, Salah Al Budair…) est rattaché à sa carte (« Aussi sur
  EveryAyah ») au lieu d'être proposé.
- **Historique** que la configuration ne garde pas (revendications, écartés après écoute, clips
  refusés et leur raison) : `src/quran_reels/catalog/history.yaml`, complété par l'état
  (`removed`, `claimed`). Une session qui applique un ticket du catalogue y ajoute la ligne.
- **Fonds** : le choix est recalculé avec la règle du rendu (traduction + thèmes) ; un reel
  garde le fond calculé la première fois que le catalogue l'a vu (`--previous`), un manifeste
  trouvé l'emporte ; un reel retiré avant le catalogue n'a pas de fond deviné. Aperçus : 4 s en
  360×640 (recadrés et adoucis comme dans le reel, sans son, ≈ 15–340 Ko) + une image, en
  cache (`.cache/catalog/`) ; Pixabay en rendu `small` via l'API (`PIXABAY_API_KEY` au
  moment de la construction seulement), une requête CDN toutes les 5 s. Scènes générées :
  dessinées en direct dans la page par leur propre shader (WebGL 2).
- **Calendrier** : 14 jours comme `quran-reels calendar --days 14` (récitateur et durée du
  choix d'aujourd'hui, raisons quand aucun n'est prêt), avancement des files et séries, 7
  prochaines images « Word of the day » (le mot et son sens du Muyassar cités tels quels).
- **Publications** : 30 derniers créneaux, liens Facebook/Instagram publics, statut TikTok
  (jamais l'identifiant de la boîte ni un message d'erreur brut), retirés avec la raison.
- Tickets : `issues/new?title=…&body=…&labels=catalog` (le libellé `catalog` doit exister
  dans le dépôt pour être posé).
- Workflow `catalog.yml` : push sur `main` (config/, docs/, catalogue), après chaque run de
  `daily-reel`, `images` et `prepare-splits` (`workflow_run` : la branche `state` ne contient
  pas les workflows), une fois par jour et à la main. Après un `workflow_run`, rien n'est
  construit si `main`, `state` et le jour n'ont pas changé (comparés au `data.json` déployé).
  Le site = copie de `docs/` (servi tel quel, `.nojekyll`) + `catalog/` ; le déploiement
  n'a lieu que si la construction réussit.

## Publier à la demande (2026-11-06)

Exception au « ne publie rien » : la section **Publier** (`#on-demand`) n'écrit toujours rien
elle-même, mais construit un ticket prérempli « À la demande : … » que le workflow
`on-demand` vérifie, prévisualise et publie après la réponse `/publier` du propriétaire
(docs/on-demand.md). Listes construites depuis `config/` à chaque déploiement : récitateurs
autorisés (rotation sans les `claimed`), 114 sourates avec leur nombre d'ayahs, fonds. Les
cartes récitateur et fond ont « Publier à la demande avec … » (`?reciter=…#on-demand`,
`?background=…#on-demand`, le formulaire s'ouvre présélectionné). Les publications à la
demande sont listées dans « Publications » (`catalog/ondemand.py`).

Depuis le 2026-11-06, le formulaire montre aussi, **avant** le ticket, les ayahs choisies (lues
en direct sur Quran.com), un avertissement si la plage coupe une phrase, et les sens du
Muyassar à cocher (`catalog/surahs/SSS.json`, écrits par `ondemand.surah_files` avec le code
et la numérotation de l'aperçu ; extraits publiés sur le site, choix du propriétaire). Les sens
sont téléchargés au plus 15 min par construction (`--meanings-minutes`), Juz' 'Amma d'abord ;
une note du catalogue dit combien de sourates sont prêtes.

