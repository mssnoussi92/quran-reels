# Plateformes : contraintes et mise en place

État vérifié en novembre 2026 dans la documentation officielle des plateformes.

## Facebook (Page) — automatique

- API : Reels Publishing API. `POST /{page-id}/video_reels` (start), upload binaire vers
  `rupload.facebook.com`, puis `upload_phase=finish&video_state=PUBLISHED`.
- Limite : 30 reels publiés par API sur 24 h glissantes.
- Jeton : Page access token (dérivé d'un jeton utilisateur longue durée → sans expiration).

## Instagram (compte Créateur relié à la Page) — automatique

- API : Instagram Graph API via Facebook Login. Conteneur `media_type=REELS`, upload
  résumable (`rupload.facebook.com/ig-api-upload/...`), puis `media_publish`.
- Limite : 50 publications API sur 24 h glissantes. Les conteneurs expirent après 24 h.
- Accès standard suffisant (l'app ne sert que les comptes du propriétaire) : pas d'App Review
  ni de vérification d'entreprise.
- Permissions : `instagram_basic`, `instagram_content_publish`, `pages_show_list`,
  `pages_read_engagement`, `pages_manage_posts`.

### État de la configuration Meta (2026-11-04)

- App Meta `Quran Words Daily Publisher` (ID `1673453344149749`), non publiée (mode développement,
  accès standard). Cas d'utilisation : « Tout gérer sur votre Page » + « Gérer les messages et les
  contenus sur Instagram » (configuration Facebook Login).
- Page `1494879297031390` · compte Instagram pro `17841475111287268`.
- La liaison Instagram ↔ Page doit être faite depuis la Page (Paramètres → Comptes liés). Une liaison
  faite seulement via l'Espace Comptes n'expose pas `instagram_business_account` à l'API.
- Secrets GitHub configurés : `META_PAGE_ID`, `META_PAGE_TOKEN` (jeton de Page, sans expiration,
  accès aux données jusqu'au 2027-02-02), `IG_USER_ID`.

### Publication (implémentée, `src/quran_reels/publishers/`)

- Un seul jeton, `META_PAGE_TOKEN` (jeton de Page), pour Facebook et Instagram. Envoyé dans
  l'en-tête `Authorization`, jamais dans l'URL ; les messages d'erreur ne contiennent jamais le
  jeton. Version de l'API Graph : `platforms.meta.graph_version` (`v24.0`).
- Contrôle à chaque exécution (`quran-reels meta-check`, et au début de `publish`) :
  `GET /debug_token` → jeton valide, de type PAGE, de la bonne Page, permissions requises,
  `data_access_expires_at` à plus de 14 jours (`platforms.meta.min_days_left`) sinon le job
  échoue avec la marche à suivre ; avertissement sous 30 jours. Puis
  `GET /{page}?fields=instagram_business_account` doit renvoyer `IG_USER_ID`.
- Facebook : `video_reels` start → upload `rupload.facebook.com/video-upload/…` (en-têtes
  `offset`, `file_size`) → finish avec `video_state=PUBLISHED`, ou `DRAFT` en dry-run → attente
  du traitement (`GET /{video_id}?fields=status`).
- Instagram : `POST /{ig}/media` (`media_type=REELS`, `upload_type=resumable`, légende,
  `thumb_offset` = milieu de la première ayah glosée) → upload `rupload…/ig-api-upload/…` →
  attente `status_code=FINISHED` → contrôle du quota (`content_publishing_limit`) →
  `media_publish`. En dry-run on s'arrête avant `media_publish`.
- Légende : celle du rendu (`caption.txt`), raccourcie automatiquement sous 2 200 caractères
  (l'arabe d'abord, puis la traduction ; les crédits restent).
- Résultats : `out/<passage>/publish.json` et résumé sur la page de l'exécution GitHub.

### Tester depuis le téléphone : workflow `publish-test`

Actions → **publish-test** → Run workflow :
1. `mode: dry-run`, passage `93` → vérifier dans Meta Business Suite → Contenu → Brouillons
   (reel Facebook non publié) ; le conteneur Instagram n'est visible nulle part et disparaît
   après 24 h. Supprimer le brouillon ensuite.
2. `mode: publish`, `confirm: PUBLIER` → publication réelle sur la Page et Instagram.

Le bouton « Run workflow » n'apparaît que pour un workflow présent sur `main`.

## TikTok — brouillon puis automatique après audit

- API : Content Posting API (`open.tiktokapis.com`).
- Sans audit : la publication directe est forcée en `SELF_ONLY` et le compte doit être privé.
  → On utilise `MEDIA_UPLOAD` : la vidéo arrive dans la boîte TikTok et le propriétaire la
  publie à la main dans les 24 h.
- L'audit demande un site, des CGU et une politique de confidentialité.
- Jeton d'accès 24 h, refresh token à faire tourner et à stocker.

## YouTube Shorts — manuel puis automatique après audit

- API : YouTube Data API v3, `videos.insert` (1 600 unités, quota par défaut 10 000/jour,
  donc environ 6 uploads par jour).
- Projets non vérifiés créés après le 28/07/2020 : vidéos verrouillées en privé.
  → Demander l'audit (formulaire YouTube API Services) dès que le projet Google Cloud existe.
  En attendant, le MP4 du jour est mis à disposition et mis en ligne à la main.
- Shorts : vertical, 3 min maximum.

## Format vidéo commun

MP4 H.264 + AAC, 1080×1920, 30 i/s, 20–90 s. Zone sûre : haut 250 px, bas 420 px, côtés 90 px.
