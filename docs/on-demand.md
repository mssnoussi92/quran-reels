# Publication à la demande (aperçu, puis approbation, depuis le téléphone)

Décidé le 2026-11-06. Le propriétaire choisit un passage, un récitateur, un fond et les
plateformes ; il reçoit un aperçu qu'il ouvre d'un geste sur son téléphone ; rien n'est publié
tant qu'il n'a pas répondu `/publier`. YouTube reste manuel : MP4 en téléchargement direct,
titre, description et hashtags prêts à copier, puis `/youtube <lien>` pour le noter.

## Décisions du propriétaire (2026-11-06)

| Question | Choix |
|---|---|
| Un reel à la demande remplace-t-il un créneau ? | **Non : en plus** des deux créneaux ; calendrier et files inchangés |
| Le calendrier arrive à un passage déjà publié à la demande | **Il ne le saute pas** : il le publie à son tour. L'état garde chaque publication à la demande, par plateforme (`on_demand` de `published.json`) |
| YouTube demandé avec un récitateur revendiqué par Content ID (`platforms.youtube.exclude_reciters` : Budair) | **YouTube refusé** pour cette demande, l'aperçu le dit et propose d'autres récitateurs ; Facebook, Instagram et TikTok continuent |
| YouTube coché (2026-11-11 : sur YouTube, toujours Tawfiq As-Sayegh, `platforms.youtube.reciter`) | Une demande fait **une seule vidéo**. Récitateur « Auto » : **Tawfiq récite tout le reel**, pour toutes les plateformes cochées (le formulaire et l'aperçu le disent). Un autre récitateur choisi : **YouTube retiré** de la demande avec une note, les autres plateformes continuent ; YouTube seul : demande refusée. Tawfiq trop long pour le passage (plus de 90 s) : refus qui dit pourquoi lui, et les autres récitateurs possibles sans YouTube. Le formulaire coche YouTube par défaut : une demande « Auto » envoyée telle quelle est donc récitée par Tawfiq ; décocher YouTube rend « Auto » à la rotation. Pas de second rendu dans une demande (deux fichiers à approuver) |

## Options comparées

### 1. Faire la demande

| | Pour | Contre |
|---|---|---|
| Formulaire `workflow_dispatch` | Rien à construire ; réservé aux comptes en écriture | Listes figées dans le YAML (récitateurs, 30 fonds : à tenir à jour à la main), aucun préremplissage par lien, l'aperçu finit dans un run, pas dans une conversation |
| Formulaire d'issue (`.github/ISSUE_TEMPLATE/*.yml`) | Préremplissable par URL (`?template=…&<id>=…`), listes déroulantes | Le préremplissage ne vaut que pour les champs texte (doc GitHub), l'app GitHub Mobile gère mal les formulaires (libellés non posés), et un dossier de modèles risque de changer le comportement des liens `issues/new?title=…&body=…` du catalogue, qui marchent |
| **Ticket prérempli depuis le catalogue** (retenu) | Même mécanisme que les tickets du catalogue, déjà utilisé depuis le téléphone (#19–#32) ; vraies listes (récitateurs autorisés, 114 sourates avec leur nombre d'ayahs, fonds avec aperçu) construites depuis `config/` à chaque déploiement ; les cartes ouvrent le formulaire avec le récitateur ou le fond déjà choisi | Demande JavaScript (sans lui : lien vers un ticket vierge à remplir, même format) |

### 2. Approuver

| | Pour | Contre |
|---|---|---|
| Environnement avec le propriétaire comme relecteur obligatoire | Barrière gérée par GitHub | L'approbation se fait dans Actions, loin de l'aperçu ; le job en attente occupe le groupe de concurrence `accounts` (GitHub n'y garde qu'un run en attente : un run du calendrier peut annuler l'autre) ; « Prevent self-review » à désactiver |
| **Commentaire `/publier`** (retenu) | Juste sous l'aperçu, dans l'app comme dans le navigateur, explicite et daté ; `/essai` pour un dry run | La sécurité dépend de notre contrôle de l'auteur (voir Sécurité) |
| Libellé | Seuls les comptes avec droits de tri peuvent étiqueter | Trois gestes sur téléphone, peu explicite, même contrôle de l'expéditeur à faire |

### 3. Héberger l'aperçu et le MP4 (rien de binaire sur `main`)

| | Pour | Contre |
|---|---|---|
| Artefact Actions classique | Déjà en place | Zippé ; téléchargement réservé aux comptes connectés |
| Artefact non zippé (`upload-artifact` v7, `archive: false`, février 2026) | Un fichier, non zippé | Toujours via la page du run et un compte connecté dans le navigateur ; un seul fichier par artefact ; 90 jours au plus |
| **Release GitHub `reels`** (retenue pour les MP4) | URL publique stable, sans connexion, **téléchargement direct** (`Content-Disposition: attachment`) → dossier Téléchargements → galerie, et proposé par l'app YouTube ; 2 Go par fichier ; hors historique git ; supprimable | Servie en `application/octet-stream` : une image d'une release ne s'affiche pas dans un commentaire |
| GitHub Pages | Lecteur intégré | Redéploiement complet à chaque fichier, le catalogue possède déjà Pages, site limité à 1 Go |
| **Branche `previews`** (retenue pour les petites images et le JSON) | `raw.githubusercontent.com` sert les JPEG en `image/jpeg` (affichés dans le commentaire) et le JSON avec CORS (lu par la page d'aperçu) | Seulement de petits fichiers (≈ 150 Ko par reel) : pas de MP4 dans git |

## Recommandation (implémentée)

1. **Demande** — catalogue, section « À la demande » (ou bouton « Publier à la demande » d'une
   carte récitateur ou fond) : récitateur (`auto` ou un de `content.rotation`, sauf écartés
   `claimed`), sourate, entière ou de l'ayah X à Y, fond (`auto` ou un de `backgrounds.yaml`),
   plateformes → « Préparer » ouvre un ticket prérempli « À la demande : … » → Envoyer.
   **Avant de créer le ticket** (ajout du 2026-11-06, choix du propriétaire) : le formulaire
   affiche les ayahs choisies (arabe et Sahih International lus en direct sur Quran.com, rien
   n'est recopié sur le site), prévient si la plage coupe une phrase (bouton « Prendre » la
   plage entière la plus proche) et liste sous chaque ayah les sens du Muyassar à cocher,
   numérotés comme l'aperçu, cochés comme les règles habituelles, 2 au plus par ayah : le
   ticket part avec sa section « ### Mots ». tafsir.app n'étant pas lisible par un navigateur
   (pas de CORS), la construction du catalogue écrit `catalog/surahs/SSS.json` (fins de phrase,
   sens numérotés par le code de l'aperçu) : **les extraits du Muyassar (≤ 170 caractères,
   phrases entières, ceux qu'un reel peut montrer) sont donc publiés sur le site**, choix du
   propriétaire. Téléchargés au plus 15 min par construction (≈ 0,5 s par ayah, 5 069 ayahs
   expliquées), dans l'ordre de lecture (Juz' 'Amma d'abord), gardés dans le cache Actions ;
   une sourate pas encore chargée se choisit après l'aperçu (`/mots`). Le workflow revérifie
   tout (phrases, durée, mots).
2. **Aperçu** (workflow `on-demand`, ≈ 4 à 7 min ; découpe en plus si besoin) :
   - refus motivé, avec des plages valides proposées, si le passage coupe une phrase (règle 4,
     même contrôle que `series-check`), dépasse 90 s avec ce récitateur, ou si le récitateur,
     le fond ou une plateforme n'est pas autorisé ;
   - découpe manquante pour ce récitateur : `quran-reels split` lancé dans le même run (le
     commentaire dit combien de temps cela prend), enregistrée sur la branche `state` ;
   - rendu par le pipeline (`render_passage`, fond imposé ou choisi comme d'habitude) ;
   - commentaire : 3 images clés, MP4 d'aperçu (540p, léger), légendes Facebook (la courte,
     ≤ 400 caractères), Instagram et TikTok (5 hashtags), lien vers la page d'aperçu
     `…/quran-reels/reel.html?r=…` (lecteur, boutons Copier).
   - **mots expliqués** : la liste numérotée de tous les sens que غريب التفسير الميسر donne
     pour les ayahs du passage, ✅ pour ceux affichés (par défaut : les règles habituelles,
     `glosses.yaml`, 2 au plus par ayah). Le propriétaire choisit en répondant `/mots 1 4 7`
     (ou en cochant sur la page d'aperçu, qui écrit la commande), un mot précis de la citation
     avec `/mots 4=قلى`, aucun avec `/mots aucun`, retour aux règles avec `/mots auto`. Le
     choix est écrit dans la section « ### Mots » du ticket, vérifié (numéro existant, sens
     affichable en phrases entières, mot présent dans la citation, 2 au plus par ayah, pas
     deux sens sur le même mot) et un nouvel aperçu suit. **Le sens n'est jamais écrit ni
     modifié** : seulement choisi parmi ceux de la source (règle 1). Ajouté le 2026-11-06 à
     la demande du propriétaire.
3. **Approbation** — `/publier` (ou `/essai` : même chemin en dry run). Ce qui est publié est
   **le fichier de l'aperçu** (même empreinte SHA-256), jamais un nouveau rendu.
4. **Publication** — `publish_reel` comme le calendrier : vérification des droits de Meta
   d'abord (règle 6 ; une demande sans Facebook ni Instagram passe quand même par un brouillon
   Meta vérifié puis supprimé), rien n'est publié nulle part si elle n'est pas propre ;
   TikTok en brouillon. Résultat par plateforme dans `published.json` (`on_demand`).
5. **YouTube** — seulement si la vérification est propre : MP4 1080p en téléchargement direct,
   titre (≤ 100 caractères, tiré de la légende), description (la légende de `caption.txt`, avec
   les crédits) et hashtags (tous, ceux du rendu), chacun à copier ; puis
   `/youtube https://youtube.com/shorts/…` (lien facultatif) → `youtube: published, by_hand`
   dans l'état, ticket fermé. Pas mis en ligne (demande de test, #39) : ticket fermé « non
   prévu », `youtube: cancelled` (+ `note`) écrit à la main dans l'état ; le catalogue ne liste
   que les demandes arrivées sur une plateforme.
6. **Reels du calendrier** — même téléchargement direct : après chaque run `daily`, le MP4
   publié et sa version YouTube (par Tawfiq As-Sayegh, quand la rotation a choisi quelqu'un
   d'autre) vont dans la release ; le ticket épinglé « 📋 Légendes à copier » donne, pour
   chaque vidéo, le lien MP4, la page YouTube (titre, description, hashtags) et la commande
   `/youtube <créneau> <lien>` à y commenter. Tawfiq pas prêt pour le passage : le MP4 seul,
   et « rien pour YouTube ce créneau ».

Commandes (commentaires du propriétaire seulement) : `/publier`, `/essai`, `/apercu` (refaire
l'aperçu ; modifier le ticket le refait aussi), `/mots …` (mots expliqués), `/youtube [lien]` ;
sur le ticket des légendes : `/youtube <jour>/<créneau> [lien]`.

## Sécurité (dépôt et logs publics)

- N'importe qui peut ouvrir un ticket ou commenter : chaque job du workflow ne démarre que si
  l'auteur est `github.repository_owner` **et** `author_association == OWNER` (contrôlé par
  GitHub avant tout secret), puis revérifié en Python sur le fichier d'événement.
- L'aperçu de référence est le dernier commentaire de `github-actions[bot]` portant le
  marqueur ; l'approbation doit être postérieure et le texte du ticket inchangé depuis
  (empreinte) ; le run d'aperçu doit être un run de `on-demand.yml` de ce dépôt ; le MP4
  téléchargé doit avoir l'empreinte annoncée. Une même demande ne republie jamais une
  plateforme déjà publiée.
- Le texte du ticket n'est jamais interpolé dans le shell (lu dans le fichier d'événement).
- Secrets seulement dans l'étape de publication ; aucun identifiant dans les logs (les
  messages réutilisent ceux de `publish.py`).
- Le calendrier et les images ne changent pas : la publication à la demande prend le groupe
  `accounts` (jamais deux publications à la fois) ; l'aperçu n'y entre pas.

## Conservation

- MP4 (release `reels`) et images/JSON (branche `previews`) : **30 jours**, puis supprimés
  par le workflow (`quran-reels files prune`). Les artefacts entre l'aperçu et la publication :
  7 jours (au-delà : `/apercu` refait l'aperçu).
- `published.json` garde chaque demande pour toujours (les liens de fichiers expirent).

## Limites connues

- Le lecteur de la page d'aperçu lit le MP4 depuis la release ; si le navigateur refuse, la
  page propose le téléchargement (même fichier).
- Pas de modèle d'issue (voir 1) : un ticket ouvert à la main doit garder le format
  « ### Récitateur … ### Passage … ### Fond … ### Plateformes » (« ### Mots » facultatif).
- Les numéros de `/mots` sont ceux du dernier aperçu : changer le passage les renumérote
  (le nouvel aperçu montre ce qui est affiché).
- Le contrôle des droits après publication reste celui du calendrier
  (`rights_after_timeout`, désactivé).
