# Statistiques de la Page

Décidé avec le propriétaire le 2026-11-15 (« je valide tes recommandations »). Il veut un tableau de bord des
statistiques, lisible sur son téléphone, qui sert aussi à décider du calendrier des reels et des vidéos
thématiques (quran-themes-demo, la même Page). **Lecture seule** : rien n'est publié, modifié ni supprimé.

## Ce qui tourne

| Pièce | Où | Quand |
|---|---|---|
| Relevé Facebook et Instagram | `quran-reels insights collect`, workflow `insights.yml` | chaque nuit, à la fin de `prepare-splits` (lancé à 02:41 par le planificateur) |
| Données | `insights.json` sur la branche `state` | écrit par le workflow, jamais à la main |
| Page | `catalog/stats.html` (« Statistiques »), construite par `catalog.yml` | après chaque relevé |
| Calendrier commun | section « Calendrier » du catalogue : les reels, et les vidéos thématiques lues dans `docs/retention/calendar.md` de quran-themes-demo | à chaque construction |
| Captures YouTube et TikTok | `quran-reels insights add`, workflow `insights.yml` avec `manual` | le dimanche, à la revue de la semaine |

**Public** (choix du propriétaire, 2026-11-15) : le dépôt, la branche `state` et le catalogue le sont. On y voit la
portée, l'accroche et la durée regardée de chaque vidéo de la Page ; aucune donnée personnelle (ni pays, ni âge, ni
liste d'abonnés).

## Le relevé

1. Contrôle du jeton (`meta-check`) ; sans `read_insights` ou `instagram_manage_insights`, une note dans le relevé.
2. Abonnés : Facebook (`followers_count`), Instagram (`followers_count`), un relevé par jour (heure de Paris).
3. Publications des 35 derniers jours : `/{page}/video_reels`, `/{page}/videos` (les films en 9:16 publiés à la
   main), les posts du Word of the day (identifiants d'`images.json`), `/{ig-user}/media`.
4. Chaque publication est reconnue (`insights/classify.py`), la même vidéo a la même clé sur les deux plateformes :
   - un créneau de `published.json` (`slot:2026-11-16/morning`, y compris `removed`), une demande (`od:39`) ;
   - un Word of the day d'`images.json` (`word:2026-11-15`) ;
   - une vidéo thématique : la première ligne de sa légende est le titre anglais d'une section de
     `docs/retention/publication-*.md` de quran-themes-demo (`theme:dua/short-1`) ; le film 16:9 (YouTube) et le
     film 9:16 (Facebook) ont le même titre, la plateforme les départage ;
   - le reste : « Autre publication ».
5. Relevés : à **48 h**, **7 jours** et **28 jours**, gardés pour de bon la première nuit après cet âge (jamais
   rattrapés plus de 48 h après : on compare des vidéos au même âge) ; et chaque nuit jusqu'à 8 jours, le « dernier
   relevé ».
6. **Budget d'appels** : l'app Meta a environ 200 appels par heure, partagés avec les publications (le 2026-11-13,
   un run les a tous pris). Le relevé s'arrête dès que Meta annonce 75 % (`X-App-Usage`) ou après 150 appels,
   garde ce qu'il a, et reprend la nuit suivante. Ordinaire : une trentaine d'appels.

Réglages : `config/insights.yaml`.

## Les chiffres

Ceux de la fiche du propriétaire (`docs/retention/calendar.md` de quran-themes-demo, « Les mesures ») :

| Chiffre | Instagram | Facebook |
|---|---|---|
| Vues | `views` | `blue_reels_play_count` (reel), `total_video_views` (vidéo), `post_media_view` (photo) |
| Personnes | `reach` | — (refusé pour les reels, 0 faux pour les photos) |
| **Passent 3 s** (l'accroche) | 100 − `reels_skip_rate` | — (courbe de rétention gardée brute, non lue) |
| **Durée moyenne regardée** et % de la durée | `ig_reels_avg_watch_time` | `post_video_avg_time_watched` |
| Encore là à 0:30 (films) | — | — (même courbe) |
| Partages, enregistrements | `shares`, `saved` | partages (`post_video_social_actions`) |
| Abonnés gagnés | — (seulement pour le compte, par jour) | `post_video_followers` |

**Premier vrai relevé (2026-11-15, 61 publications, 89 appels, aucune erreur)**, et ce qu'il a corrigé :

- La **courbe de rétention de Facebook** a 41 points quelle que soit la durée, et reste à 100 % jusqu'à
  3 s sur des reels regardés 4 à 8 s en moyenne : ni « secondes » ni « 40 intervalles » ne colle. Elle est
  gardée brute (`retention`), plus lue ; les accroches Facebook du premier relevé (81 à 100 %) sont retirées
  (`insights.json` version 2). À reprendre le jour où une courbe est comparée à Meta Business Suite.
- **Portée Facebook** : `post_impressions_unique` refusé pour les reels (code 100), `post_total_media_view_unique`
  à 0 pour des photos vues 7 à 25 fois : pas de portée sur Facebook.
- `/{page}/videos` renvoie aussi ce qui n'est pas public : neuf vidéos à 0 vue (brouillons laissés par des
  essais) et le short 3 de Moussa et al-Khadir, programmé. Elles sont écartées (`published`), et la page ne
  montre que ce que le dernier relevé a trouvé (`listed`, `seen`).
- **Attention en comparant les plateformes** : Facebook et Instagram comptent chaque lecture commencée
  (un défilement compte), YouTube Studio donne la durée moyenne des seules « vues engagées ». Une durée
  moyenne de 8 s sur Facebook et de 1:08 sur YouTube ne disent pas la même chose : on compare une vidéo à une
  autre sur la même plateforme.

- Un chiffre que Meta ne donne pas reste vide (« — »), jamais 0. Meta marque plusieurs de ces chiffres « en
  développement » et Instagram peut avoir 48 h de retard.
- Un nom de chiffre refusé par Meta pour un type de publication (erreur 100) est appris une fois (chaque chiffre
  demandé seul), rangé dans `unsupported` et plus jamais demandé.
- La durée d'une vidéo Instagram (que l'API ne donne pas) est celle de sa jumelle Facebook, ou celle écrite dans
  `publication-*.md`.
