# Scraper annunci privati Roma — PROGRESS

Stato persistente del progetto (sopravvive a reset di contesto). Aggiornare a ogni passo.

## Obiettivo
Scraper giornaliero di annunci AFFITTO da PRIVATI nel centro storico di Roma,
sui portali minori/aggregatori (i grandi Idealista/Immobiliare li copre Christian
con le notifiche push native). Output: digest email con i NUOVI annunci da contattare.

## Criteri (confermati 14/06/2026)
- Tipo: AFFITTO (no vendita)
- Budget: ≤ €1.800/mese
- Zone: Monti, Esquilino, Celio, Colle Oppio, Prati, Trastevere
- Solo PRIVATI (escludi agenzie)

## Architettura decisa
- Un solo motore Python (scraping + filtri + dedup + email)
- Cloud (routine giornaliera, sempre on) + Locale (Task Scheduler quando PC on)
- Stato condiviso annunci visti su repo GitHub
- BLOCCANTI da Christian: password-app Gmail (email), repo GitHub (cloud)

## Esito sonda fattibilità (Fase 1 — FATTA)
- 🔴 BLOCCANO (403/anti-bot): Subito, Wikicasa, Bakeca
- 🟢 SCRAPABILI: Nuroa (200), Trovit (200)
- 🟡 da sistemare URL: Nestoria (404), PortaPortese (DNS), HousingAnywhere (JS/API)
- STRATEGIA: puntare sugli AGGREGATORI (Nuroa, Trovit, Nestoria) che ripescano
  anche i siti che bloccano + decine di portali minori. Un nodo: filtrare "privati"
  sugli aggregatori (mescolano agenzie).

## Prossimi passi
1. [in corso] Inspect Nuroa/Trovit: capire se HTML statico o JS-rendered → stima precisa
2. Parser Nuroa
3. Parser Trovit
4. Filtri (zone, prezzo, privati) + dedup (seen.json)
5. Output su file (validazione senza email)
6. Email (richiede password-app Gmail)
7. Cloud + GitHub (fase successiva)

## Via C — STATO: MVP VALIDATO (14/06)
- `scraper.py` funziona end-to-end su Nuroa (pagina affitto-appartamenti-roma, 15 pagine).
- Filtri: tipo (solo appartamenti), zona (centro storico, con blocklist periferie tipo
  "prati fiscali/monte sacro"), prezzo <= 1800, e RIFIUTO uso ricettivo (scarta
  "no affitti brevi/solo uso abitativo..."), FAVORE (foresteria/investimento/turistico...).
  NB: "transitorio" rimosso dai favorevoli su richiesta di Christian.
- Dedup persistente su seen.json. Link puliti (estratti dal redirect Nuroa).
- Output: annunci_YYYY-MM-DD.txt. Run tipo: ~189 appartamenti -> 3 in target centro.
- Tutti e 3 erano su renthero.it (piattaforma PM/rent-to-rent: proprietari aperti a gestione pro).

## Cosa MANCA su Via C
- [ ] Email digest -> serve PASSWORD-APP Gmail di Christian (NON la password account!).
- [ ] Aggiungere altri aggregatori (Trovit = JS-render, da fare con API interna o Playwright; Nestoria URL da sistemare).
- [ ] Aumentare pagine / migliorare copertura zona.
- [ ] Deploy: cloud (routine giornaliera, serve repo GitHub) + locale (Task Scheduler).

## Via A (notifiche app native) — da impostare lato Christian
Idealista + Immobiliare + Subito + Bakeca: salva ricerca (Affitto, zone centro,
bilo/trilocale, max 1800, "solo privati" dove c'e') + notifiche push ON.

## Log
- 14/06: sonda fatta -> grandi siti bloccano, aggregatori ok ma agency-heavy.
- 14/06: pivot Via C (filtro su rifiuto uso ricettivo invece di privato/agenzia).
- 14/06: scraper.py Nuroa VALIDATO (3 annunci centro storico, link puliti). Email/cloud da fare.
- 14/06: aggiunto parser TROVIT (multi-fonte). Ora 4 annunci centro (Esquilino x2, Centro storico, Prati/Municipio I). TODO: verificare paginazione Trovit (?page ripete pag1?), pulire link clk.thribee. git NON installato.
