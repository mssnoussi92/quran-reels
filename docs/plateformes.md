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
  `pages_read_engagement`, `pages_manage_posts` (exigées par `meta-check`) ; en plus sur le jeton
  depuis le 2026-11-15 : `pages_manage_engagement` et `pages_read_user_content` (couverture des
  reels Facebook), `instagram_manage_contents` (retrait d'un reel Instagram rendu muet),
  `read_insights` et `instagram_manage_insights` (statistiques de la Page et du compte
  Instagram, pour un futur workflow `insights`).

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
  donc le jeton de Page actuel continue de marcher). **Fait le 2026-11-05** ; vérifié aussitôt
  sans compte : `facebook.com/plugins/video.php?href=…/reel/1455267246753851/` renvoie la vidéo
  (41 s), lisible depuis le CDN.
- Page `1494879297031390` · compte Instagram pro `17841475111287268`.
- La liaison Instagram ↔ Page doit être faite depuis la Page (Paramètres → Comptes liés). Une liaison
  faite seulement via l'Espace Comptes n'expose pas `instagram_business_account` à l'API.
- Secrets GitHub configurés : `META_PAGE_ID`, `META_PAGE_TOKEN` (jeton de Page, sans expiration,
  accès aux données jusqu'au 2027-02-13, refait le 2026-11-15), `IG_USER_ID`.

### Renouveler le jeton de Page (fait depuis le téléphone le 2026-11-15)

Le jeton est coupé quand le propriétaire change son mot de passe Facebook (2026-11-15 : « The
session has been invalidated because the user changed their password », code 190, subcode 460 ;
le Word of the day a échoué deux fois avant le nouveau jeton) et 90 jours après sa création
(accès aux données). Dans Chrome en « Version pour ordinateur » :

1. `developers.facebook.com/tools/explorer` → Application Meta : **Quran Words Daily Publisher**
   → Utilisateur ou Page : **Token utilisateur** → ajouter les permissions de la liste ci-dessus.
   Une permission absente de la liste n'est pas dans les cas d'utilisation de l'app :
   `developers.facebook.com/apps/1673453344149749/` → Cas d'utilisation → « Tout gérer sur votre
   Page » / « Gérer les messages et le contenu sur Instagram » → Personnaliser → Ajouter, puis
   recharger l'explorateur.
2. **Generate Access Token** → cocher la Page Quran Words Daily et le compte Instagram.
3. ⓘ à côté du jeton → outil de jeton d'accès → **Étendre le jeton d'accès** → copier le jeton
   utilisateur longue durée (le débogueur dit « Expiration : dans environ 2 mois »).
4. Le coller dans le champ du jeton de l'explorateur → requête
   `me/accounts?fields=id,name,access_token` → copier l'`access_token` de la Page
   1494879297031390.
5. Débogueur (`developers.facebook.com/tools/debug/accesstoken`) : **Type : Page**, **Expiration :
   Jamais**, accès aux données à 90 jours, portées complètes.
6. GitHub → Settings → Secrets and variables → Actions → `META_PAGE_TOKEN` → Update (jamais dans
   une conversation). Puis relancer `images.yml` (dans sa fenêtre de 6 h) ou attendre le run
   suivant : le contrôle du jeton se fait au début.
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
  s'arrête avant, et le brouillon est supprimé une fois le conteneur Instagram prêt (depuis le
  2026-11-06 ; avant, il restait dans Meta Business Suite → Contenu → Brouillons).
