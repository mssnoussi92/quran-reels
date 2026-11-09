# Profils des comptes : bio, images, playlists

Proposition du 2026-11-09, à appliquer **à la main** depuis le téléphone (aucune API utilisée).
Chaque texte est dans un bloc : le bouton « copier » de GitHub le prend tel quel. Les longueurs
sont comptées sous la limite de chaque plateforme.

## Ce que montrent les pages publiques (2026-11-09)

- **YouTube** : description vide, aucun mot-clé, **pas de bannière**, **photo par défaut**
  (l'initiale générée par YouTube), aucune playlist. Pourtant 66 abonnés et 6 547 vues en
  5 jours avec 10 Shorts (en tête : Ad-Duha 1,3 k, Al-Falaq 1,1 k, Ayat al-Kursi 1 k) : une
  chaîne qui démarre bien, derrière une page vide.
- **TikTok** : nom « Quran words Daily » (w minuscule), bio générique, **0 vidéo publique et
  0 abonné** d'après la page publique (les reels arrivent en brouillon dans la boîte TikTok et
  doivent être postés un par un). Photo : une image générée par IA, noir et or, avec l'ancien
  nom **« كلمات القرآن »** (la marque est « آيات » depuis le 2026-11-04), des voyelles posées au
  hasard sur la calligraphie et un **faux mushaf dont les pages portent un pseudo-texte arabe**.
  Pour une page dont la première règle est « aucun texte coranique fait par une IA », c'est la
  pire image possible : à remplacer en premier.
- **Facebook, Instagram** : pages fermées sans compte, pas lues. Les textes ci-dessous
  remplacent ce qui y est.
- **Site** (lien des bios) : annonçait encore Alafasy (écarté le 2026-11-05), Ibn Qutaybah
  (remplacé par le Muyassar) et « un passage par jour ». Corrigé dans `docs/index.html`.

## Images (`assets/brand/`, refaites par `assets/brand/src/render.py`)

| Fichier | Où | Taille |
|---|---|---|
| `avatar-1080.jpg` | photo de profil des **4** comptes (la même partout) | 1080×1080 |
| `facebook-cover-1640x624.jpg` | photo de couverture Facebook | 1640×624 |
| `youtube-banner-2560x1440.jpg` | bannière YouTube | 2560×1440 |
| `youtube-watermark-150.png` | filigrane YouTube (vidéos longues) | 150×150 |

- Photo de profil : **« آيات » seul**, sans « QURAN WORDS DAILY » : à 40 px (taille d'un
  commentaire, d'une liste d'abonnements) le texte latin de l'ancienne icône devient une ligne
  grise illisible, et le nom de la page est toujours écrit à côté de la photo. Lisible jusqu'à
  36 px, tient dans le cercle de chaque plateforme.
- Couverture et bannière : même ciel, même livre ouvert ; la phrase « One Quran passage every
  day » (fausse depuis les 2 créneaux) devient « Two Quran recitations every day ». Texte dans
  la zone vue sur téléphone (Facebook : les 1 110 px du milieu ; YouTube : 1546×423 au centre).
- `icon-1024.jpg` reste l'icône de l'app Meta (docs/plateformes.md), rien à changer là-bas.

Pour les enregistrer sur le téléphone : ouvrir le fichier sur GitHub
(`assets/brand/…`, bouton « Raw »), appui long sur l'image → enregistrer.

## Facebook (Page `quranwordsdaily`)

Photo de profil `avatar-1080.jpg`, couverture `facebook-cover-1640x624.jpg`.

Intro (bio de la Page, 101 caractères au plus) :

```
Two Quran recitations every day: Arabic, English translation and word meanings. Fridays: Al-Kahf.
```

