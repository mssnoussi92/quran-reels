# Profils des comptes : bio, images, playlists

Proposition du 2026-11-09, à appliquer **à la main** depuis le téléphone (aucune API utilisée).
Chaque texte est dans un bloc : le bouton « copier » de GitHub le prend tel quel. Les longueurs
sont comptées sous la limite de chaque plateforme.

**Le périmètre s'élargit** (le propriétaire, 2026-11-09) : la page ne publiera pas seulement des
versets récités, mais aussi des thèmes et des sujets variés (les épisodes de quran-themes-demo :
du'a, patience, repentir, khushu…, les histoires du Coran, plus tard celles racontées par le
Prophète ﷺ, les vertus, des collections). Les textes et les images disent donc **ce qui ne
change pas** (le Coran et la Sunna, pour la vie de tous les jours, toujours sourcés) plutôt que
la liste du moment ; un nouveau sujet n'oblige à refaire ni la bannière ni les bios.

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
  (remplacé par le Muyassar), « un passage par jour », et « aucune explication écrite par une
  IA » (faux pour la narration des épisodes). Corrigé dans `docs/index.html`, épisodes compris.

## Images (`assets/brand/`, refaites par `assets/brand/src/render.py`)

| Fichier | Où | Taille |
|---|---|---|
| `avatar-1080.jpg` | photo de profil des **4** comptes (la même partout) | 1080×1080 |
| `facebook-cover-1640x624.jpg` | photo de couverture Facebook | 1640×624 |
| `youtube-banner-2560x1440.jpg` | bannière YouTube | 2560×1440 |
| `youtube-watermark-150.png` | filigrane YouTube (vidéos longues : les épisodes 16:9) | 150×150 |

- Photo de profil : **« آيات » seul**, sans « QURAN WORDS DAILY » : à 40 px (taille d'un
  commentaire, d'une liste d'abonnements) le texte latin de l'ancienne icône devient une ligne
  grise illisible, et le nom de la page est toujours écrit à côté de la photo. Lisible jusqu'à
  36 px, tient dans le cercle de chaque plateforme. « آيات » couvre tous les sujets : des
  versets, et des signes (le même mot).
- Couverture et bannière : même ciel, même livre ouvert, en **deux langues** (les épisodes
  sont en arabe égyptien, les récitations traduites en anglais) : « Quran & Sunnah for everyday
  life » · « القرآن والسنة في حياتك اليومية » · « Recitations · Stories · Themes ». Un nouveau
  sujet entre dans « Themes » ; aucun horaire ni rythme écrit (« One Quran passage every day »
  était devenu faux). Texte dans la zone vue sur téléphone (Facebook : les 1 110 px du milieu ;
  YouTube : 1546×423 au centre). Les phrases sont en tête de `src/brand.html` (`TAG_EN`,
  `TAG_AR`, `KINDS`).
- `icon-1024.jpg` reste l'icône de l'app Meta (docs/plateformes.md), rien à changer là-bas.

Pour les enregistrer sur le téléphone : ouvrir le fichier sur GitHub
(`assets/brand/…`, bouton « Raw »), appui long sur l'image → enregistrer.

## Facebook (Page `quranwordsdaily`)

Photo de profil `avatar-1080.jpg`, couverture `facebook-cover-1640x624.jpg`.

Intro (bio de la Page, 101 caractères au plus) :

```
Quran & Sunnah for everyday life: daily recitations, stories and themes. Every source cited.
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
Quran & Sunnah for everyday life 🌙
Daily recitations · stories · themes
Arabic & English · every source cited
القرآن والسنة في حياتك اليومية
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
Quran & Sunnah for everyday life 🌙
Recitations · stories · themes
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
  « version pour ordinateur ») : il ne s'affiche que sur les vidéos longues, donc sur les
  épisodes 16:9.
- Bande-annonce de la chaîne (pour les non-abonnés), quand le premier épisode est en ligne :
  son premier reel (l'accroche), pas une récitation : c'est ce qui dit le mieux ce qu'est
  devenue la page.

Description (1 000 caractères au plus) :

```
Quran & Sunnah for everyday life · القرآن والسنة في حياتك اليومية

