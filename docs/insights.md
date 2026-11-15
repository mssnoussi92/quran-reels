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

## Comparer sans se tromper

La page compare chaque type de vidéo (reel du matin, du vendredi, série du dimanche, Word of the day, film,
short d'histoire, épisode de série) **à 48 heures**, en médianes, avec le nombre de vidéos. Moins de 3 vidéos ou
moins de 12 points d'écart : ce n'est pas une différence (`compare` de `config/insights.yaml`, d'après
`docs/retention.md` de quran-themes-demo, « Mesurer »). Chaque type a son jour fixe dans la grille : le jour et le
type se confondent, à garder en tête.

## Captures YouTube et TikTok

Le propriétaire envoie les captures **une fois par semaine** (le dimanche), de préférence la liste « Contenu » de
YouTube Studio et de TikTok (toutes les vidéos d'un coup), et pour une vidéo qui compte, sa page de statistiques
(rétention, « regardées » contre « balayées »). La session lit les chiffres sur l'image, les montre au
propriétaire, puis lance `insights.yml` sur `main` avec `manual` :

```json
[{"platform": "youtube", "video": "dua/short-1", "published": "2026-11-17", "seen": "2026-11-22",
  "metrics": {"views": 340, "hook": 61, "avg_watch": 41, "watch_pct": 38, "shares": 2, "follows": 1}}]
```

- `video` : l'identifiant d'une vidéo thématique (`<publication>/<short-N|film>`, voir la page), le passage d'un
  reel (`106:1-4`) ou un titre ; une entrée non reconnue est listée à part (« Captures sans vidéo reconnue »).
- `metrics` : `views`, `hook` (% qui passent 3 s ; YouTube : « regardées » ; TikTok : 100 − « taux de saut » s'il
  est affiché), `avg_watch` (s), `watch_pct`, `kept_30s`, `shares`, `saves`, `comments`, `likes`, `follows`.
- La même plateforme, la même vidéo et le même jour de capture remplacent l'entrée d'avant.
- Aucun chiffre deviné : ce qui n'est pas sur la capture n'est pas écrit.

## Ce que les statistiques ne disent pas encore

- **L'heure et le jour** : à une centaine de vues, presque toutes d'inconnus, et avec un type par jour, aucun
  relevé ne départage deux heures. Instagram ne donne la répartition des abonnés (pays, heures) qu'à partir de
  100 abonnés.
- **TikTok et YouTube** : seulement les captures (choix du propriétaire, 2026-11-15).
