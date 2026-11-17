# Vidéos thématiques sur la Page (publication automatique)

Décidé avec le propriétaire le 2026-11-15 (« je valide ») : les vidéos de quran-themes-demo (films, shorts
d'histoire, épisodes de séries) sortent sur la Page à **19:00, heure de France**, du lundi au samedi, sans geste de sa
part, à partir du **lundi 23 novembre** (le film de Dhul-Qarnayn). Avant, il les publie à la main.

| Plateforme | Ce qui part |
|---|---|
| Facebook | la vidéo (le film en 9:16, ou le short), son texte Facebook validé, sa couverture |
| Instagram | le short, son texte Instagram validé, sa couverture (pas les films : leur texte ne prévoit pas Instagram) |
| TikTok | la version signée `@quran.words.daily`, en **brouillon** dans la boîte : le propriétaire la publie, le texte est sur la page « À publier » (publier.html ; aussi dans le ticket « 📋 Légendes à copier ») |
| YouTube | **à la main** : la page « À publier » donne le MP4 (le short, ou le film 16:9), son titre, sa description et ses hashtags (`themes files` après la publication : `theme/<jour>/reel.json` sur `previews`) |

**Comme les reels** : Facebook et Instagram reçoivent d'abord la vidéo non publiée, Meta vérifie les droits sur les
deux ; si l'une des vérifications n'est pas propre, **rien ne part, TikTok compris**, et le ticket
« ⚠️ Vidéo thématique en échec » le dit.

## D'où vient chaque chose (quran-themes-demo, branche `main`, lue à chaque run)

- **Le jour** : `docs/retention/calendar.md`, section « Le calendrier », telle qu'elle est écrite. Pour chaque ligne :
  - la section vient de la colonne « Texte » (« Short N », « Le film ») ;
  - le texte de publication vient de la colonne « Texte » (`publication-<doc>.md`) ou, à défaut, de la colonne
    « Fichiers » (release `` `<doc>-candidate` ``) ; quand les deux en nomment un, ils doivent être d'accord ;
  - **jamais de la ligne d'avant** : les séries alternent (le 2026-11-15, la ligne du 25 décembre, « لاحظت الفرق؟ » 2,
    aurait pris le texte de « سنريهم آياتنا » écrit au-dessus) ;
  - les plateformes viennent de « Où » (« les quatre » : toutes) ; pour chacune, la vidéo du texte qui la prévoit
    (le film en 9:16 pour Facebook, le film 16:9 pour YouTube) ;
  - une ligne barrée est déjà publiée ; une ligne « à faire » n'a rien à publier.
  - **plusieurs lignes le même jour** (choix du propriétaire, 2026-11-17 : le quiz « معاك 5 ثواني » sur Instagram les
    lundis d'un film, qu'Instagram ne reçoit pas) : chacune sort, dans l'ordre du tableau, au même créneau de 19:00 ;
    elles ne partagent aucune plateforme (une ligne qui nomme une plateforme déjà prise ce jour-là est signalée et ne
    sort pas : une seule vidéo par plateforme et par jour). L'entrée du jour de `themes.json` garde le résultat de
    chaque plateforme ; la deuxième vidéo du jour a sa clé, `theme:<jour>-2` (ticket des légendes, page « À publier »).
- **Les textes** : `docs/retention/publication-<doc>.md`, bloc par plateforme (« **Facebook** », « **Instagram** »,
  « **TikTok** », « **Titre YouTube** »), mot pour mot : rien n'est coupé, ajouté ni réécrit ici.
- **Les fichiers** : la pré-release publique `page-<doc>` (workflow `page-files` de quran-themes-demo, lancé une fois
  les vidéos validées), noms écrits sur la ligne de fichier de chaque section (vidéo, version `-tiktok`,
  couverture `-cover.jpg`).

## Facebook : toujours en reel, même un film

