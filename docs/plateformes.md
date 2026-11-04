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
