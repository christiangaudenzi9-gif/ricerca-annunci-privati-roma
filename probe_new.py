"""Sonda URL+struttura di Nestoria e Casa.it."""
import re, sys, requests
from bs4 import BeautifulSoup
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
      "Accept-Language": "it-IT,it;q=0.9",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
CANDS = {
    "nestoria1": "https://www.nestoria.it/roma/case/affitto",
    "nestoria2": "https://www.nestoria.it/roma/affitto",
    "casa1": "https://www.casa.it/affitto/residenziale/roma/",
    "casa2": "https://www.casa.it/affitto/roma/",
}
for name, url in CANDS.items():
    try:
        r = requests.get(url, headers=UA, timeout=20)
        body = r.text.lower()
        blocked = any(w in body for w in ["captcha","datadome","access denied","request blocked","px-captcha"])
        euros = len(re.findall(r"€|&euro;|/mese", body))
        soup = BeautifulSoup(r.text, "lxml")
        arts = len(soup.find_all("article"))
        nextdata = "__next_data__" in body or "__nuxt__" in body
        # classi contenitore candidate
        from collections import Counter
        cc = Counter()
        for tag in soup.find_all(True):
            for c2 in (tag.get("class") or []):
                if re.search(r"card|listing|result|annunc|snippet|item|property|in-", c2, re.I):
                    cc[f"{tag.name}.{c2}"] += 1
        top = ", ".join(f"{k}({v})" for k,v in cc.most_common(5))
        print(f"{name:10} HTTP {r.status_code} len {len(r.text):>7} eur {euros:>4} art {arts:>3} jsondata {nextdata} blocked {blocked}")
        print(f"           top: {top}")
    except Exception as e:
        print(f"{name:10} ERR {type(e).__name__}: {e}")
