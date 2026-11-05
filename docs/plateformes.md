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
- **Mode développement = posts invisibles pour le public** (constaté le 2026-11-05 : le reel 114,
  partagé par Messenger, est « non disponible » pour un autre compte, et la Page ne lui montre
  aucun reel). Meta (*App Modes*) : « Any data generated while an app is in Development mode,
  such as test posts, can only be seen by role users », visible de tous dès le passage en Live,
  sans republier. Passer l'app en **Live** : Paramètres → Général (URL de confidentialité
  `https://mssnoussi92.github.io/quran-reels/privacy.html`, CGU `…/terms.html`, suppression des
  données : la même page de confidentialité, icône `assets/brand/icon-1024.jpg`, catégorie, e-mail
  de contact), puis « Publier ». Pas d'App Review ni de vérification d'entreprise : l'accès
  standard reste valable en Live pour les personnes qui ont un rôle sur l'app (le propriétaire,
  donc le jeton de Page actuel continue de marcher).
- Page `1494879297031390` · compte Instagram pro `17841475111287268`.
- La liaison Instagram ↔ Page doit être faite depuis la Page (Paramètres → Comptes liés). Une liaison
  faite seulement via l'Espace Comptes n'expose pas `instagram_business_account` à l'API.
- Secrets GitHub configurés : `META_PAGE_ID`, `META_PAGE_TOKEN` (jeton de Page, sans expiration,
  accès aux données jusqu'au 2027-02-02), `IG_USER_ID`.
- **Dry-run du 2026-11-04 (run #1) : échec au contrôle**, `META_PAGE_TOKEN` contient un jeton
  **USER**, pas un jeton de Page. À refaire : jeton utilisateur prolongé → `me/accounts` →
  `access_token` de la Page 1494879297031390 (le débogueur doit afficher Type : Page,
  Expiration : Jamais) → mettre à jour le secret.

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
  `offset`, `file_size`) → finish avec `video_state=DRAFT` (toujours, depuis le 2026-11-05) →
  attente du traitement (`GET /{video_id}?fields=status`) → vérification des droits (ci-dessous)
  → finish à nouveau avec `video_state=PUBLISHED` → attente de la mise en ligne. En dry-run on
  s'arrête avant : le brouillon reste dans Meta Business Suite → Contenu → Brouillons.
- Instagram : `POST /{ig}/media` (`media_type=REELS`, `upload_type=resumable`, légende,
  `thumb_offset` = milieu de la première ayah glosée) → upload `rupload…/ig-api-upload/…` →
  attente `status_code=FINISHED` → vérification des droits (ci-dessous) → contrôle du quota
  (`content_publishing_limit`) → `media_publish`. En dry-run on s'arrête avant `media_publish`.
- **Constaté (2026-11-04, runs #4–#9) :** l'upload Instagram répond presque toujours
  `400 ProcessingFailedError`. Parfois Instagram a quand même la vidéo (run #7 : conteneur
  `FINISHED` aussitôt), parfois le conteneur reste `IN_PROGRESS` pour de bon (run #9 : encore
  après 15 min). Après cette erreur, on lit donc le conteneur : `ERROR` → échec ; sinon on attend
  4 min, puis on abandonne ce conteneur et on renvoie la vidéo dans un nouveau (3 essais au
  plus). Un conteneur non publié ne coûte rien : rien n'est posté, il expire après 24 h.
  Le MP4 est aussi encodé sans edit list ni B-frames, AAC 128 kb/s (spécifications Reels).
- **Dry-runs validés :** Facebook (run #3, brouillon) et Instagram (run #7, conteneur prêt).
- **Première publication réelle (2026-11-05, publish-test run #12) :** 93:1-11 publiée sur
  Facebook et Instagram. Instagram : premier conteneur resté `IN_PROGRESS` après l'erreur
  d'upload, abandonné au bout de 4 min ; publié depuis le deuxième. Un seul post.
- **Premier reel Facebook coupé (2026-11-05)** : Rights Manager a reconnu l'enregistrement
  d'Alafasy (fichiers EveryAyah, sans licence connue). D'où la vérification ci-dessous.
- Légende : celle du rendu (`caption.txt`), raccourcie automatiquement sous 2 200 caractères
  (l'arabe d'abord, puis la traduction ; les crédits restent).
- Résultats : `out/<passage>/publish.json` et résumé sur la page de l'exécution GitHub.

### Vérification des droits avant publication (`publishers/rights.py`)

Meta compare chaque vidéo à son catalogue Rights Manager. On lit sa réponse **avant** de
publier, sur la vidéo non publiée :

| | Objet non publié | Requête | Réponse |
|---|---|---|---|
| Facebook | brouillon de reel | `GET /{video-id}?fields=copyright_check_information` | `{"status": {"status": "complete", "matches_found": false}, "copyright_matches": [...]}` |
| Instagram | conteneur `FINISHED` | `GET /{container-id}?fields=copyright_check_status` | `{"status": "complete", "matches_found": false}` |

- Interrogé toutes les 10 s jusqu'à `complete` (ou `completed`, les deux orthographes existent
  dans la documentation), 10 min au plus (`platforms.meta.rights_timeout`).
- **On publie seulement si toutes les plateformes Meta répondent `complete` avec
  `matches_found: false`.** Sinon (correspondance, `error`, `not_eligible`, pas de réponse à
  temps, champ inconnu de l'API) : rien n'est publié, nulle part, TikTok compris ; statut
  `blocked`. Le ticket d'échec donne le passage et le titulaire que Meta indique
  (`copyright_matches` : `content_title`, `author`, `owner_copyright_policy.name`, type de
  segment audio/vidéo ; Instagram ne donne le détail qu'après publication). Le créneau n'est pas
  réessayé (le même enregistrement serait refusé) et le passage reste en tête de sa file :
  changer de récitateur.
- Le brouillon Facebook d'un passage bloqué reste dans Meta Business Suite (Contenu →
  Brouillons) ; le conteneur Instagram expire seul après 24 h.
- Documentation : Meta documente ces champs pour Instagram ([Copyright Detection](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/copyright-detection),
  [IG Container](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-container)) ;
  pour Facebook, `copyright_check_information` sur la vidéo n'est décrit que par des tiers.
  La publication d'un brouillon Facebook par un second `finish` avec `video_state=PUBLISHED`
  n'est pas documentée non plus : à confirmer à la première publication réelle (en cas
  d'échec, le brouillon vérifié reste publiable à la main).
- **Dry-run du 2026-11-05, sourate 93 entière (publish-test run #14) :**

  | Récitateur | Facebook (brouillon) | Instagram (conteneur) |
  |---|---|---|
  | Alafasy (témoin) | complete, aucune correspondance (0 s) | complete, aucune correspondance (12 s) |
  | Hudhaifi | complete, aucune correspondance (0 s) | complete, aucune correspondance (12 s) |
  | Ayyub | complete, aucune correspondance (0 s) | pas de vérification : 3 conteneurs restés `IN_PROGRESS` |
  | Akhdar | complete, aucune correspondance (0 s) | pas de vérification : 3 conteneurs restés `IN_PROGRESS` |

  **Le témoin échoue** : le même enregistrement d'Alafasy a été reconnu par Rights Manager après
  publication le matin même (reel 93:1-11 coupé sur Facebook), mais les deux vérifications
  avant publication répondent « aucune correspondance ». Facebook répond en 0 s : le champ du
  brouillon ne reflète pas une analyse. La vérification reste en place (elle ne coûte qu'une
  minute et peut attraper d'autres cas), mais **elle ne garantit rien** : la protection réelle
  est le choix d'un enregistrement sous licence (Complexe du Roi Fahd). Piste : relire
  `copyright_check_information` sur la vidéo **publiée** pendant les minutes qui suivent, et
  retirer le post + alerter en cas de correspondance.

### Tester depuis le téléphone : workflow `publish-test`

Actions → **publish-test** → Run workflow :
1. `mode: dry-run`, passage `93` → vérifier dans Meta Business Suite → Contenu → Brouillons
   (reel Facebook non publié) ; le conteneur Instagram n'est visible nulle part et disparaît
   après 24 h. Supprimer le brouillon ensuite.
2. `mode: publish`, `confirm: PUBLIER` → publication réelle sur la Page et Instagram.
3. `reciters: hudhaifi,ayyoub,akhdar` (dry-run seulement) : le même passage avec plusieurs
   récitateurs, l'un après l'autre ; le résumé du run donne, pour chacun, la réponse de Meta
   sur les droits (colonne « Droits »).

Le bouton « Run workflow » n'apparaît que pour un workflow présent sur `main`.

## TikTok — brouillon puis automatique après audit

- API : Content Posting API (`open.tiktokapis.com`).
- Sans audit : la publication directe est forcée en `SELF_ONLY` et le compte doit être privé.
  → On utilise `MEDIA_UPLOAD` : la vidéo arrive dans la boîte TikTok et le propriétaire la
  publie à la main dans les 24 h.
- L'audit demande un site, des CGU et une politique de confidentialité.
- **Limite importante :** les App Review Guidelines refusent les apps « à usage privé ou
  personnel ». Notre outil ne publie que sur notre propre compte, donc une demande de mise en
  production serait probablement refusée. Plan : rester en **Sandbox** (utilisateur test
  `quran_words_daily`, scopes `user.info.basic` + `video.upload`) et envoyer des brouillons
  dans la boîte TikTok. **À vérifier en test :** que l'upload vers la boîte fonctionne en
  Sandbox. Sinon : MP4 du jour publié à la main (artefact GitHub Actions), ou service tiers
  déjà audité (payant).
- Site requis (GitHub Pages, dossier `docs/`) : préfixe d'URL
  `https://mssnoussi92.github.io/quran-reels/` vérifié par fichier de signature.
- Jeton d'accès 24 h, refresh token à faire tourner et à stocker.
- **État (2026-11-04) :** app « Quran Words Daily Publisher » créée, URL vérifiée, Sandbox
  `qwd-sandbox` avec l'utilisateur test `quran_words_daily`. Secrets GitHub : `TIKTOK_CLIENT_KEY`,
  `TIKTOK_CLIENT_SECRET` (identifiants **Sandbox**). Production non soumise.

### Publication TikTok (implémentée, `publishers/tiktok.py`, mode brouillon)

- À chaque publication : `POST /v2/oauth/token/` (`grant_type=refresh_token`) → jeton d'accès
  24 h. Si TikTok renvoie un **nouveau refresh token**, il remplace aussitôt le secret
  `TIKTOK_REFRESH_TOKEN` (avant l'envoi de la vidéo), via `gh secret set` et `GH_SECRETS_TOKEN`.
  Les jetons obtenus en cours de route sont masqués dans les logs (`::add-mask::`).
- Envoi : `POST /v2/post/publish/inbox/video/init/` (`FILE_UPLOAD`, un seul morceau jusqu'à
  64 Mo, sinon morceaux de 10 Mo) → `PUT` de la vidéo (`Content-Range`) →
  `POST /v2/post/publish/status/fetch/` jusqu'à `SEND_TO_USER_INBOX`. Le propriétaire reçoit
  une notification et termine la publication dans l'app (légende : `caption.txt` de l'artefact).
  TikTok garde au plus 5 brouillons en attente par 24 h.
- Dry-run = même envoi dans la boîte : rien n'est jamais public en mode brouillon.
- **Vérifié le 2026-11-04 :** connexion `tiktok-auth` OK (compte `quran_words_daily`, scopes
  `user.info.basic,video.upload`, refresh token enregistré par `GH_SECRETS_TOKEN`), et l'envoi
  dans la boîte **fonctionne en Sandbox** (publish-test run #8 → `SEND_TO_USER_INBOX`).

### Connexion TikTok (une fois, puis ≈ 1 fois par an)

1. Ouvrir `https://mssnoussi92.github.io/quran-reels/tiktok-login.html`, coller la *client key*
   (TikTok for Developers → app → Sandbox → Credentials ; c'est un identifiant public, la page
   ne l'enregistre ni ne l'envoie ailleurs qu'à TikTok) → Continue to TikTok.
   Pourquoi une page et pas un workflow : les logs Actions d'un dépôt public sont publics.
2. Se connecter avec `quran_words_daily`, accepter → `tiktok-callback.html` affiche le code.
3. Dans les minutes qui suivent : Actions → **tiktok-auth** → coller le code → Run. Le code est
   lu dans le fichier d'événement (jamais affiché), échangé avec `TIKTOK_CLIENT_SECRET`, et le
   refresh token est enregistré dans `TIKTOK_REFRESH_TOKEN`. Le résumé affiche le compte.
4. Tester : **publish-test**, plateforme `tiktok`.

`quran-reels tiktok-auth-url` donne la même adresse en ligne de commande (homelab).

### `GH_SECRETS_TOKEN` (jeton fin GitHub, pour écrire le secret TikTok)

github.com → photo de profil → Settings → Developer settings → Personal access tokens →
**Fine-grained tokens** → Generate new token :
- Token name `quran-reels-secrets` ; Expiration : la plus longue proposée (noter la date) ;
- Resource owner `mssnoussi92` ; Repository access : **Only select repositories** → `quran-reels` ;
- Permissions → Repository permissions → **Secrets : Read and write** (Metadata : lecture seule,
  ajouté d'office). Rien d'autre.
- Generate token → copier (affiché une seule fois) → dépôt → Settings → Secrets and variables →
  Actions → New repository secret → nom `GH_SECRETS_TOKEN`.

## YouTube Shorts — manuel puis automatique après audit

- API : YouTube Data API v3, `videos.insert` (1 600 unités, quota par défaut 10 000/jour,
  donc environ 6 uploads par jour).
- Projets non vérifiés créés après le 28/07/2020 : vidéos verrouillées en privé.
  → Demander l'audit (formulaire YouTube API Services) dès que le projet Google Cloud existe.
  En attendant, le MP4 du jour est mis à disposition et mis en ligne à la main.
- Shorts : vertical, 3 min maximum.
- OAuth Google : un projet en statut **« Test »** reçoit des refresh tokens qui expirent au bout
  de 7 jours. Il faut passer l'écran de consentement en **« En production »** (écran « app non
  validée » accepté pour un usage personnel) pour garder un refresh token durable.

## Format vidéo commun

MP4 H.264 + AAC, 1080×1920, 30 i/s, 20–90 s. Zone sûre : haut 250 px, bas 420 px, côtés 90 px.
