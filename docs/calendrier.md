# Découpage des passages et calendrier

*Déplacé de CLAUDE.md le 2026-11-05 (texte inchangé) ; CLAUDE.md en garde le résumé.*

## Découpage des passages (`selector/plan.py`)

- Sourate qui tient dans `max_seconds` (90 s, attente et queue comprises) → une seule vidéo,
  même très courte (108 : 17 s, 1 : 48 s, 93 : 56 s).
- Sinon, coupure seulement après une ayah qui **termine une phrase** dans Sahih International
  (`.` `?` `!` ; une virgule ou rien = la phrase continue) **et** termine un groupe d'Ibn Kathir.
  Programmation dynamique : passages les plus proches de 60 s, entre 40 et 90 s. Exemple
  sourate 2 : 2:1-5 (57 s), 2:6-9 (52 s), 2:10-13 (60 s)…
- Bloc entre deux coupures plus long que 90 s (78:37-40) : on coupe à une fin de phrase à
  l'intérieur du groupe, passage signalé « cut inside a tafsir group ». Une ayah seule de plus
  de 90 s (2:282) dépasse : chaque seconde au-delà coûte plus que tout le reste, donc elle reste
  seule (avant correction, 24:31 et 24:61 avalaient tout l'entre-deux : 24:31-61, 19 min).
- Tout le Coran : **1 887 passages** (`config/plan.yaml`), dont 19 de plus de 90 s (ayahs ou
  phrases trop longues, 2:282, 24:31…) laissés de côté par le calendrier pour l'instant.

## Calendrier (`selector/calendar.py`, `daily.py`)

- `config/schedule.yaml` : fuseau `Europe/Paris`, créneaux `morning` 07:30 (file `reading`) et
  `evening` 19:30 (file `themes`), vendredi : une file par créneau (`fridays: {morning:
  kahf-first-ten, evening: kahf}` ; `queue:` en donne une pour tous), `fallback` (une file
  finie passe à une autre). `enabled: false` tant que la première publication réelle n'est pas
  faite (activé le 2026-11-05). `published_by_hand` : passages publiés hors calendrier, sautés.
- Une file joue ses séries l'une après l'autre ; chaque créneau prend le premier passage pas
  encore publié. Série `repeat: true` (Al-Kahf) : recommence une fois finie.
- Al-Kahf : `kahf-first-ten` (18:1-10, une seule entrée qui recommence chaque semaine) et
  `al-kahf` (36 passages de 18:11 à 18:110, `quran-reels passages 18 --from 11` : mêmes coupes
  que plan.yaml à partir de 18:15, 18:11-14 remplace 18:6-12 et 18:13-14). 18:1-10 dure
  87,6 s avec Salah Budair, 108 à 132 s avec les autres : les reels Facebook s'arrêtent à 90 s
  (doc Reels Publishing : « 3 to 90 seconds »), la rotation choisit donc Budair chaque vendredi
  matin. `series-check` accepte un passage trop long pour l'estimation Alafasy si un récitateur
  prêt de la rotation tient dans 90 s.
- Série (`config/series/*.yaml`) : `surahs: [...]` (passages de plan.yaml) ou `passages:`
  écrits à la main, `title_ar`/`title_en` affichés sur le premier écran («آيات الدعاء · ٤ من ٣٨»)
  et en tête de la légende. `quran-reels series-check` refuse un passage qui commence ou finit
  au milieu d'une phrase, ou de plus de 90 s.
- Listes thématiques : proposées (IA, en amont) avec la règle utilisée (racine ر ز ق, «رَبَّنَا»…)
  et validées par le propriétaire en PR. Les textes viennent toujours des sources au rendu.
  « السبع آيات المنجيات » : la liste du propriétaire (9:51, 6:17, 11:6, 11:56, 29:60, 35:2,
  29:61) ; 11:6 et 29:60 retirées de la série rizq pour ne pas les publier deux fois.
- Workflow `daily` : cron `17 5,6,7` et `17 17,18,19` UTC (heure d'été et d'hiver, GitHub est
  souvent en retard ; le 2026-11-05, les trois premiers passages à :13 n'ont jamais été lancés
  par GitHub, minute changée pour réenregistrer le planning) ; `daily --check` décide sans installer ffmpeg ; un créneau commencé ne
  réessaie que les plateformes en échec, avec le même passage ; fenêtre de 3 h.
- **Reprise dans le même run** (`platforms.retry` de `config/project.yaml` : 1 fois, après
  180 s ; `publish.to_retry`, `daily.again`) : entre le 5 et le 9 novembre 2026, 4 créneaux sur
  9 ont demandé un second run pour une seule plateforme (Instagram qui refuse l'envoi, runs
  #10 et #13 ; TikTok en HTTP 500, #28), avec un ticket d'échec à chaque fois. Une plateforme
  qui **n'a rien reçu** (`failed` sans identifiant) est donc réessayée seule dans le run, avec
  sa propre vérification des droits. Jamais après un refus de la vérification des droits, ni
  quand l'échec vient pendant la publication (`failed` avec l'identifiant de ce qui a été
  envoyé : le reel est peut-être en ligne, un second essai le publierait deux fois). Encore en
  échec : le run échoue comme avant et un run suivant réessaie.
- **Le cron de GitHub n'est pas fiable dans ce dépôt** : aucun run `schedule` avant le
  2026-11-05 21:32 UTC ; depuis, il en lance (32 au 2026-11-09) mais avec 6 à 8 h de retard et
  pas à chaque fois (`daily` : 8 passages sur 24, tous hors fenêtre, donc sans effet ;
  `images` : 16 sur 94 ; `prepare` chaque jour, vers 08:00 UTC). `workflow_dispatch` marche.
  Les workflows sont donc lancés par des **tâches planifiées Claude** (choix du propriétaire,
  2026-11-05) qui réveillent la session « Quran Words Daily – planificateur » (Sonnet, dépôt
  attaché, outils GitHub) : `prepare.yml` 02:41 Paris, `daily.yml` 07:12 et 19:12 Paris
  (`CRON_TZ=Europe/Paris`), `images.yml` 11:36 UTC ; chacune lance le workflow sur `main`,
  attend la fin, relance une fois en cas d'échec (sauf prepare) et résume. Une tâche lancée
  dans une session neuve n'a pas accès au dépôt (essai du 2026-11-05) : elles visent toutes
  cette session. Les crons des workflows restent en place si GitHub se remet à les lancer
  (un passage en double ne republie rien : le créneau est déjà dans l'état).
- État : `published.json` sur la branche `state` (créée au premier passage du workflow),
  commit après chaque créneau. Un passage compte comme publié dès qu'une plateforme l'a.
  **Ce qui est sorti est écrit aussitôt** (`daily.record_slot`, avant la reprise et avant la
  version YouTube) : un run annulé ou arrêté en route (run #8) a déjà dit ce qui est publié.
  **Le push ne perd rien** (`.github/scripts/save-state.sh`, appelé par tous les workflows qui
  écrivent sur `state`) : si la branche a bougé entre-temps (l'aperçu à la demande y pousse
  ses découpes hors du groupe `accounts`) ou si le réseau échoue, le commit du run est rejoué
  sur la nouvelle tête et poussé de nouveau, 5 essais ; avant, un push refusé perdait le
  créneau et le run suivant republiait le même passage partout. Seul un vrai conflit (deux
  écritures des mêmes lignes) échoue, avec une erreur sur le run.
- **Publication à la main** (`publish-test` en `mode: publish` : un créneau rouvert, le premier
  reel d'un récitateur) : `quran-reels state record <jour>/<créneau> --publish publish.json
  --reciter <id>` écrit le créneau **et** remet son passage parmi les publiés de sa file
  (`calendar.record_by_hand`). Écrire le créneau à la main ne suffit pas : après un `state
  reopen`, le passage est en tête de sa file et le créneau suivant le publierait une seconde
  fois. Le créneau porte `by_hand` : le run quotidien ne le complète pas (Instagram attend que
  le propriétaire ait vu les droits sur Facebook).
- **Créneau jamais tenté** : un créneau des 2 derniers jours dont la fenêtre est finie et qui
  n'a aucune entrée dans l'état (ni rouvert, ni déjà signalé) est noté sous `missed` par le
  premier run qui passe (`daily --check`, sortie `missed`) et signalé une fois dans le ticket
  d'échec, même si ce run publie normalement son propre créneau ; pas en dry run ni avec une
  heure simulée. Les runs du cron tardif de GitHub servent ainsi de témoin indépendant du
  planificateur.
- Prévenir le propriétaire (`notify.py`, étape « Tell the owner », `issues: write`) :
  `daily` écrit `out/daily-report.json` (même s'il s'arrête, avec l'erreur). Échec → ticket
  « ⚠️ Publication quotidienne en échec » assigné au propriétaire et @mention (notification
  push dans l'app GitHub), commentaire s'il est déjà ouvert ; fermé par la prochaine
  publication réussie. Chaque publication met à jour le ticket épinglé « 📋 Légendes à copier
  (TikTok, YouTube) » : légendes des 4 dernières vidéos avec 5 hashtags, la limite de TikTok
  (`platforms.tiktok.max_hashtags`) ; aucune notification.
  Aussi dans le résumé du run. Dry-run : jamais le ticket d'échec, pas de TikTok (son seul
  test serait un vrai brouillon) ; entrée `now` du workflow pour simuler l'heure.
