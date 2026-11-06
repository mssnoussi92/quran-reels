# Sources de données

*Déplacé de CLAUDE.md le 2026-11-05 (texte inchangé) ; CLAUDE.md en garde le résumé.*

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
  **AbdulSamad** (`AbdulSamad_64kbps_QuranExplorer.Com`, ticket #18) **non retenu** (ticket
  fermé par le propriétaire, 2026-11-06 ; il reste parmi les candidats du catalogue) : le
  fichier de la 1re ayah de chaque sourate commence par ≈ 6–9 s de récitation puis une pause
  avant l'ayah (112:1 16,8 s, 112:2 5,9 s ; 114, 93, 18 pareil) : c'est la basmala
  (reconnaissance, 2026-11-06 : « بسم الله الرحمن الرحيم » avant la pause, puis l'ayah) ;
  avec la basmala ajoutée par le pipeline, elle serait récitée deux fois et le texte de
  l'ayah 1 affiché pendant ; nom complet du récitateur inconnu (crédit) ; très lent (2:255 :
  94 s seule) ; encodages mêlés (64 kb/s, VBR avec en-tête Xing, d'autres débits sur 25
  fichiers tirés) : durées par la taille peu fiables ; son `bismillah.mp3` est encodé à part
  (22 kHz, 40 kb/s).
- **Husary** (`husary`, EveryAyah `Husary_128kbps`, Mahmoud Khalil Al-Husary, ticket #32) :
  **en essai**, dans `content.reciters` mais pas dans la rotation. 128 kb/s constants (40
  fichiers sur 40), `bismillah.mp3` = son 1:1 (5,1 s), fichiers de 1re ayah sans basmala
  (reconnaissance) ; allure proche d'Alafasy (2:255 : 61 s ; 112 entière : 31,7 s avec la
  basmala). Reel 112 rendu et vérifié par reconnaissance (basmala, début de chaque ayah, fin
  sans mot de trop). Prochaine étape : premier reel sur Facebook seul (skill `test-reciter`).
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