• Quran recitation, twice a day: whole passages with the Arabic text, the English translation (Sahih International) and the meaning of its difficult words (Tafsir al-Muyassar). Every Friday: Surah Al-Kahf.
• Themes for life: du'a, patience, repentance, trust in God, khushu…
• Stories from the Quran: Moses and al-Khidr, Dhul-Qarnayn…

Every verse and hadith comes from a published source, cited in the video. The Quran is always recited by a real reciter. Hadith: Sahih al-Bukhari, Sahih Muslim, Jami' at-Tirmidhi (graded by al-Albani). Themes and stories: Egyptian Arabic narration (AI-generated voice), English subtitles.

كِتَـٰبٌ أَنزَلْنَـٰهُ إِلَيْكَ مُبَـٰرَكٌ لِّيَدَّبَّرُوٓا۟ ءَايَـٰتِهِۦ وَلِيَتَذَكَّرَ أُو۟لُوا۟ ٱلْأَلْبَـٰبِ
"[This is] a blessed Book which We have revealed to you, [O Muḥammad], that they might reflect upon its verses and that those of understanding would be reminded." (Sad, 38:29)
```

Le verset 38:29 (« ليدبروا آياته », d'où vient le nom « آيات ») et sa traduction sont recopiés
tels quels de l'API Quran.com (texte uthmani, Sahih International, ressource 20), comme dans
les vidéos. Les exemples (thèmes, histoires) sont ceux qui seront en ligne en premier : en
changer de temps en temps, la phrase autour reste vraie.

**Avant de changer les bios, mettre en ligne au moins un épisode.** Les huit épisodes de
quran-themes-demo sont validés et prêts (releases `<épisode>-latest`) ; sans eux, « stories »
et « themes » promettent ce que la page ne montre pas encore.

## Ce qui ne change pas quand le périmètre s'élargit

- **Le nom reste « Quran Words Daily »**. Il pourrait sembler étroit pour des épisodes sur la
  patience ou les comparaisons, mais chaque sujet part d'un verset (règle des épisodes : un
  événement, puis son verset ; une leçon, puis sa preuve), le nom est sur chaque image des
  vidéos et dans quatre identifiants. Changer coûterait les abonnés qui le reconnaissent, pour
  un gain nul. À reconsidérer seulement pour des sujets sans aucun verset.
- **La promesse ne porte que sur les sources** : chaque verset et chaque hadith vient d'une
  source publiée, cité dans la vidéo ; le Coran est toujours récité par un vrai récitateur ;
  la voix de synthèse est déclarée. Pas « rien n'est écrit par une IA » : la narration des
  épisodes l'est, puis validée par le propriétaire.
- **Pas « tout l'islam »** : ni fatwas, ni actualité, ni débats entre écoles. Une page qui
  publie de tout perd ce qui la distingue (le sourcé, le calme) et s'expose aux polémiques ; un
  nouveau sujet entre par un des formats de `docs/formats.md` (quran-themes-demo) et la
  politique des hadiths (`content/policy.yaml`).
- **Deux publics sur un même fil** : les récitations parlent anglais (traduction), les épisodes
  arabe égyptien (sous-titres anglais). Les playlists et les publications épinglées font le
  tri ; regarder dans les statistiques qui regarde quoi après quelques semaines, et en reparler
  si l'un des deux publics décroche.

## Playlists

### YouTube : une architecture qui grandit avec les sujets

YouTube est le seul des quatre où les playlists comptent : elles apparaissent dans la
recherche, sur la page de la chaîne et enchaînent les vidéos. Trois familles, et une règle :
**chaque vidéo va dans 1 à 3 playlists au plus** (sa famille de format, son thème, sa sourate),
pour que le classement à la main reste tenable. Une playlist se crée avec sa première vidéo,
jamais vide. Création dans l'app YouTube : sur une vidéo → ⋮ → Enregistrer → Nouvelle
playlist, **Publique**. Titre : `<anglais> · <arabe>`.

**1. Par thème** (le cœur, une par thème, récitations et épisodes mêlés : celui qui cherche
« patience » veut les versets et l'épisode) :

| Titre | Description | Contenu |
|---|---|---|
| `Du'a · الدعاء` | `Calling upon Allah: verses of du'a from the Quran, and what the Quran and the Sunnah say about it.` | série « du'a » du soir, épisode `dua` |
| `Patience · الصبر` | `Patience in the Quran and the Sunnah: what it is, and what it is not.` | série « sabr », épisode `sabr` |
| `Repentance · التوبة` | `Turning back to Allah: verses of repentance and forgiveness, and the wrong ideas that keep people away.` | série « tawba », épisode `tawba` |
| `Provision · الرزق` | `Verses about provision (rizq): who provides, and how it comes.` | série « rizq » |
| `Trust in Allah · التوكل` | `Tawakkul in the Quran and the Sunnah.` | épisode `tawakkul` (+ 11:56 de la série munjiyat) |
| `Khushu · الخشوع` | `Presence of the heart in prayer.` | épisode `khushu` |
| `The comparison trap · فخ المقارنات` | `Comparing yourself to others, and gratitude.` | épisode `muqarana` |
| `Ayat al-Kursi & the seven munjiyat · آية الكرسي والسبع المنجيات` | `Ayat al-Kursi (2:255), then the seven verses known as al-munjiyat.` | 2:255, 9:51, 6:17, puis la série |

Chaque nouveau thème de quran-themes-demo (sincérité, gratitude, espérance…) ajoute **sa**
playlist, sur le même modèle ; un thème déjà ouvert reçoit ses nouvelles vidéos.

**2. Par sourate ou lecture suivie** :

| Titre | Description | Contenu |
|---|---|---|
| `Juz' 'Amma · جزء عمّ` | `The surahs of Juz' 'Amma, recited in full, from An-Nas to An-Naba': Arabic text, English translation and word meanings.` | 114, 113, 112, 111, puis chaque sourate du matin ; 93 (publiée à la main) à sa place, après 94 |
| `Surah Al-Kahf · سورة الكهف` | `Surah Al-Kahf for Friday: its recitation passage by passage, and its stories.` | 18:1-10 **une seule fois**, puis 18:11-14… dans l'ordre des versets ; les épisodes `khidr` et `qarnayn`, puis les gens de la caverne et l'homme aux deux jardins quand ils existeront |

