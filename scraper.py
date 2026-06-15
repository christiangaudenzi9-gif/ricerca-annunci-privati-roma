"""
Scraper Via C — annunci affitto Roma centro dagli aggregatori (Nuroa).
NON filtra agenzia/privato. Filtra:
  - tipo: appartamenti (esclude negozi, uffici, box, garage, stanze...)
  - zona: centro storico (lista target)
  - prezzo: <= MAX_PREZZO
  - uso ricettivo: SCARTA chi lo rifiuta (no affitti brevi / solo uso abitativo...)
    e mette in cima chi lo favorisce (uso transitorio, foresteria, investimento...)

Dedup persistente su seen.json (solo NUOVI annunci a ogni run).
Output: file digest datato + riepilogo a schermo. (Email: TODO con password-app Gmail.)
"""
import json
import os
import re
import smtplib
import sys
import time
from datetime import date
from email.message import EmailMessage
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = Path(__file__).resolve().parent

# ----------------------------- CONFIG ------------------------------------- #
MAX_PREZZO = 1800
# zona centro storico: match preciso. "prati" esclude "Prati Fiscali"; "monti"
# esclude "Monti Tiburtini" (zone diverse, fuori centro).
ZONE_RE = re.compile(
    r"\b(esquilino|celio|colle\s+oppio|trastevere|centro\s+storico)\b"
    r"|\bprati\b(?!\s*fiscal)"
    r"|\bmonti\b(?!\s*tiburtin)", re.I)
# zone periferiche: se presenti, l'annuncio NON e' centro storico (gli aggregatori
# elencano cluster di macrozone, es. "nuovo salario, prati fiscali, monte sacro...")
ZONE_EXCLUDE = re.compile(
    r"prati fiscal|monte sacro|monti tiburtin|nuovo salario|talenti|vigne nuove|"
    r"serpentara|montagnola|casalotti|portuens|magliana|infernetto|axa|"
    r"bufalotta|fidene|tor ", re.I)
# tipi da TENERE (l'annuncio inizia di solito con la tipologia)
TIPI_OK = ["appartament", "casa", "attico", "bilocale", "trilocale", "monolocale",
           "quadrilocale", "loft", "mansarda"]
TIPI_NO = ["negozio", "ufficio", "box", "garage", "posto auto", "magazzino",
           "capannone", "stanza", "camera", "locale commerciale", "terreno",
           "laboratorio", "cantina"]

# uso ricettivo RIFIUTATO -> scarta
RIFIUTO = re.compile(
    r"no affitt[io] brev|niente affitt[io] brev|no uso turistic|no turistic|"
    r"no casa vacanz|no b\s?&\s?b|no bed\s?and\s?breakfast|solo uso abitativ|"
    r"esclusivamente (uso )?abitativ|uso esclusivamente abitativ|solo residenzial|"
    r"esclusivamente residenzial|no foresteri|no uso ricettiv|no airbnb", re.I)
# uso ricettivo FAVORITO -> in cima
FAVORE = re.compile(
    r"affitt[io] brev|uso foresteri|foresteri|"
    r"casa vacanz|b\s?&\s?b|investiment|a reddito|\breddito\b|uso ricettiv|"
    r"ideale per investiment|rendita|turistic|airbnb", re.I)

SEEN_FILE = BASE / "seen.json"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "it-IT,it;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def log(m): print(m, flush=True)


def clean_link(link):
    """Estrae l'URL reale della fonte dal redirect Nuroa (multi-encoded)."""
    dec = link
    for _ in range(4):
        dec = unquote(dec)
    cands = re.findall(r"url=(https?://[^&]+)", dec)
    src = [u for u in cands if "nuroa.it" not in u]
    if src:
        return src[-1]
    return cands[-1] if cands else link


def load_seen():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
    return set()


def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(sorted(seen)), encoding="utf-8")


def email_cfg():
    """Credenziali email da env (cloud) o da config.json locale (gitignored)."""
    cfg = {}
    cfgfile = BASE / "config.json"
    if cfgfile.exists():
        cfg = json.loads(cfgfile.read_text(encoding="utf-8"))
    user = os.environ.get("GMAIL_USER") or cfg.get("gmail_user")
    pwd = os.environ.get("GMAIL_PASS") or cfg.get("gmail_pass")
    to = os.environ.get("MAIL_TO") or cfg.get("mail_to") or user
    return user, pwd, to


def send_email(subject, body):
    user, pwd, to = email_cfg()
    if not (user and pwd):
        log("Email non configurata (manca GMAIL_USER/GMAIL_PASS) -> salto invio.")
        return False
    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(user, pwd.replace(" ", ""))
        s.send_message(msg)
    log(f"Email inviata a {to}")
    return True


def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return r.text


