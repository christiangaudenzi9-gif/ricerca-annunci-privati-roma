"""Anatomia card Casa.it."""
import re, sys, requests
from bs4 import BeautifulSoup
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
      "Accept-Language": "it-IT,it;q=0.9"}
html = requests.get("https://www.casa.it/affitto/residenziale/roma/", headers=UA, timeout=25).text
open("sample_casa.html","w",encoding="utf-8").write(html)
soup = BeautifulSoup(html, "lxml")

# link annuncio
links = soup.find_all("a", href=re.compile(r"/immobili/\d+"))
print("link /immobili/<id>:", len(links))
if links:
    print("  esempio href:", links[0].get("href")[:80], "| text:", links[0].get_text(' ',strip=True)[:50])

# trova il contenitore card a partire da un prezzo
pn = None
for el in soup.find_all(string=re.compile(r"€")):
    if re.search(r"\d", el):
        pn = el; break
if pn:
    node = pn.parent
    for i in range(6):
        if node is None: break
        cls = node.get("class")
        idd = node.get("id")
        print(f"  parent[{i}] <{node.name}> class={cls} id={idd}")
        node = node.parent

# classi con 'price' e 'title'
for kw in ["price","prezzo","title","titolo","srpcard__title","address","location"]:
    s = set()
    for tag in soup.find_all(True):
        for c in (tag.get("class") or []):
            if kw.lower() in c.lower():
                s.add(f"{tag.name}.{c}")
    if s: print(f"  classi '{kw}':", list(s)[:5])