- La courbe de rétention brute est gardée (`retention`) : sa lecture (secondes ou 40 intervalles, fraction ou
  pourcentage) se corrige sans relire Meta.

## Le tableau de bord (choix du propriétaire, 2026-11-21)

La page « Statistiques » commence par un tableau de bord, fait d'après la maquette qu'il a validée le 2026-11-21
(« un dashboard complet, bien classé, utile aux autres sessions pour faire des audits et voir ce qui marche et ce qui
ne marche pas, avec des courbes ») : `catalog/dashboard.py` calcule, `catalog/charts.py` dessine (SVG dans la page,
une info-bulle au toucher sur chaque point, couleurs vérifiées sur le fond de la page).

- **Vue d'ensemble** : les abonnés de chaque plateforme et leur courbe.
- **Ce qui marche** : chaque type de vidéo, un point par vidéo à 48 h, la médiane en trait blanc : vues (Facebook,
  Instagram, YouTube), vues engagées de YouTube, part regardée, taux de clics des miniatures (exports de Studio) ;
  sous la courbe, les médianes en chiffres (le tableau d'avant).
- **Audits** : par récitateur, par fond, par durée, par série, par jour de la semaine, version courte contre short
  entier ; puis **avant / après** chaque changement de `trials` (`config/insights.yaml`).
- **YouTube en détail** (`youtube-detail.json`, chaque nuit) : d'où viennent les vues, les pays, la rétention médiane,
  ce qu'on tape pour nous trouver. **Facebook** : sa courbe de rétention, seconde par seconde. **TikTok** : les
  dernières captures.
- **Essais en cours** et **Données manquantes** (`trials`, `missing` de `config/insights.yaml`, avec la date du dernier
  envoi) : une session ajoute un essai le jour où un changement part, et une source le jour où elle en trouve une.
- **Pour les sessions** : `catalog/dataset.json`, une ligne par vidéo et par plateforme avec tout ce qu'on sait d'elle
  et ses chiffres à 48 h, 7 jours, 28 jours et au dernier relevé. Les audits de la revue et des sessions partent de
  ce fichier, avec la règle ci-dessous.

## Comparer sans se tromper

La page compare chaque type de vidéo (reel du matin, du vendredi, série du dimanche, Word of the day, film,
short d'histoire, épisode de série) **à 48 heures**, en médianes, avec le nombre de vidéos. Moins de 3 vidéos ou
moins de 12 points d'écart : ce n'est pas une différence (`compare` de `config/insights.yaml`, d'après
`docs/retention.md` de quran-themes-demo, « Mesurer »). Chaque type a son jour fixe dans la grille : le jour et le
type se confondent, à garder en tête.

## Version courte d'un short (Facebook, Instagram)

Depuis l'essai du 24 novembre 2026 (docs/themes.md), Facebook et Instagram peuvent recevoir la version courte d'un
short de quran-themes-demo. `classify.Classifier` la reconnaît par `themes.json` (`cut` du jour, identifiants des
publications) : même clé que le short (`theme:qarnayn/short-1`), son propre type (`theme-short-cut`, « Thème : short,
version courte ») et sa propre durée. La carte du short garde le type et la durée du short entier.

## YouTube, lu chaque nuit (choix du propriétaire, 2026-11-15)

Plutôt qu'une capture de YouTube Studio chaque dimanche, le workflow `insights` lit la chaîne lui-même, en
**lecture seule** (`insights/youtube.py`, étape « Read YouTube », sans effet tant que les secrets manquent) :

- **YouTube Data API** (`youtube.readonly`) : les vidéos publiques des `days` derniers jours, avec leurs vues, likes
  et commentaires (compteurs en direct) ;
- **YouTube Analytics API** (`yt-analytics.readonly`) : durée moyenne regardée (`avg_watch`), pourcentage regardé
  (`watch_pct`), partages, abonnés gagnés (`follows`), calculés par YouTube avec un ou deux jours de retard ; et les
  mêmes chiffres **jour par jour** (vues, likes, commentaires compris).

Chaque vidéo publique devient une publication comme celles de Facebook et Instagram (`youtube:<id>`, son lien, son
dernier relevé, refait chaque nuit), et les abonnés de la chaîne s'ajoutent à ceux de la Page. **Ses relevés à 48 h,
7 jours et 28 jours sont comptés sur les jours de YouTube Analytics** (2026-11-15, `youtube.window` et `total`) : du
jour de la publication au premier jour à la fin duquel la vidéo a l'âge voulu, en heure du Pacifique (celle de
YouTube) ; pour 48 h, de 49 à 72 heures, comme le relevé de nuit de Meta (48 à 72 h). Ils sont comptés quand le dernier
de ces jours a `youtube.lag_days` jours (2 : YouTube remplit ses jours avec retard), puis recomptés chaque nuit tant
que la vidéo est dans les `days` derniers jours (YouTube affine ses chiffres). Ainsi les vidéos publiées avant la
lecture automatique ont aussi leurs 48 h, et la comparaison « à 48 h » de YouTube porte sur toutes. Les moyennes
(`avg_watch`, `watch_pct`) sont pondérées par les vues de chaque jour. Sans les chiffres par jour (une erreur de
YouTube Analytics), les relevés se prennent comme sur Meta, à l'âge de la vidéo la nuit du relevé (`collect.due`).
Sur YouTube, un Short qui repart en boucle compte encore : son `watch_pct` dépasse souvent 100 %. Elle se range avec son reel ou sa vidéo thématique : la
référence d'un reel dans le titre ou dans la ligne « Surah … (9:51) » de la description collée depuis reel.html, sinon
les noms de son titre (« Surah Al-Masad · سورة المسد » ; une sourate en plusieurs passages : le dernier publié avant) ;
le titre d'une vidéo thématique, le film en 16:9 avec sa version verticale de Facebook ; à défaut, un reel publié à
la main (`hand:93:1-11` : une publication de Meta hors du calendrier dont la légende porte la référence, ses captures
avec elle). Le premier soir (2026-11-15),
les chiffres ont été rangés comme des captures (source `youtube-api`) : ces entrées sont retirées au relevé suivant. Une panne de YouTube ne fait jamais perdre les chiffres de Meta (étape
à part, `continue-on-error`). Ce qu'aucune API ne donne (impressions, taux de clics, « regardées » contre
« balayées » des Shorts) reste dans YouTube Studio. Mise en place : docs/plateformes.md, « Statistiques YouTube ».

