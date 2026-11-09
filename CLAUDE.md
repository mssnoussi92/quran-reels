# Quran Words Daily — contexte projet

Pipeline open source qui produit chaque jour un reel vertical (1080×1920) d'un passage du Coran
et le publie sur Facebook, Instagram, TikTok et YouTube Shorts.

Comptes : Facebook `quranwordsdaily` · Instagram / YouTube `quran_words_daily` · TikTok
`quran.words.daily` (renommé le 2026-11-09, avant `quran_words_daily6` ; `@quran_words_daily` y
est le compte vide de quelqu'un d'autre, à signaler, docs/profils.md) ·
e-mail du projet `quranwordsdaily@gmail.com`. Le propriétaire travaille depuis son téléphone
(pas de PC) : tout doit tourner dans le cloud (session Claude, GitHub Actions).

**Le contredire, toujours** (demande du propriétaire, 2026-11-08) : quand une de ses idées ou de ses
décisions, ou une des tiennes, est fausse ou plus faible qu'une autre (source, récitateur, fond, série,
choix technique), dis-le franchement, avec la raison et ce que tu ferais à la place. Il tranche ; ne suis
jamais en silence, ne passe jamais outre en silence.

## Décisions validées

| Sujet | Choix |
|---|---|
| Format | **≈ 1 minute** (cible 60 s, 40–90 s), jamais coupé au milieu d'une phrase ; **sourate courte entière** (≤ 90 s, même très courte) |
| Basmala | **Au début de chaque vidéo**, même pour quelques versets ; sauf sourate 9 et avant 1:1 (qui est la basmala) |
| Rythme | **2 vidéos par jour**, heure de Paris : **07:30** lecture dans l'ordre, **19:30** séries thématiques |
| Images | **Word of the day**, carrousel de 3 images 1080×1350 (le mot, son ayah, son sens dans le Tafsir al-Muyassar), **1 par jour** à 11:30 UTC sur Instagram et Facebook ; **Ayah of the day** préparé, désactivé (docs/images.md) |
| Lecture | **Juz' 'Amma d'abord** (114 → 78), puis Al-Fatiha et 2 → 77, passages de `config/plan.yaml` |
| Thèmes | Ayat al-Kursi, les 7 versets « المنجيات », versets de du'a, versets du rizq, puis (proposés le 2026-11-06) la patience (ص ب ر) et le repentir (ت و ب)… : listes **proposées par l'IA en PR, validées par le propriétaire** |
| Vendredi | **Al-Kahf sur les deux créneaux** (choix du propriétaire, 2026-11-05) : le matin, **les 10 premières ayahs (18:1-10) en une seule vidéo, chaque vendredi** ; le soir, la suite **à partir de 18:11**, un passage par vendredi (36), puis on recommence |
| Texte arabe | Uthmani (Hafs), police **Amiri Quran** (OFL) |
| Traduction | **Sahih International** (anglais), créditée dans chaque légende |
| Mots difficiles | **غريب التفسير الميسر** (Tafsir al-Muyassar, Complexe du Roi Fahd ; `almuyassar-ghareeb` sur tafsir.app), choix du propriétaire le 2026-11-05 (avant : Ibn Qutaybah, *Tafsir Gharib al-Qur'an*), sens en arabe, **1 à 3 mots liés** surlignés |
| Récitateurs | **Choisis par passage** (`content.rotation`, `reciters.py`) parmi ceux du propriétaire (2026-11-05) : **Omar Hisham Al-Arabi, Muhammad Siddiq Al-Minshawi, Tawfiq As-Sayegh, Salah Budair, Fares Abbad** (EveryAyah, ajouté depuis le catalogue, ticket #19, directement dans la rotation sans essai sur Facebook seul : choix du propriétaire) : prêt pour le passage (découpe vérifiée), ≤ 90 s, pas un des 2 derniers publiés, puis le plus proche de 60 s (passage long → récitateur rapide, sourate courte → plus lent). Écartés : Alafasy, **Nabil Ar-Rifai** (Rights Manager : 2:255 rendue muette par Facebook dans 24 territoires, 2026-11-05) et **Saad Al-Ghamdi** (2:255 revendiquée par UMG, muette en Russie, le même soir), Hudhaifi, Ayyub, Akhdar (après écoute) ; un récitateur revendiqué après publication est écarté automatiquement (`claimed`) ; **en essai** : Husary (ticket #32, EveryAyah, Facebook seul d'abord) ; **YouTube** : Budair écarté (Content ID, 2026-11-06), version YouTube par un autre récitateur |
| Droits | **Vérification Meta avant chaque publication** : brouillon Facebook + conteneur Instagram, publiés seulement si Meta répond `complete` sans correspondance, sinon rien n'est publié (TikTok compris). Elle n'a vu ni Alafasy, ni Ar-Rifai, ni Al-Ghamdi (revendications arrivées quelques minutes après la publication). Contrôle après publication prêt (`rights_after_timeout` > 0 : relu 5 min puis à chaque run pendant 2 jours ; muet ou bloqué → retiré de Facebook et Instagram + alerte, récitateur écarté) mais **désactivé : le propriétaire vérifie lui-même pour l'instant** (2026-11-05) ; nouveaux récitateurs testés sur Facebook seul, Instagram ensuite |
| Fond | **choisi selon ce que dit le passage** (montagnes, mer, rivières, jardins, nuit, aube, ciel…) : vidéos Pexels choisies par le propriétaire et scènes générées (aube, nuit, mer), **sans personnes ni animaux** ; scènes **animées** au rythme d'un ciel filmé (nuages, brume, vagues, lumière) avec un **zoom lent** sur toute la vidéo, le texte immobile (Facebook : « image statique » sur 6:17, 2026-11-09) |
| Exécution | GitHub Actions (dépôt public → gratuit), migrable sur le homelab (Docker) |
| À la demande | Reel choisi depuis le téléphone (récitateur, sourate entière ou ayahs X à Y, fond, plateformes, **mots expliqués** cochés dans le formulaire **avant le ticket**, sous les ayahs affichées, ou `/mots 1 4` après l'aperçu, parmi les sens numérotés du Muyassar, jamais écrits ; extraits du Muyassar publiés sur le site pour le formulaire, choix du 2026-11-06) : catalogue → ticket prérempli → **aperçu** en commentaire → publié seulement après **`/publier`** du propriétaire ; **en plus** des 2 créneaux ; le calendrier **ne saute pas** un passage publié à la demande ; YouTube refusé pour un récitateur revendiqué par Content ID (choix du 2026-11-06, docs/on-demand.md) |
| Périmètre | **Pas seulement des versets récités** : la page publiera aussi des thèmes et des sujets variés (épisodes de quran-themes-demo : thèmes, histoires…), choix du propriétaire le 2026-11-09 ; bios, images et site disent ce qui ne change pas (le Coran et la Sunna au quotidien, toujours sourcés), pas la liste du moment (docs/profils.md) |
| Titres | **Toujours en arabe et en anglais** (choix du propriétaire, 2026-11-09) : noms des comptes, série et sourate en tête des légendes (`render.series_line` : « Supplications from the Quran · آيات الدعاء · 3/38 »), titres YouTube (raccourcis par parties entières, jamais une seule langue), Word of the day, playlists, images ; le texte des ayahs reste hors de la légende Facebook |
| Comptes pro | Page Facebook + Instagram en type **Créateur**, reliés |
| Signature | **@quran_words_daily** sur chaque image, dans la zone sûre (repartages) ; **TikTok : `@quran.words.daily`** (choix du propriétaire, 2026-11-09 : `@quran_words_daily` y est à quelqu'un d'autre) : sa propre version de chaque reel (`platforms.tiktok.signature`, `render.signatures` : calque fixe redessiné, `out/<passage>/tiktok.mp4`) et la même signature à la fin de sa légende (`Reel.for_platform`) |
| Hashtags | Fin de légende, dans l'ordre : `#QuranWordsDaily`, `#Quran`, 1er tag de la série, sourate (`#SurahAdDuhaa` `#سورة_الضحى`), `#القرآن_الكريم`, autres tags de la série, récitateur, gloses (`#تفسير_القرآن`) ; **Instagram et TikTok : les 5 premiers** (leur limite), Facebook 8, `caption.txt` tous (YouTube à la main). **Facebook : légende courte, ≤ 400 caractères hashtags compris** (sa liste de qualité, 2026-11-09) : série et référence (titres en arabe et en anglais), crédits sur une ligne, signature, hashtags ; ni le texte arabe des ayahs ni la traduction (dans la vidéo ; choix du propriétaire) ; trop longue → des hashtags de la fin |

## Règles de contenu (non négociables)

1. **Aucun texte coranique, traduction ou explication n'est généré par une IA.** Tout vient de
   sources publiées, référencées par identifiant d'édition, et se vérifie.
2. Chaque vidéo crédite le récitateur, la traduction et la source des gloses, et porte la
   signature de la page (`video.handle`).
3. L'IA intervient seulement en amont (préparer le calendrier des passages et les séries) et,
   plus tard en option, pour les légendes. Le pipeline quotidien reste **déterministe**.
4. On ne coupe jamais un passage au milieu d'une phrase. Découpage candidat : regroupements
   d'ayahs des tafsirs (Ibn Kathir / Muyassar), sous contrainte de durée.
5. Les jeux de données tiers (traduction complète, tafsir) **ne sont pas commités** : un script
   d'ingestion les télécharge dans un cache (`.cache/`, Actions cache). Le dépôt reste publiable.
6. **Rien n'est publié sans la vérification des droits de Meta** (`publishers/rights.py`) : une
   récitation reconnue par Rights Manager fait couper ou rendre muet le reel (93:1-11 sur
   Facebook, 2026-11-05, Alafasy ; 2:255, Ar-Rifai, muette dans 24 territoires). Le propriétaire
   vérifie chaque nouveau récitateur sur Facebook avant Instagram ; un contrôle automatique après
   publication existe (`rights_after_timeout`, désactivé pour l'instant).

## Architecture

```
config/            project.yaml (choix éditoriaux), backgrounds.yaml (fonds et thèmes),
                   images.yaml (formats image, heure UTC), exclude.yaml (ayahs jamais en image),
                   image-candidates.yaml (candidats image figés : `quran-reels images build`),
                   glosses.yaml (choix éditoriaux : 1 à 3 mots surlignés par sens),
                   schedule.yaml (créneaux, files, vendredi), series/*.yaml (séries),
                   plan.yaml (tout le Coran découpé, figé : `quran-reels plan --write`)
src/quran_reels/
  models.py        AyahRef, Ayah, GlossEntry, WordGloss, Passage, Reel, PublishResult
  config.py        chargement de config/, chemins (.cache/, out/)
  arabic.py        normalisation uthmani/imla'i, ancrage d'une glose sur un mot de l'ayah
  ingest.py        `quran-reels ingest` : jeux de données → .cache/
  passage.py       assemble un passage : texte + traduction + gloses ancrées + audio
  sources/         quran_com (texte, sourates, traduction), tafsir_app (gloses),
                   everyayah (audio), backgrounds (choix du fond par thème, clips en boucle),
                   scenes/ (scènes générées : shaders GLSL dessinés dans Chromium), http
  selector/        plan.py : découpe d'une sourate en passages d'≈ 1 min ;
                   calendar.py : créneaux, files de séries, vendredi, état, vérification des séries
  render/          frames.py (template HTML → PNG, Chromium/Playwright), screens.py (longue
                   ayah sur plusieurs écrans),
                   video.py (minutage audio + ffmpeg → MP4), __init__ (orchestration)
  publishers/      un adaptateur par plateforme, interface commune `Publisher` (dry_run) :
                   meta.py (client Graph, contrôle du jeton), facebook.py, instagram.py
                   (prepare → rights → commit), rights.py (vérification des droits Meta),
                   tiktok.py (brouillon dans la boîte TikTok, connexion OAuth)
  publish.py       `quran-reels publish|meta-check|tiktok-auth` : contrôle, publication, résumé
  gh_secrets.py    réécrit un secret Actions (refresh token TikTok) via gh + GH_SECRETS_TOKEN
  daily.py         `quran-reels daily` : créneaux dus maintenant → rendu → publication → état
  images/          publications image (docs/images.md) : candidates.py (règles 1-4, liste
                   figée), select.py (exclusions, ordre stable, état), cards.py + templates/
                   (1080×1350), caption.py, publish.py (carrousel Instagram, post Facebook
                   multi-photos), daily.py (`quran-reels images run`)
  notify.py        `quran-reels notify` : tickets GitHub (alerte d'échec, légendes à copier)
  ondemand/        publication à la demande (docs/on-demand.md) : request.py (ticket), check.py
                   (mêmes règles que le calendrier, plages valides proposées), commands.py
                   (propriétaire seulement, approbation), flow.py (`quran-reels on-demand
                   route|check|preview|publish|youtube|words|daily-files`), words.py (sens du
                   Muyassar numérotés, choix `/mots` vérifié → `passage.build(glosses=…)`),
                   media.py (aperçu 540p, images clés), files.py (release `reels`, branche
                   `previews`), state.py
  catalog/         `quran-reels catalog build` : catalogue public en lecture seule (+ formulaire
                   « Publier » : ondemand.py écrit surahs/SSS.json, fins de phrase et sens du
                   Muyassar numérotés, téléchargés 15 min max par construction)
                   (docs/catalog.md) : récitateurs (+ candidats EveryAyah), fonds (aperçus
                   360p), calendrier et séries, publications ; décisions par tickets préremplis ;
                   history.yaml (revendications, clips refusés) ; ne modifie rien
  cli.py           `quran-reels ingest|render|passages|plan|series-check|calendar|daily|publish|catalog`
tests/             pytest, sans réseau
.github/workflows/ daily.yml (cron 2 créneaux × 3 essais ; ne publie rien tant que
                   schedule.yaml dit enabled: false ; état sur la branche `state`),
                   publish-test.yml (manuel : dry-run, ou publication réelle avec PUBLIER),
                   tiktok-auth.yml (manuel : échange du code TikTok → TIKTOK_REFRESH_TOKEN)
                   prepare.yml (chaque nuit : découpes vérifiées de la semaine → `state`)
                   tests.yml (pytest + ruff à chaque PR et sur main, ffmpeg statique)
                   images.yml (toutes les heures ; `images run --check` décide selon
                   config/images.yaml ; état images.json sur la branche `state`)
                   catalog.yml (push main config/docs, après daily/images/prepare, chaque jour,
                   à la main : docs/ + catalog/ → GitHub Pages, source « GitHub Actions »)
                   on-demand.yml (tickets « À la demande » et commentaires `/publier`,
                   `/essai`, `/apercu`, `/mots`, `/youtube` **du propriétaire seulement** ; aperçu hors
                   groupe `accounts`, publication dans `accounts`)
                   Runners épinglés sur `ubuntu-24.04` (`ubuntu-latest` passe à 26.04),
                   actions en versions Node.js 24. **Pas d'apt** : le miroir Ubuntu a mis
                   40 min à installer ffmpeg (run du soir du 2026-11-05, bloqué) ; ffmpeg =
                   build statique d'imageio-ffmpeg (pip, épinglé 0.8.1 : ffmpeg 9.0.2,
                   libx264, aac ; les tests passent avec), sans ffprobe (durées lues par
                   ffmpeg) ; Chromium de Playwright, `--with-deps` seulement s'il ne démarre pas.
docs/              site GitHub Pages (CGU, confidentialité, tiktok-login.html, tiktok-callback.html,
                   reel.html : aperçu d'un reel et textes YouTube à copier),
                   déployé par catalog.yml avec le catalogue (/quran-reels/catalog/) ;
                   notes : sources.md, calendrier.md, rendu.md, images.md, plateformes.md,
                   catalog.md, on-demand.md, profils.md (bio, images, playlists des 4 comptes)
assets/brand/      photo de profil, couverture Facebook, bannière et filigrane YouTube, refaits
                   par src/render.py (src/brand.html) ; icon-1024.jpg : icône de l'app Meta
.claude/skills/    procédures pour les sessions Claude (voir « Skills »)
```

Flux : `selector` → `sources` (texte + traduction + gloses + audio par ayah + fond) →
`render` (une image par ayah, durée = durée du MP3 de l'ayah) → MP4 → `publishers` → `state`.

Commandes :

```bash
quran-reels ingest                  # texte, traduction, sourates, index des gloses (4 requêtes)
quran-reels ingest --all-glosses    # + tous les sens du Muyassar (≈ 5 070 requêtes, reprise)
quran-reels passages 2              # découpe la sourate 2 en passages d'≈ 1 min
quran-reels render 93               # sourate courte entière → out/093_001-011.mp4
quran-reels render 2:1-5            # un passage → out/002_001-005.mp4 (complète le cache)
```

`render 78` sur une sourate trop longue pour une vidéo ne rend rien et liste ses passages.

```bash
quran-reels plan --write            # tout le Coran → config/plan.yaml (1 887 passages)
quran-reels series-check            # séries : phrases entières, ≤ 90 s
quran-reels calendar --days 14      # ce que les 14 prochains jours publieraient
quran-reels daily --check           # un créneau est-il dû maintenant ? (rien n'est publié)
quran-reels daily                   # publie les créneaux dus, écrit state/published.json
quran-reels notify --outcome failure --run-url …   # tickets GitHub (workflow daily)
```

```bash
quran-reels images build            # règles 1-4 → config/image-candidates.yaml (≈ 20 min)
quran-reels images next --days 7    # la semaine à venir (rien n'est publié)
quran-reels images render --days 7  # la dessine dans out/images/ (aperçu)
quran-reels images run              # publie le format dû, écrit state/images.json
```

```bash
quran-reels catalog build --state state-branch --out _site/catalog   # catalogue (lecture seule)
```

```bash
quran-reels on-demand check --issue 42       # une demande : règles, refus motivé, découpe ?
quran-reels on-demand preview --issue 42     # rendu + aperçu commenté (workflow on-demand)
quran-reels on-demand daily-files            # MP4 du calendrier en téléchargement direct
```

```bash
quran-reels meta-check              # jeton de Page : valide, permissions, accès aux données
quran-reels publish 93 --dry-run    # rendu + brouillon Facebook + conteneur Instagram
quran-reels publish out/093_001-011.mp4 --platform facebook   # publication réelle
```

```bash
quran-reels publish 93 --platform tiktok      # brouillon dans la boîte TikTok
quran-reels tiktok-auth --code …              # connexion (en pratique : workflow tiktok-auth)
```

Secrets lus dans l'environnement (`META_PAGE_ID`, `META_PAGE_TOKEN`, `IG_USER_ID`,
`TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN`, `GH_SECRETS_TOKEN`).

`out/093_001-003/` contient aussi les calques PNG, des aperçus (`preview/`), la légende
(`caption.txt`) et `manifest.json` : chaque texte affiché avec son édition, sa source et son
minutage. Le cache se remplit à la demande : `render` télécharge ce qui manque.

## Sources de données (détails : docs/sources.md)

- Texte uthmani, sourates, Sahih International : API Quran.com v4 (une requête par ressource).
  Sens des mots : `almuyassar-ghareeb` (غريب التفسير الميسر, tafsir.app). Jeux de données
  téléchargés dans `.cache/` (Actions cache), jamais commités.
- Audio : récitateurs à **un fichier par sourate** (mp3quran.net avec son minutage par ayah ;
  archive.org pour Omar Hisham), découpés par ayah (`sources/surah_audio.py`) et **vérifiés par
  reconnaissance** (`sources/recognition.py`, Whisper affiné sur la récitation) : chaque segment
  doit être reconnu comme son ayah (≥ 0,75) et **chaque coupe est réécoutée des deux côtés**
  (`check_cut` : aucun mot d'une ayah dans la voisine, « Alif » et « لا » ratés le 2026-11-05) ;
  la basmala finit au dernier vrai silence avant l'ayah 1. Découpe commitée
  `config/splits/<id>/SSS.json` (temps seulement, et temps des mots des ayahs de 15 mots ou
  plus) : `quran-reels split <passage>`, `quran-reels split --audit --fix <sourates>`. Le texte
  reconnu n'est que comparé, jamais affiché ni publié.
- Récitateur choisi par passage (`reciters.py`, `content.rotation`) parmi ceux dont la découpe
  du passage est vérifiée ; workflow `prepare` chaque nuit pour les 8 jours suivants. Fares
  Abbad : **un fichier par ayah** (EveryAyah), toujours prêt, rien à découper ; fichiers à 48 ou
  64 kb/s, durées prévues à 48 kb/s (jamais plus courtes que la réalité). AbdulSamad (#18) non
  retenu : basmala dans le fichier de la 1re ayah, nom inconnu (docs/sources.md). Husary
  (#32) en essai : dans la liste, pas dans la rotation, essai sur Facebook seul à faire.
- Fonds : clips Pexels (liste à la main) et Pixabay (`PIXABAY_API_KEY`, jamais affichée),
  scènes générées ; skill `add-background`.

## Plateformes (voir docs/plateformes.md)

- Facebook + Instagram : publication auto via l'API Graph, app Meta en accès standard
  (comptes du propriétaire uniquement), sans validation Meta ni vérification d'entreprise.
  Chaque reel est d'abord envoyé non publié (brouillon Facebook, conteneur Instagram) et publié
  seulement si la vérification des droits de Meta est propre partout (voir docs/plateformes.md).
- TikTok : sans audit, la publication directe est forcée en privé → mode **brouillon**
  (MEDIA_UPLOAD vers la boîte TikTok) en attendant l'audit.
- YouTube : sans audit, les uploads API sont verrouillés en privé → **upload manuel** du MP4
  en attendant ; demander l'audit tôt. Quota ≈ 6 uploads/jour. Droits : **Content ID**, à
  part de Meta : Salah Budair y est revendiqué (Short 18:1-10 bloqué partout le 2026-11-06 ;
  un Short de plus d'1 min revendiqué l'est toujours) → **version YouTube à part** par un autre
  récitateur (`platforms.youtube.exclude_reciters`, `out/youtube/`, ticket des légendes).
  **Téléchargement direct** (2026-11-06) : chaque MP4 publié (et sa version YouTube) va dans la
  release GitHub `reels` (URL publique, non zippée, 30 jours) ; la page `reel.html` donne titre
  (≤ 100 car., tiré de la légende), description (`caption.txt`) et hashtags à copier ; mise en
  ligne notée par `/youtube <jour>/<créneau> <lien>` sur le ticket des légendes (état :
  `results.youtube`, `by_hand`).

## Découpage et calendrier (détails : docs/calendrier.md)

- `config/plan.yaml` : tout le Coran en passages d'≈ 1 min (1 887), coupés seulement à une fin
  de phrase (Sahih International) et de groupe d'Ibn Kathir ; figé (`quran-reels plan --write`).
- `config/schedule.yaml` : créneaux 07:30 (`reading`) et 19:30 (`themes`), vendredi une file par
  créneau (`kahf-first-ten`, `kahf`), `fallback`, `published_by_hand`. Séries dans
  `config/series/*.yaml`, vérifiées par `quran-reels series-check`.
- État : `published.json` sur la branche `state` (créneaux, files, `claimed`, `removed`) ;
  un créneau supprimé se republie avec `quran-reels state reopen <jour>/<créneau>` (skill
  `republish`).
- **Le cron de GitHub ne se déclenche jamais dans ce dépôt** (0 run `schedule` depuis la
  création, problème de GitHub connu en 2026 au niveau du compte ; `workflow_dispatch` marche).
  Les workflows sont donc lancés par des **tâches planifiées Claude** (choix du propriétaire,
  2026-11-05) qui réveillent la session « Quran Words Daily – planificateur » (Sonnet, dépôt
  attaché, outils GitHub) : `prepare.yml` 02:41 Paris, `daily.yml` 07:12 et 19:12 Paris
  (`CRON_TZ=Europe/Paris`), `images.yml` 11:36 UTC ; chacune lance le workflow sur `main`,
  attend la fin, relance une fois en cas d'échec (sauf prepare) et résume (skill
  `check-publication`).
- Échec → ticket « ⚠️ Publication quotidienne en échec » (`notify.py`) ; légendes TikTok dans
  le ticket épinglé « 📋 Légendes à copier », avec pour chaque vidéo le lien MP4 direct, la page
  YouTube et la commande `/youtube`.
- **À la demande** (docs/on-demand.md) : `on_demand` de `published.json`, une entrée par ticket,
  un résultat par plateforme (YouTube : `manual` puis `published` + `by_hand`) ; le calendrier
  ne le lit pas (il republie le passage à son tour, choix du propriétaire). Aperçus : images et
  `reel.json` sur la branche `previews` (jamais fusionnée), MP4 dans la release `reels` ;
  supprimés après 30 jours.

## Rendu (détails : docs/rendu.md)

- Template `render/templates/reel.html.j2` (maquette validée `docs/mockup/apercu-reel-93-2.png`),
  zone sûre haut 250 px, bas 420 px, côtés 90 px ; calques PNG transparents (Chromium) sur le
  fond, une image par ayah, durée = durée de son audio.
- **Longue ayah sur plusieurs écrans** (`render/screens.py`) : texte réduit sous 70 % → coupé
  après les signes de pause, traduction après les fins de phrase, chaque écran affiché quand
  son premier mot est récité (temps des mots de la découpe ; sinon au prorata des lettres).
- Fond choisi par les mots de la traduction (`config/backgrounds.yaml`), même passage → même
  fond. MP4 H.264 sans B-frames, AAC 48 kHz, sans edit list (Instagram), ≤ 6 Mb/s.
- Scènes générées animées (nuages en deux couches, brume, sable, vagues, lumière ; boucle de
  30 s sans saut) et **zoom lent** sur toute la vidéo (`scenes.push_in` de backgrounds.yaml :
  8 % par minute, 12 % au plus ; `perspective` de ffmpeg, sous le texte qui ne bouge pas).
  Shader modifié → nouvelle boucle (nom = empreinte du shader), anciennes effacées du cache.
- Hashtags déterministes (`render.hashtags`), Instagram et TikTok : les 5 premiers.
  Facebook : sa légende courte (`render.facebook_caption`, ≤ 400 caractères,
  `platforms.facebook.max_caption_chars`), rangée dans `manifest.json` (`captions.facebook`).

## Publications image (détails : docs/images.md)

- Word of the day (carrousel 1080×1350 : le mot, son ayah, son sens dans le Muyassar), une fois
  par jour ; candidats figés dans `config/image-candidates.yaml` (`quran-reels images build`),
  ordre stable, exclusions `config/exclude.yaml` ; état `images.json` sur la branche `state`.

## Skills (`.claude/skills/`)

Procédures à suivre, pour toute session (le planificateur compris) : `check-publication`
(lire un run, l'état, rapporter), `test-reciter` (découper, vérifier, Facebook d'abord, puis
Instagram), `republish` (rouvrir un créneau et republier), `add-background` (chercher, vérifier,
proposer un fond), `propose-series` (proposer une série, validée en PR).

## Secrets (jamais dans le code ni dans la conversation)

GitHub Actions secrets : `META_PAGE_ID`, `META_PAGE_TOKEN`, `IG_USER_ID`, `TIKTOK_CLIENT_KEY`,
`TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN` (écrit par le workflow `tiktok-auth` puis à
chaque rotation), `GH_SECRETS_TOKEN` (jeton fin GitHub, Secrets : lecture/écriture sur ce dépôt
seulement, voir docs/plateformes.md ; noter sa date d'expiration), `YOUTUBE_*`.
Jamais un jeton dans un log : en-têtes `Authorization`, erreurs reconstruites, `::add-mask::`.
Les logs Actions d'un dépôt public sont publics : rien d'identifiant n'y est imprimé.

Jeton de Page Meta : expiration « Jamais », mais **l'accès aux données expire le 2027-02-02**
(90 jours). Pour le renouveler : explorateur Graph → jeton utilisateur → prolonger →
`me/accounts` → nouveau `META_PAGE_TOKEN`. Fait : `meta-check` (et chaque `publish`) lit
`data_access_expires_at` via `GET /debug_token` et fait échouer le job (message clair, marche à
suivre) à moins de 14 jours de l'échéance, soit à partir du 2027-01-19.

## État

- [x] Comptes créés (Gmail, Page FB, IG Créateur reliés, TikTok, YouTube)
- [x] Squelette du dépôt, polices, maquette
- [ ] Environnement cloud `quran-reels` (accès réseau Custom)
- [x] Ingestion des données + rendu v1 avec audio (`quran-reels render 93:1-3`, fond provisoire)
- [x] Passages d'≈ 1 min, sourate courte entière (`quran-reels passages`, `render 93`)
- [x] App Meta (voir docs/plateformes.md)
- [x] Dry-run Facebook (run #3, brouillon créé) et Instagram (run #7, conteneur FINISHED, non
      publié). [x] Première publication réelle : 93:1-11 sur Facebook et Instagram
      (publish-test run #12, 2026-11-05 ; Instagram : 1er conteneur bloqué, publié au 2e).
- [x] App TikTok Sandbox · [x] connexion (`tiktok-auth`, compte quran_words_daily, refresh
      token jusqu'à ≈ 2027-11-04) · [x] brouillon dans la boîte TikTok en Sandbox (run #8)
- [ ] Demande d'audit YouTube
- [x] Calendrier : 2 créneaux, Juz' 'Amma, séries (Ayat al-Kursi, munjiyat, du'a, rizq), Al-Kahf le
      vendredi, état, workflow `daily` — **activé** (`enabled: true`) ; 93:1-11, publiée à la
      main, est dans `published_by_hand` (jamais republiée par le calendrier)
- [x] Série « السبع آيات المنجيات » · [x] séries patience (29 passages) et repentir (16) proposées
      (2026-11-06, `sabr.yaml`, `tawba.yaml`, après rizq dans la file `themes`)
- [x] Fonds choisis selon le passage (scènes générées + 3 clips Pexels, PR #8 ; + 21 clips
      Pixabay validés ; tickets du catalogue : 2 retirés, 3 clips de mer ajoutés, 4 écartés)
- [x] Publications image : Word of the day **activé** (tirages du 6 au 12 novembre avec le
      Muyassar validés par le propriétaire le 2026-11-05 ; candidats refaits : 8 599 mots,
      4 913 ayahs), Ayah of the day désactivé · [ ] premier dry-run Meta des images ·
      [ ] première publication réelle (11:30 UTC le lendemain de la fusion)
- [x] Vérification des droits Meta avant publication. Facebook : un brouillon de reel ne se
      publie pas par l'API (« The video was not uploaded », code 6000, subcode 1363130, run
      #18) → le fichier vérifié est renvoyé directement en PUBLISHED, brouillon supprimé.
      [x] 114 avec Omar Hisham publiée sur Facebook (publish-test run #19, 2026-11-05),
      Facebook n'y signale aucun problème de droits (constaté par le propriétaire).
      [x] **App Meta passée en Live** (2026-11-05) : en mode développement, ce qu'elle publiait
      n'était visible que des comptes qui ont un rôle sur l'app (114 « non disponible » pour un
      autre compte) ; aussitôt après, le lecteur intégré de Facebook sert le reel 114 sans
      compte (vidéo de 41 s), sans republier (docs/plateformes.md).
- [x] Récitateurs choisis par passage (6, `content.rotation`) · [x] découpes vérifiées
      (`quran-reels split`, workflow `prepare` chaque nuit) · [ ] Juz' 'Amma et thèmes pour
      tous · [ ] refaire le plan (calculé avec Alafasy) si des passages dépassent 90 s
- [x] Publication à la demande (docs/on-demand.md, `on-demand.yml`) : [x] dry run sur la branche (#34, 2026-11-06 : aperçu, `/essai`, droits Meta propres, MP4 1080p et textes YouTube ; refus #35 et découpe non nette #34)
      · [x] première demande approuvée par le propriétaire depuis son téléphone (#39,
      2026-11-06 : 101:1-11, Omar Hisham, YouTube seul ; aperçu refait après la correction des
      coupes FLAC, PR #40 ; `/publier`, droits Meta propres, MP4 1080p et textes YouTube) :
      **demande de test, pas mise en ligne** (le propriétaire garde 2 publications par jour),
      ticket fermé « non prévu », `youtube: cancelled` dans l'état · [ ] première publication
      publique à la demande et `/youtube <lien>` en vrai
- [x] Catalogue (docs/catalog.md, `catalog.yml`) · [x] Pages passé en « GitHub Actions » par le
      propriétaire, premier déploiement (run #1, 2026-11-05) · [x] libellé « Catalog » créé ·
      [x] premiers tickets appliqués (#19–#28) · [x] #18 AbdulSamad non retenu (basmala dans
      la 1re ayah, confirmée par reconnaissance ; nom inconnu) · [ ] #32 Husary : ajouté à la
      liste, reel 112 vérifié, essai sur Facebook seul à faire
- [ ] Profils des 4 comptes (docs/profils.md, proposés et **validés par le propriétaire** le
      2026-11-09) : bio, nom, photo unique
      « آيات », couverture, bannière (« Quran & Sunnah for everyday life », bilingues), playlists
      YouTube par thème, sourate et format, Facebook (3), à appliquer à la main par le
      propriétaire ; YouTube vide ; TikTok renommé `@quran.words.daily` et reels signés de
      ce nom sur TikTok (2026-11-09) ; le compte vide `@quran_words_daily`, à quelqu'un
      d'autre, à signaler
- [x] Liste de qualité de Facebook sur 6:17 (2026-11-09 : « image statique », « légende de
      qualité (10 à 400 caractères) ») : scènes générées animées + zoom lent, légende Facebook
      courte · [ ] relire la liste de qualité sur le prochain reel avec une scène générée