Essais à blanc du 2026-11-15 :
- **en reel** (l'API Reels, `publishers/facebook.py`) : le short de 2:05 et le film de 8:24 sont acceptés, et la
  vérification des droits de Meta répond aussitôt « complete, aucune correspondance » ;
- **en vidéo de Page** (`/{page}/videos`, `publishers/facebook_video.py`) : Meta ne donne aucune vérification en
  10 minutes (« dernier état : aucun ») ; rien n'aurait été publié.

Toute vidéo jusqu'à `reels_max_seconds` (900 s) passe donc en reel. Au-delà, la voie des vidéos de Page reste dans le
code, mais sans vérification elle ne publie rien.

## Instagram : une copie réencodée, qu'il télécharge lui-même

Essais à blanc du 2026-11-15, short de 2:05 :
- envoyé à l'adresse d'envoi d'Instagram (`rupload`, comme les reels quotidiens), le fichier d'origine puis une copie
  réencodée : l'envoi échoue aussitôt (« ProcessingFailedError ») et le conteneur reste « IN_PROGRESS » 20 minutes,
  quatre fois ;
- donné par son adresse publique (`video_url`) : Instagram le télécharge lui-même, conteneur prêt en 2 minutes,
  vérification des droits « complete, aucune correspondance » en 32 s.

Instagram reçoit donc une copie réencodée comme les reels (H.264 High sans B-frames, AAC 48 kHz, faststart, sans
edit list : `for_instagram`, une minute pour 2 minutes de vidéo ; les vidéos de Remotion portent des edit lists,
qu'Instagram refusait déjà sur les reels, docs/rendu.md), mise dans la release publique `reels` (`host`, comme les MP4
des reels, effacée après 30 jours), et le conteneur est fait avec son adresse. Facebook et TikTok reçoivent le fichier
tel quel. Un seul conteneur, attendu jusqu'à `instagram_processing_seconds` (1 200 s).

## Version courte pour Facebook et Instagram (essai, à partir du 24 novembre)

Premières mesures (2026-11-16) : sur Facebook et Instagram, on regarde un short de 2 minutes 4 à 8 secondes. La
session quran-themes-demo coupe donc un short en version courte (60 à 75 s, même voix, un verset ou une explication
en moins), validée par le propriétaire, et l'écrit sur la ligne des fichiers du short, après la couverture : « ·
version courte pour Facebook et Instagram : `qarnayn-short-1-west-cut.mp4`, 1:13 » (fichier public dans
`page-<doc>`).

- Facebook et Instagram reçoivent la version courte (`run.file_for`), avec les **mêmes textes** ; TikTok (sa version
  signée) et YouTube (le MP4 du ticket et de la page « À publier ») gardent le short entier.
- `themes.json` note `cut` pour le jour ; la page « Statistiques » range ces publications sous leur short, avec leur
  durée (« version courte, 73 s »), et les compare à part (« Thème : short, version courte »).
- **L'essai** (choix du propriétaire, 2026-11-16, question à choix) : les trois shorts de Dhul-Qarnayn, 24, 25 et 26
  novembre. Un seul n'aurait rien montré : sous 3 vidéos, la page n'affirme aucune différence. Les coupes des shorts
  2 et 3 sont à faire par quran-themes-demo ; sans elles, ces jours-là publient le short entier.

## Ce qui tourne

| Pièce | Où |
|---|---|
| Réglages | `config/themes.yaml` (`from`, heure, fenêtre, plateformes, `reels_max_seconds`) |
| Code | `src/quran_reels/themepub/` : `texts.py` (les textes), `calendar.py` (le jour → la vidéo), `run.py` (dû, téléchargement, publication, état, rapport) |
| Workflow | `.github/workflows/themes.yml`, groupe `accounts` ; lancé par le planificateur à 18:41 (lundi à samedi) |
| État | `themes.json` sur la branche `state` : une entrée par jour, un résultat par plateforme |
| Alerte | ticket « ⚠️ Vidéo thématique en échec » (`notify --alert themes`), le sien |

```bash
quran-reels themes check --days 14        # les 14 prochains jours : vidéo trouvée ? fichiers publics ?
quran-reels themes run --check            # une vidéo est-elle due maintenant ?
quran-reels themes run --dry-run --day 2026-11-24   # essai à blanc d'un jour : envoi, droits, effacement
```

- Une plateforme déjà faite pour le jour n'est jamais renvoyée ; une qui a échoué avant que rien ne lui parvienne
  est réessayée au run suivant de la fenêtre (19:00 − 20 min à 22:00).
- L'essai à blanc ne publie rien, n'enregistre rien et n'envoie aucun brouillon TikTok (il arriverait dans la boîte).
- `themes check` sert à la revue du dimanche : un jour sans vidéo (« à faire »), une ligne non reliée ou un fichier
  absent de `page-<doc>` y apparaissent avant le jour.

## À savoir

- **Légendes courtes** (choix du propriétaire, 2026-11-15 : « un petit texte attirant, 3 à 5 hashtags ») : Facebook,
  Instagram et TikTok reçoivent le titre, une accroche en égyptien et en anglais (reprise de la description validée),
  « 🎙️ AI-generated voice · صوت مولَّد بالذكاء الاصطناعي » et les hashtags (3 sur Facebook, 5 ailleurs), moins de
  400 caractères ; YouTube garde la description entière (sources et liens, chapitres, crédits). Tant que le texte
  d'un fichier dit « pas encore validé(e)s » (`tools/trial/publish.py` l'écrit tant que le propriétaire n'a pas
  validé les accroches), rien n'en est publié : `themes check` et le run le disent.
- Les statistiques de ces vidéos sont relevées comme les autres (docs/insights.md) ; elles sont reconnues par la
  première ligne de leur légende.
