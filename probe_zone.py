"""Trova lo schema URL per zona/appartamenti su Nuroa."""
import re, sys, requests
from bs4 import BeautifulSoup
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
      "Accept-Language": "it-IT,it;q=0.9"}
CANDS = [
    "https://www.nuroa.it/affitto-appartamenti-roma",
    "https://www.nuroa.it/affitto-appartamento-roma",
    "https://www.nuroa.it/affitto-trastevere-roma",
    "https://www.nuroa.it/affitto-roma-trastevere",
    "https://www.nuroa.it/affitto-appartamenti-trastevere-roma",
    "https://www.nuroa.it/affitto-appartamenti-roma?q=trastevere",
    "https://www.nuroa.it/affitto-prati-roma",
    "https://www.nuroa.it/affitto-monti-roma",
]
for url in CANDS:
    try:
        r = requests.get(url, headers=UA, timeout=20)
        soup = BeautifulSoup(r.text, "lxml")
        cards = len(soup.select("h3.nu_list_title"))
        zona_hits = len(re.findall(r"trastevere|prati|monti", r.text, re.I))
        print(f"HTTP {r.status_code} card:{cards:>3} zonahits:{zona_hits:>4}  {url}")
    except Exception as e:
        print(f"ERR {type(e).__name__:18}  {url}")