- Catégories : **Créateur de vidéos** et **Éducation** (pas « Organisation religieuse » : la
  page n'en est pas une).
- Site web : `https://mssnoussi92.github.io/quran-reels/` · E-mail : `quranwordsdaily@gmail.com`.
- Épingler en haut de la Page le reel qui marche le mieux (voir « Autres améliorations »).

## Instagram (`@quran_words_daily`)

Photo `avatar-1080.jpg`.

Nom (le champ « Nom » est cherché par Instagram ; « القرآن » fait trouver la page en arabe) :

```
Quran Words Daily | القرآن
```

Bio (150 caractères au plus) :

```
Two Quran recitations every day 🌙
Arabic · English translation · word meanings
📖 Word of the day · Fridays: Surah Al-Kahf
```

Lien : `https://mssnoussi92.github.io/quran-reels/` (titre « Website »).

## TikTok (`@quran_words_daily`)

Photo `avatar-1080.jpg` (remplace l'image noir et or).

Nom :

```
Quran Words Daily | القرآن
```

Bio (80 caractères au plus) :

```
Two Quran recitations every day 🌙
Arabic · English translation · word meanings
```

Lien cliquable : TikTok le réserve aux comptes de 1 000 abonnés ou aux comptes Entreprise
(selon les pays) ; regarder dans Profil → Modifier si le champ « Site web » est proposé. Ne pas
écrire l'adresse dans la bio : elle n'y est pas cliquable.

## YouTube (`@quran_words_daily`)

YouTube → Vous → Votre chaîne → Modifier (ou l'app YouTube Studio) :

- Photo `avatar-1080.jpg`, bannière `youtube-banner-2560x1440.jpg`.
- Nom : **Quran Words Daily** (inchangé).
- Liens (affichés sous le nom de la chaîne) : Website, Facebook, Instagram, TikTok.
- E-mail de contact : `quranwordsdaily@gmail.com` (champ à part, pas dans la description).
- Filigrane `youtube-watermark-150.png` (Personnalisation → Branding ; sur ordinateur ou en
  « version pour ordinateur ») : il ne s'affiche que sur les vidéos longues, utile dès que les
  épisodes 16:9 de quran-themes-demo y seront.

Description (1 000 caractères au plus) :

```
Two Quran recitations every day, each a complete passage, never cut mid-sentence, with the Uthmani Arabic text, the Sahih International English translation and the meaning of its difficult words.

• Juz' 'Amma, then the whole Quran in order
• Themes: Ayat al-Kursi, du'a, provision, patience, repentance
• Every Friday: Surah Al-Kahf

Reciters: Omar Hisham Al-Arabi, Muhammad Siddiq Al-Minshawi, Tawfiq As-Sayegh, Fares Abbad.
Word meanings: Tafsir al-Muyassar (King Fahd Complex).
The Quran text, its translation and the word meanings are never written by AI: each comes from a published source, credited under every video.

كِتَـٰبٌ أَنزَلْنَـٰهُ إِلَيْكَ مُبَـٰرَكٌ لِّيَدَّبَّرُوٓا۟ ءَايَـٰتِهِۦ وَلِيَتَذَكَّرَ أُو۟لُوا۟ ٱلْأَلْبَـٰبِ
"[This is] a blessed Book which We have revealed to you, [O Muḥammad], that they might reflect upon its verses and that those of understanding would be reminded." (Surah Sad, 38:29, Sahih International)
```

Quand le premier épisode animé (quran-themes-demo) sera en ligne, la remplacer par celle-ci
(liste des récitateurs retirée pour la place) :

```
Two Quran recitations every day, each a complete passage, never cut mid-sentence, with the Uthmani Arabic text, the Sahih International English translation and the meaning of its difficult words.

• Juz' 'Amma, then the whole Quran in order
• Themes: Ayat al-Kursi, du'a, provision, patience, repentance
• Every Friday: Surah Al-Kahf
• Stories from the Quran, in Egyptian Arabic with English subtitles (AI narrator voice; the Quran is always recited by a real reciter)

Word meanings: Tafsir al-Muyassar (King Fahd Complex).
The Quran text, its translation and the word meanings are never written by AI: each comes from a published source, credited under every video.

كِتَـٰبٌ أَنزَلْنَـٰهُ إِلَيْكَ مُبَـٰرَكٌ لِّيَدَّبَّرُوٓا۟ ءَايَـٰتِهِۦ وَلِيَتَذَكَّرَ أُو۟لُوا۟ ٱلْأَلْبَـٰبِ
"[This is] a blessed Book which We have revealed to you, [O Muḥammad], that they might reflect upon its verses and that those of understanding would be reminded." (Surah Sad, 38:29, Sahih International)
```

Le verset 38:29 (« ليدبروا آياته », d'où vient le nom « آيات ») et sa traduction sont recopiés
tels quels de l'API Quran.com (texte uthmani, Sahih International, ressource 20), comme dans
les vidéos. Les récitateurs nommés sont ceux de YouTube (Salah Budair n'y est pas, Content ID) :
à mettre à jour si la rotation change.

Bio Instagram à ce moment-là (TikTok : pas la place, la bio reste telle quelle) :

```
Two Quran recitations every day 🌙
Arabic · English translation · word meanings
📖 Word of the day · Stories · Fridays: Al-Kahf
```

## Playlists

### YouTube : 7 maintenant, 2 avec les épisodes

YouTube est le seul des quatre où les playlists comptent : elles apparaissent dans la
recherche, sur la page de la chaîne et enchaînent les vidéos. Créer une playlist au moment où
sa première vidéo existe, jamais vide. Création dans l'app YouTube : sur un Short → ⋮ →
Enregistrer → Nouvelle playlist, **Publique**. Ordre : celui indiqué.

| # | Titre (≤ 150) | Description | Vidéos, dans l'ordre |
|---|---|---|---|
| 1 | `Juz' 'Amma · جزء عمّ` | `The surahs of Juz' 'Amma, recited in full, from An-Nas to An-Naba': Arabic text, English translation and word meanings.` | 114, 113, 112, 111, puis chaque sourate du matin ; 93 (publiée à la main) à sa place, après 94 |
| 2 | `Surah Al-Kahf · سورة الكهف` | `Surah Al-Kahf, read every Friday: its first ten verses, then the rest of the surah, passage by passage.` | 18:1-10 **une seule fois** (pas chaque vendredi), puis 18:11-14, 18:15-16… dans l'ordre des versets |
| 3 | `Ayat al-Kursi & the seven munjiyat · آية الكرسي والسبع المنجيات` | `Ayat al-Kursi (2:255), then the seven verses known as al-munjiyat.` | 2:255, 9:51, 6:17, puis la série |
| 4 | `Du'a from the Quran · آيات الدعاء` | `Verses where the prophets and the believers call upon their Lord.` | série du'a, quand elle commence |
| 5 | `Provision (rizq) · آيات الرزق` | `Verses about provision: who provides, and how it comes.` | série rizq |
| 6 | `Patience (sabr) · آيات الصبر` | `Verses where patience is commanded, praised or rewarded.` | série sabr |
| 7 | `Repentance · آيات التوبة والاستغفار` | `Verses that call to repentance and to seek forgiveness.` | série tawba |

Les descriptions reprennent les critères de choix des séries (`config/series/*.yaml`), sans
promesse de récompense (série munjiyat : « no promised reward »).

Avec les épisodes animés (quran-themes-demo), **par thème plutôt que par format** : un
spectateur qui cherche « patience » veut les versets et l'épisode, pas un rayon « épisodes ».

- l'épisode du du'a dans la playlist 4, la patience dans la 6, le repentir dans la 7 ;
  Moussa et al-Khadir, Dhul-Qarnayn dans la 2 (ce sont des passages d'Al-Kahf) ;
- 8 : `Stories from the Quran · قصص من القرآن` (khidr, qarnayn, puis les histoires à venir :
  épisode entier, puis ses 5 parties dans l'ordre) ;
- 9 : `3 wrong ideas · تلات أفكار غلط` (du'a, patience, repentir, comparaisons, tawakkul,
  khushu : les épisodes entiers).

Pas de playlist par récitateur pour l'instant : utile pour la recherche (« Minshawi »), mais
chaque Short serait à classer deux fois à la main. À faire quand l'audit YouTube permettra de
publier par l'API, playlists comprises.

### Facebook : 2 seulement

Les playlists de Page existent (vidéos ou reels, aide de Meta « Create a Facebook video or
reels playlist »), mais elles ne se créent que dans Meta Business Suite (sur téléphone : le
navigateur en « version pour ordinateur ») et ne se voient que dans l'onglet Vidéos/Reels de la
Page, où presque personne ne va : on regarde les reels dans le fil. Chaque reel serait à y
ajouter à la main. Je n'en ferais que deux, celles où l'on revient exprès :

- `Surah Al-Kahf on Friday · سورة الكهف يوم الجمعة` (même contenu que la playlist YouTube 2) ;
- `Juz' 'Amma · جزء عمّ`.

Instagram n'a pas de playlists ; TikTok en a, mais réservées pour l'instant aux comptes d'environ
10 000 abonnés (critère non publié, à vérifier dans l'app plus tard).

## Autres améliorations, par ordre d'importance

1. **TikTok : poster les brouillons.** 0 vidéo publique : tout le reste est inutile tant
   qu'aucun reel n'est posté depuis la boîte de réception TikTok (ou que l'audit TikTok ne
   permet la publication directe).
2. **YouTube : demander l'audit** (toujours à faire, voir CLAUDE.md). Sans lui, chaque Short,
   son titre et sa playlist se font à la main ; avec lui, le pipeline publie et range seul.
3. **Titres YouTube réguliers.** Les 10 Shorts ont au moins 5 formats différents (« سورة الضحى » seul,
   « #surahalkahf » dans le titre, « Surah Al-Ikhlas  · » avec deux espaces, sans référence
   pour 9:51). Prendre toujours le titre de la page `reel.html` (lien dans le ticket « 📋
   Légendes à copier »). Corrigé avec ce changement : une ayah seule s'écrit « (6:17) », plus
   « (6:17-17) » ni « (2:255-255) », dans toutes les légendes.
4. **Épingler 3 publications** sur Instagram, TikTok et Facebook : Ayat al-Kursi, Al-Kahf
   18:1-10 et celle qui marche le mieux (Ad-Duha sur YouTube). Un nouveau visiteur voit
   d'abord le meilleur, pas le dernier.
5. **« Vidéo associée » des Shorts** (YouTube, champ « Related video » à l'envoi) : chaque
   partie d'un épisode animé renvoie vers l'épisode entier ; chaque passage d'Al-Kahf vers le
   suivant. C'est le seul lien cliquable d'un Short.
6. Pas recommandé : des hashtags dans les bios (sur Instagram ils sont cliquables et emmènent le
   visiteur vers d'autres comptes ; sur TikTok ils prennent la place de la phrase), des
   horaires (« 7:30 Paris » ne dit rien à Kuala Lumpur), un verset dans les bios Instagram et
   TikTok (pas la place, et le texte uthmani s'affiche mal en petit), changer l'adresse
   Facebook `quranwordsdaily` pour coller à `@quran_words_daily` (Facebook refuse le « _ » et
   l'ancienne adresse est déjà dans l'app Meta et la politique de confidentialité).