**Vues engagées et part de la recherche** (choix du propriétaire, 2026-11-21) : sur YouTube, les « vues » d'un Short
comptent chaque lecture, boucles comprises : un reel de 17 à 30 s qui repart en boucle paraît bien plus fort qu'un
short thématique de 2 minutes. Le relevé de nuit garde donc aussi `engaged` (`engagedViews` d'YouTube Analytics : les
vues qui dépassent les premières secondes ; dans le dernier relevé, par vidéo, et dans les relevés 48 h / 7 j / 28 j
comptés sur les jours) et `search_pct` (100 × les vues venues de la recherche YouTube, `YT_SEARCH`, sur toutes les
vues, une décimale ; une requête par vidéo, de son jour de publication à aujourd'hui, dans le dernier relevé
seulement). Si YouTube refuse la requête à cause d'`engagedViews` (HTTP 400), elle est refaite sans ce chiffre ; une
requête de la recherche refusée ne coûte que son chiffre. La page « Statistiques » les montre (« vues engagées »,
« par la recherche (%) ») ; la comparaison des Shorts YouTube se fait toujours sur les vues, la revue du dimanche
décidera si elle passe aux vues engagées.

**À la demande, le détail** (demande du propriétaire, 2026-11-21 : « vois si tu peux récupérer plus d'info ») :
`insights.yml` lancé avec `youtube_detail` lit seulement YouTube, avec le même jeton en lecture seule
(`insights/youtube_detail.py`) : pour chaque vidéo des 30 derniers jours, d'où viennent ses vues (fil des Shorts,
recherche, vidéos suggérées, accueil…), les pays de ses spectateurs, sa courbe de rétention et, si YouTube les
donne, ses vues « engagées » ; pour la chaîne, ses sources, ses pays, les recherches et les vidéos qui l'amènent.
Le résultat est un artefact du run (`youtube-detail`, 3 jours) qu'une session lit ; rien n'est écrit sur `state`,
et le journal ne montre ni les recherches ni rien d'autre que nos titres et des chiffres.

