"""Anatomia di una card nu_listing_details."""
import sys
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
soup = BeautifulSoup(open("sample_nuroa.html", encoding="utf-8").read(), "lxml")

cards = soup.select("div.nu_listing_details")
print(f"card trovate: {len(cards)}\n")
card = cards[0]
# risali al contenitore-annuncio (genitore con <a>)
container = card
for _ in range(4):
    if container.parent and container.parent.find("a", href=True):
        container = container.parent
    else:
        break

for el in container.find_all(True, recursive=True):
    cls = el.get("class")
    txt = el.get_text(" ", strip=True)
    if txt and len(txt) < 80:
        extra = ""
        if el.name == "a":
            extra = " href=" + (el.get("href") or "")[:60]
        print(f"<{el.name}> {cls} :: {txt[:70]}{extra}")
