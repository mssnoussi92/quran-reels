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
| Lecture | **Juz' 'Amma d'abord** (114 → 78), puis Al-Fatiha et 2 → 77, passages de `config/plan.yaml` |
| Thèmes | Ayat al-Kursi, les 7 versets « المنجيات », versets de du'a, versets du rizq… : listes **proposées par l'IA en PR, validées par le propriétaire** |
| Vendredi | **Les deux créneaux lisent Al-Kahf** (2 passages par vendredi, 38 au total, puis on recommence) |
| Texte arabe | Uthmani (Hafs), police **Amiri Quran** (OFL) |
| Traduction | **Sahih International** (anglais), créditée dans chaque légende |
| Mots difficiles | **Ibn Qutaybah, *Tafsir Gharib al-Qur'an*** (`ar-ghareeb-ibn-qutaybah`), glose en arabe |
| Récitateur | **Mishary Alafasy** par défaut, paramétrable (`config/project.yaml`) |
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

## Architecture

```
config/            project.yaml (choix éditoriaux), backgrounds.yaml (fonds et thèmes),
                   glosses.yaml (choix éditoriaux : 1 ou 2 mots surlignés par glose),
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
                   meta.py (client Graph, contrôle du jeton), facebook.py, instagram.py,
                   tiktok.py (brouillon dans la boîte TikTok, connexion OAuth)
  publish.py       `quran-reels publish|meta-check|tiktok-auth` : contrôle, publication, résumé
  gh_secrets.py    réécrit un secret Actions (refresh token TikTok) via gh + GH_SECRETS_TOKEN
  daily.py         `quran-reels daily` : créneaux dus maintenant → rendu → publication → état
  notify.py        `quran-reels notify` : tickets GitHub (alerte d'échec, légendes à copier)
  cli.py           `quran-reels ingest|render|passages|plan|series-check|calendar|daily|publish`
tests/             pytest, sans réseau
.github/workflows/ daily.yml (cron 2 créneaux × 3 essais ; ne publie rien tant que
                   schedule.yaml dit enabled: false ; état sur la branche `state`),
                   publish-test.yml (manuel : dry-run, ou publication réelle avec PUBLIER),
                   tiktok-auth.yml (manuel : échange du code TikTok → TIKTOK_REFRESH_TOKEN)
                   Runners épinglés sur `ubuntu-24.04` (même ffmpeg 6.1 que les tests ;
                   `ubuntu-latest` passe à 26.04), actions en versions Node.js 24.
docs/              site GitHub Pages (CGU, confidentialité, tiktok-login.html, tiktok-callback.html)
```

Flux : `selector` → `sources` (texte + traduction + gloses + audio par ayah + fond) →
`render` (une image par ayah, durée = durée du MP3 de l'ayah) → MP4 → `publishers` → `state`.

Commandes :

```bash
quran-reels ingest                  # texte, traduction, sourates, index des gloses (4 requêtes)
quran-reels ingest --all-glosses    # + toutes les gloses d'Ibn Qutaybah (2 394 requêtes, reprise)
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
- Gloses Ibn Qutaybah (tranché) : `tafsir.app` (Nuqayah). `/sources/sources.json` liste, pour
  `ghareeb-ibn-qutaybah`, les ayahs qui ont une entrée (`keys`, index global 1–6236 ;
  `keys_flag: 1`) : 2 394 ayahs. `/get.php?src=ghareeb-ibn-qutaybah&s=93&a=2&ver=1` renvoie
  `{"data": "﴿وَاللَّيْلِ إِذَا سَجَى﴾ إذا سكَن. …"}`. Stockage brut par sourate dans
  `.cache/tafsir.app/ghareeb-ibn-qutaybah/SSS.json`. À l'affichage : notes de l'éditeur
  `[[…]]` retirées, phrases entières seulement (`max_chars`), sinon la glose est omise.
  Absente de QUL et de Quran.com.
- Audio : EveryAyah, un MP3 par ayah, `https://everyayah.com/data/Alafasy_128kbps/SSSAAA.mp3`.
  Décodé en PCM 48 kHz pour un minutage exact à l'échantillon.
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
  refusé : 1858301 (canards sur le lac).

## Plateformes (voir docs/plateformes.md)

- Facebook + Instagram : publication auto via l'API Graph, app Meta en accès standard
  (comptes du propriétaire uniquement), sans validation Meta ni vérification d'entreprise.
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
  `evening` 19:30 (file `themes`), vendredi → file `kahf` pour les deux, `fallback` (une file
  finie passe à une autre). `enabled: false` tant que la première publication réelle n'est pas
  faite (activé le 2026-11-05). `published_by_hand` : passages publiés hors calendrier, sautés.
- Une file joue ses séries l'une après l'autre ; chaque créneau prend le premier passage pas
  encore publié. Série `repeat: true` (Al-Kahf) : recommence une fois finie.
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
  Clips : recadrés en 9:16 autour de `focus`, mis en boucle sans saut (les 2 dernières
  secondes fondues dans les premières), en cache. Scènes générées (`sources/scenes/*.frag`,
  `vec3 scene(uv, t)`) : dessinées par WebGL dans Chromium lancé directement (pas Playwright,
  dont la surveillance réseau copie chaque image), 540×960, boucle de 30 s dont les 5 premières
  secondes fondent t + 30 dans t, ≈ 3–4 min la première fois, puis en cache.
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
- Choix éditorial (validé) : **1 ou 2 mots** de la citation dans `config/glosses.yaml`,
  `"93:2": سجى` (comme la maquette), `"20:131": زهرة الحياة`, ou une liste pour deux gloses
  d'une même ayah `"2:2": [ريب, هدى]`. Diacritiques facultatifs, imla'i ou uthmani. Plus de
  2 mots → erreur ; mot absent de la citation → avertissement et citation entière gardée.
  Deux mots non contigus s'affichent « خَتَمَ … قُلُوبِهِمْ ». Clé sans guillemets (`93:2:`)
  acceptée (YAML la lit en base 60, on la décode).
- Sur le corpus complet (2 394 ayahs, 3 561 entrées) : 96 % des entrées s'ancrent, 2 301 ayahs
  affichent au moins une glose. Les autres (entrée rattachée à une autre ayah dans la source,
  citation à cheval sur deux ayahs « * ») sont omises, jamais devinées.

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