def parse_nuroa(html):
    """Estrae le card da una pagina Nuroa. Ritorna lista di dict."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for h in soup.select("h3.nu_list_title"):
        # risali alla card (blocco con prezzo)
        card = h
        for _ in range(6):
            card = card.find_parent() if card else None
            if card and re.search(r"€", card.get_text(" ", strip=True)):
                break
        if not card:
            continue
        a = card.find("a", class_=re.compile(r"nu_adlink"), href=True)
        if not a:
            continue
        link = a["href"]
        if "/conversion/featured/" in link:   # ad sponsor non immobiliare
            continue
        link = clean_link(link)
        # id annuncio dalla classe nu_adlink_<id>
        ad_id = ""
        for c in (a.get("class") or []):
            m = re.match(r"nu_adlink_(\w+)", c)
            if m:
                ad_id = m.group(1)
        title = h.get_text(" ", strip=True)
        addr_el = card.select_one(".nu_address_text")
        addr = addr_el.get_text(" ", strip=True) if addr_el else ""
        price_el = card.select_one(".nu_price, .nu_long_price")
        ptxt = price_el.get_text(" ", strip=True) if price_el else card.get_text(" ", strip=True)
        pm = re.search(r"(\d[\d.]*)\s*€|€\s*(\d[\d.]*)", ptxt)
        price = int((pm.group(1) or pm.group(2)).replace(".", "")) if pm else None
        desc_el = card.select_one(".nu_desc_container, .nu_snippet, .nu_description")
        desc = desc_el.get_text(" ", strip=True) if desc_el else ""
        key = ad_id or re.sub(r"\W+", "", (title + str(price)))[:40]
        out.append({"key": key, "title": title, "price": price, "addr": addr,
                    "desc": desc, "link": link})
    # dedup intra-pagina (mobile+desktop)
    uniq = {d["key"]: d for d in out}
    return list(uniq.values())


def parse_trovit(html):
    """Estrae le card da una pagina Trovit (article.snippet-listing)."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for card in soup.select("article.snippet-listing"):
        aid = card.get("data-id") or ""
        a = card.select_one("a.js-listing") or card.find("a", href=True)
        link = a.get("href", "") if a else ""
        if link.startswith("/"):
            link = "https://casa.trovit.it" + link
        price_el = card.select_one(".price__actual")
        ptxt = price_el.get_text(" ", strip=True) if price_el else ""
        pm = re.search(r"(\d[\d.]*)", ptxt)
        price = int(pm.group(1).replace(".", "")) if pm else None
        type_el = card.select_one(".address_property-type")
        addr = type_el.get_text(" ", strip=True) if type_el else ""
        desc_el = card.select_one(".snippet-listing-content-header-description")
        title = desc_el.get_text(" ", strip=True) if desc_el else addr
        key = aid or re.sub(r"\W+", "", (title + str(price)))[:40]
        out.append({"key": key, "title": title, "price": price, "addr": addr,
                    "desc": title, "link": link})
    uniq = {d["key"]: d for d in out}
    return list(uniq.values())


def tipo_ok(title):
    t = title.lower()
    if any(x in t for x in TIPI_NO):
        return False
    return any(x in t for x in TIPI_OK)


def zona_ok(addr, title):
    blob = addr + " " + title
    if ZONE_EXCLUDE.search(blob):
        return False
    return bool(ZONE_RE.search(blob))


def fetch_detail(url):
    """Apre la pagina dell'annuncio e ne estrae il TESTO completo (per leggere la
    descrizione vera, dove sta l'eventuale 'no uso ricettivo'). None se la fonte blocca."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "lxml")
        for t in soup(["script", "style", "noscript"]):
            t.extract()
        return soup.get_text(" ", strip=True).lower()
    except Exception:
        return None


def private_signal(text):
    """Euristica privato vs agenzia dal testo dell'annuncio."""
    if not text:
        return "?"
    has_ag = bool(re.search(r"agenzia|immobiliare s\.?r\.?l|real estate|gruppo immobiliar|"
                            r"rif\.?\s*agenzia", text))
    has_priv = bool(re.search(r"\bprivato\b|da privato|annuncio di un privato|no agenzie|"
                              r"niente agenzie|nessuna agenzia", text))
    if has_priv and not has_ag:
        return "privato"
    if has_priv and has_ag:
        return "privato?"
    if has_ag:
        return "agenzia"
    return "?"


