"""Arricchimento: contesto allenatore + statistiche avanzate Sofascore.

⚠️ Questo file **non fa parte di fishertiger originale**: è nostro. Vedi `../FONTE.md`.

Perché esiste
-------------
fishertiger proietta benissimo il rendimento individuale, ma **non sa nulla
dell'allenatore**. In una stagione con Sarri all'Atalanta, Gasperini alla Roma,
Allegri al Napoli e Spalletti alla Juve, il contesto è la variabile più pesante:
un attaccante forte in una squadra che non produce gol vale meno, un difensore
in una difesa solida vale di più (e col modificatore difesa vale il doppio).

Cosa aggiunge a ogni giocatore
------------------------------
Un blocco `contesto_allenatore` con:

- `moltiplicatore` — la correzione (>1 il contesto aiuta, <1 penalizza);
- `motivi` — **perché**, in parole, una riga per fattore. fishertiger è esplicito
  sulle sue ragioni ("Perché", "Attenzione") e questo blocco segue la stessa regola:
  un numero senza il suo perché non è utilizzabile all'asta;
- l'anagrafica del contesto (allenatore, modulo, gol fatti/subiti a partita);
- `avanzate` — xG, xA e **scarto gol−xG** da Sofascore, *dove disponibili*.

Regola di sicurezza
-------------------
Questo modulo **non può rompere la pipeline**. Ogni errore viene assorbito e i
giocatori tornano invariati: un arricchimento che fa fallire la generazione dei
dati sarebbe molto peggio di un arricchimento assente.

Copertura
---------
Il contesto allenatore c'è per **tutte e 20** le squadre. Le statistiche avanzate
solo per quelle scaricate da Sofascore prima del blocco (13 su 20 al 2026-09-03):
`avanzate` è `None` per le altre, e il campo `avanzate_disponibili` lo dichiara.
"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

# fishertiger/advisor/contesto_allenatore.py -> fishertiger -> progetto
PROGETTO = Path(__file__).resolve().parents[2]
DATI = PROGETTO / "dati"

# I nomi squadra di fishertiger (dal listone Fantacalcio) e i nostri (Sofascore)
# coincidono su 17 su 20. Questi tre no.
SQUADRE = {"Milan": "AC Milan", "Napoli": "SSC Napoli", "Roma": "AS Roma"}

# fishertiger usa i ruoli del fantacalcio, analizza.py quelli di Sofascore.
RUOLI = {"A": "F", "C": "M", "D": "D", "P": "G"}

# La stagione di riferimento per le avanzate: l'ultima **completa**.
# La 26/27 ha due giornate, ed è rumore.
STAGIONE = "25/26"


def _senza_accenti(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def _cognome_fantacalcio(nome: str) -> str:
    """"Martinez L." -> "martinez"; "Dimarco" -> "dimarco"."""
    testa = _senza_accenti(nome).split()
    if not testa:
        return ""
    # scarta un'eventuale iniziale finale ("L.", "K.")
    if len(testa) > 1 and len(testa[-1].rstrip(".")) <= 1:
        testa = testa[:-1]
    return " ".join(testa)


def _carica(nome: str):
    with open(DATI / nome, encoding="utf-8") as f:
        return json.load(f)


def _indice_sofascore(giocatori: dict) -> dict:
    """(squadra_nostra, cognome) -> record Sofascore."""
    idx = {}
    for p in giocatori.values():
        cognome = _senza_accenti(p["nome"]).split()
        if not cognome:
            continue
        # indicizza sia sull'ultimo token sia sugli ultimi due (cognomi doppi)
        chiavi = {cognome[-1]}
        if len(cognome) >= 2:
            chiavi.add(" ".join(cognome[-2:]))
        for k in chiavi:
            idx.setdefault((p["squadra"], k), p)
    return idx


def _avanzate(record: dict) -> dict | None:
    st = (record.get("stagioni") or {}).get(STAGIONE) or {}
    s = st.get("stats") or {}
    if not s.get("appearances"):
        return None
    gol = s.get("goals") or 0
    xg = s.get("expectedGoals")
    fuori = round(gol - xg, 2) if xg is not None else None
    return {
        "stagione": STAGIONE,
        "presenze": s.get("appearances"),
        "minuti": s.get("minutesPlayed"),
        "gol": gol,
        "assist": s.get("assists") or 0,
        "xG": round(xg, 2) if xg is not None else None,
        "xA": round(s["expectedAssists"], 2) if s.get("expectedAssists") is not None else None,
        "tiri": s.get("totalShots"),
        "rating": s.get("rating"),
        # >0 ha segnato PIÙ di quanto le occasioni dicessero; <0 meno.
        "scarto_gol_xg": fuori,
    }


def _giudizio_scarto(av: dict, ruolo_ft: str) -> str | None:
    """Una riga di lettura dello scarto gol-xG, solo quando è significativo."""
    if not av or av.get("scarto_gol_xg") is None or ruolo_ft not in ("A", "C"):
        return None
    d, xg = av["scarto_gol_xg"], av["xG"]
    if xg is None or xg < 1.5:  # troppo poche occasioni per dire qualcosa
        return None
    if d >= 2.5:
        return (f"⚠️ ha segnato {d:+.1f} gol oltre le occasioni create "
                f"({av['gol']} gol contro {xg} xG nel {av['stagione']}): difficile da ripetere")
    if d <= -2.5:
        return (f"ha segnato {d:+.1f} gol rispetto alle occasioni "
                f"({av['gol']} gol contro {xg} xG nel {av['stagione']}): sotto-rendimento, può rimbalzare")
    return None


def arricchisci(players: list) -> list:
    """Aggiunge `contesto_allenatore` a ogni giocatore. Non solleva mai."""
    try:
        sys.path.insert(0, str(PROGETTO))
        from analizza import contesto_squadra, moltiplicatore  # riuso, non duplico

        squadre = _carica("squadre.json")
        allenatori = _carica("allenatori.json")
        try:
            idx = _indice_sofascore(_carica("giocatori.json"))
        except Exception:
            idx = {}

        cache: dict[str, dict] = {}
        for p in players:
            sq_ft = p.get("squadra")
            sq_nostra = SQUADRE.get(sq_ft, sq_ft)
            ruolo_ft = p.get("ruolo")

            if sq_nostra not in cache:
                cache[sq_nostra] = contesto_squadra(sq_nostra, squadre, allenatori) or {}
            ctx = cache[sq_nostra]

            molt, motivi = moltiplicatore(RUOLI.get(ruolo_ft, ruolo_ft), ctx)

            rec = idx.get((sq_nostra, _cognome_fantacalcio(p.get("nome", ""))))
            av = _avanzate(rec) if rec else None
            riga = _giudizio_scarto(av, ruolo_ft)
            if riga:
                motivi = list(motivi) + [riga]

            p["contesto_allenatore"] = {
                "moltiplicatore": round(molt, 3),
                "motivi": motivi,
                "allenatore": ctx.get("allenatore"),
                "modulo": ctx.get("modulo"),
                "gol_fatti_pg": ctx.get("gol_fatti_pg"),
                "gol_subiti_pg": ctx.get("gol_subiti_pg"),
                "gol_miglior_punta_media": ctx.get("gol_miglior_punta_media"),
                "avanzate": av,
                "avanzate_disponibili": av is not None,
            }
        return players
    except Exception as errore:  # mai far fallire la pipeline per un arricchimento
        print(f"contesto allenatore non applicato: {errore}", file=sys.stderr)
        return players
