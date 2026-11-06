"""On-demand reels: requested, previewed and approved from the owner's phone (docs/on-demand.md).

1. The catalogue's form opens a pre-filled issue «À la demande : …» (request.py: its body).
2. The `on-demand` workflow checks it (check.py: allowed reciter, whole sentences, at most
   max_seconds with that reciter, background, platforms), splits the recording if needed,
   renders it with the pipeline and comments a preview (flow.py, files.py): key frames, a
   light MP4, the captions, a page with copy buttons.
3. The owner answers `/publier` (or `/essai`, a dry run): the previewed file, and nothing
   else, goes through publish.publish_reel (Meta's rights check first, TikTok as a draft).
4. YouTube, by hand: once Meta's check is clean, the 1080p MP4 as a direct download, its
   title, description and hashtags; `/youtube <link>` records it (state.py).

Only the repository owner's issues and comments are acted on (commands.py). Nothing here
writes Quran text, translations or meanings: the reel and its captions come from the renderer.
"""
