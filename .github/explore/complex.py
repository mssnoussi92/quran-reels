"""Temporary research (removed before the PR): what the King Fahd Complex site offers.

Prints the download links and usage-rights text of its recitation pages, then, for each .zip
found, whether it can be read by ranges (central directory, a few ayahs of surah 93).
"""
import html as htmllib
import io
import re
import subprocess
import urllib.parse
import urllib.request
import zipfile

UA = {"User-Agent": "quran-reels/0.1 (+https://github.com/mssnoussi92/quran-reels)"}
PAGES = [
    "https://qurancomplex.gov.sa/quran-audios/",
    "https://qurancomplex.gov.sa/sounds/",
    "https://qurancomplex.gov.sa/category/kfgqpc-quran-audio/recite/moratal/hafs/",
    "https://qurancomplex.gov.sa/category/kfgqpc-quran-audio/recite/moratal/hafs/huthify/",
    "https://qurancomplex.gov.sa/sounds-hafs-ayyoub/",
]
KEYS = (".zip", ".mp3", "download", "kfgqpc-quran-audio", "sounds-", "rights", "terms",
        "license", "licence", "usage", "%d8%ad%d9%82%d9%88%d9%82")


def req(url, method="GET", headers=None):
    r = urllib.request.Request(url, method=method, headers={**UA, **(headers or {})})
    return urllib.request.urlopen(r, timeout=60)


def text_of(html):
    html = re.sub(r"(?s)<(script|style).*?</\1>", " ", html)
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", html))).strip()


zips, rights = set(), set()
for page in PAGES:
    try:
        html = req(page).read().decode("utf-8", "replace")
    except Exception as e:
        print(f"## {page}: {e}")
        continue
    print(f"## {page} ({len(html)} chars)")
    for link in sorted(set(re.findall(r'href=["\']([^"\'#]+)', html))):
        full = urllib.parse.urljoin(page, link)
        low = full.lower()
        if any(k in low for k in KEYS):
            print("   ", urllib.parse.unquote(full))
        if low.endswith(".zip"):
            zips.add(full)
        if "%d8%ad%d9%82%d9%88%d9%82" in low or "rights" in low or "terms" in low:
            rights.add(full)
    t = text_of(html)
    for m in re.finditer(r"(حقوق|رخص|ترخيص|مجان|License|license|rights)", t):
        print("    …", t[max(0, m.start() - 150):m.end() + 250])
        break

for page in sorted(rights)[:4]:
    try:
        t = text_of(req(page).read().decode("utf-8", "replace"))
        i = max(t.find("حقوق"), 0)
        print(f"## rights page {urllib.parse.unquote(page)}\n{t[i:i + 3000]}")
    except Exception as e:
        print(f"## rights page {page}: {e}")


class HttpFile(io.RawIOBase):
    def __init__(self, url):
        h = req(url, "HEAD")
        self.url, self.size, self.pos = h.geturl(), int(h.headers["Content-Length"]), 0
        self.ranges = h.headers.get("Accept-Ranges")

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def readinto(self, b):
        if self.pos >= self.size:
            return 0
        end = min(self.size, self.pos + len(b)) - 1
        data = req(self.url, headers={"Range": f"bytes={self.pos}-{end}"}).read()
        b[:len(data)] = data
        self.pos += len(data)
        return len(data)


for url in sorted(zips):
    print(f"## zip {urllib.parse.unquote(url)}")
    try:
        f = HttpFile(url)
        print(f"   {f.size / 1e6:.1f} MB, Accept-Ranges: {f.ranges}, final URL {f.url}")
        z = zipfile.ZipFile(io.BufferedReader(f, buffer_size=1 << 20))
        names = z.namelist()
        print(f"   {len(names)} entries; first: {names[:8]}; last: {names[-3:]}")
        print(f"   compression: {sorted({i.compress_type for i in z.infolist()})}")
        picks = [n for n in names if re.search(r"(^|/)0*93[_-]?0*0?[1-3]\D", n.split('/')[-1] + '.')
                 or re.search(r"093(001|002|003)", n)][:3]
        print(f"   surah 93 samples: {picks}")
        for n in picks:
            data = z.read(n)
            open("s.mp3", "wb").write(data)
            dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                  "format=duration:format_tags=artist,title,album,comment",
                                  "-of", "compact=p=0", "s.mp3"],
                                 capture_output=True, text=True).stdout.strip()
            info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a",
                                   "-show_entries", "stream=codec_name,bit_rate,sample_rate",
                                   "-of", "compact=p=0", "s.mp3"],
                                  capture_output=True, text=True).stdout.strip()
            print(f"   {n}: {len(data)} bytes; {dur}; {info}")
    except Exception as e:
        print(f"   {type(e).__name__}: {e}")