def main():
    seen = load_seen()
    SOURCES = [
        {"name": "nuroa",
         "url": "https://www.nuroa.it/affitto-appartamenti-roma",
         "parser": parse_nuroa, "pages": 15,
         "pagefmt": lambda u, p: u if p == 1 else f"{u}/{p}"},
        {"name": "trovit",
         "url": "https://casa.trovit.it/affitto-roma",
         "parser": parse_trovit, "pages": 3,  # TODO verificare param paginazione
         "pagefmt": lambda u, p: u if p == 1 else f"{u}?page={p}"},
    ]
    raw = []
    for s in SOURCES:
        log(f"[{s['name']}]")
        for p in range(1, s["pages"] + 1):
            url = s["pagefmt"](s["url"], p)
            try:
                html = fetch(url)
            except Exception as e:
                log(f"  pag {p}: errore {type(e).__name__}")
                break
            cards = s["parser"](html)
            log(f"  {url} -> {len(cards)} card")
            if not cards:
                break
            raw.extend(cards)
            time.sleep(1.5)

    # dedup globale
    allcards = {c["key"]: c for c in raw}.values()

    tot = len(allcards)
    cand, scartati_tipo, scartati_zona, scartati_prezzo, scartati_rifiuto = [], 0, 0, 0, 0
    for c in allcards:
        if not tipo_ok(c["title"]):
            scartati_tipo += 1; continue
        if not zona_ok(c["addr"], c["title"]):
            scartati_zona += 1; continue
        if c["price"] is not None and c["price"] > MAX_PREZZO:
            scartati_prezzo += 1; continue
        if RIFIUTO.search(" ".join([c["title"], c["addr"], c["desc"]])):  # rifiuto gia' nella card
            scartati_rifiuto += 1; continue
        cand.append(c)

    # Verifica la DESCRIZIONE COMPLETA solo per i candidati NUOVI: apre l'annuncio,
    # legge il testo e SCARTA chi rifiuta l'uso ricettivo. Tagga privato/agenzia.
    nuovi_cand = [c for c in cand if c["key"] not in seen]
    keep, scartati_rifiuto_desc, non_verif = [], 0, 0
    for c in nuovi_cand:
        detail = fetch_detail(c["link"])
        full = " ".join([c["title"], c["addr"], c["desc"], detail or ""])
        if detail and RIFIUTO.search(full):
            scartati_rifiuto_desc += 1
            continue   # rifiuta l'uso ricettivo nella descrizione -> fuori
        c["classe"] = "favorevole" if FAVORE.search(full) else "neutro"
        c["fonte_tipo"] = private_signal(detail)
        c["verificato"] = detail is not None
        if not detail:
            non_verif += 1
        keep.append(c)
        time.sleep(0.6)

    # ordina: favorevoli prima, poi i piu' "privati" prima
    keep.sort(key=lambda c: (0 if c["classe"] == "favorevole" else 1,
                             0 if c["fonte_tipo"].startswith("privato") else 1))
    nuovi = keep
    favorevoli = [c for c in nuovi if c["classe"] == "favorevole"]
    neutri = [c for c in nuovi if c["classe"] == "neutro"]

    # report
    log("\n===== RIEPILOGO =====")
    log(f"card totali (dedup): {tot}")
    log(f"  scartati tipo (no appartamento): {scartati_tipo}")
    log(f"  scartati zona (fuori centro):    {scartati_zona}")
    log(f"  scartati prezzo (> {MAX_PREZZO}):     {scartati_prezzo}")
    log(f"  scartati rifiuto (gia nella card): {scartati_rifiuto}")
    log(f"  candidati in target: {len(cand)} (nuovi da verificare: {len(nuovi_cand)})")
    log(f"  scartati rifiuto (in descrizione): {scartati_rifiuto_desc}")
    log(f"  INVIATI: {len(nuovi)} (favorevoli {len(favorevoli)}, neutri {len(neutri)}, non verificati {non_verif})")

    # output file digest
    out_lines = [f"# Annunci affitto Roma centro — {date.today()}",
                 f"# Nuovi in target: {len(nuovi)} (favorevoli {len(favorevoli)}, neutri {len(neutri)})",
                 "# Tag: [privato/agenzia/?] + stato verifica descrizione.\n"]
    for sezione, lst in [("FAVOREVOLI (uso ricettivo ok)", favorevoli), ("NEUTRI (da verificare)", neutri)]:
        out_lines.append(f"\n## {sezione}")
        for c in lst:
            price = f"€{c['price']}" if c["price"] else "€?"
            ver = "descrizione OK" if c.get("verificato") else "⚠️ descrizione NON verificata (apri il link)"
            out_lines.append(f"- {c['title'][:60]} | {price} | {c['addr'][:35]} | [{c.get('fonte_tipo','?')}] [{ver}]\n  {c['link']}")
    outfile = BASE / f"annunci_{date.today()}.txt"
    outfile.write_text("\n".join(out_lines), encoding="utf-8")
    log(f"\nDigest scritto in: {outfile.name}")

    # invio email (solo se ci sono annunci nuovi)
    if nuovi:
        send_email(f"Annunci casa Roma centro — {date.today()} ({len(nuovi)} nuovi)",
                   "\n".join(out_lines))
    else:
        log("Nessun nuovo annuncio: niente email.")

    # aggiorna seen con TUTTI i candidati in target (anche gli scartati per rifiuto in
    # descrizione, cosi' non li riapriamo/rinviamo)
    seen.update(c["key"] for c in cand)
    save_seen(seen)


if __name__ == "__main__":
    main()
