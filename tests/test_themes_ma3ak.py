"""The test page « معاك 5 ثواني » (owner's request, 2026-11-19): the workflow `themes` with `page: ma3ak`
publishes it every day at 18:00 Paris from its own settings (config/themes-ma3ak.yaml), its own token
(META_PAGE_TOKEN_5, its Page and Instagram account read from it) and its own failure issue."""
from datetime import date, datetime

import pytest
import yaml

from quran_reels import notify
from quran_reels.config import load
from quran_reels.publishers.meta import MetaEnv
from quran_reels.themepub import calendar as cal
from quran_reels.themepub import run as R
from quran_reels.themepub import texts as T

TEXTS = """# You Have 5 Seconds · معاك 5 ثواني : textes de publication

Pour chaque short, les textes à copier : sur Facebook et Instagram, la légende courte en trois textes. Titres et descriptions **validés par le propriétaire le 2026-11-18** ; Légendes courtes de Facebook et Instagram (titre, accroche et voix IA, hashtags) **validées par le propriétaire le 2026-11-17**.

## Short 5 · "Beautiful patience"… and the second time? · «فصبر جميل»… المرة التانية؟

`quiz-short-5-sabr-ma3ak.mp4`, signée `@ma3ak.5.thawani` · 0:58 · 9:16 · Facebook et Instagram · couverture : `quiz-short-5-sabr-ma3ak-cover.jpg`

**Facebook · Titre**

```text
T5
```

**Facebook · Hashtags (3)**

```text
#a #b #c
```

**Instagram · Titre**

```text
T5
```

**Instagram · Hashtags (5)**

```text
#a #b #c #d #e
```
"""

CALENDAR = """## Le calendrier

| Date | Quoi | Où | Fichiers | Texte |
| --- | --- | --- | --- | --- |
| ~~mer. 18 nov.~~ | ~~Quiz 4~~ | Facebook, Instagram | release `page-quiz-ma3ak` | `publication-quiz-ma3ak.md` : « Short 4 » |
| jeu. 19 nov. | Quiz 5 | Facebook, Instagram | release `page-quiz-ma3ak` | `publication-quiz-ma3ak.md` : « Short 5 » |
| sam. 28 nov. | à faire : plus de quiz en stock | Facebook, Instagram | | |
"""


def paris(day, hhmm):
    return datetime.fromisoformat(f"{day}T{hhmm}:00+01:00")


def test_the_test_page_settings_say_18_00_facebook_and_instagram_from_the_19th():
    cfg = load()
    s = R.settings(cfg, cfg.root / "config" / "themes-ma3ak.yaml")
    assert s["time"] == "18:00" and s["platforms"] == ["facebook", "instagram"]
    assert s["calendar"] == "docs/retention/calendar-ma3ak.md" and str(s["from"]) == "2026-11-19"
    assert R.settings(cfg)["calendar"] == "docs/retention/calendar.md"      # the Page's, unchanged


def test_its_quiz_is_due_at_18_00_on_its_own_platforms():
    s = yaml.safe_load((load().root / "config" / "themes-ma3ak.yaml").read_text(encoding="utf-8"))
    videos = T.parse("quiz-ma3ak", TEXTS)
    rows = cal.rows(CALENDAR, date(2026, 11, 19))
    for row in rows:
        cal.resolve(row, videos, s["platforms"])
    src = R.Sources(videos, rows)
    assert R.due(s, {"posts": {}}, src, paris("2026-11-19", "17:39")) is None
    row = R.due(s, {"posts": {}}, src, paris("2026-11-19", "17:41"))
    assert row.day == date(2026, 11, 19) and set(row.videos) == {"facebook", "instagram"}
    assert row.videos["instagram"].video == "quiz-short-5-sabr-ma3ak.mp4"
    assert R.due(s, {"posts": {}}, src, paris("2026-11-19", "21:01")) is None
    assert R.due(s, {"posts": {}}, src, paris("2026-11-28", "18:00")) is None     # nothing in stock


def test_only_the_token_is_needed_and_the_ids_come_from_it(monkeypatch):
    for name in ("META_PAGE_ID", "IG_USER_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("META_PAGE_TOKEN", "tok")
    with pytest.raises(SystemExit, match="META_PAGE_ID"):          # the Page's runs: as before
        MetaEnv.from_environ(["facebook", "instagram"])
    monkeypatch.setenv("META_IDS_FROM_TOKEN", "1")
    env = MetaEnv.from_environ(["facebook", "instagram"])
    assert env.page_id == "" and env.ig_user_id is None

    class Graph:
        def get(self, path, **params):
            return {"me": {"id": 555}, "555": {"instagram_business_account": {"id": "777"}}}[path]

    env = env.ids_from_token(Graph())
    assert (env.page_id, env.ig_user_id, env.token) == ("555", "777", "tok")
    monkeypatch.delenv("META_PAGE_TOKEN")
    with pytest.raises(SystemExit, match="META_PAGE_TOKEN"):        # no token: the run fails
        MetaEnv.from_environ(["facebook"])


def test_the_test_page_has_its_own_failure_issue():
    assert notify.ALERTS["ma3ak"] not in (notify.ALERTS["themes"], notify.ALERTS["daily"])
    assert "معاك 5 ثواني" in notify.ALERTS["ma3ak"]


def test_the_test_page_step_never_sees_the_page_secrets():
    """themes.yml: the test page's step has META_PAGE_TOKEN_5 only, the Page's step never has it."""
    wf = yaml.safe_load((load().root / ".github" / "workflows" / "themes.yml").read_text(encoding="utf-8"))
    steps = {s.get("id"): s for s in wf["jobs"]["post"]["steps"] if s.get("id")}
    ma3ak, page = steps["post_ma3ak"]["env"], steps["post"]["env"]
    assert ma3ak["META_PAGE_TOKEN"] == "${{ secrets.META_PAGE_TOKEN_5 }}"
    assert not any("secrets." in str(v) for k, v in ma3ak.items() if k != "META_PAGE_TOKEN")
    assert "META_PAGE_TOKEN_5" not in str(page)
    assert "inputs.page != 'ma3ak'" in steps["post"]["if"] and "inputs.page == 'ma3ak'" in steps["post_ma3ak"]["if"]


def test_the_instagram_account_found_where_meta_gives_it(monkeypatch):
    """First dry run of the test page (2026-11-19): no instagram_business_account on the Page."""
    monkeypatch.setenv("META_PAGE_TOKEN", "tok")
    monkeypatch.setenv("META_IDS_FROM_TOKEN", "1")
    env = MetaEnv.from_environ(["instagram"])

    class Graph:
        token = "tok"

        def __init__(self, page, granted):
            self.page, self.granted = page, granted

        def get(self, path, **params):
            if path == "me":
                return {"id": "555"}
            if path == "debug_token":
                return {"data": {"granular_scopes": [
                    {"scope": "instagram_content_publish", "target_ids": self.granted}]}}
            return self.page

    assert env.ids_from_token(Graph({"connected_instagram_account": {"id": "88"}}, [])).ig_user_id == "88"
    assert env.ids_from_token(Graph({}, ["99"])).ig_user_id == "99"
    assert env.ids_from_token(Graph({}, [])).ig_user_id is None
    assert env.ids_from_token(Graph({}, ["98", "99"])).ig_user_id is None      # which one? none