Plus tard : `The Quran in order · القرآن بالترتيب` (quand la lecture passera à Al-Fatiha),
`Surah Yusuf · سورة يوسف` si l'histoire de Youssouf est faite en cinq parties.

**3. Par format** (pour ceux qui aiment un genre plus qu'un thème) :

| Titre | Contenu |
|---|---|
| `Stories from the Quran · قصص من القرآن` | `khidr`, `qarnayn`, puis chaque histoire : épisode entier, puis ses parties dans l'ordre |
| `3 wrong ideas · تلات أفكار غلط` | les épisodes `misconceptions` : du'a, patience, repentir, comparaisons, tawakkul, khushu |
| `Stories told by the Prophet ﷺ · قصص من السنة` | quand la première sera faite (les trois hommes de la grotte, le lépreux, le chauve et l'aveugle…) |

Une récitation du soir va donc dans 1 playlist (son thème), une du matin dans 1 (sa sourate),
un épisode dans 2 (son thème et son format), une histoire d'Al-Kahf dans 2 (Al-Kahf et
« Stories »). Les descriptions reprennent les critères des séries (`config/series/*.yaml`) ou
le titre validé de l'épisode, sans promesse de récompense (série munjiyat : « no promised
reward ») : à relire par le propriétaire comme le reste.

