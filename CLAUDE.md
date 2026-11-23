# Quran Words Daily — contexte projet

Pipeline open source qui produit chaque jour un reel vertical (1080×1920) d'un passage du Coran
et le publie sur Facebook, Instagram, TikTok et YouTube Shorts.

Comptes : Facebook `quranwordsdaily` · Instagram / YouTube `quran_words_daily` · TikTok
`quran.words.daily` (renommé le 2026-11-09, avant `quran_words_daily6` ; `@quran_words_daily` y
est le compte vide de quelqu'un d'autre, à signaler, docs/profils.md) ·
e-mail du projet `quranwordsdaily@gmail.com`. Le propriétaire travaille depuis son téléphone
(pas de PC) : tout doit tourner dans le cloud (session Claude, GitHub Actions).

**Le contredire, toujours** (demande du propriétaire, 2026-11-08) : quand une de ses idées ou de ses
décisions, ou une des tiennes, est fausse ou plus faible qu'une autre (source, récitateur, fond, série,
choix technique), dis-le franchement, avec la raison et ce que tu ferais à la place. Il tranche ; ne suis
jamais en silence, ne passe jamais outre en silence.

**Les questions, toujours à choix** (demande du propriétaire, 2026-11-15 : « toujours fait ça si t'as des
questions, et je veux que toutes les sessions futures feront ça ») : toute question pour lui (une décision, une
validation, un choix entre options) se pose avec l'outil de questions à choix (`AskUserQuestion`), pas dans un
paragraphe : chaque question tient seule (il ne voit peut-être que la fenêtre de la question), 2 à 4 options, ta
recommandation en premier marquée « (Recommandé) », un aperçu quand il aide (un texte, une légende) ; il peut toujours
répondre autre chose. Le message garde le contexte, les chiffres et la contradiction franche. Une validation par un
choix vaut sa parole si l'option nomme exactement ce qui est validé. Sans cet outil (session planifiée, personne en
face) : la question va dans le rapport, ses options numérotées.

**L'amélioration continue** (demande du propriétaire, 2026-11-21 : « le workflow est censé évoluer, pas l'utiliser tel
qu'il est ; il faut que toutes les sessions sachent ça ; s'il trouve des optimisations, des améliorations ou un besoin
d'ajouter, il n'hésite pas : on est dans l'amélioration continue, on tire les stats petit à petit et on continue de
produire de meilleures choses ») : workflows, outils, gabarits, miniatures, titres et statistiques sont faits pour
évoluer, ici comme dans quran-themes-demo. Une session qui voit une optimisation, une amélioration ou un manque le dit
et le propose, avec sa raison et les chiffres quand il y en a (page « Statistiques », `insights.yml` avec
`youtube_detail`) ; ce qui touche une décision du propriétaire (un texte, le calendrier, un récitateur…) lui est
demandé comme toujours, le reste se fait (PR, checks, fusion). Chaque changement part de ce que disent les mesures,
et se mesure ensuite.

## Décisions validées

