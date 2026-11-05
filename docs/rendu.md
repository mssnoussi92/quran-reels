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
