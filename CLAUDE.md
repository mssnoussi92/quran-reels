# Quran Words Daily — contexte projet

Pipeline open source qui produit chaque jour un reel vertical (1080×1920) d'un passage du Coran
et le publie sur Facebook, Instagram, TikTok et YouTube Shorts.

Comptes : Facebook `quranwordsdaily` · Instagram / TikTok / YouTube `quran_words_daily` ·
e-mail du projet `quranwordsdaily@gmail.com`. Le propriétaire travaille depuis son téléphone
(pas de PC) : tout doit tourner dans le cloud (session Claude, GitHub Actions).

## Décisions validées

| Sujet | Choix |
|---|---|
| Format | **≈ 1 minute** (cible 60 s, 40–90 s), jamais coupé au milieu d'une phrase ; **sourate courte entière** (≤ 90 s, même très courte) |
| Basmala | **Au début de chaque vidéo**, même pour quelques versets ; sauf sourate 9 et avant 1:1 (qui est la basmala) |
| Rythme | **2 vidéos par jour**, heure de Paris : **07:30** lecture dans l'ordre, **19:30** séries thématiques |
| Images | **Word of the day**, carrousel de 3 images 1080×1350 (le mot, son ayah, son sens dans le Tafsir al-Muyassar), **1 par jour** à 11:30 UTC sur Instagram et Facebook ; **Ayah of the day** préparé, désactivé (docs/images.md) |
| Lecture | **Juz' 'Amma d'abord** (114 → 78), puis Al-Fatiha et 2 → 77, passages de `config/plan.yaml` |
| Thèmes | Ayat al-Kursi, les 7 versets « المنجيات », versets de du'a, versets du rizq… : listes **proposées par l'IA en PR, validées par le propriétaire** |
| Vendredi | **Al-Kahf sur les deux créneaux** (choix du propriétaire, 2026-11-05) : le matin, **les 10 premières ayahs (18:1-10) en une seule vidéo, chaque vendredi** ; le soir, la suite **à partir de 18:11**, un passage par vendredi (36), puis on recommence |
| Texte arabe | Uthmani (Hafs), police **Amiri Quran** (OFL) |
| Traduction | **Sahih International** (anglais), créditée dans chaque légende |
| Mots difficiles | **غريب التفسير الميسر** (Tafsir al-Muyassar, Complexe du Roi Fahd ; `almuyassar-ghareeb` sur tafsir.app), choix du propriétaire le 2026-11-05 (avant : Ibn Qutaybah, *Tafsir Gharib al-Qur'an*), sens en arabe, **1 à 3 mots liés** surlignés |
| Récitateurs | **Choisis par passage** (`content.rotation`, `reciters.py`) parmi ceux du propriétaire (2026-11-05) : **Omar Hisham Al-Arabi, Muhammad Siddiq Al-Minshawi, Tawfiq As-Sayegh, Salah Budair, Fares Abbad** (EveryAyah, ajouté depuis le catalogue, ticket #19, directement dans la rotation sans essai sur Facebook seul : choix du propriétaire) : prêt pour le passage (découpe vérifiée), ≤ 90 s, pas un des 2 derniers publiés, puis le plus proche de 60 s (passage long → récitateur rapide, sourate courte → plus lent). Écartés : Alafasy, **Nabil Ar-Rifai** (Rights Manager : 2:255 rendue muette par Facebook dans 24 territoires, 2026-11-05) et **Saad Al-Ghamdi** (2:255 revendiquée par UMG, muette en Russie, le même soir), Hudhaifi, Ayyub, Akhdar (après écoute) ; un récitateur revendiqué après publication est écarté automatiquement (`claimed`) |
| Droits | **Vérification Meta avant chaque publication** : brouillon Facebook + conteneur Instagram, publiés seulement si Meta répond `complete` sans correspondance, sinon rien n'est publié (TikTok compris). Elle n'a vu ni Alafasy, ni Ar-Rifai, ni Al-Ghamdi (revendications arrivées quelques minutes après la publication). Contrôle après publication prêt (`rights_after_timeout` > 0 : relu 5 min puis à chaque run pendant 2 jours ; muet ou bloqué → retiré de Facebook et Instagram + alerte, récitateur écarté) mais **désactivé : le propriétaire vérifie lui-même pour l'instant** (2026-11-05) ; nouveaux récitateurs testés sur Facebook seul, Instagram ensuite |
| Fond | **choisi selon ce que dit le passage** (montagnes, mer, rivières, jardins, nuit, aube, ciel…) : vidéos Pexels choisies par le propriétaire et scènes générées (aube, nuit, mer), **sans personnes ni animaux** |
| Exécution | GitHub Actions (dépôt public → gratuit), migrable sur le homelab (Docker) |
| Comptes pro | Page Facebook + Instagram en type **Créateur**, reliés |
| Signature | **@quran_words_daily** sur chaque image, dans la zone sûre (repartages) |
| Hashtags | Fin de légende, dans l'ordre : `#QuranWordsDaily`, `#Quran`, 1er tag de la série, sourate (`#SurahAdDuhaa` `#سورة_الضحى`), `#القرآن_الكريم`, autres tags de la série, récitateur, gloses (`#تفسير_القرآن`) ; **Instagram et TikTok : les 5 premiers** (leur limite), Facebook 8, `caption.txt` tous (YouTube à la main) |

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
  render/          frames.py (template HTML → PNG, Chromium/Playwright),
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
  catalog/         `quran-reels catalog build` : catalogue public en lecture seule
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
                   images.yml (toutes les heures ; `images run --check` décide selon
                   config/images.yaml ; état images.json sur la branche `state`)
                   catalog.yml (push main config/docs, après daily/images/prepare, chaque jour,
                   à la main : docs/ + catalog/ → GitHub Pages, source « GitHub Actions »)
                   Runners épinglés sur `ubuntu-24.04` (`ubuntu-latest` passe à 26.04),
                   actions en versions Node.js 24. **Pas d'apt** : le miroir Ubuntu a mis
                   40 min à installer ffmpeg (run du soir du 2026-11-05, bloqué) ; ffmpeg =
                   build statique d'imageio-ffmpeg (pip, épinglé 0.8.1 : ffmpeg 9.0.2,
                   libx264, aac ; les tests passent avec), sans ffprobe (durées lues par
                   ffmpeg) ; Chromium de Playwright, `--with-deps` seulement s'il ne démarre pas.
docs/              site GitHub Pages (CGU, confidentialité, tiktok-login.html, tiktok-callback.html),
                   déployé par catalog.yml avec le catalogue (/quran-reels/catalog/)
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

## Sources de données

- Texte uthmani, sourates, Sahih International : API Quran.com v4, sans clé, tout le Coran en
  une requête par ressource (`/quran/verses/uthmani`, `/chapters`,
  `/quran/translations/{id}?fields=verse_key`, id résolu depuis le slug
  `en-sahih-international`). Les marques de notes `<sup foot_note>` sont retirées.
- Sens des mots : `almuyassar-ghareeb` (غريب التفسير الميسر, Complexe du Roi Fahd), choisi le
  2026-11-05 après comparaison (plus clair, ≈ 5 070 ayahs couvertes au lieu de 2 394, citations
  en écriture uthmanie, même origine que Hudhaifi) ; `siraaj-ghareeb` (السراج, al-Khudairi)
  saute des mots (منطق الطير, سكينة). Format identique (« ﴿…﴾: sens »), `keys_flag: -1`
  (keys = ayahs sans entrée). Avant : gloses Ibn Qutaybah : `tafsir.app` (Nuqayah). `/sources/sources.json` liste, pour
  `ghareeb-ibn-qutaybah`, les ayahs qui ont une entrée (`keys`, index global 1–6236 ;
  `keys_flag: 1`) : 2 394 ayahs. `/get.php?src=ghareeb-ibn-qutaybah&s=93&a=2&ver=1` renvoie
  `{"data": "﴿وَاللَّيْلِ إِذَا سَجَى﴾ إذا سكَن. …"}`. Stockage brut par sourate dans
  `.cache/tafsir.app/ghareeb-ibn-qutaybah/SSS.json`. À l'affichage : notes de l'éditeur
  `[[…]]` retirées, phrases entières seulement (`max_chars`), sinon la glose est omise.
  Absente de QUL et de Quran.com.
- Audio : EveryAyah, un MP3 par ayah, `https://everyayah.com/data/<dossier>/SSSAAA.mp3`.
  Décodé en PCM 48 kHz pour un minutage exact à l'échantillon : le texte suit la récitation.
  Récitateurs (`content.reciters`, `QURAN_REELS_RECITER` pour un essai) : `alafasy`
  (`Alafasy_128kbps`), et les enregistrements Hafs du Complexe du Roi Fahd `hudhaifi`
  (`Hudhaify_128kbps`, coupes propres sur un silence), `ayyoub` (`Muhammad_Ayyoub_128kbps` ; son
  `bismillah.mp3` dure 2,9 s, coupé : on prend son 1:1), `akhdar` (`Ibrahim_Akhdar_32kbps`,
  32 kb/s mono seulement, pas de `bismillah.mp3`). Le site du Complexe (`qurancomplex.gov.sa`,
  qui propose « المصحف كاملاً آيات », ≈ 800 Mo par récitateur, et une page « حقوق الاستخدام »)
  ne répond ni depuis ce conteneur ni depuis les runners GitHub (connexion expirée,
  2026-11-05) : la provenance des fichiers EveryAyah n'a pas pu être comparée à l'original.
  `mp3quran.net` (sourates entières + minutage par ayah, `api/v3/ayat_timing`) répond depuis
  GitHub : piste de repli.
- Al-Minshawi (murattal), Al-Ghamdi, Ar-Rifai (Nabil), As-Sayegh, Budair : **mp3quran.net**, un
  fichier par sourate (`cdn.mp3quran.net/audio/<nom>/r1/SSS.mp3`) **et le minutage par ayah**
  (`/api/v3/ayat_timing?surah=S&read=R`, R = 112, 30, 87, 17, 43 ; les 114 sourates). Le
  minutage (bénévoles, approximatif) sert d'estimation des coupes, puis coupe au moment calme et
  vérification par reconnaissance, comme Omar Hisham. Allure (Alafasy = 1) : As-Sayegh 0,76,
  Ar-Rifai 0,78, Al-Ghamdi et Budair 0,79, Al-Minshawi 1,16. Pas sur EveryAyah : Nabil Ar-Rifai,
  As-Sayegh (Ghamadi_40kbps, Minshawy_*, Salah_Al_Budair_128kbps y sont).
- **Fares Abbad** (`fares_abbad`, EveryAyah `Fares_Abbad_64kbps`, ticket #19 du catalogue) :
  fichiers à 48 **ou** 64 kb/s (22 kHz, sans en-tête de durée ; 24 sur 40 tirés au hasard à
  48), donc `kbps: 48` : la durée prévue n'est jamais plus courte que la vraie (90 s Facebook),
  les fichiers à 64 kb/s sont surestimés d'un tiers. Pas de `bismillah.mp3` : basmala = 1:1.
  Toujours « prêt » (un fichier par ayah, rien à découper) : `prepare` le saute. Durées par
  requêtes HEAD (une par ayah de la sourate, en cache `.cache/everyayah/`).
  **AbdulSamad** (`AbdulSamad_64kbps_QuranExplorer.Com`, ticket #18) **en attente** : le
  fichier de la 1re ayah de chaque sourate commence par ≈ 6–9 s de récitation puis une pause
  avant l'ayah (112:1 16,8 s, 112:2 5,9 s ; 114, 93, 18 pareil), sans doute la basmala :
  avec la basmala ajoutée par le pipeline, elle serait récitée deux fois et le texte de
  l'ayah 1 affiché pendant ; nom complet du récitateur inconnu (crédit) ; très lent (2:255 :
  94 s seule) ; son `bismillah.mp3` est encodé à part (22 kHz, 40 kb/s).
- Choix par passage (`reciters.py`, `content.rotation`) : seulement les récitateurs dont la
  découpe de la sourate est commitée et chaque ayah du passage (et la basmala) vérifiée ;
  aucun prêt → rien n'est publié pour ce créneau (l'erreur donne `quran-reels split <passage>`).
  Workflow **`prepare`** (chaque nuit 01:41 UTC, et à la main) : `quran-reels split --upcoming 8`
  découpe et vérifie les passages des 8 prochains jours pour chaque récitateur de la rotation,
  sur un runner (torch CPU, ffmpeg statique d'imageio-ffmpeg, pas d'apt), et pousse les
  découpes sur la branche `state` (`splits/`) ; `daily` et `publish-test` les lisent
  (`QURAN_REELS_SPLITS`), en plus de `config/splits/` (commitées) : le fichier qui a le plus
  d'ayahs vérifiées l'emporte. Rouge seulement si un passage n'a aucun récitateur prêt.
  Omar Hisham : pas de découpe au-delà de 15 min d'enregistrement (`split_max_minutes`).
  `quran-reels split 2:255` ne vérifie que ce passage. Le créneau garde son récitateur
  (`published.json`, champ `reciter`) ; un nouvel essai reprend le même. `calendar` l'affiche.
- Omar Hisham Al-Arabi (`omar_hisham`) : aucune source par ayah (ni EveryAyah, ni Quran.com,
  mp3quran, QuranicAudio, alquran.cloud) ; seulement des sourates entières copiées sur
  archive.org par des tiers, sans licence (`omar-hisham-al-arabi`, 320 kb/s, 71 sourates, même
  enregistrement que `Omar-Hisham` utilisé par surahquran.com ; `OmarHishamAl-Arabi_murattel`
  est en 16 kHz, 22 kb/s, sans pause : écarté). Ses enregistrements sont aussi diffusés sur
  Apple Music et Spotify : risque Rights Manager. Style lent pour une partie des sourates :
  93 dure 5 min 24 s (Alafasy 55 s), 89 et 96 plus de 8 min ; les courtes sont proches
  d'Alafasy (112 : 19 s, 113 : 24 s, 114 : 40 s). 108 manque. Les pauses seules ne trouvent pas
  les ayahs : il enchaîne des ayahs sans respirer et en répète (114 : ayahs 2 et 3 d'un souffle,
  ayah 6 deux fois ; le découpage sur les pauses était décalé d'une ayah, vu par reconnaissance).
  `sources/surah_audio.py` (`surah_url` dans le catalogue) + `sources/recognition.py` :
  1. mots reconnus avec leurs temps (`tarteel-ai/whisper-base-ar-quran`, Whisper affiné sur la
     récitation ; temps des mots par l'attention de `openai/whisper-base`), alignés sur le texte
     uthmani (programmation dynamique ; une répétition reste avec son ayah, la 1re récitation
     compte) → début de chaque ayah ;
  2. coupe au moment le plus calme proche (silence ou creux de l'enveloppe ≥ 2 dB, la
     réverbération remplit les silences) ; début non reconnu (le 1er mot avale la basmala) →
     proportion des durées d'Alafasy ;
  3. chaque segment est reconnu à nouveau et comparé à son ayah (≥ 0,75, répétition admise ;
     0 s'il ressemble plus à l'ayah avec ne serait-ce qu'un mot d'une voisine : بسم الله… قل هو,
     لم يلد ولم يولد ولم). Pour chaque coupe, les moments calmes voisins sont essayés tour à
     tour (près d'un minutage publié : −0,6/+0,4 s) jusqu'à ce que le segment soit reconnu. Les
     ayahs reconnues restent vérifiées même si d'autres échouent : un passage demande toutes
     les siennes. 114 : 1,00 1,00 1,00 0,93 0,91 1,00 ; 1 (Al-Fatiha) refusée (ayah 3 : 0,67).
  Découpe vérifiée **commitée** (`config/splits/<id>/SSS.json`, temps seulement) par
  `quran-reels split <sourates>` (extra `asr` : `pip install torch --index-url
  https://download.pytorch.org/whl/cpu && pip install -e .[asr]`) : le pipeline quotidien n'a
  besoin ni du modèle ni de la vérification. Basmala : début du fichier de la sourate (même
  séance, sans isti'adha) ; elle finit au **dernier vrai silence avant l'ayah 1** (le récitateur s'arrête toujours après la basmala ; le début publié par mp3quran peut être en retard : chez Budair, sourate 2, la basmala gardait « Alif », entendu « ah » avant Ayat al-Kursi, 2026-11-05). Les FLAC coupés portent leurs temps de coupe dans leur nom (jamais une ancienne coupe du cache). Le texte reconnu n'est que comparé, jamais affiché ni publié. La légende crédite le producteur (« Recitation: Ali Al-Hudhaifi
  (King Fahd Complex) ») ; `manifest.json` et `publish.json` gardent le récitateur et sa licence.
- Durées pour le découpage : Quran.com (`timings_id`, Alafasy seulement) ou, sinon, taille des
  fichiers EveryAyah (débit constant, `kbps` : octets × 8 / débit, une requête HEAD par ayah, en
  cache) ; sourate 93 entière : 62,6 s Alafasy, 66,5 s Hudhaifi, 68,9 s Ayyub, 72,0 s Akhdar.
  Changer de récitateur par défaut demande de refaire `quran-reels plan --write` (le plan figé
  est calculé avec Alafasy) et `quran-reels series-check`.
- Découpage (par sourate, à la demande, petits fichiers) : durées par ayah depuis
  `/chapter_recitations/7/{s}?segments=true` (même enregistrement d'Alafasy, ±2 %, sans
  télécharger les MP3) ; groupes d'ayahs d'Ibn Kathir abrégé (`en-tafisr-ibn-kathir`, id 169 :
  les ayahs commentées avec la précédente ont un texte vide).
- Fonds : l'**émission de nouvelles clés API Pexels est en pause** (nov. 2026). On utilise donc
  une liste sélectionnée à la main (`config/backgrounds.yaml`) d'URL directes de fichiers
  `videos.pexels.com`, ce qui ne demande pas de clé. Les pages `www.pexels.com` refusent ce
  conteneur (403, Cloudflare) : l'URL du fichier se devine pour les vidéos anciennes
  (`{id}/{id}-uhd_3840_2160_24fps.mp4`), pas pour les récentes (numéro de fichier distinct).
  Chaque clip est vérifié image par image (personnes, animaux, texte) avant d'être ajouté ;
  refusé : 1858301 (canards sur le lac). Décision (2026-11-05) : pas de liens à la main.
- **Pixabay** (`sources/pixabay.py`, clé `PIXABAY_API_KEY` : secret GitHub ; absente de ce
  conteneur, qui atteint pourtant `pixabay.com/api` et `cdn.pixabay.com`) : API vidéos,
  `category=nature`, `safesearch=true`, `video_type=film`. Leurs règles : réponses en cache
  24 h (`.cache/pixabay/`, clé de cache sans la clé API), une requête toutes les 0,7 s au plus
  (< 100/min) et pause si `X-RateLimit-Remaining` tombe à 0, pas de téléchargement en masse.
  La clé passe en paramètre (l'API l'exige) mais n'est jamais affichée ni mise en cache
  (erreurs reconstruites, masquée `***` dans les journaux Actions). Le CDN limite aussi les
  téléchargements : 32 aperçus à 0,3 s d'écart → `429 Rate limit exceeded, Retry-After 210` ;
  un aperçu toutes les 5 s, et on attend `Retry-After`.
- Processus pour un nouveau clip : workflow `backgrounds-search` (manuel, thème optionnel) ou
  `quran-reels backgrounds search` → candidats par thème (termes de `backgrounds.yaml` →
  `pixabay`), premier tri sur les tags (personnes, animaux, texte, villes) ; puis aperçus
  (`_tiny.mp4`) vérifiés image par image (8 images par clip, zoom sur les plages et les lacs)
  → proposés au propriétaire → seuls les clips validés vont dans `backgrounds.yaml` avec
  `source: pixabay`, `pixabay_id`, `author`, `page` ; le fichier vient de l'API au premier
  usage (`file_url`, rendu `large`), puis la boucle traitée est en cache. Le manifeste de chaque
  vidéo garde `pixabay_id`, `author`, `page`. 2026-11-05 : 38 candidats, 9 refusés (phare,
  maisons, lumières de ville, canoës, personnes sur une plage, petit objet sur l'eau), 22
  proposés (2–3 par thème), 21 validés par le propriétaire (213423, aurore, refusé), dans
  `backgrounds.yaml` (`pb-…`). Tickets du catalogue (2026-11-05) : `pb-grey-clouds` et
  `pb-cumulus-forest` retirés ; 7 clips de mer approuvés, 3 gardés après le contrôle image par
  image (`pb-golden-surf` 4006, `pb-aerial-shore` 24216, `pb-dusk-sea` 22183), écartés :
  338904 (deux nageurs), 28268 (un promeneur), 1890 (un bateau), 19368 (phare, refusé par le
  propriétaire) ; tous dans `src/quran_reels/catalog/history.yaml` avec la raison. Un clip indisponible (pas de clé, clip retiré, réseau) ne fait
  jamais échouer un reel : repli sur une scène générée, signalé dans le journal.

## Plateformes (voir docs/plateformes.md)

- Facebook + Instagram : publication auto via l'API Graph, app Meta en accès standard
  (comptes du propriétaire uniquement), sans validation Meta ni vérification d'entreprise.
  Chaque reel est d'abord envoyé non publié (brouillon Facebook, conteneur Instagram) et publié
  seulement si la vérification des droits de Meta est propre partout (voir docs/plateformes.md).
- TikTok : sans audit, la publication directe est forcée en privé → mode **brouillon**
  (MEDIA_UPLOAD vers la boîte TikTok) en attendant l'audit.
- YouTube : sans audit, les uploads API sont verrouillés en privé → **upload manuel** du MP4
  en attendant ; demander l'audit tôt. Quota ≈ 6 uploads/jour.

## Découpage des passages (`selector/plan.py`)

- Sourate qui tient dans `max_seconds` (90 s, attente et queue comprises) → une seule vidéo,
  même très courte (108 : 17 s, 1 : 48 s, 93 : 56 s).
- Sinon, coupure seulement après une ayah qui **termine une phrase** dans Sahih International
  (`.` `?` `!` ; une virgule ou rien = la phrase continue) **et** termine un groupe d'Ibn Kathir.
  Programmation dynamique : passages les plus proches de 60 s, entre 40 et 90 s. Exemple
  sourate 2 : 2:1-5 (57 s), 2:6-9 (52 s), 2:10-13 (60 s)…
- Bloc entre deux coupures plus long que 90 s (78:37-40) : on coupe à une fin de phrase à
  l'intérieur du groupe, passage signalé « cut inside a tafsir group ». Une ayah seule de plus
  de 90 s (2:282) dépasse : chaque seconde au-delà coûte plus que tout le reste, donc elle reste
  seule (avant correction, 24:31 et 24:61 avalaient tout l'entre-deux : 24:31-61, 19 min).
- Tout le Coran : **1 887 passages** (`config/plan.yaml`), dont 19 de plus de 90 s (ayahs ou
  phrases trop longues, 2:282, 24:31…) laissés de côté par le calendrier pour l'instant.

## Calendrier (`selector/calendar.py`, `daily.py`)

- `config/schedule.yaml` : fuseau `Europe/Paris`, créneaux `morning` 07:30 (file `reading`) et
  `evening` 19:30 (file `themes`), vendredi : une file par créneau (`fridays: {morning:
  kahf-first-ten, evening: kahf}` ; `queue:` en donne une pour tous), `fallback` (une file
  finie passe à une autre). `enabled: false` tant que la première publication réelle n'est pas
  faite (activé le 2026-11-05). `published_by_hand` : passages publiés hors calendrier, sautés.
- Une file joue ses séries l'une après l'autre ; chaque créneau prend le premier passage pas
  encore publié. Série `repeat: true` (Al-Kahf) : recommence une fois finie.
- Al-Kahf : `kahf-first-ten` (18:1-10, une seule entrée qui recommence chaque semaine) et
  `al-kahf` (36 passages de 18:11 à 18:110, `quran-reels passages 18 --from 11` : mêmes coupes
  que plan.yaml à partir de 18:15, 18:11-14 remplace 18:6-12 et 18:13-14). 18:1-10 dure
  87,6 s avec Salah Budair, 108 à 132 s avec les autres : les reels Facebook s'arrêtent à 90 s
  (doc Reels Publishing : « 3 to 90 seconds »), la rotation choisit donc Budair chaque vendredi
  matin. `series-check` accepte un passage trop long pour l'estimation Alafasy si un récitateur
  prêt de la rotation tient dans 90 s.
- Série (`config/series/*.yaml`) : `surahs: [...]` (passages de plan.yaml) ou `passages:`
  écrits à la main, `title_ar`/`title_en` affichés sur le premier écran («آيات الدعاء · ٤ من ٣٨»)
  et en tête de la légende. `quran-reels series-check` refuse un passage qui commence ou finit
  au milieu d'une phrase, ou de plus de 90 s.
- Listes thématiques : proposées (IA, en amont) avec la règle utilisée (racine ر ز ق, «رَبَّنَا»…)
  et validées par le propriétaire en PR. Les textes viennent toujours des sources au rendu.
  « السبع آيات المنجيات » : la liste du propriétaire (9:51, 6:17, 11:6, 11:56, 29:60, 35:2,
  29:61) ; 11:6 et 29:60 retirées de la série rizq pour ne pas les publier deux fois.
- Workflow `daily` : cron `17 5,6,7` et `17 17,18,19` UTC (heure d'été et d'hiver, GitHub est
  souvent en retard ; le 2026-11-05, les trois premiers passages à :13 n'ont jamais été lancés
  par GitHub, minute changée pour réenregistrer le planning) ; `daily --check` décide sans installer ffmpeg ; un créneau commencé ne
  réessaie que les plateformes en échec, avec le même passage ; fenêtre de 3 h.
- **Le cron de GitHub ne se déclenche jamais dans ce dépôt** (0 run `schedule` depuis la
  création, problème de GitHub connu en 2026 au niveau du compte ; `workflow_dispatch` marche).
  Les workflows sont donc lancés par des **tâches planifiées Claude** (choix du propriétaire,
  2026-11-05) qui réveillent la session « Quran Words Daily – planificateur » (Sonnet, dépôt
  attaché, outils GitHub) : `prepare.yml` 02:41 Paris, `daily.yml` 07:12 et 19:12 Paris
  (`CRON_TZ=Europe/Paris`), `images.yml` 11:36 UTC ; chacune lance le workflow sur `main`,
  attend la fin, relance une fois en cas d'échec (sauf prepare) et résume. Une tâche lancée
  dans une session neuve n'a pas accès au dépôt (essai du 2026-11-05) : elles visent toutes
  cette session. Les crons des workflows restent en place si GitHub se remet à les lancer
  (un passage en double ne republie rien : le créneau est déjà dans l'état).
- État : `published.json` sur la branche `state` (créée au premier passage du workflow),
  commit après chaque créneau. Un passage compte comme publié dès qu'une plateforme l'a.
- Prévenir le propriétaire (`notify.py`, étape « Tell the owner », `issues: write`) :
  `daily` écrit `out/daily-report.json` (même s'il s'arrête, avec l'erreur). Échec → ticket
  « ⚠️ Publication quotidienne en échec » assigné au propriétaire et @mention (notification
  push dans l'app GitHub), commentaire s'il est déjà ouvert ; fermé par la prochaine
  publication réussie. Chaque publication met à jour le ticket épinglé « 📋 Légendes à copier
  (TikTok, YouTube) » : légendes des 4 dernières vidéos avec 5 hashtags, la limite de TikTok
  (`platforms.tiktok.max_hashtags`) ; aucune notification.
  Aussi dans le résumé du run. Dry-run : jamais le ticket d'échec, pas de TikTok (son seul
  test serait un vrai brouillon) ; entrée `now` du workflow pour simuler l'heure.

## Rendu

- Maquette validée : `docs/mockup/apercu-reel-93-2.png`, template `render/templates/reel.html.j2`.
- Zone sûre (boutons Reels/TikTok) : haut 250 px, bas 420 px, côtés 90 px.
- Deux calques PNG transparents sur le fond : `static` (voile, signature, crédits, fixe) et un
  `content` par ayah (référence, ayah, traduction, gloses) en fondu de 0,25 s.
- Fond (`sources/backgrounds.py`, `config/backgrounds.yaml`) : les `themes` comptent leurs mots
  dans la traduction (sans les [ajouts] du traducteur) × leur poids ; le meilleur thème qui a
  un fond gagne (égalité : le plus rare, listé d'abord), même passage → même fond ; aucun thème
  → `default`. Le manifeste garde les scores. Environ un tiers des passages ont un thème.
  Clips : recadrés en 9:16 autour de `focus`, adoucis (`soften` : flou 2,5 px, 15 % plus
  sombres, pour lire le texte sur l'eau vive), mis en boucle sans saut (les 2 dernières
  secondes fondues dans les premières), en cache. Signature et crédits : ombre serrée + ombre
  douce (lisibles sur un horizon clair). Débit vidéo plafonné à 6 Mb/s (un clip d'eau vive
  seul atteignait 22 Mb/s, 180 Mo la minute). Scènes générées (`sources/scenes/*.frag`,
  `vec3 scene(uv, t)`) : dessinées par WebGL dans Chromium lancé directement (pas Playwright,
  dont la surveillance réseau copie chaque image), 540×960, boucle de 30 s dont les 5 premières
  secondes fondent t + 30 dans t, ≈ 3–4 min la première fois (4 min 30 sur un runner
  GitHub, run #4 du 2026-11-05), puis en cache. Fichier temporaire propre à chaque processus.
  Sans aucun fond listé : boucle de 12 s générée (numpy) dans la palette de la
  maquette, ciel de nuit vers l'aube, étoiles qui scintillent, mise en cache.
- Hashtags (`render.hashtags`, déterministes) : `captions.brand`/`broad` et
  `platforms.*.max_hashtags` dans project.yaml, `content.reciter.hashtags`,
  `content.glosses.hashtags` (seulement si une glose est affichée), `hashtags:` de chaque série.
  Sourate : `name_simple`/`name_arabic` de Quran.com (`#SurahAliImran`, `#سورة_آل_عمران`).
  `caption.txt` = légende + tous les tags sur la dernière ligne ; `manifest.json` les liste ;
  `Reel.text(n)` garde les n premiers.
- Basmala (`content.basmala`) : `bismillah.mp3` d'EveryAyah (≈ 6 s), texte uthmani et
  traduction de 1:1 (Quran.com), premier segment du minutage ; écran sans référence ni numéro.
  Comptée dans le découpage (93 entière : 62 s). Pas pour la sourate 9 (`skip_surahs`) ni
  quand la vidéo commence à 1:1. Ligne arabe en tête de la légende.
- MP4 : H.264 High sans B-frames, AAC 48 kHz, `faststart`, **sans edit list** (`-use_editlist 0`) :
  Instagram Reels refuse les edit lists que ffmpeg écrit par défaut.
- Texte réduit automatiquement (`--k`) s'il dépasse la zone sûre ; avertissement sous 70 %.
  Les ayahs trop longues pour un écran seront découpées en segments synchronisés (timings par
  mot de QUL) ou évitées par le sélecteur.
- Mot glosé surligné dans l'ayah (or `#f6c86b`). La glose d'Ibn Qutaybah est en orthographe
  imla'i alors que le texte est uthmani : correspondance sur formes normalisées (diacritiques
  et marques coraniques supprimés, alif/ya unifiés, puis squelette sans alif + similarité).
  Ibn Qutaybah cite souvent plusieurs mots («وَاللَّيْلِ إِذَا سَجَى», «حَبِطَتْ أَعْمَالُهُمْ»).
  Par défaut on surligne toute la citation, particules de bord retirées («فَإِنْ عُثِرَ» →
  عُثِرَ) : deviner un seul mot s'est révélé faux une fois sur deux sur le corpus.
- Choix éditorial (validé, 3 mots depuis le 2026-11-05) : **1 à 3 mots** de la citation dans `config/glosses.yaml`,
  `"93:2": سجى` (comme la maquette), `"20:131": زهرة الحياة`, ou une liste pour deux gloses
  d'une même ayah `"2:2": [ريب, هدى]`. Diacritiques facultatifs, imla'i ou uthmani. Plus de
  3 mots → erreur ; mot absent de la citation → avertissement et citation entière gardée.
  Deux mots non contigus s'affichent « خَتَمَ … قُلُوبِهِمْ ». Clé sans guillemets (`93:2:`)
  acceptée (YAML la lit en base 60, on la décode).
- Sur le corpus complet (2 394 ayahs, 3 561 entrées) : 96 % des entrées s'ancrent, 2 301 ayahs
  affichent au moins une glose. Les autres (entrée rattachée à une autre ayah dans la source,
  citation à cheval sur deux ayahs « * ») sont omises, jamais devinées.

## Publications image (`images/`, docs/images.md)

- Formats (`config/images.yaml`) : `word` (carrousel de 3 images : mot en grand, ayah avec le
  mot surligné + Sahih International, sens du Muyassar mot pour mot) activé, une fois par
  jour à `time_utc` 11:30 ; `ayah` (une image) préparé, désactivé. 1080×1350, même charte que
  les reels, fond généré en CSS (aucune photo, aucun droit), pas d'audio (pas de Rights
  Manager). Gabarit `images/templates/card.html.j2` d'après `docs/mockup/images/cards.html`.
- Sélection déterministe, sans IA ni validation : candidats figés dans
  `config/image-candidates.yaml` par `quran-reels images build` (références seulement), à
  refaire après un changement de `glosses.yaml`, du gabarit ou de `min_scale`.
  1. une entrée de sens ancrée sur 1 à 3 mots liés (`glosses.max_words` ; comme les reels : mots de `glosses.yaml`,
     sinon citation sans particules de bord) ;
  2. glose montrée entière : texte complet (notes `[[…]]` retirées) ≤ 170 caractères et fini
     par une phrase, sinon écartée, jamais raccourcie ;
  3. image 2 = phrase complète : l'ayah grandit à la plus petite suite qui commence après une
     fin de phrase et en finit une (93:3 → 93:1-3, le serment commence en 93:1) ;
  4. chaque image lisible : texte réduit au plus à `min_scale` (0,7), sinon écartée ;
  5. `config/exclude.yaml` (lu à chaque passage, valeurs gardées en texte : `2:55` non cité
     n'est pas lu comme un nombre en base 60) : ayahs, plages, sourates ; une suite est écartée
     si une de ses ayahs l'est ;
  6. rang = hash(graine, tour, id) : ordre stable même si la liste change, pas de répétition
     avant la fin d'un tour (puis nouvel ordre), jamais deux jours de suite la même sourate
     quand une autre est disponible.
- Légende : modèle fixe (`images/caption.py`) ; Instagram garde les 5 premiers hashtags.
- Publication : URL publique exigée par Instagram (pas d'envoi binaire d'image) → les 3 images
  sont envoyées sur la Page Facebook **non publiées** (`published=false`), leur URL CDN
  (`?fields=images`, la plus grande) sert à Instagram (3 conteneurs `is_carousel_item`, un
  `CAROUSEL`, `media_publish`), puis post Facebook `/feed` avec `attached_media` dans l'ordre.
  Choisi plutôt que GitHub Pages : pas de JPEG commités chaque jour (≈ 160 Mo/an d'historique),
  pas d'attente de déploiement, images non publiques avant le post. Dry-run : rien n'est posté,
  photos supprimées.
- État : `images.json` sur la branche `state` (un post par jour : id, ayah, mot, résultats par
  plateforme) ; une plateforme en échec est réessayée avec les mêmes images pendant
  `window_hours` (6 h). Workflow `images.yml` toutes les heures.

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
- [x] Série « السبع آيات المنجيات » · [ ] d'autres séries avant la fin des thèmes (≈ 2 mois)
- [x] Fonds choisis selon le passage (scènes générées + 3 clips Pexels, PR #8 ; + 21 clips
      Pixabay validés)
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
- [x] Catalogue (docs/catalog.md, `catalog.yml`) · [x] Pages passé en « GitHub Actions » par le
      propriétaire, premier déploiement (run #1, 2026-11-05) · [x] libellé « Catalog » créé ·
      [x] premiers tickets appliqués (#19–#28) · [ ] #18 AbdulSamad en attente (basmala dans
      la 1re ayah, nom inconnu)