- Couverture Facebook (2026-11-06) : après la publication, `POST /{video}/thumbnails`
  (`source` = l'image à `thumb_offset`, la même qu'Instagram ; `is_preferred=true`) ; sinon
  Facebook choisit lui-même. Permissions `pages_manage_engagement` et `pages_read_user_content` ;
  sans elles, un avertissement et rien d'autre. Le dry-run l'essaie sur le brouillon : posée
  sur le brouillon de 114 (publish-test run #25, 2026-11-06), le jeton actuel suffit.
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
- **2026-11-13, budget d'appels épuisé** : le soir de la reprise (Al-Kahf 18:15-16, run #48),
  six conteneurs en deux essais sont restés `IN_PROGRESS` ; chacun était relu toutes les 10 s,
  soit environ 300 appels en 35 min, au-delà de la limite horaire de l'app Meta (environ 200
  appels par heure pour une app à un seul utilisateur). La relance du planificateur (run #49)
  a été refusée dès le contrôle du jeton : « (#4) Application request limit reached » (Facebook
  et TikTok étaient déjà passés). Depuis, un conteneur est relu toutes les 30 s, et l'attente
  s'arrête quand Meta annonce 75 % du budget utilisé (en-tête `X-App-Usage`, `Graph.usage`) :
  Instagram échoue proprement, sans nouveau conteneur, et le run suivant a encore des appels.
  Ce refus se lève en moins d'une heure (fenêtre glissante).
- **2026-11-06** : le matin (run #10), trois conteneurs de suite sont restés `IN_PROGRESS` ;
  Instagram n'est sorti qu'au run suivant. Les conteneurs mis de côté restent désormais
  surveillés aux essais suivants : le premier prêt est publié. **Essayé et abandonné** : faire
  prendre à Instagram la copie Facebook du brouillon (`video_url` = `GET /{video}?fields=source`,
  publish-test run #24) : cette copie est en 720×1280 à 201 kb/s, et Instagram l'a refusée
  (conteneur `ERROR`, code 2207076).
  Le MP4 est aussi encodé sans edit list ni B-frames, AAC 128 kb/s (spécifications Reels).
- **Dry-runs validés :** Facebook (run #3, brouillon) et Instagram (run #7, conteneur prêt).
- **Première publication réelle (2026-11-05, publish-test run #12) :** 93:1-11 publiée sur
  Facebook et Instagram. Instagram : premier conteneur resté `IN_PROGRESS` après l'erreur
  d'upload, abandonné au bout de 4 min ; publié depuis le deuxième. Un seul post.
- **Premier reel Facebook coupé (2026-11-05)** : Rights Manager a reconnu l'enregistrement
  d'Alafasy (fichiers EveryAyah, sans licence connue). D'où la vérification ci-dessous.
- Légende : celle du rendu (`caption.txt`), raccourcie automatiquement sous 2 200 caractères
  (l'arabe d'abord, puis la traduction ; les crédits restent).
- **Facebook : légende courte** (2026-11-09) : sa liste de qualité a refusé celle de 6:17
  (« Utilisez une légende de qualité (entre 10 et 400 caractères) »). Facebook reçoit donc
  `render.facebook_caption`, ≤ 400 caractères hashtags compris
  (`platforms.facebook.max_caption_chars`) : série, référence, crédits sur une ligne
  (récitateur, traduction, et la source des gloses quand la vidéo en montre), signature, les 8
  premiers hashtags ; ni arabe ni traduction (ayahs, traduction et crédits sont dans la vidéo ;
  pas de traduction dans la légende Facebook, choix du propriétaire). Trop longue : des
  hashtags de la fin.
  Calculée au rendu, rangée dans `manifest.json` (`captions.facebook`), lue par `load_reel` :
  calendrier, publish-test et à la demande. Un reel rendu avant reçoit la légende entière.
  YouTube et `caption.txt` gardent la légende entière.
- **Instagram et TikTok : légende courte, l'arabe gardé** (choix du propriétaire, 2026-11-15 :
  « très longue et inutile ») : `render.social_caption`, série et référence, le texte arabe de
  chaque ayah (on cherche un verset par ses mots, et les deux applis cherchent dans les
  légendes), crédits sur une ligne, signature (TikTok : la sienne), leurs 5 hashtags ; **sans la
  traduction** (dans la vidéo). Plus de 2 200 caractères : sans l'arabe, comme Facebook.
  Rangée dans `manifest.json` (`captions.social`), lue par `load_reel` (`Reel.social`,
  `Reel.for_platform`) ; un reel rendu avant reçoit la légende entière.
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
- **`error` sans correspondance : un nouvel envoi, une fois** (choix du propriétaire,
  2026-11-20). Meta n'a pas pu faire la vérification, ce n'est pas un ayant droit trouvé : le
  2026-11-20, 18:17-18 (Tawfiq As-Sayegh) a été bloqué pour un `error` d'Instagram, juste après
  un envoi en `ProcessingFailedError`, alors que Facebook ne trouvait rien sur le même fichier.
  Le reel est renvoyé dans un nouveau brouillon ou conteneur et vérifié de nouveau, dans le même
  run (`publish.check_rights`, reels du calendrier, à la demande et vidéos thématiques) ; un
  second `error`, une correspondance ou un délai dépassé bloquent comme avant. Ce jour-là,
  le second conteneur a eu le même `error` : à la demande du propriétaire, le reel est parti
  sur Facebook et TikTok sans Instagram (créneau rouvert, puis `daily.yml` avec l'entrée
  `without: instagram`, pour ce run seulement ; la vérification de Facebook a lieu quand même).
- **Instagram laissé de côté, automatiquement** (choix du propriétaire, 2026-11-20, après ce
  cas) : quand Instagram répond `error` sans correspondance aux deux envois et que Facebook ne
  trouve rien sur le même reel, le reel est publié sur Facebook et TikTok, pas sur Instagram
  (`publish.set_aside` ; statut `blocked` d'Instagram, « laissé de côté » dans son erreur) ; le
  run échoue et le ticket d'alerte le dit. Une correspondance où que ce soit, ou Facebook qui
  n'est pas propre, bloque tout comme avant. Reels du calendrier et à la demande ; pas les
  vidéos thématiques (rien n'a été demandé pour elles).
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

### Contrôle après publication (2026-11-05, désactivé pour l'instant)

**État : `platforms.meta.rights_after_timeout: 0` (désactivé), le propriétaire vérifie lui-même chaque nouveau reel sur Facebook avant Instagram.** Revendiqués le 2026-11-05 : Ar-Rifai (24 territoires) et Al-Ghamdi (UMG, Russie), quelques minutes après la publication. Mettre une durée (300) pour l'activer.

La vérification avant publication n'a vu ni Alafasy (93:1-11) ni Nabil Ar-Rifai (2:255, rendue
muette par Facebook dans 24 territoires « où Meta ne dispose pas des droits musicaux » : Iran,
Syrie, Chine, Cuba, Azerbaïdjan…). Le même champ est donc relu **sur les reels publiés** :

| | Objet publié | Requête |
|---|---|---|
| Facebook | reel | `GET /{video-id}?fields=copyright_check_information` (statut, `copyright_matches` avec `owner_copyright_policy.actions` : `BLOCK`, `MUTE`, `TRACK`… et `geos`) |
| Instagram | média | `GET /{ig-media-id}?fields=copyright_check_information` |

- `publish.after_check` : jusqu'à `platforms.meta.rights_after_timeout` (300 s) juste après la
  publication ; `daily.recheck` : une lecture à chaque run pour les créneaux des 2 derniers jours.
- Revendication qui rend muet ou bloque (toute action autre que `TRACK` ou `MONETIZE`, ou une
  correspondance sans action indiquée) → reel **supprimé de Facebook et d'Instagram** (statut
  `removed`), ticket d'échec avec l'ayant droit et les territoires, brouillon TikTok à ne pas
  publier ; le créneau est marqué `claimed` (pas réessayé), le passage revient en tête de sa
  file et le récitateur entre dans `claimed` de `published.json` : la rotation ne le choisit
  plus jamais (choix du propriétaire).
- Suppression Instagram (`DELETE /{ig-media-id}`) : demande la permission
  **`instagram_manage_contents`** sur le jeton de Page. Sans elle, le reel Instagram reste en
  ligne avec « À RETIRER À LA MAIN » dans le ticket, et `meta-check` l'annonce en avertissement.
  Pour l'ajouter : explorateur Graph → jeton utilisateur avec `instagram_manage_contents` en
  plus → prolonger → `me/accounts` → nouveau `META_PAGE_TOKEN`.

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
- Un morceau refusé par une erreur du serveur (HTTP 5xx) ou du réseau est renvoyé, les mêmes
  octets au même endroit, 3 essais (5 s, puis 10 s) : le run #28 du 2026-11-09 a échoué sur un
  HTTP 500 une seconde après le début de l'envoi, Facebook et Instagram déjà publiés. Un échec
  avant que TikTok ait tout le fichier ne porte pas d'identifiant et peut être réessayé dans
  le même run (docs/calendrier.md) ; après, il porte le `publish_id` (le brouillon peut
  encore arriver) et n'est pas renvoyé. Un nouveau refresh token est aussi gardé dans
  l'environnement du run, pour son envoi suivant.
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
- Son échéance est lue à chaque publication (`gh_secrets.token_expiry`, en-tête
  `github-authentication-token-expiration` de la réponse de GitHub) et imprimée dans le journal
  (« GH_SECRETS_TOKEN: valid until … »). À 14 jours ou moins, le ticket d'alerte le dit une
  fois. Expiré, le prochain refresh token de TikTok ne peut plus être enregistré : refaire le
  jeton comme ci-dessus, puis la connexion TikTok si un run échoue sur le rafraîchissement.

## YouTube Shorts — mis en ligne par le run depuis le 2026-11-21

- API : YouTube Data API v3, `videos.insert`, dans son propre compteur depuis 2026 : **100 mises
  en ligne par jour**, 1 unité chacune (avant : 1 600 unités sur 10 000, environ 6 par jour).
- **Plus de verrouillage en privé ni d'audit** : de juillet 2020 au 1er novembre 2026, une vidéo
  mise en ligne par l'API d'un projet non audité restait privée. YouTube a levé cette règle le
  2026-11-02 ([historique de l'API](https://developers.google.com/youtube/v3/revision_history),
  [videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert) : « Videos uploaded
  from unverified API projects are not restricted to private viewing mode »). L'audit n'est plus
  nécessaire ; il ne servirait qu'à dépasser les quotas.
- **Les Shorts du calendrier sont mis en ligne par le run `daily`** (choix du propriétaire,
  2026-11-21 : les reels d'abord, les vidéos thématiques et les demandes restent à la main) :
  `platforms.youtube.upload` de config/project.yaml, `publishers/youtube.py`, `daily.to_youtube`.
  - **Quoi** : la version YouTube du créneau (par Tawfiq As-Sayegh, ci-dessous), en **public**,
    avec les textes de la page « À publier » : titre (la tête de la légende, l'arabe d'abord),
    description (`caption.txt`) suivie de tous les hashtags, hashtags aussi en tags ; « pas
    conçue pour les enfants », « pas de contenu synthétique réaliste » ; catégorie : celle de
    YouTube par défaut, comme à la main (`category` pour en fixer une).
  - **Quand** : juste après la publication du reel du créneau, seulement s'il est sorti (le
    passage est publié) ; tous les reels du calendrier, le matin comme le dimanche soir.
  - **Droits (règle 6)** : la vérification de Meta voit le fichier envoyé : celle du reel quand
    c'est la même vidéo, sinon une à elle (brouillon Facebook supprimé, conteneur Instagram
    jamais publié, comme une demande « YouTube seul »). Pas propre : pas mise sur YouTube (`blocked`)
    et le ticket d'alerte le dit. Content ID ne se lit pas par l'API pour une chaîne comme la
    nôtre : la seule garde est Tawfiq, jamais revendiqué jusqu'ici, comme à la main.
  - **Jamais deux fois** : un envoi qui n'a rien donné à YouTube (pas d'identifiant : réseau,
    quota, jeton) fait échouer le run (ticket d'alerte) et le run suivant du créneau le refait,
    seul ; un envoi qui a un identifiant (YouTube l'a refusé, ou l'a gardé privé) n'est jamais
    refait : à voir dans Studio. Un passage déjà sur la chaîne (même passage, autre créneau)
    n'y est pas remis.
  - **Tant que le propriétaire ne s'est pas connecté pour la mise en ligne**
    (`YOUTUBE_UPLOAD_REFRESH_TOKEN`, « Mise en ligne des Shorts » ci-dessous), rien ne change :
    à la main, comme avant. La page « À publier » montre « YouTube ✓ » et le lien dès que le run l'a
    mis en ligne ; le ticket « 📋 Légendes à copier » dit « mis en ligne par le run, rien à
    faire » ; sinon, MP4, textes et `/youtube` comme avant.
- Shorts : vertical, 3 min maximum.
- **Droits : Content ID, pas Rights Manager.** YouTube a ses propres empreintes, que Meta n'a
  pas forcément : la sourate Al-Kahf de **Salah Budair** (al-Haram, 1426-1427 H, déposée au
  nom de « الشيخ صلاح البدير ») est dans Content ID. Le Short 18:1-10 (1:28), propre sur
  Facebook et Instagram, y a été **bloqué dans le monde entier** le 2026-11-06 : un Short de
  plus d'une minute qui a une revendication Content ID active, quelle qu'elle soit, est bloqué
  partout ([aide YouTube](https://support.google.com/youtube/answer/15424877)) ; sous une
  minute, la politique du titulaire s'applique (suivi, monétisation ou blocage). Une
  revendication n'est pas un avertissement pour la chaîne ; ne pas la contester (enregistrement
  du récitateur).
- **Sur YouTube, toujours Tawfiq As-Sayegh** (choix du propriétaire, 2026-11-11 :
  `platforms.youtube.reciter: sayegh`) : aucune revendication constatée sur ses récitations, et
  c'est la voix des épisodes thématiques de la même chaîne. La rotation ne change pas pour
  Facebook, Instagram et TikTok. Quand elle choisit un autre récitateur (environ 4 créneaux sur
  5), le run `daily` publie comme d'habitude, puis rend le passage une seconde fois par Tawfiq :
  `out/youtube/<passage>.mp4`, envoyé dans la release `reels` ; le ticket « 📋 Légendes à
  copier » dit « pas cette vidéo mais ce MP4 » et donne sa légende (`daily.youtube_version`,
  `reciters.other_for`, état : `youtube` du créneau). Quand elle le choisit, la même vidéo sert.
  - **Tawfiq pas prêt pour le passage** (découpe pas vérifiée, ou plus de `max_seconds`, 180 s,
    la limite des Shorts) : **rien pour YouTube ce créneau**, aucun autre récitateur à sa place
    (choix du propriétaire) ; le ticket le dit avec la raison, sans lien ni commande `/youtube`,
    et l'état garde `youtube: {reciter: null, error}`. Le workflow `prepare` découpe sa
    récitation chaque nuit pour les 8 jours suivants, même s'il sort un jour de la rotation, et
    signale d'un avertissement (`::warning`) les passages où il n'est pas prêt : la découpe se
    corrige avant (`quran-reels split --audit --fix <sourate>`).
  - Une revendication sur Meta (`claimed`) l'écarte de la rotation, pas de YouTube : Content
    ID et Rights Manager sont deux systèmes.
  - **Une seule voix, un seul point de panne** : si Content ID le revendique un jour, tout
    YouTube s'arrête (18:1-10, 109 s avec lui, serait bloqué partout). Retirer alors
    `reciter` de `platforms.youtube` : on revient à la règle d'avant, ci-dessous.
  - Les Shorts déjà en ligne ne sont pas refaits.
- **Sans `reciter`** (la règle du 2026-11-06 au 2026-11-11, toujours dans le code) : YouTube
  reçoit la vidéo du jour, sauf quand la rotation choisit un récitateur de
  `platforms.youtube.exclude_reciters` (Budair) ; le run rend alors le passage par un autre
  récitateur prêt, au plus `max_seconds`, le plus proche de 60 s.
- **Téléchargement direct depuis le téléphone** (2026-11-06, docs/on-demand.md) : les artefacts
  Actions sont zippés et demandent une connexion. Chaque MP4 publié va donc aussi dans la
  release GitHub `reels` (pré-version, URL publique `…/releases/download/reels/<fichier>.mp4`,
  servie en téléchargement : Téléchargements → galerie → app YouTube), supprimé après 30 jours.
  La page « À publier » (lien fixe, https://mssnoussi92.github.io/quran-reels/publier.html,
  2026-11-15) donne ces liens et tous les textes à copier ; en secours, le ticket « 📋 Légendes
  à copier » donne pour chaque vidéo ce lien, la page
  `reel.html?r=daily/<jour>-<créneau>` (titre ≤ 100 caractères tiré de la légende, description =
  `caption.txt`, tous les hashtags, boutons Copier) et la commande à commenter une fois en ligne :
  `/youtube <jour>/<créneau> <lien>` (état : `results.youtube` du créneau, `by_hand`).
- Nouveau récitateur sur YouTube (si `platforms.youtube.reciter` change un jour) : mettre en
  ligne en **privé**, attendre quelques minutes, regarder les revendications (YouTube Studio →
  Contenu → Restrictions), puis rendre public. Avec la mise en ligne par le run : passer d'abord
  `upload.privacy` à `private` (un Short gardé privé est un échec avec identifiant : alerte, pas
  de second envoi), le rendre public dans Studio, puis remettre `public`.
- OAuth Google : un projet en statut **« Test »** reçoit des refresh tokens qui expirent au bout
  de 7 jours. Il faut passer l'écran de consentement en **« En production »** (écran « app non
  validée » accepté pour un usage personnel) pour garder un refresh token durable.

### Statistiques YouTube (lecture seule, choix du propriétaire, 2026-11-15)

Le workflow `insights` lit chaque nuit les chiffres de la chaîne (docs/insights.md, « YouTube, lu chaque nuit »)
avec un client OAuth du projet Google Cloud du propriétaire. Lecture seule : `youtube.readonly` et
`yt-analytics.readonly`, rien ne peut être mis en ligne, modifié ni supprimé. Mise en place, depuis le téléphone :

1. **Projet** : https://console.cloud.google.com/projectcreate, avec le compte Google de la chaîne, nom « Quran
   Words Daily » → Créer, puis le choisir en haut de la page.
2. **Deux API**, bouton « Activer » de chacune :
   https://console.cloud.google.com/apis/library/youtube.googleapis.com et
   https://console.cloud.google.com/apis/library/youtubeanalytics.googleapis.com.
3. **Écran de consentement** : https://console.cloud.google.com/auth/overview → Commencer : nom de l'app « Quran
   Words Daily », e-mail d'assistance, audience **Externe**, coordonnées, accepter → Créer. Puis **Audience →
   Publier l'application → « En production »** : en « Test », Google invalide le jeton au bout de 7 jours.
   L'application reste « non validée » : pour un usage par son seul propriétaire, c'est permis (avertissement à
   passer à la connexion).
4. **Client** : https://console.cloud.google.com/auth/clients → Créer un client → type **Application Web**, nom
   « quran-reels », URI de redirection autorisé :
   `https://mssnoussi92.github.io/quran-reels/youtube-callback.html` → Créer. Garder l'ID client et le code secret.
5. **Secrets GitHub** (dépôt quran-reels → Settings → Secrets and variables → Actions) : `YOUTUBE_CLIENT_ID` et
   `YOUTUBE_CLIENT_SECRET`. Jamais dans une conversation.
6. **Connexion** : https://mssnoussi92.github.io/quran-reels/youtube-login.html, coller l'ID client → Google :
   le compte de la chaîne, « Google n'a pas validé cette application » → Paramètres avancés → Accéder à Quran Words
   Daily, cocher les deux cases → la page de retour montre un code → dans les minutes qui suivent, Actions →
   **youtube-auth** → coller le code → Run. Le jeton est enregistré dans `YOUTUBE_REFRESH_TOKEN`
   (`GH_SECRETS_TOKEN`) ; le résumé du run nomme la chaîne.
7. **Essai** : Actions → **insights** → `dry_run` coché → l'étape « Read YouTube » dit combien de vidéos elle lit.

Un changement de mot de passe Google ou une révocation (myaccount.google.com → Sécurité → Accès tiers) coupe le
jeton : refaire l'étape 6. Sans ces secrets, YouTube reste aux captures.

### Mise en ligne des Shorts (choix du propriétaire, 2026-11-21)

Un second jeton, à part de celui des statistiques, qui reste en lecture seule : `YOUTUBE_UPLOAD_REFRESH_TOKEN`,
autorisations `youtube.upload` et `youtube.readonly` : il met en ligne et lit, il ne peut ni modifier ni supprimer une
vidéo. Même projet, même client, même page ; depuis le téléphone, une fois (5 minutes) :

1. https://mssnoussi92.github.io/quran-reels/youtube-login.html, coller l'ID client → bouton **« Uploads: continue to
   Google »** → le compte de la chaîne, « Google n'a pas validé cette application » → Paramètres avancés → Accéder à
   Quran Words Daily → cocher les cases (gérer vos vidéos YouTube, voir votre compte YouTube) → la page de retour
   montre un code.
2. Dans les minutes qui suivent, Actions → **youtube-auth** → coller le code → Run. Le workflow reconnaît la mise en
   ligne aux autorisations données et enregistre `YOUTUBE_UPLOAD_REFRESH_TOKEN` ; le résumé du run nomme la chaîne
   et dit « mise en ligne des Shorts du calendrier ».
3. Le prochain reel du calendrier part aussi sur YouTube. Pour l'arrêter : `upload: daily: false` dans
   config/project.yaml (une PR), ou retirer l'accès (myaccount.google.com → Sécurité → Accès tiers) : retour à la
   main.

Le jeton se perd comme l'autre (mot de passe Google changé, accès retiré) : le run le dit (« connexion YouTube
perdue »), le Short du jour reste à mettre à la main, refaire les étapes 1 et 2.

## Format vidéo commun

MP4 H.264 + AAC, 1080×1920, 30 i/s, 20–90 s. Zone sûre : haut 250 px, bas 420 px, côtés 90 px.