**Maintenant chaque nuit** (choix du propriétaire, 2026-11-21, pour le tableau de bord de la page « Statistiques ») : le
relevé de nuit (étape « Read YouTube ») lance aussi `quran-reels insights youtube-detail --days 35` et garde le
résultat dans `youtube-detail.json` sur la branche `state` (compact, sans indentation) ; s'il échoue, un avertissement,
le fichier d'avant reste et rien d'autre n'est perdu. Le mode à la demande (artefact) ne change pas.

## Captures TikTok (et ce que l'API YouTube ne donne pas)

TikTok n'a pas d'API pour nous : ses chiffres n'existent que par les captures du propriétaire, envoyées **dans
n'importe quelle session** (sa demande, 2026-11-15), quran-reels, quran-themes-demo ou le planificateur, le dimanche
à la revue ou un autre jour : de préférence la liste « Contenu » de TikTok Studio (toutes les vidéos d'un coup), et
pour une vidéo qui compte, sa page de statistiques. La marche à suivre est le skill **`record-stats`**
(`.claude/skills/record-stats/`, et son renvoi dans quran-themes-demo) : la session reconnaît chaque vidéo, lit les
chiffres sur l'image, les montre au propriétaire et demande, puis lance `insights.yml` sur `main` avec `manual` :

```json
[{"platform": "youtube", "video": "dua/short-1", "published": "2026-11-17", "seen": "2026-11-22",
  "metrics": {"views": 340, "hook": 61, "avg_watch": 41, "watch_pct": 38, "shares": 2, "follows": 1}}]
```

- `video` : l'identifiant d'une vidéo thématique (`<publication>/<short-N|film>`, voir la page), le passage d'un
  reel (`106:1-4`) ou un titre ; une entrée non reconnue est listée à part (« Captures sans vidéo reconnue »).
- `metrics` : `views`, `hook` (% qui passent 3 s ; TikTok : 100 − « taux de saut » s'il est affiché ; YouTube :
  « Ont choisi de regarder » va dans `viewed_pct` depuis le 2026-11-21, une entrée plus ancienne garde `hook`), `avg_watch` (s), `watch_pct`, `kept_30s`, `finished` (% qui ont regardé jusqu'au bout ; TikTok :
  « A regardé la vidéo en entier »), `shares`, `saves`, `comments`, `likes`, `follows`, `reach` (Facebook : une
  exportation de Meta Business Suite, l'API ne le donne pas pour les reels), et trois chiffres des exportations de
  YouTube Studio, que l'API n'a pas : `impressions` (impressions de miniatures), `ctr` (taux de clics sur la miniature,
  en %), `viewed_pct` (Shorts : « Ont choisi de regarder » / « Viewed (vs. swiped away) », en %).
- **Exportation « Contenu » de YouTube Studio** (Analytics → Mode avancé → exporter, un zip de CSV) : le propriétaire
  envoie le zip, `quran-reels insights import-youtube --zip FICHIER.zip --state <branche state> --seen AAAA-MM-JJ`
  (ou `--csv` pour le seul tableau « Informations relatives aux tableaux ») lit une ligne par vidéo, ne garde que
  `impressions`, `ctr` et, si la colonne existe, `viewed_pct`, et imprime **une ligne de JSON** : la liste à donner à
  `insights.yml` (`manual`). `video` y est la clé de la vidéo dans `insights.json` (`slot:…`, `theme:…`) ; un
  identifiant que l'état ne connaît pas est listé sur stderr et laissé de côté ; la ligne « Total » est ignorée.
  En-têtes français ou anglais, virgule décimale comprise.
- La même plateforme, la même vidéo et le même jour de capture remplacent l'entrée d'avant ; avec
  `"remove": true` (sans `metrics`), l'entrée de ce jour est retirée (une capture rangée sous une mauvaise vidéo).
- Aucun chiffre deviné : ce qui n'est pas sur la capture n'est pas écrit.

## Ce que les statistiques ne disent pas encore

- **L'heure et le jour** : à une centaine de vues, presque toutes d'inconnus, et avec un type par jour, aucun
  relevé ne départage deux heures. Instagram ne donne la répartition des abonnés (pays, heures) qu'à partir de
  100 abonnés.
- **TikTok** : seulement les captures (choix du propriétaire, 2026-11-15) ; YouTube est lu chaque nuit depuis le
  2026-11-15 (ci-dessus).

## À regarder à la prochaine revue (2026-11-15)

- **Trois reels presque pas montrés par Instagram**, quand Facebook les a montrés comme les autres : 109:1-6
  (11 nov., Minshawi : 8 vues sur Instagram, 293 sur Facebook), 18:15-16 (13 nov., Minshawi : 2 et 228), 107:1-7
  (14 nov., Fares Abbad : 5 et 298) ; les 11 autres : 124 à 789 vues sur Instagram. Rien ne les distingue dans nos
  données (récitateurs, heures, fonds, publication sans reprise ni erreur), et les captures du propriétaire donnent
  les mêmes chiffres que l'API. « Statut du compte » d'Instagram est au vert pour les recommandations (seule la
  monétisation est en attente : « Présence établie », un compte trop récent). Hypothèse non prouvée : l'audio reconnu
  après la publication. **Un quatrième le 2026-11-16** : 106:1-4 (Tawfiq As-Sayegh : 6 vues sur Instagram en 43 h,
  295 sur Facebook), soit 4 des 7 reels publiés du 11 au 17 novembre, avec trois récitateurs différents. **Réponse
  du propriétaire (2026-11-18, question à choix)** : dans l'app, 106:1-4 et 107:1-7 n'affichent **aucune mention**
  (ni « Audio indisponible » ni « Ce reel est limité »). L'audio reconnu devient moins probable ; la cause reste
  inconnue. À suivre à chaque revue : combien de reels Instagram restent sous 10 vues.
- **Word of the day en pause** depuis le 2026-11-15 (choix du propriétaire : 4 vues en médiane par publication sur
  Instagram, 21 vues en tout sur Facebook en 9 jours) ; ses relevés restent pour comparer s'il revient.

## À la revue du dimanche 22 novembre : l'ordre des langues dans les titres

Décidé avec le propriétaire le 2026-11-21 : « applique cette règle et mets-la disponible pour toutes les sessions, on
s'adapte après la revue si nécessaire ». La règle en place : **YouTube, l'arabe d'abord** (titres et `caption.txt` ;
74 % des vues de la chaîne viennent de pays arabophones, et les recherches qui amènent des vues sont en arabe) ;
**Facebook, Instagram et TikTok, l'anglais d'abord, toujours** (reels : `render.series_line`, `render.surah_line` ;
vidéos thématiques : `publish.py` de quran-themes-demo et son test `tests/test_title_order.py`).

- **Ce qui manque pour en juger** : la langue du public sur Facebook, Instagram et TikTok. Aucune API lue ici ne la
  donne. Instagram ne donne la répartition par pays qu'à partir de 100 abonnés. Il faut donc des captures, si les
  applications les montrent : l'onglet « Audience » de Meta Business Suite (pays, Facebook et Instagram) et l'onglet
  « Spectateurs » de TikTok Studio (pays).
- **Pas d'essai A/B possible** : un même titre ne sort pas dans deux ordres. Le choix se fait sur le public, pas sur
  une comparaison de vues.
- **La question à poser au propriétaire** (choix) : garder l'anglais d'abord sur ces trois plateformes ; passer à
  l'arabe d'abord partout ; ou décider plateforme par plateforme selon la part arabophone. À changer, c'est un seul
  réglage dans chaque dépôt (`arabic_first` de `render.series_line` et `render.surah_line` ; `publish.py` de
  quran-themes-demo et son test).

## À la revue du dimanche 29 novembre : l'essai de la version courte

Décidé avec le propriétaire le 2026-11-17 : « on fait le point dimanche ». Les shorts 1, 2 et 3 de Dhul-Qarnayn sont
partis en version courte sur Facebook et Instagram les 24, 25 et 26 novembre (73, 73 et 79 s, au lieu de 125, 114 et
111 s ; TikTok et YouTube en short entier ; docs/themes.md). Leurs relevés à 48 h sont tous faits la nuit du 28 au 29.

- **Ce qu'on compare** : sur la page, « Thème : short, version courte » (n = 3) contre « Thème : short d'histoire »
  (les shorts entiers des semaines d'avant), Facebook, Instagram et **YouTube** à part. YouTube est dans l'essai depuis
  le 2026-11-18 (choix du propriétaire) : le propriétaire y met la version courte, celle de la page « À publier » ; la
  page la reconnaît à sa durée. Sur YouTube, les shorts entiers d'avant faisaient 279 vues en médiane à leur dernier
  relevé (n = 3, regardés à 47 %), contre 904 pour un reel (n = 18) ; si le propriétaire a mis en ligne le short
  entier, la page le range avec les shorts entiers, et YouTube ne compte pas dans l'essai.
- **Le piège** : un short plus court a mécaniquement un « % regardé » plus haut. On compare surtout les **secondes
  regardées**, « passent 3 s » (Instagram), les vues (la plateforme le montre-t-elle davantage ?), les partages et
  les abonnés. Le pourcentage n'est qu'un indice.
- **La prudence** : 3 vidéos, des sujets différents des shorts d'avant. Sous 12 points d'écart, aucune différence n'est
  affirmée ; un écart net est une piste à confirmer sur d'autres coupes, pas une règle.
- **La question à poser au propriétaire** (choix) : couper le reste du stock pour Facebook et Instagram, refaire
  l'essai sur trois autres shorts, ou en rester au short entier.

## À la revue du dimanche 6 décembre : une Page ou deux

Question du propriétaire (2026-11-18) : créer de nouveaux comptes pour les vidéos thématiques et ne garder que les reels
récités sur Quran Words Daily ? **Sa décision, le même jour (question à choix) : une seule Page pour l'instant, la
décision à cette revue**, avec la règle écrite d'avance.

Les chiffres du 2026-11-18 (vidéos d'au moins 48 h, médianes des vues au dernier relevé) :

| | Reel récité | Short thématique |
|---|---|---|
| YouTube | 904 (n = 18), regardé à 105 %, 8 abonnés pour 1 000 vues | 279 (n = 3), regardé à 47 %, 4 pour 1 000 vues |
| TikTok (capture du 15 nov.) | ≈ 740 (n = 18) | 699 et 732 (n = 2) |
| Facebook | 299 (n = 14) | 176 (n = 3) ; le film du du'a : 20 partages en 32 h (7 pour les 14 reels réunis) |
| Instagram | 142 (n = 14) | 132 (n = 3) ; les films : 9 et 2 vues (plus de film sur Instagram depuis le 2026-11-17) |

Abonnés : YouTube 152 (118 le 15 novembre), Facebook 48, Instagram 15. Depuis l'arrivée des vidéos thématiques
(12 novembre), les reels du matin n'ont pas baissé sur YouTube (996, 1 078, 963, 1 376 vues, contre 702 à 1 309 avant).
Avis de la session : l'écart n'existe que sur YouTube, et sa cause probable est la durée (un reel de 20 à 60 s est
revu en boucle, un short de 2 min ne l'est pas), pas le mélange ; une nouvelle chaîne aurait le même problème en
partant de zéro, pour un prix élevé (quatre comptes, connexions et secrets, publication automatique à refaire,
mises en ligne à la main doublées).

**La règle** : une deuxième chaîne **YouTube seulement** (Facebook, Instagram et TikTok restent ensemble) si l'une de
ces trois choses est vraie :

1. sur YouTube, les vidéos thématiques (shorts entiers et version courte de l'essai du 24 novembre) restent **sous le
   tiers des vues d'un reel** (médianes, au moins 3 vidéos de chaque) ;
2. les **reels baissent sur YouTube** les jours qui suivent une vidéo thématique (comparer les reels du matin à ceux
   d'avant le 12 novembre) ;
3. le **public YouTube des reels ne parle pas arabe** : YouTube Studio → Audience → « Principaux pays » (capture
   demandée au propriétaire le 2026-11-18 ; la narration en égyptien ne se comprend pas hors du monde arabe).

Sinon : une seule Page, et la question ne revient que si les chiffres changent. La séparation de tout (quatre comptes)
n'est pas proposée : sur Instagram et TikTok un short thématique fait autant qu'un reel.

## Essai d'une deuxième page Meta : « معاك 5 ثواني » (quiz 4 à 6)

Décidé avec le propriétaire le 2026-11-18 (questions à choix), après la question « une Page ou deux » ci-dessus : son
doute porte surtout sur Meta. Avis de la session, donné avant : sur Instagram un short thématique fait déjà autant qu'un
reel (132 vues contre 142), le point faible de Meta est le même partout (72 % partent avant 3 s) ; mieux valait
attendre l'essai de la version courte ; jamais les mêmes vidéos sur deux pages (Meta réduit la diffusion de ce qu'il
voit comme des copies). **Son choix : l'essai propre, avec les quiz en réserve.**

- **La page test** : Facebook et Instagram (Créateur), nommée « معاك 5 ثواني · You Have 5 Seconds » (son choix), faite
  par le propriétaire ; **publiée à la main**, sans l'app Meta ni les secrets de quran-reels.
- **Ce qu'elle publie** : les quiz 4, 5 et 6 de quran-themes-demo (`dabba` 0:58, `sabr` 0:58, `hudhud` 1:01), qui ne
  sortent nulle part ailleurs ; ses textes validés (`publication-quiz.md`, « Short 4 » à « Short 6 », légende courte
  d'Instagram et de Facebook). **Rendus de nouveau, signés du nom de la page test** (son choix : signés
  `@quran_words_daily`, ils ressembleraient à une vidéo reprise et la page test partirait désavantagée) ; le @ exact
  est attendu du propriétaire, le rendu se fait dans quran-themes-demo (`handles` de content/publish.yaml).
- **Le calendrier** : chaque quiz de la page test le même jour, à la même heure (19:00, Paris) que son pendant sur
  Instagram de la page principale : quiz 4 et quiz 1 le lundi 23 novembre, quiz 5 et quiz 2 le 30 novembre, quiz 6 et
  quiz 3 le 28 décembre.
- **Ce qu'on compare** : Instagram, à 48 h, vues, « passent 3 s » (100 − taux de saut) et durée moyenne regardée, la
  page test contre la page principale, paire par paire. Les chiffres de la page principale sont relevés seuls chaque
  nuit ; ceux de la page test viennent des **captures du propriétaire** (statistiques de chaque reel dans l'app
  Instagram, à 48 h), rangés dans le tableau ci-dessous, **jamais dans `insights.json`** (la page « Statistiques » ne
  montre que la Page principale). Facebook de la page test : noté s'il est publié, comparé aux shorts thématiques de la
  page principale seulement à titre d'indice.
- **La prudence** : trois paires, des épisodes différents, et un compte neuf, souvent moins montré au début. Sous 12
  points d'écart, ou si la page test fait moins bien, rien n'est affirmé. Premier regard à la revue du 6 décembre (deux
  paires), conclusion vers le 30 décembre.
- **La question à poser au propriétaire** (choix) après la troisième paire : garder une seule Page, ou donner une page
  à part aux vidéos thématiques sur Meta.

**Changé le 2026-11-18 au soir (choix du propriétaire, questions à choix)** : il a publié le quiz 4 **dès le 18
novembre**, et la page test publie désormais **un quiz par jour** : le quiz 5 le 19, le 6 le 20, puis un lot de 7 quiz
nouveaux, du 21 au 27 novembre (série `ma3ak` de quran-themes-demo, signée `@ma3ak.5.thawani`, jamais sur la Page ;
`docs/scripts/quiz.md`), sans numéro d'épisode. Ce que ça change :

- **Le 23 novembre ne fait qu'une paire** : le quiz 1 de la Page (Instagram) contre le quiz 9 de la page test (`dhahib`),
  publiés à la même heure. Une paire seule ne dit rien.
- **La vraie lecture** : quand la page test a une semaine de quiz quotidiens (vers le 27 novembre), sa médiane Instagram
  à 48 h contre celle de la Page : ses quiz (1 le 23, 2 le 30) et ses shorts thématiques. Même seuil : sous 3 vidéos ou
  12 points d'écart, aucune différence n'est affirmée.
- **Le biais à garder en tête** : la page test publie chaque jour un quiz, la Page un reel le matin et une vidéo
  thématique le soir ; l'âge des comptes diffère d'un mois.
- Les quiz 2 et 3 de la Page (30 novembre, 28 décembre) restent comparés à ceux de la page test du même jour.

| Quiz | Publié le | Page | Vues à 48 h | Passent 3 s | Durée moyenne regardée |
|---|---|---|---|---|---|
| 4 `dabba` | 18 nov. | test | | | |
| 5 `sabr` | 19 nov. | test | | | |
| 6 `hudhud` | 20 nov. | test | | | |
| 7 `qitr` | 21 nov. | test | | | |
| 8 `marah` | 22 nov. | test | | | |
| 1 `sayyara` | 23 nov. | principale | | | |
| 9 `dhahib` | 23 nov. | test | | | |
| 10 `abb` | 24 nov. | test | | | |
| 11 `khashi` | 25 nov. | test | | | |
| 12 `faqir` | 26 nov. | test | | | |
| 13 `yamm` | 27 nov. | test | | | |
| 2 `khatima` | 30 nov. | principale | | | |
| 3 `qalaha` | 28 déc. | principale | | | |

**Changé le 2026-11-19 (demande du propriétaire)** : la page test est **publiée par quran-reels, chaque jour à 18 h**
(Paris), à partir du quiz 5 le 19 novembre, et **relevée seule chaque nuit** avec son jeton (`META_PAGE_TOKEN_5`). Ce que
ça change :

- **Publication** : le workflow `themes` avec `page: ma3ak` (`config/themes-ma3ak.yaml`, le calendrier
  `docs/retention/calendar-ma3ak.md` de quran-themes-demo, l'état `themes-ma3ak.json`, son ticket d'échec « ⚠️ Page test
  « معاك 5 ثواني » en échec »), Facebook et Instagram après la vérification des droits de Meta, comme sur la Page ; lancé
  par la session planificateur à 17:42, après le run de la Page. Le stock finit le 27 novembre (quiz 13).
- **Chiffres** : le workflow `insights` lit la page test avant la Page (elles partagent le budget d'appels de l'app
  Meta) et range ses chiffres dans **`insights-ma3ak.json`** (branche `state`), jamais dans `insights.json` : la page
  « Statistiques » ne montre toujours que la Page. Les relevés à 48 h, 7 et 28 jours sont les mêmes. Le tableau
  ci-dessus se remplit depuis ce fichier ; plus besoin de captures, sauf pour le quiz 4 (publié le 18, avant le jeton :
  relevé lui aussi s'il a moins de 35 jours).
- **L'heure** : 18 h sur les deux pages (la Page passe aussi à 18 h le même jour, à la demande du propriétaire) ; la
  Page sort d'abord, la page test 5 à 30 min après (les runs passent l'un après l'autre).
