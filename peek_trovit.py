"""Capisce dove stanno i dati in Trovit (prezzi in data-attr o JSON?)."""
import re, sys, json
from bs4 import BeautifulSoup
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
html = open("sample_trovit.html", encoding="utf-8").read()
soup = BeautifulSoup(html, "lxml")

# JSON blobs?
print("__NEXT_DATA__:", "__NEXT_DATA__" in html)
for sc in soup.find_all("script", type="application/ld+json"):
    txt = sc.string or ""
    if "price" in txt.lower() or "offer" in txt.lower():
        print("ld+json con price! len", len(txt), "preview:", txt[:200].replace("\n"," "))

# primo article: attributi + struttura
arts = soup.find_all("article")
print("\narticle trovati:", len(arts))
if arts:
    a = arts[0]
    print("attrs article:", {k: (v if len(str(v))<60 else str(v)[:60]) for k,v in a.attrs.items()})
    for el in a.find_all(True, recursive=True)[:25]:
        dattrs = {k:v for k,v in el.attrs.items() if k.startswith("data-") or k in ("class","itemprop","content")}
        txt = el.get_text(" ", strip=True)[:45]
        print(f"  <{el.name}> {dattrs} :: {txt}")
