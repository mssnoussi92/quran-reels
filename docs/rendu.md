# Rendu

*Déplacé de CLAUDE.md le 2026-11-05 (texte inchangé) ; CLAUDE.md en garde le résumé.*

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
- **Scènes animées** (2026-11-09) : la liste de qualité de Facebook a dit de 6:17 (nuit)
  « Votre reel est une image statique ». Mesure : médiane de l'écart moyen absolu entre deux
  images à 0,5 s d'intervalle (gris, 270×480, ffmpeg `tblend` + `signalstats`, YAVG) :
  6:17 0,42, 9:51 0,44 (nuit), 112:1-4 0,34 (aube), contre 2,90 pour 113:1-5 (forêt filmée,
  non signalée). Les scènes bougent maintenant au rythme d'un ciel filmé : nuit, deux couches
  de nuages (la proche plus rapide, roulée par un `fbm` de déformation) qui passent devant la
  lune, brume dans la vallée, étoiles qui scintillent plus vite ; aube, deux couches de nuages
  (jusque devant le soleil), rayons qui miroitent et tournent, halo qui respire, brume sur les
  dunes, ombres des nuages sur le sable, sable soufflé des crêtes ; mer, houle un peu plus
  rapide, nuages plus nombreux qui dérivent et changent de forme. Plus un **zoom lent** sur
  toute la vidéo (`scenes.push_in` de backgrounds.yaml : 8 % par minute, 12 % au plus), filtre
  `perspective` de ffmpeg (entre les pixels : un `crop`/`zoompan` avance par pixels entiers et
  tremble), appliqué à la boucle 540×960 avant l'agrandissement ; les calques de texte ne
  bougent pas. Les clips filmés n'ont pas de zoom. Mesuré sur des rendus locaux des mêmes
  passages (2026-11-09) : 6:17 nuit 0,42 → 2,60, 112:1-4 aube 0,34 → 2,77, 108:1-3 mer
  5,33 → 6,51 ; débit 2,0 → 3,1, 1,9 → 3,4 et 3,5 → 4,2 Mb/s (plafond 6). Mouvement d'ensemble
  (`backgrounds.motion`) des boucles : 4 à 5, loin des 34,9 du clip refusé (accélérés filmés
  gardés : jusqu'à 23,5). Coût : ≈ 6 à 9 min par boucle sur 4 vCPU (au lieu de 3 à 5), une
  fois par version du shader.
  Une scène modifiée change l'empreinte du shader, donc le nom du fichier en cache : la boucle
  est redessinée au premier rendu (le cache des Actions ne la sert plus) et les anciennes
  versions de cette scène sont effacées de `.cache/backgrounds/`.
  Sans aucun fond listé : boucle de 12 s générée (numpy) dans la palette de la
  maquette, ciel de nuit vers l'aube, étoiles qui scintillent, mise en cache.
- Hashtags (`render.hashtags`, déterministes) : `captions.brand`/`broad` et
  `platforms.*.max_hashtags` dans project.yaml, `content.reciter.hashtags`,
  `content.glosses.hashtags` (seulement si une glose est affichée), `hashtags:` de chaque série.
  Sourate : `name_simple`/`name_arabic` de Quran.com (`#SurahAliImran`, `#سورة_آل_عمران`).
  `caption.txt` = légende + tous les tags sur la dernière ligne ; `manifest.json` les liste ;
  `Reel.text(n)` garde les n premiers.
- Légende Facebook (`render.facebook_caption`, 2026-11-09) : ≤ 400 caractères hashtags compris
  (`platforms.facebook.max_caption_chars`), ni le texte arabe des ayahs ni la traduction (dans
  la vidéo) : série et sourate en arabe et en anglais (« The seven munjiyat verses · السبع آيات
  المنجيات · 2/7 », « Surah Al-An'am (6:17) · سورة الأنعام » ; titres toujours dans les deux
  langues, 2026-11-09), crédits sur une ligne (« Word meanings » seulement si la vidéo montre une
  glose, avec `glosses.label_en`), signature, les 8 premiers hashtags. Trop longue : des
  hashtags de la fin (en dernier recours, la signature puis la série ; jamais les crédits). Dans `manifest.json` (`captions.facebook`) ;
  `Reel.text_for("facebook")` la rend, les autres plateformes gardent `Reel.text(n)`.
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
