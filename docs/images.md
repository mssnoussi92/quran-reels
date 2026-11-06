# Publications image (Instagram + Facebook)

Décisions du 2026-11-05. Maquettes : `docs/mockup/images/` (`cards.html?card=word-1|word-2|word-3|ayah`,
rendus JPG à côté). Exemple : 93:3, données vérifiées (ar-uthmani-hafs, en-sahih-international,
ar-ghareeb-ibn-qutaybah).

## Formats

Deux formats préparés, **un seul publié pour l'instant** :

| Format | Contenu | Statut |
|---|---|---|
| **Word of the day** (carrousel 3 images) | 1. le mot glosé en grand + sourate et référence (sert aussi de vignette dans la grille) · 2. l'ayah, mot surligné, + traduction Sahih International · 3. le mot + sa glose d'Ibn Qutaybah, mot pour mot, avec la source | **publié, 1 par jour** |
| **Ayah of the day** (image seule) | une ayah complète + traduction | préparé, désactivé |

Format 1080×1350 (4:5), même charte que les reels (Amiri Quran, Amiri, Lora, or `#f6c86b`),
signature `@quran_words_daily` sur chaque image, crédits sur les images 2 et 3. Fond généré
(pas de photo), donc aucun risque de droits sur l'image. Pas d'audio, donc pas de Rights Manager.

## Sélection : entièrement automatique et déterministe

Pas d'IA dans la boucle quotidienne, pas de validation manuelle. Règles :

1. **Candidats** : ayahs dont une glose d'Ibn Qutaybah s'ancre sur 1 ou 2 mots (`arabic.py`,
   `config/glosses.yaml`). Une publication = une entrée de glose.
2. **Glose** : phrases entières, sans notes de l'éditeur, longueur max (≈ 170 caractères, comme
   les reels). Sinon l'entrée est écartée, jamais raccourcie.
3. **Contexte** (garde-fou principal, puisque personne ne valide) : l'image 2 doit montrer une
   **phrase complète**. L'ayah commence après une fin de phrase (ayah précédente terminée par
   `.` `?` `!` dans Sahih International, ou première ayah de la sourate) et se termine par une fin
   de phrase. Sinon, on l'étend à la plus petite suite d'ayahs qui forme une phrase complète, si
   elle tient sur l'image ; sinon on l'écarte.
4. **Place** : l'ayah (ou la suite) et sa traduction tiennent sur l'image sans descendre sous
   le seuil de lisibilité du rendu.
5. **Exclusions** : `config/exclude.yaml`, que le propriétaire peut modifier à tout moment
   (ayahs, plages ou sourates à ne pas publier en image).
6. **Ordre** : permutation stable (graine fixe) de tous les candidats, sans répétition avant
   épuisement, et pas deux jours de suite la même sourate. Le prochain choix est donc prévisible :
   `quran-reels images next --days 7` affiche la semaine à venir.

## Légende (modèle, pas d'IA)

```
Word of the day: قَلَىٰ
Surah Ad-Duha 93:3

Translation: Sahih International
Meaning: Ibn Qutaybah, Tafsir Gharib al-Qur'an

#Quran #ArabicWords #QuranWordsDaily #SurahAdDuha #سورة_الضحى #القرآن_الكريم
```

## Publication

- **Instagram** : carrousel = 3 conteneurs `is_carousel_item=true` → conteneur `CAROUSEL` →
  `media_publish`. L'API image demande une **URL publique** (`image_url`) : pas d'envoi
  binaire pour les images. Options : photo Facebook non publiée puis son URL CDN, ou GitHub Pages.
- **Facebook** : 3 photos envoyées non publiées (`published=false`), puis une publication de Page
  avec `attached_media` dans l'ordre.
- `state/` : une entrée par publication (format, ayah, mot, ids) pour éviter les doublons.
- Planification : un créneau par jour (workflow GitHub Actions, heure en UTC dans la config),
  ajusté plus tard selon les statistiques.
- Plus tard : TikTok accepte les publications photo par l'API depuis un domaine vérifié (notre
  préfixe GitHub Pages l'est), mais l'app est en Sandbox.

## Implémentation

*Déplacé de CLAUDE.md le 2026-11-05 (texte inchangé) ; CLAUDE.md en garde le résumé.*

- Formats (`config/images.yaml`) : `word` (carrousel de 3 images : mot en grand, ayah avec le
  mot surligné + Sahih International, sens du Muyassar mot pour mot) activé, une fois par
  jour à `time_utc` 11:30 ; `ayah` (une image) préparé, désactivé. 1080×1350, même charte que
  les reels, fond généré en CSS (aucune photo, aucun droit), pas d'audio (pas de Rights
  Manager). Gabarit `images/templates/card.html.j2` d'après `docs/mockup/images/cards.html`.
- Sélection déterministe, sans IA ni validation : candidats figés dans
  `config/image-candidates.yaml` par `quran-reels images build` (références seulement), à
  refaire après un changement de `glosses.yaml`, du gabarit ou de `min_scale`.
  1. une entrée de sens ancrée sur 1 à 3 mots liés (`glosses.max_words` ; comme les reels : mots de `glosses.yaml`,
     sinon citation sans particules de bord) ;
  2. glose montrée entière : texte complet (notes `[[…]]` retirées) ≤ 170 caractères et fini
     par une phrase, sinon écartée, jamais raccourcie ;
  3. image 2 = phrase complète : l'ayah grandit à la plus petite suite qui commence après une
     fin de phrase et en finit une (93:3 → 93:1-3, le serment commence en 93:1) ;
  4. chaque image lisible : texte réduit au plus à `min_scale` (0,7), sinon écartée ;
  5. `config/exclude.yaml` (lu à chaque passage, valeurs gardées en texte : `2:55` non cité
     n'est pas lu comme un nombre en base 60) : ayahs, plages, sourates ; une suite est écartée
     si une de ses ayahs l'est ;
  6. rang = hash(graine, tour, id) : ordre stable même si la liste change, pas de répétition
     avant la fin d'un tour (puis nouvel ordre), jamais deux jours de suite la même sourate
     quand une autre est disponible.
- Légende : modèle fixe (`images/caption.py`) ; Instagram garde les 5 premiers hashtags.
- Publication : URL publique exigée par Instagram (pas d'envoi binaire d'image) → les 3 images
  sont envoyées sur la Page Facebook **non publiées** (`published=false`), leur URL CDN
  (`?fields=images`, la plus grande) sert à Instagram (3 conteneurs `is_carousel_item`, un
  `CAROUSEL`, `media_publish`), puis post Facebook `/feed` avec `attached_media` dans l'ordre.
  Choisi plutôt que GitHub Pages : pas de JPEG commités chaque jour (≈ 160 Mo/an d'historique),
  pas d'attente de déploiement, images non publiques avant le post. Dry-run : rien n'est posté,
  photos supprimées.
- État : `images.json` sur la branche `state` (un post par jour : id, ayah, mot, résultats par
  plateforme) ; une plateforme en échec est réessayée avec les mêmes images pendant
  `window_hours` (6 h). Workflow `images.yml` toutes les heures.
