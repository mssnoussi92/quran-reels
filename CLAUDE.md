# Quran Words Daily — contexte projet

Pipeline open source qui produit chaque jour un reel vertical (1080×1920) d'un passage du Coran
et le publie sur Facebook, Instagram, TikTok et YouTube Shorts.

Comptes : Facebook `quranwordsdaily` · Instagram / TikTok / YouTube `quran_words_daily` ·
e-mail du projet `quranwordsdaily@gmail.com`. Le propriétaire travaille depuis son téléphone
(pas de PC) : tout doit tourner dans le cloud (session Claude, GitHub Actions).

## Décisions validées

| Sujet | Choix |
|---|---|
| Format | **Passage complet** (2–5 versets qui forment un sens), 20–90 s |
| Texte arabe | Uthmani (Hafs), police **Amiri Quran** (OFL) |
| Traduction | **Sahih International** (anglais), créditée dans chaque légende |
| Mots difficiles | **Ibn Qutaybah, *Tafsir Gharib al-Qur'an*** (`ar-ghareeb-ibn-qutaybah`), glose en arabe |
| Récitateur | **Mishary Alafasy** par défaut, paramétrable (`config/project.yaml`) |
| Fond | vidéos nature libres (Pexels/Pixabay), **sans personnes ni animaux** |
| Exécution | GitHub Actions (dépôt public → gratuit), migrable sur le homelab (Docker) |
| Comptes pro | Page Facebook + Instagram en type **Créateur**, reliés |
| Signature | **@quran_words_daily** sur chaque image, dans la zone sûre (repartages) |

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
config/            project.yaml (choix éditoriaux), backgrounds.yaml (fonds sélectionnés),
                   glosses.yaml (choix éditoriaux : 1 ou 2 mots surlignés par glose)
src/quran_reels/
  models.py        AyahRef, Ayah, GlossEntry, WordGloss, Passage, Reel, PublishResult
  config.py        chargement de config/, chemins (.cache/, out/)
  arabic.py        normalisation uthmani/imla'i, ancrage d'une glose sur un mot de l'ayah
  ingest.py        `quran-reels ingest` : jeux de données → .cache/
  passage.py       assemble un passage : texte + traduction + gloses ancrées + audio
  sources/         quran_com (texte, sourates, traduction), tafsir_app (gloses),
                   everyayah (audio), backgrounds (clip ou fond provisoire généré), http
  selector/        quel passage aujourd'hui (calendrier, séries, historique)
  render/          frames.py (template HTML → PNG, Chromium/Playwright),
                   video.py (minutage audio + ffmpeg → MP4), __init__ (orchestration)
  publishers/      un adaptateur par plateforme, interface commune `Publisher`
  state/           ce qui a été publié où (évite doublons, reprise après échec)
  cli.py           `quran-reels ingest|render|publish|run`
tests/             pytest, sans réseau
.github/workflows/ daily.yml (lancement manuel avec un passage → rendu + artefact)
```

Flux : `selector` → `sources` (texte + traduction + gloses + audio par ayah + fond) →
`render` (une image par ayah, durée = durée du MP3 de l'ayah) → MP4 → `publishers` → `state`.

Commandes :

```bash
quran-reels ingest                  # texte, traduction, sourates, index des gloses (4 requêtes)
quran-reels ingest --all-glosses    # + toutes les gloses d'Ibn Qutaybah (2 394 requêtes, reprise)
quran-reels render 93:1-3           # → out/093_001-003.mp4 (complète le cache au besoin)
```

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
- Fonds : l'**émission de nouvelles clés API Pexels est en pause** (nov. 2026). On utilise donc
  une liste sélectionnée à la main (`config/backgrounds.yaml`) d'URL directes de fichiers
  Pexels/Pixabay, ce qui ne demande pas de clé.

## Plateformes (voir docs/plateformes.md)

- Facebook + Instagram : publication auto via l'API Graph, app Meta en accès standard
  (comptes du propriétaire uniquement), sans validation Meta ni vérification d'entreprise.
- TikTok : sans audit, la publication directe est forcée en privé → mode **brouillon**
  (MEDIA_UPLOAD vers la boîte TikTok) en attendant l'audit.
- YouTube : sans audit, les uploads API sont verrouillés en privé → **upload manuel** du MP4
  en attendant ; demander l'audit tôt. Quota ≈ 6 uploads/jour.

## Rendu

- Maquette validée : `docs/mockup/apercu-reel-93-2.png`, template `render/templates/reel.html.j2`.
- Zone sûre (boutons Reels/TikTok) : haut 250 px, bas 420 px, côtés 90 px.
- Deux calques PNG transparents sur le fond : `static` (voile, signature, crédits, fixe) et un
  `content` par ayah (référence, ayah, traduction, gloses) en fondu de 0,25 s. Fond provisoire
  tant que `backgrounds.yaml` est vide : boucle de 12 s générée (numpy) dans la palette de la
  maquette, ciel de nuit vers l'aube, étoiles qui scintillent, mise en cache.
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

GitHub Actions secrets : `META_PAGE_ID`, `META_PAGE_TOKEN`, `IG_USER_ID`, `TIKTOK_*`,
`YOUTUBE_*`. Le refresh token TikTok tourne : prévoir sa mise à jour (`gh secret set`).

## État

- [x] Comptes créés (Gmail, Page FB, IG Créateur reliés, TikTok, YouTube)
- [x] Squelette du dépôt, polices, maquette
- [ ] Environnement cloud `quran-reels` (accès réseau Custom)
- [x] Ingestion des données + rendu v1 avec audio (`quran-reels render 93:1-3`, fond provisoire)
- [ ] App Meta + publication FB/IG
- [ ] App TikTok (brouillons) · demande d'audit YouTube
- [ ] Workflow quotidien