| Sujet | Choix |
|---|---|
| Format | **≈ 1 minute** (cible 60 s, 40–90 s), jamais coupé au milieu d'une phrase ; **sourate courte entière** (≤ 90 s, même très courte) ; **le soir, le passage de la série tel quel, même une seule ayah** (15 à 30 s : 76 des 111 passages des séries du soir sont une seule ayah ; constaté sur les reels publiés le 2026-11-09, gardé ainsi le 2026-11-10 : la série dit quelle ayah, on ne la noie pas dans son contexte pour atteindre la minute) |
| Basmala | **Publications automatiques sans basmala depuis le 2026-11-16, jusqu'à ce que le propriétaire la remette** (choix du 2026-11-15, début de sourate compris, contre l'avis de la session : les qurra' la récitent toujours au début d'une sourate ; `content.basmala.days_off` de project.yaml : `from`, `until` vide ; la remettre = `until` au dernier jour sans elle) ; 1:1 reste (une ayah) ; **à la demande : case « Basmala »** du formulaire, cochée par défaut comme le calendrier du jour (section `### Basmala` : oui, non, auto). Avant : au début de chaque vidéo, même pour quelques versets ; sauf sourate 9 et avant 1:1 (qui est la basmala) |
| Rythme | Depuis le 2026-11-14 (choix du propriétaire, 2026-11-13) : **chaque matin à 07:30** (heure de Paris) la lecture dans l'ordre, le vendredi matin Al-Kahf un passage par vendredi ; **le dimanche soir à 18:00** les séries thématiques (à 19:30 jusqu'au 2026-11-19 ; 18:00 à sa demande, avec les vidéos thématiques ; file `themes` ; celui du 2026-11-15 annulé par le propriétaire, premier le 2026-11-22) ; avant : 2 par jour, 07:30 lecture et 19:30 séries. Jours d'un créneau : `days` (périodes `from` / `until` / `weekdays`) dans `config/schedule.yaml`. Reels en pause du 2026-11-12 au soir au 2026-11-13 au matin (`pause` : les épisodes thématiques démarraient) |
| Images | **Word of the day**, carrousel de 3 images 1080×1350 (le mot, son ayah, son sens dans le Tafsir al-Muyassar), 1 par jour à 11:30 UTC sur Instagram et Facebook, **en pause depuis le 2026-11-15** (choix du propriétaire : 4 vues en médiane par publication sur Instagram, 21 vues en tout sur Facebook en 9 jours ; `enabled: false`, prêt à reprendre) ; **Ayah of the day** préparé, désactivé (docs/images.md) |
| Lecture | **Juz' 'Amma d'abord** (114 → 78), puis Al-Fatiha et 2 → 77, passages de `config/plan.yaml` |
| Thèmes | Ayat al-Kursi, les 7 versets « المنجيات », versets de du'a, versets du rizq, puis (proposés le 2026-11-06) la patience (ص ب ر) et le repentir (ت و ب)… : listes **proposées par l'IA en PR, validées par le propriétaire** |
| Vendredi | **Al-Kahf** (choix du propriétaire, 2026-11-05) : **depuis le 2026-11-20, le vendredi matin, la sourate un passage par vendredi** (série `al-kahf`, à partir de 18:17-18, là où le soir s'était arrêté ; choix du propriétaire, 2026-11-13, avec 1 reel par jour) ; avant : le matin **18:1-10 chaque vendredi** (`kahf-first-ten`, plus jouée), le soir la suite **à partir de 18:11** (36 passages), puis on recommence |
| Texte arabe | Uthmani (Hafs), police **Amiri Quran** (OFL) |
| Traduction | **Sahih International** (anglais), créditée dans chaque légende |
| Mots difficiles | **غريب التفسير الميسر** (Tafsir al-Muyassar, Complexe du Roi Fahd ; `almuyassar-ghareeb` sur tafsir.app), choix du propriétaire le 2026-11-05 (avant : Ibn Qutaybah, *Tafsir Gharib al-Qur'an*), sens en arabe, **1 à 3 mots liés** surlignés |
| Récitateurs | **Choisis par passage** (`content.rotation`, `reciters.py`) parmi ceux du propriétaire (2026-11-05) : **Omar Hisham Al-Arabi, Muhammad Siddiq Al-Minshawi, Tawfiq As-Sayegh, Salah Budair, Fares Abbad** (EveryAyah, ajouté depuis le catalogue, ticket #19, directement dans la rotation sans essai sur Facebook seul : choix du propriétaire) : prêt pour le passage (découpe vérifiée), ≤ 90 s, **Omar Hisham d'abord dès que sa découpe du passage est vérifiée** (choix du propriétaire, 2026-11-21 : `content.rotation.prefer` ; ses enregistrements de Juz' 'Amma enchaînent les ayahs sans pause et se vérifient rarement), sinon pas un des 2 derniers publiés, puis le plus proche de 60 s (passage long → récitateur rapide, sourate courte → plus lent). Écartés : Alafasy, **Nabil Ar-Rifai** (Rights Manager : 2:255 rendue muette par Facebook dans 24 territoires, 2026-11-05) et **Saad Al-Ghamdi** (2:255 revendiquée par UMG, muette en Russie, le même soir), Hudhaifi, Ayyub, Akhdar (après écoute) ; un récitateur revendiqué après publication est écarté automatiquement (`claimed`) ; **en essai** : Husary (ticket #32, EveryAyah, Facebook seul d'abord) ; **YouTube : toujours Tawfiq As-Sayegh** (choix du propriétaire, 2026-11-11, `platforms.youtube.reciter` : aucune revendication constatée sur ses récitations, la voix des épisodes thématiques de la même chaîne) : un reel d'un autre récitateur a sa version YouTube par lui ; pas prêt pour le passage → rien pour YouTube ce créneau, aucun autre à sa place ; Budair y reste revendiqué (Content ID, 2026-11-06) |
| Droits | **Vérification Meta avant chaque publication** : brouillon Facebook + conteneur Instagram, publiés seulement si Meta répond `complete` sans correspondance, sinon rien n'est publié (TikTok compris) ; **sauf** Instagram en `error` sans correspondance aux deux envois avec Facebook propre : laissé de côté, le reel part sur les autres et l'alerte le dit (choix du propriétaire, 2026-11-20, docs/plateformes.md). Elle n'a vu ni Alafasy, ni Ar-Rifai, ni Al-Ghamdi (revendications arrivées quelques minutes après la publication). Contrôle après publication prêt (`rights_after_timeout` > 0 : relu 5 min puis à chaque run pendant 2 jours ; muet ou bloqué → retiré de Facebook et Instagram + alerte, récitateur écarté) mais **désactivé : le propriétaire vérifie lui-même pour l'instant** (2026-11-05) ; nouveaux récitateurs testés sur Facebook seul, Instagram ensuite |
| YouTube | **Shorts du calendrier mis en ligne par le run, en public** (choix du propriétaire, 2026-11-21 : « les reels d'abord » ; YouTube ne verrouille plus en privé ce qu'un projet non audité met en ligne par l'API depuis le 2026-11-02, et donne 100 mises en ligne par jour) : la version YouTube du créneau (Tawfiq As-Sayegh), juste après le reel s'il est sorti, avec les textes de la page « À publier », après la vérification de Meta sur ce fichier même (règle 6), jamais deux fois ; seulement une fois le propriétaire connecté pour cela (`YOUTUBE_UPLOAD_REFRESH_TOKEN`, fait le 2026-11-21 ; avant : à la main) ; **les vidéos thématiques aussi, par le run `themes`** (choix du propriétaire, 2026-11-21 : shorts et films, miniature comprise ; le film 16:9 sur la vérification de son jumeau 9:16, même son ; « contenu synthétique » : non ; **description et hashtags, jamais les crédits**, son choix ; docs/themes.md) ; **demandes : à la main** ; la « vidéo associée » d'un Short, absente de l'API : à la main (`platforms.youtube.upload`, docs/plateformes.md) ; **langue arabe déclarée** à chaque envoi et **sous-titres exacts des reels** (mushaf et Sahih International, tirés du manifeste, envoyés la nuit par le workflow `playlists` ; choix du propriétaire, 2026-11-21 : `captions.py`) ; ni tags ni « non répertorié 24 h » (YouTube : rôle minime, aucun effet) ; **playlists rangées chaque nuit par le run** (choix du propriétaire, 2026-11-21 : « reprends les miennes et ajoute s'il n'existe pas » ; ses 6 playlists reprises par leur identifiant, titres en arabe d'abord, chaque vidéo publiée depuis le 2026-11-21 ajoutée à la fin, une playlist par série nouvelle à sa première vidéo ; workflow `playlists`, config/playlists.yaml, son jeton `YOUTUBE_PLAYLISTS_REFRESH_TOKEN`) ; **description et mots-clés de la chaîne** validés par lui (2026-11-21, `config/channel.yaml`, appliqués une fois par le workflow `youtube-channel` ; une marque de sens invisible au début des lignes qui en ont besoin, `bidi.py`, pour que l'arabe et l'anglais se lisent bien partout ; de même dans la description de chaque vidéo mise en ligne, sauf hashtags, mention, chapitres et liens) ; **le nom arabe d'une série ajouté aux mots-clés la nuit de sa première vidéo** par le workflow `playlists` (son choix, même soir), jamais un retiré, à 500 caractères le run le dit |
| Fond | **choisi selon ce que dit le passage** (montagnes, mer, rivières, jardins, nuit, aube, ciel…) : vidéos Pexels choisies par le propriétaire et scènes générées (aube, nuit, mer), **sans personnes ni animaux** ; scènes **animées** au rythme d'un ciel filmé (nuages, brume, vagues, lumière) avec un **zoom lent** sur toute la vidéo, le texte immobile (Facebook : « image statique » sur 6:17, 2026-11-09) |
| Exécution | GitHub Actions (dépôt public → gratuit), migrable sur le homelab (Docker) |
| À la demande | Reel choisi depuis le téléphone (récitateur, sourate entière ou ayahs X à Y, fond, plateformes, **mots expliqués** cochés dans le formulaire **avant le ticket**, sous les ayahs affichées, ou `/mots 1 4` après l'aperçu, parmi les sens numérotés du Muyassar, jamais écrits ; extraits du Muyassar publiés sur le site pour le formulaire, choix du 2026-11-06) : catalogue → ticket prérempli → **aperçu** en commentaire → publié seulement après **`/publier`** du propriétaire ; **en plus** des 2 créneaux ; le calendrier **ne saute pas** un passage publié à la demande ; YouTube coché : une seule vidéo par demande, donc « Auto » = Tawfiq As-Sayegh pour tout le reel, et YouTube retiré de la demande avec un autre récitateur (choix du 2026-11-11, docs/on-demand.md) |
| Périmètre | **Pas seulement des versets récités** : la page publiera aussi des thèmes et des sujets variés (épisodes de quran-themes-demo : thèmes, histoires…), choix du propriétaire le 2026-11-09 ; bios, images et site disent ce qui ne change pas (le Coran et la Sunna au quotidien, toujours sourcés), pas la liste du moment (docs/profils.md) |
| Vidéos thématiques | **Publiées automatiquement à partir du 2026-11-19** (choix du propriétaire, 2026-11-15 ; le 2026-11-19, il avance le départ prévu le 2026-11-23 à ce jour même) : celle du jour de `docs/retention/calendar.md` de quran-themes-demo à **18:00** (19:00 jusqu'à sa demande du 2026-11-19), **13:00 à partir du 2026-11-27** (choix du propriétaire, 2026-11-21 : ses spectateurs YouTube sont là de 14 h à 16 h en semaine ; `times` de config/themes.yaml ; essai mesuré, `trials`), du lundi au samedi, ses textes validés mot pour mot (`publication-<doc>.md`), ses fichiers de la pré-release publique `page-<doc>` ; Facebook et Instagram après la vérification des droits de Meta (sinon rien, TikTok et YouTube compris), **TikTok en brouillon** (le propriétaire publie), **YouTube par le run depuis le 2026-11-21** (à la main avant ; ligne « YouTube ») ; avant le 19, le propriétaire publiait à la main (docs/themes.md) ; **version courte sur Facebook, Instagram et YouTube** quand la ligne des fichiers d'un short en nomme une (`…-cut.mp4`, essai choisi par le propriétaire le 2026-11-16 sur les trois shorts de Dhul-Qarnayn, 24 à 26 novembre ; YouTube ajouté le 2026-11-18, son choix : le fichier de la page « À publier », reconnu à sa durée dans les statistiques ; mêmes textes ; TikTok garde le short entier ; comparée à part sur la page « Statistiques ») ; **plusieurs vidéos le même jour**, chacune sur ses plateformes, jamais deux sur la même (2026-11-17 : le quiz « معاك 5 ثواني » sur Instagram les lundis d'un film) ; **la page test « معاك 5 ثواني »** (Facebook et Instagram, `@ma3ak.5.thawani`, son jeton `META_PAGE_TOKEN_5`) **publiée chaque jour à 18:00 depuis le 2026-11-19** (demande du propriétaire : `themes.yml` avec `page: ma3ak`, `config/themes-ma3ak.yaml`, `calendar-ma3ak.md` de quran-themes-demo ; statistiques dans `insights-ma3ak.json` ; docs/themes.md, docs/insights.md), jamais sur la Page |
| Chiffres | **123, jamais ١٢٣** (demande du propriétaire, 2026-11-17 : « les nombres doivent être 123 et non pas ١٢٣ ; à mémoriser pour toutes les sessions », même règle dans quran-themes-demo) : ligne de série (« آيات الدعاء · 3 من 38 »), références, titres, légendes, images, catalogue, textes ; **seule exception, son choix** : le numéro qui ferme une ayah dans le texte coranique (﴿١٩﴾ des reels, des légendes et des images, `arabic_digits`), comme dans le mushaf ; ce qui est déjà publié n'est pas refait |
| Titres | **Toujours en arabe et en anglais** (choix du propriétaire, 2026-11-09) : noms des comptes, série et sourate en tête des légendes (`render.series_line`, `render.surah_line` : « آيات الدعاء · Supplications from the Quran · 3/38 », « سورة الضحى · Surah Ad-Duhaa (93:1-11) »), titres YouTube (raccourcis par parties entières, jamais une seule langue), le compteur d'une série en dernier ; **l'arabe d'abord partout, titres et descriptions, sur toutes les plateformes** (choix du propriétaire, 2026-11-21 : « je veux l'arabe d'abord partout titres et description » ; 74 % des vues de la chaîne viennent de pays arabophones et les recherches qui amènent des vues sont en arabe ; il corrige une session qui avait compris « l'anglais d'abord sur Facebook, Instagram et TikTok » et l'avait appliqué, PR #100 : ne pas y revenir sans sa décision) ; reels : légendes Facebook, Instagram, TikTok et `caption.txt` ; vidéos thématiques : `publish.py` de quran-themes-demo ; les reels déjà publiés gardent leur légende, leurs titres YouTube se changent à la main dans Studio ; Word of the day, playlists, images ; le texte des ayahs reste hors de la légende Facebook |
| Comptes pro | Page Facebook + Instagram en type **Créateur**, reliés |
| Signature | **@quran_words_daily** sur chaque image, dans la zone sûre (repartages) ; **TikTok : `@quran.words.daily`** (choix du propriétaire, 2026-11-09 : `@quran_words_daily` y est à quelqu'un d'autre) : sa propre version de chaque reel (`platforms.tiktok.signature`, `render.signatures` : calque fixe redessiné, `out/<passage>/tiktok.mp4`) et la même signature à la fin de sa légende (`Reel.for_platform`) |
| Hashtags | Fin de légende, dans l'ordre : `#QuranWordsDaily`, `#Quran`, 1er tag de la série, sourate (`#SurahAdDuhaa` `#سورة_الضحى`), `#القرآن_الكريم`, autres tags de la série, récitateur, gloses (`#تفسير_القرآن`) ; **Instagram et TikTok : les 5 premiers** (leur limite), **l'arabe d'abord depuis le 2026-11-24** (essai choisi par le propriétaire le 2026-11-23 : « #القرآن_الكريم #سورة_… #جزء_عم #QuranWordsDaily #Quran », `platforms.<nom>.hashtags: arabic_first`), Facebook 8, `caption.txt` tous (YouTube : description et tags). **Facebook : légende courte, ≤ 400 caractères hashtags compris** (sa liste de qualité, 2026-11-09) : série et référence (titres en arabe et en anglais), crédits sur une ligne, signature, hashtags ; ni le texte arabe des ayahs ni la traduction (dans la vidéo ; choix du propriétaire) ; trop longue → des hashtags de la fin. **Instagram et TikTok : légende courte** (2026-11-15) : la même, plus le texte arabe des ayahs, sans la traduction ; **Instagram sans le texte des ayahs depuis le 2026-11-21** (choix du propriétaire : « Instagram coupe parfois la couverture à cause des mots dans les versets » ; `platforms.instagram.caption_verses: false`, TikTok le garde) ; YouTube (`caption.txt`) garde tout |

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
6. **Rien n'est publié sans la vérification des droits de Meta** (`publishers/rights.py`) : une
   récitation reconnue par Rights Manager fait couper ou rendre muet le reel (93:1-11 sur
   Facebook, 2026-11-05, Alafasy ; 2:255, Ar-Rifai, muette dans 24 territoires). Le propriétaire
   vérifie chaque nouveau récitateur sur Facebook avant Instagram ; un contrôle automatique après
   publication existe (`rights_after_timeout`, désactivé pour l'instant).

## Seul le propriétaire

Les outils GitHub d'une session agissent **sous le compte du propriétaire** : un commentaire, un
lancement ou une fusion faits par une session passent les contrôles « propriétaire seulement »
des workflows. Une session ne fait donc jamais de son propre chef, seulement sur sa demande
explicite pour cette action :

- poster `/publier`, `/essai`, `/mots`, `/youtube` ou toute autre commande sur un ticket ;
- lancer `publish-test.yml` en `mode: publish` (taper `PUBLIER`), ni rouvrir un créneau
  (`state reopen`), ni enregistrer une publication (`state record`) ;
- pousser sur `main` (tout passe par une PR), ou fusionner une PR hors de la règle ci-dessous ;
- supprimer un reel, un ticket, une release.

Lancer `daily.yml`, `images.yml` ou `prepare.yml` sur `main` sans entrées reste permis (ils
décident seuls de ce qui est dû et ne publient rien deux fois) ; c'est le rôle du planificateur.

**Fusion des PR : la session suit sa PR et la fusionne elle-même** (choix du propriétaire,
2026-11-17 : « que toutes les sessions suivent la merge et la mergent automatiquement quand les
checks passent » ; même règle dans quran-themes-demo). Après avoir ouvert une PR, la session :

1. attend la fin de ses checks (ici `tests.yml` : pytest et ruff ; `pull_request_read`,
   `get_check_runs`, toutes les 30 à 60 s), jamais avant ; aucun check lancé en 10 minutes : ne
   pas fusionner, le dire ;
2. **checks verts et PR fusionnable** : la fusionne (`merge_pull_request`, méthode `merge`).
   Pas fusionnable (`main` a bougé) : fusionner `main` dans la branche, repousser, attendre de
   nouveau les checks (jamais de force push). **Checks rouges** : corriger et repousser, jamais
   fusionner, jamais désactiver ni sauter un test ;
3. **sauf une PR qui porte une décision du propriétaire pas encore donnée** (choix du 2026-11-17) :
   série proposée, changement de calendrier (`schedule.yaml`, `calendar.md`), texte, accroche ou
   titre à valider, récitateur ajouté ou retiré, et tout ce que ce fichier dit « validé par le
   propriétaire en PR » : elle attend son « je valide » dans la conversation (question à choix
   qui nomme la PR), puis la fusionne de même ;
4. après la fusion, fait ce que la PR annonçait (relancer un workflow, vérifier la page déployée)
   et le dit en une ligne avec le lien. Seulement ses propres PR : ni Dependabot, ni celle d'une
   autre session sans la demande du propriétaire. Un commit poussé après la fusion n'est pas
   fusionné : il part dans une nouvelle PR (2026-11-17 : le skill de la revue, poussé une
   minute après la fusion de la #74, n'était pas arrivé sur `main`).

## Architecture

```
config/            project.yaml (choix éditoriaux), backgrounds.yaml (fonds et thèmes),
                   images.yaml (formats image, heure UTC), exclude.yaml (ayahs jamais en image),
                   image-candidates.yaml (candidats image figés : `quran-reels images build`),
                   glosses.yaml (choix éditoriaux : 1 à 3 mots surlignés par sens),
                   schedule.yaml (créneaux, files, vendredi), series/*.yaml (séries),
                   plan.yaml (tout le Coran découpé, figé : `quran-reels plan --write`)
src/quran_reels/
  models.py        AyahRef, Ayah, GlossEntry, WordGloss, Passage, Reel, PublishResult
  config.py        chargement de config/, chemins (.cache/, out/)
  arabic.py        normalisation uthmani/imla'i, ancrage d'une glose sur un mot de l'ayah
  ingest.py        `quran-reels ingest` : jeux de données → .cache/
  passage.py       assemble un passage : texte + traduction + gloses ancrées + audio
  sources/         quran_com (texte, sourates, traduction), tafsir_app (gloses),
                   everyayah (audio), backgrounds (choix du fond par thème, clips en boucle),
                   scenes/ (scènes générées : shaders GLSL dessinés dans Chromium), http
  selector/        plan.py : découpe d'une sourate en passages d'≈ 1 min ;
                   calendar.py : créneaux, files de séries, vendredi, état, vérification des séries
  render/          frames.py (template HTML → PNG, Chromium/Playwright), screens.py (longue
                   ayah sur plusieurs écrans),
                   video.py (minutage audio + ffmpeg → MP4), __init__ (orchestration)
  publishers/      un adaptateur par plateforme, interface commune `Publisher` (dry_run) :
                   meta.py (client Graph, contrôle du jeton), facebook.py, instagram.py
                   (prepare → rights → commit), rights.py (vérification des droits Meta),
                   tiktok.py (brouillon dans la boîte TikTok, connexion OAuth),
                   youtube.py (Short du calendrier mis en ligne par le run, envoi reprenable)
  publish.py       `quran-reels publish|meta-check|tiktok-auth` : contrôle, publication, résumé
  gh_secrets.py    réécrit un secret Actions (refresh token TikTok) via gh + GH_SECRETS_TOKEN
  daily.py         `quran-reels daily` : créneaux dus maintenant → rendu → publication → état
                   (écrit dès que le reel est sorti) → reprise dans le run d'une plateforme
                   qui n'a rien reçu (`platforms.retry`, `publish.to_retry`)
  images/          publications image (docs/images.md) : candidates.py (règles 1-4, liste
                   figée), select.py (exclusions, ordre stable, état), cards.py + templates/
                   (1080×1350), caption.py, publish.py (carrousel Instagram, post Facebook
                   multi-photos), daily.py (`quran-reels images run`)
  themepub/        vidéos thématiques sur la Page (docs/themes.md) : texts.py (publication-<doc>.md :
                   textes par plateforme, fichiers), calendar.py (calendar.md tel qu'écrit → la vidéo
                   de chaque plateforme, jamais la ligne d'avant), run.py (`quran-reels themes run|check` :
                   dû à 18:00, téléchargement de `page-<doc>`, droits Meta, publication, `themes.json`) ;
                   Facebook toujours en reel, film compris (jusqu'à 15 min : seule voie où Meta vérifie
                   les droits avant publication, essais du 2026-11-15) ; Instagram : une copie réencodée
                   sans edit list (`for_instagram`), mise dans la release `reels` et téléchargée par
                   Instagram (`video_url` : l'envoi direct d'un short de 2 min échouait toujours) ;
                   publishers/facebook_video.py (/{page}/videos) n'a pas de vérification, il ne publie rien ;
                   YouTube (2026-11-21) : `to_youtube`, après la vérification de Meta, miniature comprise
  playlists.py     `quran-reels youtube-playlists` : les playlists YouTube (ses 6 reprises, une par série
                   nouvelle), chaque nuit par le workflow `playlists` après `insights`, et les sous-titres
                   en attente (captions.py : pistes exactes des reels, écrites par le run du matin)
  notify.py        `quran-reels notify` : tickets GitHub (alerte d'échec, légendes à copier ;
                   les images ont leur propre alerte, `--alert images`, depuis le 2026-11-15)
  feed.py          la page « À publier » (docs/publier.html, lien fixe) : `feed.json` sur
                   `previews`, les 14 derniers jours, refait avec chaque `reel.json` (reels et
                   vidéos thématiques)
  insights/        statistiques de la Page (docs/insights.md) : collect.py (`quran-reels insights
                   collect` : abonnés, publications des 35 jours, relevés à 48 h / 7 j / 28 j,
                   arrêt à 75 % du budget Meta → `insights.json` sur `state` ; `insights add` :
                   chiffres des captures YouTube/TikTok), classify.py (créneau, Word of the day,
                   vidéo thématique reconnue par son titre), metrics.py (chiffres Meta → vues,
                   accroche à 3 s, durée regardée, partages…), themes.py (publication-*.md et
                   calendar.md de quran-themes-demo, lus en ligne), youtube.py (`quran-reels insights
                   youtube` : la chaîne, Data API + Analytics API ; `youtube-auth`) ; lecture seule
  ondemand/        publication à la demande (docs/on-demand.md) : request.py (ticket), check.py
                   (mêmes règles que le calendrier, plages valides proposées), commands.py
                   (propriétaire seulement, approbation), flow.py (`quran-reels on-demand
                   route|check|preview|publish|youtube|words|daily-files`), words.py (sens du
                   Muyassar numérotés, choix `/mots` vérifié → `passage.build(glosses=…)`),
                   media.py (aperçu 540p, images clés), files.py (release `reels`, branche
                   `previews`), state.py
  catalog/         `quran-reels catalog build` : catalogue public en lecture seule (+ formulaire
                   « Publier » : ondemand.py écrit surahs/SSS.json, fins de phrase et sens du
                   Muyassar numérotés, téléchargés 15 min max par construction)
                   (docs/catalog.md) : récitateurs (+ candidats EveryAyah), fonds (aperçus
                   360p), calendrier et séries (+ vidéos thématiques de quran-themes-demo),
                   publications, statistiques (stats.py → stats.html) ; décisions par tickets préremplis ;
                   history.yaml (revendications, clips refusés) ; ne modifie rien
  cli.py           `quran-reels ingest|render|passages|plan|series-check|calendar|daily|publish|catalog`
tests/             pytest, sans réseau
.github/workflows/ daily.yml (cron 2 créneaux × 3 essais ; ne publie rien tant que
                   schedule.yaml dit enabled: false ; état sur la branche `state`),
                   publish-test.yml (manuel : dry-run, ou publication réelle avec PUBLIER),
                   tiktok-auth.yml (manuel : échange du code TikTok → TIKTOK_REFRESH_TOKEN)
                   youtube-auth.yml (manuel : échange du code Google → YOUTUBE_REFRESH_TOKEN, lecture
                   seule, pages docs/youtube-login.html et youtube-callback.html)
                   prepare.yml (chaque nuit : découpes vérifiées de la semaine → `state` ;
                   son propre groupe de concurrence, hors de `accounts`)
                   tests.yml (pytest + ruff à chaque PR et sur main, ffmpeg statique, et
                   Chromium : tests/test_render_chromium.py dessine une image pour de bon,
                   polices chargées, texte dans la zone sûre même réduit)
                   images.yml (lancé par le planificateur ; `images run --check` décide selon
                   config/images.yaml ; état images.json sur la branche `state`)
                   catalog.yml (push main config/docs, après daily/images/insights, chaque jour,
                   à la main : docs/ + catalog/ → GitHub Pages, source « GitHub Actions »)
                   insights.yml (à la fin de prepare-splits : statistiques Facebook et Instagram
                   → `insights.json` ; à la main avec `manual` : chiffres d'une capture ; son
                   propre groupe de concurrence, lecture seule, docs/insights.md)
                   playlists.yml (à la fin d'insights : les nouvelles vidéos dans leurs playlists
                   YouTube, son propre jeton, `youtube-playlists.json` sur `state`)
                   themes.yml (lancé par le planificateur à 17:40, lundi à samedi : la vidéo
                   thématique du jour, groupe `accounts`, état themes.json sur `state`, ticket
                   « ⚠️ Vidéo thématique en échec » ; à la main : essai à blanc d'un jour, docs/themes.md)
                   on-demand.yml (tickets « À la demande » et commentaires `/publier`,
                   `/essai`, `/apercu`, `/mots`, `/youtube` **du propriétaire seulement** ; aperçu hors
                   groupe `accounts`, publication dans `accounts`)
                   `.github/scripts/save-state.sh` : commit et push de la branche `state`
                   pour tous ces workflows ; branche déplacée ou réseau en panne → commit
                   rejoué sur la nouvelle tête et poussé de nouveau (tests/test_save_state.py)
                   `constraints.txt` (`PIP_CONSTRAINT` de chaque workflow) : versions de ce
                   qui change la sortie sans commit (playwright et son Chromium, numpy, torch,
                   transformers, tokenizers), changées exprès ; `.github/dependabot.yml` :
                   versions des actions GitHub, une PR par mois.
                   Runners épinglés sur `ubuntu-24.04` (`ubuntu-latest` passe à 26.04),
                   actions en versions Node.js 24. **Pas d'apt** : le miroir Ubuntu a mis
                   40 min à installer ffmpeg (run du soir du 2026-11-05, bloqué) ; ffmpeg =
                   build statique d'imageio-ffmpeg (pip, épinglé 0.8.1 : ffmpeg 9.0.2,
                   libx264, aac ; les tests passent avec), sans ffprobe (durées lues par
                   ffmpeg) ; Chromium de Playwright, `--with-deps` seulement s'il ne démarre pas.
docs/              site GitHub Pages (CGU, confidentialité, tiktok-login.html, tiktok-callback.html,
                   reel.html : aperçu d'un reel et textes YouTube à copier ; publier.html : ce qui se
                   publie à la main, TikTok et YouTube, lien fixe),
                   déployé par catalog.yml avec le catalogue (/quran-reels/catalog/) ;
                   notes : sources.md, calendrier.md, rendu.md, images.md, plateformes.md,
                   catalog.md, on-demand.md, profils.md (bio, images, playlists des 4 comptes)
assets/brand/      photo de profil, couverture Facebook, bannière et filigrane YouTube, refaits
                   par src/render.py (src/brand.html) ; icon-1024.jpg : icône de l'app Meta
.claude/skills/    procédures pour les sessions Claude (voir « Skills »)
```

Flux : `selector` → `sources` (texte + traduction + gloses + audio par ayah + fond) →
`render` (une image par ayah, durée = durée du MP3 de l'ayah) → MP4 → `publishers` → `state`.

Commandes :

```bash
quran-reels ingest                  # texte, traduction, sourates, index des gloses (4 requêtes)
quran-reels ingest --all-glosses    # + tous les sens du Muyassar (≈ 5 070 requêtes, reprise)
quran-reels passages 2              # découpe la sourate 2 en passages d'≈ 1 min
quran-reels render 93               # sourate courte entière → out/093_001-011.mp4
quran-reels render 2:1-5            # un passage → out/002_001-005.mp4 (complète le cache)
```

`render 78` sur une sourate trop longue pour une vidéo ne rend rien et liste ses passages.

```bash
quran-reels plan --write            # tout le Coran → config/plan.yaml (1 887 passages)
quran-reels series-check            # séries : phrases entières, ≤ 90 s
quran-reels calendar --days 14      # ce que les 14 prochains jours publieraient
quran-reels daily --check           # un créneau est-il dû maintenant ? (rien n'est publié)
quran-reels daily                   # publie les créneaux dus, écrit state/published.json
quran-reels notify --outcome failure --run-url …   # tickets GitHub (workflow daily)
quran-reels state reopen 2026-11-05/evening --why "coupe ratée"   # créneau supprimé, à republier
quran-reels state record 2026-11-05/evening --publish publish.json --reciter sayegh
                                    # publication faite à la main (publish-test) : créneau + file
```

```bash
quran-reels images build            # règles 1-4 → config/image-candidates.yaml (≈ 20 min)
quran-reels images next --days 7    # la semaine à venir (rien n'est publié)
quran-reels images render --days 7  # la dessine dans out/images/ (aperçu)
quran-reels images run              # publie le format dû, écrit state/images.json
```

```bash
quran-reels catalog build --state state-branch --out _site/catalog   # catalogue (lecture seule)
quran-reels insights collect --state state-branch [--dry-run]       # statistiques de la nuit
quran-reels insights add --state state-branch --json '{"platform": "youtube", …}'  # capture
```

```bash
quran-reels on-demand check --issue 42       # une demande : règles, refus motivé, découpe ?
quran-reels on-demand preview --issue 42     # rendu + aperçu commenté (workflow on-demand)
quran-reels on-demand daily-files            # MP4 du calendrier en téléchargement direct
```

```bash
quran-reels meta-check              # jeton de Page : valide, permissions, accès aux données
quran-reels publish 93 --dry-run    # rendu + brouillon Facebook + conteneur Instagram
quran-reels publish out/093_001-011.mp4 --platform facebook   # publication réelle
```

```bash
quran-reels publish 93 --platform tiktok      # brouillon dans la boîte TikTok
quran-reels tiktok-auth --code …              # connexion (en pratique : workflow tiktok-auth)
```

Secrets lus dans l'environnement (`META_PAGE_ID`, `META_PAGE_TOKEN`, `IG_USER_ID` ; `META_PAGE_TOKEN_5` : la page test, son seul secret,
`TIKTOK_CLIENT_KEY`, `TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN`, `GH_SECRETS_TOKEN`).

`out/093_001-003/` contient aussi les calques PNG, des aperçus (`preview/`), la légende
(`caption.txt`) et `manifest.json` : chaque texte affiché avec son édition, sa source et son
minutage. Le cache se remplit à la demande : `render` télécharge ce qui manque.

## Sources de données (détails : docs/sources.md)

- Texte uthmani, sourates, Sahih International : API Quran.com v4 (une requête par ressource).
  Sens des mots : `almuyassar-ghareeb` (غريب التفسير الميسر, tafsir.app). Jeux de données
  téléchargés dans `.cache/` (Actions cache), jamais commités.
- Audio : récitateurs à **un fichier par sourate** (mp3quran.net avec son minutage par ayah ;
  archive.org pour Omar Hisham), découpés par ayah (`sources/surah_audio.py`) et **vérifiés par
  reconnaissance** (`sources/recognition.py`, Whisper affiné sur la récitation) : chaque segment
  doit être reconnu comme son ayah (≥ 0,75) et **chaque coupe est réécoutée des deux côtés**
  (`check_cut` : aucun mot d'une ayah dans la voisine, « Alif » et « لا » ratés le 2026-11-05) ;
  la basmala finit au dernier vrai arrêt avant l'ayah 1 et se vérifie **aussi sur
  l'enregistrement, sans reconnaissance** (`stops`, `basmala_break`, 2026-11-11) : une seule
  émission de voix, sans arrêt de 0,3 s à l'intérieur (silence, ou calme 20 dB sous le niveau
  du récitateur). Ce qui suit un arrêt est le début de l'ayah 1 (« Alif » de « الم » après la
  basmala de la version YouTube de 29:60 par Tawfiq, que la reconnaissance n'entendait pas) ;
  ce qui le précède est l'isti'adha (ses sourates 6, 40 et 78 : la basmala commence après).
  Elle doit aussi être **reconnue comme elle-même** (≥ 0,9, sans répétition : l'isti'adha
  devant valait 0,77 et passait) ; une découpe plus ancienne sous 0,9 se lit comme non
  vérifiée. Contrôle demandé à la découpe, à l'audit, chaque nuit par `prepare` (une basmala
  contredite est recoupée) et une dernière fois au rendu (`CutError` : le run quotidien passe
  au récitateur suivant, pas de version YouTube, rien de publié avec cette coupe). Découpe commitée
  `config/splits/<id>/SSS.json` (temps seulement, et temps des mots des ayahs de 15 mots ou
  plus) : `quran-reels split <passage>`, `quran-reels split --audit --fix <sourates>`. Le texte
  reconnu n'est que comparé, jamais affiché ni publié.
- Récitateur choisi par passage (`reciters.py`, `content.rotation`) parmi ceux dont la découpe
  du passage est vérifiée ; workflow `prepare` chaque nuit pour les 8 jours suivants. Fares
  Abbad : **un fichier par ayah** (EveryAyah), toujours prêt, rien à découper ; fichiers à 48 ou
  64 kb/s, durées prévues à 48 kb/s (jamais plus courtes que la réalité). AbdulSamad (#18) non
  retenu : basmala dans le fichier de la 1re ayah, nom inconnu (docs/sources.md). Husary
  (#32) en essai : dans la liste, pas dans la rotation, essai sur Facebook seul à faire.
- Fonds : clips Pexels (liste à la main) et Pixabay (`PIXABAY_API_KEY`, jamais affichée),
  scènes générées ; skill `add-background`.

## Plateformes (voir docs/plateformes.md)

- Facebook + Instagram : publication auto via l'API Graph, app Meta en accès standard
  (comptes du propriétaire uniquement), sans validation Meta ni vérification d'entreprise.
  Chaque reel est d'abord envoyé non publié (brouillon Facebook, conteneur Instagram) et publié
  seulement si la vérification des droits de Meta est propre partout (voir docs/plateformes.md).
- TikTok : sans audit, la publication directe est forcée en privé → mode **brouillon**
  (MEDIA_UPLOAD vers la boîte TikTok) en attendant l'audit.
- YouTube : **le run `daily` met en ligne le Short du calendrier** (2026-11-21, choix du
  propriétaire ; `publishers/youtube.py`, `daily.to_youtube`) : plus de verrouillage en privé
  ni d'audit depuis le 2026-11-02, 100 mises en ligne par jour ; **les vidéos thématiques aussi**
  (run `themes`, 2026-11-21). Les demandes : **à la main**. Droits : **Content ID**, à
  part de Meta : Salah Budair y est revendiqué (Short 18:1-10 bloqué partout le 2026-11-06 ;
  un Short de plus d'1 min revendiqué l'est toujours). **Sur YouTube, toujours Tawfiq
  As-Sayegh** (choix du propriétaire, 2026-11-11 : `platforms.youtube.reciter`,
  `reciters.other_for`, `daily.youtube_version`) : quand la rotation choisit un autre
  récitateur (environ 4 créneaux sur 5), le run rend le passage une seconde fois par lui, après
  la publication (`out/youtube/`, release `reels`, ticket des légendes : « pas cette vidéo mais
  ce MP4 ») ; quand elle le choisit, la même vidéo sert. Tawfiq pas prêt pour le passage
  (découpe pas vérifiée, plus de 180 s) : **rien pour YouTube ce créneau**, aucun autre à sa
  place ; le ticket le dit, l'état garde `youtube: {reciter: null, error}`. `prepare` le
  découpe chaque nuit même s'il sort de la rotation (une revendication Meta ne compte pas sur
  YouTube) et avertit des passages où il n'est pas prêt. Une seule voix, un seul point de
  panne : revendiqué un jour par Content ID, tout YouTube s'arrête ; retirer alors `reciter`
  (retour à la règle d'avant : la vidéo du jour, sauf `exclude_reciters`, Budair).
  **Téléchargement direct** (2026-11-06) : chaque MP4 publié (et sa version YouTube) va dans la
  release GitHub `reels` (URL publique, non zippée, 30 jours) ; la page `reel.html` donne titre
  (≤ 100 car., tiré de la légende), description (`caption.txt`) et hashtags à copier ; mise en
  ligne notée par `/youtube <jour>/<créneau> <lien>` sur le ticket des légendes (état :
  `results.youtube`, `by_hand`).

## Découpage et calendrier (détails : docs/calendrier.md)

- `config/plan.yaml` : tout le Coran en passages d'≈ 1 min (1 887), coupés seulement à une fin
  de phrase (Sahih International) et de groupe d'Ibn Kathir ; figé (`quran-reels plan --write`).
- `config/schedule.yaml` : créneaux 07:30 (`reading`) et 18:00 (`themes`, le dimanche), vendredi une file par
  créneau (`kahf-first-ten`, `kahf`), `fallback`, `published_by_hand`. Séries dans
  `config/series/*.yaml`, vérifiées par `quran-reels series-check`.
- **Reprise dans le run** (2026-11-09 : 4 créneaux sur 9 avaient demandé un second run) :
  une plateforme qui n'a rien reçu (`failed` sans identifiant : Instagram refuse l'envoi,
  TikTok en HTTP 500) est réessayée une fois, seule, 180 s plus tard (`platforms.retry`) ;
  jamais après un refus des droits ni un échec pendant la publication (reel peut-être en
  ligne). L'état est écrit dès que le reel est sorti, et son push rejoue le commit si la
  branche `state` a bougé (`save-state.sh`) : une publication non enregistrée serait refaite.
- État : `published.json` sur la branche `state` (créneaux, files, `claimed`, `removed`,
  `missed`, `told`) ; un créneau supprimé se republie avec `quran-reels state reopen
  <jour>/<créneau>` et une publication faite à la main s'enregistre avec `quran-reels state
  record` (skill `republish`), jamais en modifiant le fichier : le créneau seul ne suffit pas,
  le passage resterait en tête de sa file et sortirait une seconde fois. Un créneau `by_hand`
  n'est pas complété par le run quotidien.
- **Créneau jamais tenté** (`calendar.missed_slots`, sortie `missed` de `daily`) : l'alerte
  d'échec est écrite par un run ; quand aucun run n'a tourné dans la fenêtre d'un créneau
  (planificateur muet, panne de GitHub : le 2026-11-09 au soir, deux lancements sans job),
  rien ne prévenait. Tout run suivant, y compris ceux du cron tardif de GitHub, voit un créneau
  des 2 derniers jours sans entrée dans l'état, le note (`missed`) et ouvre le ticket
  « ⚠️ Publication quotidienne en échec » une fois. Le même ticket prévient 14 jours avant
  l'expiration de `GH_SECRETS_TOKEN` (`gh_secrets.token_expiry`, état `told`).
- **Le cron de GitHub n'est pas fiable dans ce dépôt** : il lance des runs depuis le
  2026-11-05 au soir, mais 6 à 8 h en retard et pas à chaque fois (`daily` : 8 passages sur
  24 au 2026-11-09, tous hors fenêtre, sans effet ; `workflow_dispatch` marche).
  Seul `daily.yml` garde son cron (témoin indépendant pour l'alerte « créneau jamais tenté ») :
  ceux d'`images.yml` et de `prepare.yml` sont retirés (2026-11-09), leurs runs tardifs ne
  faisaient rien et prenaient la seule place en attente du groupe `accounts` (un run `images`
  du cron a annulé ainsi un `prepare` en attente le 2026-11-09 à 22:40 UTC ; une publication en
  attente aurait été annulée de même, sans job donc sans alerte).
  Les workflows sont donc lancés par des **tâches planifiées Claude** (choix du propriétaire,
  2026-11-05) qui réveillent la session « Quran Words Daily – planificateur » (Sonnet, dépôt
  attaché, outils GitHub) : `prepare.yml` 02:41 Paris, `daily.yml` 07:12 Paris et le dimanche 17:40, `themes.yml` 17:40 Paris du lundi au samedi, 12:40 à partir du 2026-11-27 (les deux heures pendant le changement) (tâche
  créée le 2026-11-15 après les essais à blanc ; rien n'est dû avant le 2026-11-19), `themes.yml` avec `page: ma3ak` 17:42 chaque jour
  (la page test ; les tâches d'une même session passent l'une après l'autre : la Page d'abord ; heures du 2026-11-19, avant 19:12 et 18:41)
  (`CRON_TZ=Europe/Paris`), `images.yml` 11:36 UTC ; chacune lance le workflow sur `main`,
  attend la fin, relance une fois en cas d'échec (sauf prepare) et résume (skill
  `check-publication`).
- Échec → ticket « ⚠️ Publication quotidienne en échec » (`notify.py`). **Ce qui se publie à la
  main** (texte du brouillon TikTok, MP4 et textes YouTube) : la page **« À publier »**, lien
  fixe https://mssnoussi92.github.io/quran-reels/publier.html (demande du propriétaire,
  2026-11-15 : le ticket était difficile à utiliser depuis le téléphone ; `feed.py` :
  `feed.json` sur `previews`, refait dans le commit de chaque `reel.json`, par `on-demand
  daily-files` et `themes files` ; la page lit aussi l'état pour dire « ✓ sur YouTube »). Le
  ticket épinglé « 📋 Légendes à copier » reste à jour en secours (lien MP4, page YouTube,
  commande `/youtube`, devenue facultative).
- **À la demande** (docs/on-demand.md) : `on_demand` de `published.json`, une entrée par ticket,
  un résultat par plateforme (YouTube : `manual` puis `published` + `by_hand`) ; le calendrier
  ne le lit pas (il republie le passage à son tour, choix du propriétaire). Aperçus : images et
  `reel.json` sur la branche `previews` (jamais fusionnée), MP4 dans la release `reels` ;
  supprimés après 30 jours.

## Rendu (détails : docs/rendu.md)

- **La question du mot** (essai choisi par le propriétaire le 2026-11-23, à partir du 24 ; docs/insights.md) : les reels
  du matin s'ouvrent, 3 secondes, sur « «<mot>»… تعرف معناها؟ » et « Do you know what this word means? » (le premier
  mot expliqué après le premier verset ; `video.hook`), sur Facebook, Instagram et TikTok ; **YouTube sans** (témoin :
  sa version est refaite sans la question, vérifiée par Meta). Né des captures du 2026-11-22 : sur Instagram la langue
  parlée décide du public (la récitation va en Iran, en Turquie, en Inde ; la bande-annonce, ouverte sur «أبابيل»… تعرف
  معناها؟, aux pays arabes, 8 partages en 10 h) ; sur TikTok la région du compte (Europe), quoi qu'on fasse.
- Template `render/templates/reel.html.j2` (maquette validée `docs/mockup/apercu-reel-93-2.png`),
  zone sûre haut 250 px, bas 420 px, côtés 90 px ; calques PNG transparents (Chromium) sur le
  fond, une image par ayah, durée = durée de son audio.
- **Longue ayah sur plusieurs écrans** (`render/screens.py`) : texte réduit sous 70 % → coupé
  après les signes de pause, traduction après les fins de phrase, chaque écran affiché quand
  son premier mot est récité (temps des mots de la découpe ; sinon au prorata des lettres).
- Fond choisi par les mots de la traduction (`config/backgrounds.yaml`), même passage → même
  fond. MP4 H.264 sans B-frames, AAC 48 kHz, sans edit list (Instagram), ≤ 6 Mb/s.
- **Volume** (décision du propriétaire, 2026-11-10) : chaque reel à **−16 LUFS** intégrés, comme
  les vidéos thématiques (`video.loudness` de project.yaml, `render/video.py` : `level`) : un
  seul gain pour tout le reel d'après sa mesure EBU R128, puis un limiteur (plafond −1,9 dBFS,
  délai compensé : aucun échantillon ne bouge) ; mesure et gain dans `manifest.json`
  (`loudness`). Avant : de −19,4 à −10,7 LUFS sur 8 reels publiés, 3 avec des crêtes à 0 dB.
- Scènes générées animées (nuages en deux couches, brume, sable, vagues, lumière ; boucle de
  30 s sans saut) et **zoom lent** sur toute la vidéo (`scenes.push_in` de backgrounds.yaml :
  8 % par minute, 12 % au plus ; `perspective` de ffmpeg, sous le texte qui ne bouge pas).
  Shader modifié → nouvelle boucle (nom = empreinte du shader), anciennes effacées du cache.
- Hashtags déterministes (`render.hashtags`), Instagram et TikTok : les 5 premiers.
  Instagram et TikTok : leur légende courte (`render.social_caption`, choix du propriétaire,
  2026-11-15) : série, référence, **texte arabe des ayahs**, crédits sur une ligne, signature,
  sans la traduction (`captions.social`) ; Instagram la sienne, sans les ayahs (`captions.instagram`, 2026-11-21) ; `caption.txt` (YouTube) reste entière.
  Facebook : sa légende courte (`render.facebook_caption`, ≤ 400 caractères,
  `platforms.facebook.max_caption_chars`), rangée dans `manifest.json` (`captions.facebook`).

## Publications image (détails : docs/images.md)

- Word of the day (carrousel 1080×1350 : le mot, son ayah, son sens dans le Muyassar), une fois
  par jour ; candidats figés dans `config/image-candidates.yaml` (`quran-reels images build`),
  ordre stable, exclusions `config/exclude.yaml` ; état `images.json` sur la branche `state`.

## Skills (`.claude/skills/`)

Procédures à suivre, pour toute session (le planificateur compris) : `check-publication`
(lire un run, l'état, rapporter), `test-reciter` (découper, vérifier, Facebook d'abord, puis
Instagram), `republish` (rouvrir un créneau et republier), `add-background` (chercher, vérifier,
proposer un fond), `propose-series` (proposer une série, validée en PR), `weekly-review`
(la revue, le dimanche : statistiques, deux calendriers, stock des thèmes, les points notés pour elle dans
docs/insights.md, 1 à 3 propositions ; ne change rien seule ; **quand le propriétaire dit « on commence la
revue », « on fait le point » ou autre chose de ce genre, dans n'importe quelle session** : maintenant avec lui,
ou dimanche par la revue automatique de 09:23, demandé par une question à choix si ce n'est pas clair ; sa demande
du 2026-11-17), `record-stats` (les captures de statistiques, TikTok surtout, envoyées dans n'importe quelle
session : reconnaître la vidéo, lire, montrer, demander, enregistrer, vérifier).

## Secrets (jamais dans le code ni dans la conversation)

GitHub Actions secrets : `META_PAGE_ID`, `META_PAGE_TOKEN`, `IG_USER_ID`, `TIKTOK_CLIENT_KEY`,
`TIKTOK_CLIENT_SECRET`, `TIKTOK_REFRESH_TOKEN` (écrit par le workflow `tiktok-auth` puis à
chaque rotation), `GH_SECRETS_TOKEN` (jeton fin GitHub, Secrets : lecture/écriture sur ce dépôt
seulement, voir docs/plateformes.md ; son échéance est lue à chaque publication et imprimée
dans le journal, ticket d'alerte 14 jours avant), `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`,
`YOUTUBE_REFRESH_TOKEN` (statistiques YouTube en lecture seule, écrit par le workflow `youtube-auth`),
`YOUTUBE_UPLOAD_REFRESH_TOKEN` (mise en ligne des reels et des vidéos thématiques : envoyer et lire, ni modifier ni
supprimer ; même workflow, bouton « Uploads » de youtube-login.html ; `daily.yml` et `themes.yml` seuls),
`YOUTUBE_PLAYLISTS_REFRESH_TOKEN` (playlists : `youtube.force-ssl`, qui pourrait aussi modifier et supprimer ; bouton
« Playlists » ; le workflow `playlists` seul).
Jamais un jeton dans un log : en-têtes `Authorization`, erreurs reconstruites, `::add-mask::`.
Les logs Actions d'un dépôt public sont publics : rien d'identifiant n'y est imprimé.

Jeton de Page Meta : expiration « Jamais », mais **l'accès aux données expire le 2027-02-13**
(90 jours ; refait le 2026-11-15, l'ancien coupé par le changement de mot de passe Facebook du
propriétaire : tout changement de mot de passe ou « déconnexion de toutes les sessions » le coupe
de même, code 190/460). Il porte aussi `read_insights`, `instagram_manage_insights`,
`instagram_manage_contents` et `pages_read_user_content`. Pour le renouveler, pas à pas :
docs/plateformes.md (« Renouveler le jeton de Page »). Fait : `meta-check` (et chaque `publish`) lit
`data_access_expires_at` via `GET /debug_token` et fait échouer le job (message clair, marche à
suivre) à moins de 14 jours de l'échéance, soit à partir du 2027-01-30.

## Statistiques (détails : docs/insights.md)

- Chaque nuit (fin de `prepare-splits`), `insights.yml` lit les chiffres Facebook et Instagram de
  tout ce que la Page publie (reels, Word of the day, vidéos thématiques reconnues par leur titre)
  → `insights.json` (branche `state`) → page « Statistiques » du catalogue, **publique** (choix du
  propriétaire, 2026-11-15). Comparaisons à 48 h, en médianes ; sous 3 vidéos ou 12 points
  d'écart, aucune différence n'est affirmée. **YouTube lu chaque nuit** en lecture seule (choix du
  propriétaire, 2026-11-15 : `insights/youtube.py`, Data API + Analytics API) : une publication
  par vidéo comme sur Facebook et Instagram (relevés 48 h / 7 j / 28 j **comptés sur les jours de
  YouTube Analytics**, donc aussi pour les vidéos plus anciennes ; rangée avec son reel ou sa vidéo
  thématique ; 93:1-11, publiée à la main, est `hand:93:1-11`), abonnés de la chaîne ; mise en place : docs/plateformes.md, « Statistiques YouTube ») ;
  TikTok : captures envoyées par le propriétaire **dans n'importe quelle session**, enregistrées
  après son accord par le skill `record-stats` (`insights.yml`, entrée `manual`).
  **Vues engagées et part de la recherche YouTube** lues chaque nuit (choix du propriétaire, 2026-11-21 :
  `engaged`, `search_pct` ; les vues d'un Short comptent ses boucles) : montrées, la comparaison reste sur les vues.
- **Tableau de bord** en tête de la page « Statistiques » (choix du propriétaire, 2026-11-21, maquette validée) :
  abonnés, types de vidéos à 48 h (un point par vidéo), audits (récitateur, fond, durée, série, jour, version
  courte), avant / après chaque essai (`trials` de `config/insights.yaml`), YouTube en détail (`youtube-detail.json`
  chaque nuit), rétention Facebook, TikTok, données manquantes (`missing`) ; `catalog/dataset.json`, une ligne par
  vidéo et par plateforme, pour les audits de toute session (docs/insights.md, « Le tableau de bord »). Une session
  qui fait partir un changement l'ajoute à `trials` ; les exports de YouTube Studio s'importent par
  `quran-reels insights import-youtube` (skill `record-stats`).
- Le calendrier du catalogue montre aussi les vidéos thématiques (calendar.md de
  quran-themes-demo, tel qu'écrit) : un seul calendrier pour la Page ; à partir du 2026-11-19
  ils y sont « automatique », et « publié » d'après `themes.json`.

## État

- [x] Comptes créés (Gmail, Page FB, IG Créateur reliés, TikTok, YouTube)
- [x] Squelette du dépôt, polices, maquette
- [ ] Environnement cloud `quran-reels` (accès réseau Custom)
- [x] Ingestion des données + rendu v1 avec audio (`quran-reels render 93:1-3`, fond provisoire)
- [x] Passages d'≈ 1 min, sourate courte entière (`quran-reels passages`, `render 93`)
- [x] App Meta (voir docs/plateformes.md)
- [x] Dry-run Facebook (run #3, brouillon créé) et Instagram (run #7, conteneur FINISHED, non
      publié). [x] Première publication réelle : 93:1-11 sur Facebook et Instagram
      (publish-test run #12, 2026-11-05 ; Instagram : 1er conteneur bloqué, publié au 2e).
- [x] App TikTok Sandbox · [x] connexion (`tiktok-auth`, compte quran_words_daily, refresh
      token jusqu'à ≈ 2027-11-04) · [x] brouillon dans la boîte TikTok en Sandbox (run #8)
- [x] Audit YouTube : plus nécessaire (verrouillage en privé levé par YouTube le 2026-11-02), pas
      demandé (choix du propriétaire, 2026-11-21) ; pages Confidentialité et Conditions complétées
      pour les règles de l'API YouTube ·
      [x] mise en ligne des Shorts du calendrier par le run (2026-11-21) · [x] connexion
      « Uploads » par le propriétaire (2026-11-21) · [x] vidéos thématiques aussi (2026-11-21) ·
      [x] premier Short mis en ligne par le run (2026-11-22, 101:1-11 par Tawfiq As-Sayegh, public, titre en arabe
      d'abord : https://youtube.com/shorts/Qs1JsZOdPjo) · [ ] regardé dans Studio par le propriétaire · [ ] premier film mis en
      ligne par le run (Dhul-Qarnayn, lundi 23), miniature regardée · [x] playlists rangées par le
      run (2026-11-21) · [x] connexion « Playlists » par le propriétaire · [x] première nuit (2026-11-22 : les 7 titres en
      arabe d'abord, rien d'autre à faire) ·
      [x] description et mots-clés de la chaîne appliqués par le run (2026-11-21, `youtube-channel` ;
      marques de sens gardées par YouTube, relu une minute après) · [x] premier nom de série ajouté la nuit (2026-11-22 : آية الكرسي, السبع آيات المنجيات, موسى والخضر, الدعاء)
- [x] **Reels en pause** du 2026-11-12 au soir au 2026-11-13 au matin (`pause` de
      `config/schedule.yaml`, demande du propriétaire : les épisodes thématiques démarrent) ·
      [x] reprise le 2026-11-13 au soir (Al-Kahf 18:15-16), puis **un reel chaque matin et les
      séries le dimanche soir** (`days` des créneaux)
- [x] Calendrier : 2 créneaux, Juz' 'Amma, séries (Ayat al-Kursi, munjiyat, du'a, rizq), Al-Kahf le
      vendredi, état, workflow `daily` — **activé** (`enabled: true`) ; 93:1-11, publiée à la
      main, est dans `published_by_hand` (jamais republiée par le calendrier)
- [x] Série « السبع آيات المنجيات » · [x] séries patience (29 passages) et repentir (16) proposées
      (2026-11-06, `sabr.yaml`, `tawba.yaml`, après rizq dans la file `themes`)
- [x] Fonds choisis selon le passage (scènes générées + 3 clips Pexels, PR #8 ; + 21 clips
      Pixabay validés ; tickets du catalogue : 2 retirés, 3 clips de mer ajoutés, 4 écartés)
- [x] Publications image : Word of the day **en pause depuis le 2026-11-15** (presque pas vu : 4 vues en médiane sur
      Instagram ; choix du propriétaire), activé du 6 au 15 novembre (tirages du 6 au 12 novembre avec le
      Muyassar validés par le propriétaire le 2026-11-05 ; candidats refaits : 8 599 mots,
      4 913 ayahs), Ayah of the day désactivé · [ ] premier dry-run Meta des images ·
      [ ] première publication réelle (11:30 UTC le lendemain de la fusion)
- [x] Vérification des droits Meta avant publication. Facebook : un brouillon de reel ne se
      publie pas par l'API (« The video was not uploaded », code 6000, subcode 1363130, run
      #18) → le fichier vérifié est renvoyé directement en PUBLISHED, brouillon supprimé.
      [x] 114 avec Omar Hisham publiée sur Facebook (publish-test run #19, 2026-11-05),
      Facebook n'y signale aucun problème de droits (constaté par le propriétaire).
      [x] **App Meta passée en Live** (2026-11-05) : en mode développement, ce qu'elle publiait
      n'était visible que des comptes qui ont un rôle sur l'app (114 « non disponible » pour un
      autre compte) ; aussitôt après, le lecteur intégré de Facebook sert le reel 114 sans
      compte (vidéo de 41 s), sans republier (docs/plateformes.md).
- [x] Récitateurs choisis par passage (6, `content.rotation`) · [x] découpes vérifiées
      (`quran-reels split`, workflow `prepare` chaque nuit) · [ ] Juz' 'Amma et thèmes pour
      tous · [ ] refaire le plan (calculé avec Alafasy) si des passages dépassent 90 s
- [x] YouTube : toujours Tawfiq As-Sayegh (2026-11-11 ; prêt pour les 16 passages des 8 jours
      suivants ; version YouTube de 108:1-3 rendue dans une session par `daily.youtube_version` :
      16,8 s, crédit et légende à son nom) · [x] premier run `daily` avec la règle (2026-11-22 : reel d'Omar Hisham, version YouTube par Tawfiq) · [ ] premier
      Short mis en ligne par le propriétaire, revendications regardées dans YouTube Studio
- [x] Basmala vérifiée sur l'enregistrement (2026-11-11, après « الم » entendu après la basmala
      de la version YouTube de 29:60) : 115 basmalas auditées, 4 de Tawfiq refaites (29 ; 6, 40,
      78 : isti'adha), version YouTube de 29:60 refaite et écoutée en entier par la
      reconnaissance · [ ] premier run `prepare` et premier run `daily` avec ces contrôles
- [x] Publication à la demande (docs/on-demand.md, `on-demand.yml`) : [x] dry run sur la branche (#34, 2026-11-06 : aperçu, `/essai`, droits Meta propres, MP4 1080p et textes YouTube ; refus #35 et découpe non nette #34)
      · [x] première demande approuvée par le propriétaire depuis son téléphone (#39,
      2026-11-06 : 101:1-11, Omar Hisham, YouTube seul ; aperçu refait après la correction des
      coupes FLAC, PR #40 ; `/publier`, droits Meta propres, MP4 1080p et textes YouTube) :
      **demande de test, pas mise en ligne** (le propriétaire garde 2 publications par jour),
      ticket fermé « non prévu », `youtube: cancelled` dans l'état · [ ] première publication
      publique à la demande et `/youtube <lien>` en vrai
- [x] Catalogue (docs/catalog.md, `catalog.yml`) · [x] Pages passé en « GitHub Actions » par le
      propriétaire, premier déploiement (run #1, 2026-11-05) · [x] libellé « Catalog » créé ·
      [x] premiers tickets appliqués (#19–#28) · [x] #18 AbdulSamad non retenu (basmala dans
      la 1re ayah, confirmée par reconnaissance ; nom inconnu) · [ ] #32 Husary : ajouté à la
      liste, reel 112 vérifié, essai sur Facebook seul à faire
- [ ] Profils des 4 comptes (docs/profils.md, proposés et **validés par le propriétaire** le
      2026-11-09) : bio, nom, photo unique
      « آيات », couverture, bannière (« Quran & Sunnah for everyday life », bilingues), playlists
      YouTube par thème, sourate et format, Facebook (3), à appliquer à la main par le
      propriétaire ; YouTube vide ; TikTok renommé `@quran.words.daily` et reels signés de
      ce nom sur TikTok (2026-11-09) ; le compte vide `@quran_words_daily`, à quelqu'un
      d'autre, à signaler
- [x] Liste de qualité de Facebook sur 6:17 (2026-11-09 : « image statique », « légende de
      qualité (10 à 400 caractères) ») : scènes générées animées + zoom lent, légende Facebook
      courte · [ ] relire la liste de qualité sur le prochain reel avec une scène générée
      · « vidéo avec bordures » sur des reels (2026-11-13) : la colline de la scène de nuit,
      presque noire et immobile, faisait une bande noire de 110 px en bas (9:51, 6:17, 111,
      confirmés par le propriétaire ; leur autre point : l'image statique, déjà corrigée) ;
      colline texturée et éclairée, brume qui passe, test Chromium (docs/rendu.md)
