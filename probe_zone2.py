"""Estrae i veri href delle zone da una pagina Nuroa."""
import re, sys, requests
from bs4 import BeautifulSoup
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
      "Accept-Language": "it-IT,it;q=0.9"}
r = requests.get("https://www.nuroa.it/affitto-appartamenti-roma", headers=UA, timeout=20)
soup = BeautifulSoup(r.text, "lxml")
seen = set()
for a in soup.find_all("a", href=True):
    href = a["href"]
    txt = a.get_text(" ", strip=True)
    if re.search(r"trastevere|prati|monti|esquilino|celio|centro", href + " " + txt, re.I):
        k = href
        if k not in seen:
            seen.add(k)
            print(f"[{txt[:30]:30}] {href[:90]}")