Pas de playlist par récitateur pour l'instant : utile pour la recherche (« Minshawi »), mais
chaque Short serait à classer une fois de plus à la main. À faire quand l'audit YouTube
permettra de publier par l'API, playlists comprises.

### Facebook : 3 seulement

Les playlists de Page existent (vidéos ou reels, aide de Meta « Create a Facebook video or
reels playlist »), mais elles ne se créent que dans Meta Business Suite (sur téléphone : le
navigateur en « version pour ordinateur ») et ne se voient que dans l'onglet Vidéos/Reels de la
Page, où presque personne ne va : on regarde les reels dans le fil. Chaque reel serait à y
ajouter à la main. Je n'en ferais que trois, celles où l'on revient exprès ou qu'on regarde
d'affilée :

- `Surah Al-Kahf · سورة الكهف` (même contenu que sur YouTube) ;
- `Stories from the Quran · قصص من القرآن` (les parties d'une histoire se suivent) ;
- `Juz' 'Amma · جزء عمّ`.

Instagram n'a pas de playlists ; TikTok en a, mais réservées pour l'instant aux comptes d'environ
10 000 abonnés (critère non publié, à vérifier dans l'app plus tard).

## Autres améliorations, par ordre d'importance

1. **TikTok : poster les brouillons.** 0 vidéo publique : tout le reste est inutile tant
   qu'aucun reel n'est posté depuis la boîte de réception TikTok (ou que l'audit TikTok ne
   permet la publication directe).
2. **YouTube : demander l'audit** (toujours à faire, voir CLAUDE.md). Sans lui, chaque Short,
   son titre et ses playlists se font à la main, et le classement grossit avec chaque sujet ;
   avec lui, le pipeline publie et range seul.
3. **La playlist écrite à côté du titre.** En attendant l'audit : que la page `reel.html`
   (récitations) et les notes de release de quran-themes-demo (épisodes) donnent, pour chaque
   vidéo, les playlists YouTube où la mettre, comme elles donnent déjà le titre. Pas fait :
   à décider (une correspondance série → playlist dans `config/series/*.yaml`, thème →
   playlist dans les épisodes).
4. **Titres YouTube réguliers.** Les 10 Shorts ont au moins 5 formats différents (« سورة الضحى »
   seul, « #surahalkahf » dans le titre, « Surah Al-Ikhlas  · » avec deux espaces, sans
   référence pour 9:51). Prendre toujours le titre de `reel.html` (lien dans le ticket
   « 📋 Légendes à copier »). Corrigé avec ce changement : une ayah seule s'écrit « (6:17) »,
   plus « (6:17-17) » ni « (2:255-255) », dans toutes les légendes.
5. **Épingler 3 publications** sur Instagram, TikTok et Facebook, une par pilier : Ayat
   al-Kursi (récitation), le premier reel d'un épisode (thème), Al-Kahf 18:1-10 ou une histoire.
   Un nouveau visiteur voit d'un coup ce qu'est la page, pas seulement la dernière vidéo.
6. **« Vidéo associée » des Shorts** (YouTube, champ « Related video » à l'envoi) : chaque
   partie d'un épisode renvoie vers l'épisode entier ; chaque passage d'Al-Kahf vers le
   suivant. C'est le seul lien cliquable d'un Short.
7. Pas recommandé : des hashtags dans les bios (sur Instagram ils sont cliquables et emmènent le
   visiteur vers d'autres comptes ; sur TikTok ils prennent la place de la phrase), des
   horaires (« 7:30 Paris » ne dit rien à Kuala Lumpur), un verset dans les bios Instagram et
   TikTok (pas la place, et le texte uthmani s'affiche mal en petit), changer l'adresse
   Facebook `quranwordsdaily` pour coller à `@quran_words_daily` (Facebook refuse le « _ » et
   l'ancienne adresse est déjà dans l'app Meta et la politique de confidentialité).
