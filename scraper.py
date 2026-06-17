"""
Scraper Via C — annunci affitto Roma centro dagli aggregatori (Nuroa/Trovit/Casa.it).
NON filtra agenzia/privato. Filtra:
  - tipo: appartamenti (esclude negozi, uffici, box, garage, stanze...)
  - zona: primi 10 rioni (R.I–R.X) + Trastevere + Esquilino, Celio, Colle Oppio,
    Aventino, Testaccio. Esclusi Prati/Vaticano/Borgo, San Lorenzo, San Giovanni e
    periferia. Classificazione a 3 esiti (in/fuori/forse); i "forse" entrano solo se
    il DETTAGLIO conferma il target (rione/landmark/CAP).
  - prezzo: <= MAX_PREZZO
  - uso ricettivo: SCARTA chi lo rifiuta (no affitti brevi / solo uso abitativo...)
    e mette in cima chi lo favorisce (uso transitorio, foresteria, investimento...)

Dedup persistente su seen.json (solo NUOVI annunci a ogni run).
Email inviata SEMPRE (anche 0 nuovi: fa da battito + segnala se i siti bloccano).
Output: file digest datato + riepilogo a schermo.
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

# ----------------------------- ZONA --------------------------------------- #
# Target = PRIMI 10 RIONI di Roma (R.I–R.X) + TRASTEVERE (R.XIII) + Esquilino,
# Celio, Colle Oppio, Aventino, Testaccio (rimessi su richiesta Christian 17/06).
# NON inclusi: Prati/Vaticano/Borgo, San Lorenzo, San Giovanni, e tutta la periferia.
#
# Strategia: la card spesso non nomina il rione (solo "Roma" o una via). Quindi
# classifichiamo con tre esiti — "in" (zona target sicura), "fuori" (zona esclusa
# sicura), "forse" (ignota) — e per i "forse" apriamo il dettaglio (dove c'e'
# l'indirizzo completo + CAP) prima di decidere.

# --- TARGET: nomi rione + vie/piazze/landmark caratteristici dei 10 rioni + Trastevere
ZONE_TARGET = re.compile(
    r"\bcentro\s+storico\b|"
    # rioni
    r"\b(trastevere|campo\s+marzio|sant'?\s?eustachio|s\.?\s?eustachio|"
    r"campitelli|parione|regola|pigna|colonna|trevi|"
    r"esquilino|celio|colle\s+oppio|aventino|testaccio)\b|"
    r"\brione\s+monti\b|\bmonti\b(?!\s*(tiburtin|sacro|parioli))|\bponte\b(?!\s*(mammolo|galeria|milvio))|"
    # landmark / vie / piazze centrali
    r"pantheon|piazza\s+navona|campo\s+de'?\s?fiori|fontana\s+di\s+trevi|"
    r"piazza\s+di\s+spagna|piazza\s+del\s+popolo|piazza\s+venezia|piazza\s+colonna|"
    r"piazza\s+farnese|piazza\s+della\s+rotonda|largo\s+(di\s+torre\s+)?argentina|"
    r"fori\s+imperiali|foro\s+romano|campidoglio|teatro\s+di\s+marcello|"
    r"trinit[aà]\s+dei\s+monti|montecitorio|quirinale|"
    r"via\s+del\s+corso|via\s+condotti|via\s+frattina|via\s+borgognona|via\s+del\s+babuino|"
    r"via\s+margutta|via\s+di\s+ripetta|via\s+della\s+scrofa|via\s+giulia|via\s+dei\s+coronari|"
    r"via\s+del\s+governo\s+vecchio|via\s+dei\s+giubbonari|via\s+monserrato|via\s+arenula|"
    r"via\s+cavour|via\s+nazionale|via\s+panisperna|via\s+dei\s+serpenti|via\s+urbana|"
    r"via\s+del\s+tritone|via\s+due\s+macelli|via\s+del\s+plebiscito|via\s+delle\s+botteghe\s+oscure|"
    r"piazza\s+santa\s+maria\s+in\s+trastevere|viale\s+(di\s+)?trastevere|piazza\s+trilussa|"
    r"via\s+della\s+lungaretta|via\s+di\s+san\s+francesco\s+a\s+ripa|ponte\s+sisto|"
    # Esquilino / Celio / Colle Oppio / Aventino / Testaccio (rimessi 17/06)
    r"piazza\s+vittorio|santa\s+maria\s+maggiore|san\s+pietro\s+in\s+vincoli|"
    r"via\s+merulana|via\s+labicana|colosseo|san\s+clemente|celimontana|"
    r"terme\s+di\s+caracalla|circo\s+massimo|giardino\s+degli\s+aranci|"
    r"piramide|monte\s+testaccio|mercato\s+(di\s+)?testaccio",
    re.I)

# --- CAP centrali (rete di sicurezza, cercata nel dettaglio completo) ---
# 00184 Monti · 00186 Ponte/Parione/Regola/S.Eustachio/Pigna/Campitelli ·
# 00187 Trevi/Colonna/Campo Marzio · 00153 Trastevere
ZONE_CAP = re.compile(r"\b(00184|00186|00187|00153)\b")

# --- ESCLUSE: periferia + zone centrali-ma-fuori-target (Vaticano/Prati, Esquilino...)
ZONE_EXCLUDE = re.compile(
    # Vaticano / Prati / Borgo (la segnalazione "lontana" del 16/06)
    r"\bprati\b|prati\s+degli\s+strozzi|vaticano|\bborgo\b|ottaviano|cipro|lepanto|"
    r"cola\s+di\s+rienzo|della\s+vittoria|delle\s+vittorie|piazza\s+delle\s+muse|"
    # quartieri adiacenti ma esclusi (Esquilino/Celio/Aventino/Testaccio sono TARGET)
    r"san\s+lorenzo|san\s+giovanni|s\.?\s?giovanni|appio|"
    # macrozone periferiche
    r"prati\s+fiscal|monte\s+sacro|monti\s+tiburtin|nuovo\s+salario|talenti|vigne\s+nuove|"
    r"serpentara|montagnola|casalotti|portuens|magliana|infernetto|\baxa\b|"
    r"bufalotta|fidene|\btor\s|parioli|pinciano|trieste|salario|nomentan|"
    r"tuscolan|tiburtin|pietralata|collatino|centocelle|prenestin|casilin|"
    r"eur\b|laurentin|spinaceto|trigoria|acilia|ostia|vitinia|giustiniana|olgiata|"
    r"casal|torrenova|tor\s+tre\s+teste|bravetta|pisana|garbatella|ardeatin|"
    # Trovit: "Municipio Roma <N>" — solo il I e' il centro storico; II–XV = fuori
    r"municipio\s+roma\s+(ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv)\b",
    re.I)
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


def parse_casa(html):
    """Estrae le card da Casa.it (a.csaSrpcard__det__title--a)."""
    soup = BeautifulSoup(html, "lxml")
    out = []
    for a in soup.select("a.csaSrpcard__det__title--a"):
        title = a.get_text(" ", strip=True)
        href = a.get("href", "")
        if href.startswith("/"):
            href = "https://www.casa.it" + href
        card = a
        for _ in range(8):
            card = card.find_parent() if card else None
            if card and card.select_one(".csaSrpcard__det__feats--price"):
                break
        price_el = card.select_one(".csaSrpcard__det__feats--price") if card else None
        ptxt = price_el.get_text(" ", strip=True) if price_el else ""
        pm = re.search(r"(\d[\d.]*)", ptxt)
        price = int(pm.group(1).replace(".", "")) if pm else None
        loc_el = card.select_one(".location") if card else None
        addr = loc_el.get_text(" ", strip=True) if loc_el else ""
        m = re.search(r"/immobili/(\d+)", href)
        key = "casa-" + m.group(1) if m else re.sub(r"\W+", "", (title + str(price)))[:40]
        out.append({"key": key, "title": title or addr, "price": price, "addr": addr,
                    "desc": title, "link": href})
    uniq = {d["key"]: d for d in out}
    return list(uniq.values())


def tipo_ok(title):
    t = title.lower()
    if any(x in t for x in TIPI_NO):
        return False
    return any(x in t for x in TIPI_OK)


def zona_classifica(text):
    """Classifica un testo (card o dettaglio) rispetto al target geografico:
      'fuori' -> zona esclusa certa (periferia / Vaticano-Prati / Esquilino...)
      'in'    -> primi 10 rioni o Trastevere (rione, landmark o CAP centrale)
      'forse' -> nessun segnale: zona ignota, va verificata nel dettaglio.
    L'esclusione vince sull'inclusione (se un annuncio nomina sia un landmark
    centrale sia una macrozona periferica, meglio scartarlo)."""
    if not text:
        return "forse"
    if ZONE_EXCLUDE.search(text):
        return "fuori"
    if ZONE_TARGET.search(text) or ZONE_CAP.search(text):
        return "in"
    return "forse"


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
        {"name": "casa.it",
         "url": "https://www.casa.it/affitto/residenziale/roma/",
         "parser": parse_casa, "pages": 4,
         "pagefmt": lambda u, p: u if p == 1 else f"{u}?page={p}"},
    ]
    raw = []
    fonti_stat = []   # (nome, n_card, nota) per il report/email — rende visibile un blocco
    for s in SOURCES:
        log(f"[{s['name']}]")
        n_src, nota = 0, "ok"
        for p in range(1, s["pages"] + 1):
            url = s["pagefmt"](s["url"], p)
            try:
                html = fetch(url)
            except Exception as e:
                log(f"  pag {p}: errore {type(e).__name__}")
                nota = f"errore {type(e).__name__} a pag {p}"
                break
            cards = s["parser"](html)
            log(f"  {url} -> {len(cards)} card")
            if not cards:
                if p == 1:
                    nota = "0 card a pag 1 (parser rotto o sito che blocca?)"
                break
            raw.extend(cards)
            n_src += len(cards)
            time.sleep(1.5)
        fonti_stat.append((s["name"], n_src, nota))

    # dedup globale
    allcards = list({c["key"]: c for c in raw}.values())

    tot = len(allcards)
    # filtro card: tipo -> prezzo -> zona (3 esiti) -> rifiuto gia' nella card
    cand, scartati_tipo, scartati_zona, scartati_prezzo, scartati_rifiuto = [], 0, 0, 0, 0
    for c in allcards:
        if not tipo_ok(c["title"]):
            scartati_tipo += 1; continue
        if c["price"] is not None and c["price"] > MAX_PREZZO:
            scartati_prezzo += 1; continue
        z = zona_classifica(" ".join([c["addr"], c["title"], c["desc"]]))
        if z == "fuori":
            scartati_zona += 1; continue
        if RIFIUTO.search(" ".join([c["title"], c["addr"], c["desc"]])):
            scartati_rifiuto += 1; continue
        c["zona_card"] = z   # "in" o "forse"
        cand.append(c)

    # Verifica la DESCRIZIONE COMPLETA solo per i candidati NUOVI: apre l'annuncio,
    # legge il testo, ri-classifica la zona (CAP/indirizzo completo), scarta chi
    # rifiuta l'uso ricettivo o e' fuori target, tagga privato/agenzia.
    nuovi_cand = [c for c in cand if c["key"] not in seen]
    keep, scartati_rifiuto_desc, scartati_zona_desc, non_verif = [], 0, 0, 0
    for c in nuovi_cand:
        detail = fetch_detail(c["link"])
        full = " ".join([c["title"], c["addr"], c["desc"], detail or ""])
        if detail and RIFIUTO.search(full):
            scartati_rifiuto_desc += 1
            continue   # rifiuta l'uso ricettivo -> fuori
        # zona: card "in" basta; card "forse" entra SOLO se il dettaglio CONFERMA
        # il target (rione/landmark/CAP). Conferma solo positiva: niente esclusioni
        # sul dettaglio (evita falsi scarti tipo "a 5 min da Termini") e niente
        # calderone "da verificare" (sarebbe rumore: idealista blocca il dettaglio).
        if c["zona_card"] != "in":
            if not (detail and zona_classifica(detail) == "in"):
                scartati_zona_desc += 1
                continue
        c["zona_finale"] = "in"
        c["classe"] = "favorevole" if FAVORE.search(full) else "neutro"
        c["fonte_tipo"] = private_signal(detail)
        c["verificato"] = detail is not None
        if not detail:
            non_verif += 1
        keep.append(c)
        time.sleep(0.6)

    # ordina: favorevoli prima, poi i piu' "privati"
    keep.sort(key=lambda c: (0 if c["classe"] == "favorevole" else 1,
                             0 if c["fonte_tipo"].startswith("privato") else 1))
    nuovi = keep   # tutti zona_finale == "in": primi 10 rioni + Trastevere
    fav = [c for c in nuovi if c["classe"] == "favorevole"]
    neu = [c for c in nuovi if c["classe"] == "neutro"]

    # report a schermo
    log("\n===== RIEPILOGO =====")
    log(f"card totali (dedup): {tot}")
    for nome, n, nota in fonti_stat:
        log(f"  fonte {nome}: {n} card ({nota})")
    log(f"  scartati tipo (no appartamento): {scartati_tipo}")
    log(f"  scartati prezzo (> {MAX_PREZZO}): {scartati_prezzo}")
    log(f"  scartati zona card (fuori target): {scartati_zona}")
    log(f"  scartati zona da dettaglio: {scartati_zona_desc}")
    log(f"  scartati rifiuto ricettivo: {scartati_rifiuto + scartati_rifiuto_desc}")
    log(f"  candidati: {len(cand)} (nuovi verificati: {len(nuovi_cand)})")
    log(f"  TENUTI (centro confermato): {len(nuovi)} (fav {len(fav)}, neu {len(neu)})")

    # --- costruzione corpo email/digest (SEMPRE, anche con 0 nuovi) ---
    def riga(c):
        price = f"€{c['price']}" if c["price"] else "€?"
        ver = "descr. OK" if c.get("verificato") else "⚠️ descr. NON letta"
        addr = c["addr"][:35] or "(zona non in card)"
        return (f"- {c['title'][:60]} | {price} | {addr} | "
                f"[{c.get('fonte_tipo','?')}] [{ver}]\n  {c['link']}")

    fonti_riepilogo = " · ".join(f"{nome}:{n}" for nome, n, _ in fonti_stat)
    out_lines = [f"# Annunci affitto Roma centro — {date.today()}",
                 f"# Filtro: 10 rioni + Trastevere + Esquilino/Celio/Aventino/Testaccio · ≤ €{MAX_PREZZO} · appartamenti",
                 f"# Card raccolte: {tot} ({fonti_riepilogo}) · nuovi tenuti: {len(nuovi)}",
                 ""]
    note_fonti = [f"{nome} ({nota})" for nome, n, nota in fonti_stat if nota != "ok"]
    if note_fonti:
        out_lines.append("⚠️ FONTI CON PROBLEMI: " + "; ".join(note_fonti) + "\n")

    if not nuovi:
        out_lines.append("Nessun annuncio NUOVO in target oggi.")
        if tot == 0:
            out_lines.append("⚠️ Attenzione: 0 card raccolte da TUTTE le fonti — "
                             "probabile blocco/cambio sito. Controllare lo scraper.")
    else:
        for sezione, lst in [("FAVOREVOLI (uso ricettivo ok)", fav),
                             ("NEUTRI (da verificare descrizione)", neu)]:
            if not lst:
                continue
            out_lines.append(f"\n## {sezione}")
            out_lines.extend(riga(c) for c in lst)

    outfile = BASE / f"annunci_{date.today()}.txt"
    outfile.write_text("\n".join(out_lines), encoding="utf-8")
    log(f"\nDigest scritto in: {outfile.name}")

    # invio email SEMPRE (anche 0 nuovi: serve come 'battito' + monitoraggio blocchi)
    n = len(nuovi)
    if n:
        subj = f"🏠 Annunci Roma centro — {date.today()} ({n} nuovi)"
    elif tot == 0:
        subj = f"⚠️ Annunci Roma centro — {date.today()} (0 card: scraper da controllare)"
    else:
        subj = f"Annunci Roma centro — {date.today()} (nessun nuovo)"
    send_email(subj, "\n".join(out_lines))

    # aggiorna seen con TUTTI i candidati (anche scartati a valle), per non riaprirli
    seen.update(c["key"] for c in cand)
    save_seen(seen)


if __name__ == "__main__":
    main()
