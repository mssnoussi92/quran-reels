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
config/            project.yaml (choix éditoriaux), backgrounds.yaml (fonds sélectionnés)
src/quran_reels/
  models.py        AyahRef, Ayah, WordGloss, Passage, Reel, PublishResult
  sources/         une interface par source (texte, traduction, gloses, audio, fonds)
  selector/        quel passage aujourd'hui (calendrier, séries, historique)
  render/          template HTML → PNG (Chromium/Playwright) + ffmpeg → MP4
  publishers/      un adaptateur par plateforme, interface commune `Publisher`
  state/           ce qui a été publié où (évite doublons, reprise après échec)
  cli.py           `quran-reels render|publish|run`
.github/workflows/ daily.yml
```

Flux : `selector` → `sources` (texte + traduction + gloses + audio par ayah + fond) →
`render` (une image par ayah, durée = durée du MP3 de l'ayah) → MP4 → `publishers` → `state`.

## Sources de données

- Texte, traduction, tafsir : API Quran.com / Quran Foundation (`*.quran.com`,
  `*.quran.foundation`) ou QUL (`qul.tarteel.ai`). Gloses Ibn Qutaybah : voir `tafsir.app`.
  **À trancher :** la source en masse de l'édition Ibn Qutaybah.
- Audio : EveryAyah, un MP3 par ayah, `https://everyayah.com/data/Alafasy_128kbps/SSSAAA.mp3`.
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
- Taille du texte arabe à ajuster selon la longueur de l'ayah. Les ayahs trop longues pour un écran
  seront découpées en segments synchronisés (timings par mot de QUL) ou évitées par le sélecteur.
- Mot glosé surligné dans l'ayah (or `#f6c86b`). La glose d'Ibn Qutaybah est en orthographe
  imla'i alors que le texte est uthmani : normaliser avant correspondance (supprimer
  diacritiques et marques coraniques, unifier alif/ya).

## Secrets (jamais dans le code ni dans la conversation)

GitHub Actions secrets : `META_PAGE_ID`, `META_PAGE_TOKEN`, `IG_USER_ID`, `TIKTOK_*`,
`YOUTUBE_*`. Le refresh token TikTok tourne : prévoir sa mise à jour (`gh secret set`).

Jeton de Page Meta : expiration « Jamais », mais **l'accès aux données expire le 2027-02-02**
(90 jours). Pour le renouveler : explorateur Graph → jeton utilisateur → prolonger →
`me/accounts` → nouveau `META_PAGE_TOKEN`. Le publisher Meta doit lire
`data_access_expires_at` via `GET /debug_token` à chaque exécution et faire échouer le job
(message clair) à moins de 14 jours de l'échéance.

## État

- [x] Comptes créés (Gmail, Page FB, IG Créateur reliés, TikTok, YouTube)
- [x] Squelette du dépôt, polices, maquette
- [ ] Environnement cloud `quran-reels` (accès réseau Custom)
- [ ] Ingestion des données + rendu v1 avec audio
- [ ] App Meta + publication FB/IG
- [ ] App TikTok (brouillons) · demande d'audit YouTube
- [ ] Workflow quotidien
