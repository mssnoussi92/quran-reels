"""Temporary research (removed before the PR): can a runner reach the King Fahd Complex?"""
import socket
import subprocess

for host in ("qurancomplex.gov.sa", "www.qurancomplex.gov.sa", "dm.qurancomplex.gov.sa",
             "quran.ksu.edu.sa", "mp3quran.net", "server11.mp3quran.net", "archive.org"):
    try:
        print(host, "→", sorted({a[4][0] for a in socket.getaddrinfo(host, 443)}))
    except OSError as e:
        print(host, "→ DNS", e)
for url in ("https://qurancomplex.gov.sa/", "http://qurancomplex.gov.sa/",
            "https://www.qurancomplex.gov.sa/", "https://qurancomplex.gov.sa/en/",
            "https://mp3quran.net/api/v3/reciters?language=eng&reciter=ali-alhuthaifi",
            "https://www.mp3quran.net/api/v3/ayat_timing/reads",
            "https://archive.org/advancedsearch.php?q=Huthaifi+ayah&fl[]=identifier&rows=5&output=json"):
    r = subprocess.run(["curl", "-sS", "-o", "/tmp/b", "-w", "%{http_code} %{size_download} %{time_total}s",
                        "--max-time", "25", "-A", "quran-reels/0.1", url], capture_output=True, text=True)
    print(url, "→", r.stdout, r.stderr.strip()[:120])
    try:
        print("   ", open("/tmp/b", encoding="utf-8", errors="replace").read(400).replace("\n", " "))
    except OSError:
        pass
