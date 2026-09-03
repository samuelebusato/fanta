# -*- coding: utf-8 -*-
"""Genera LISTA.md: la board d'asta, da leggere al volo mentre si chiama un giocatore.

Fonte unica: `fishertiger/data/processed/<profilo>/<stagione>/auction_data.json`,
che dopo la nostra patch contiene **sia** le proiezioni di fishertiger **sia** il
blocco `contesto_allenatore` (moltiplicatore, motivi, xG/xA). Vedi
`fishertiger/FONTE.md`.

Si rigenera con:
    python genera_lista.py
"""

import datetime
import io
import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
DATI = os.path.join(DIR, "fishertiger", "data", "processed", "lega-2026-27", "2026-27")
FONTE = os.path.join(DATI, "auction_data.json")
USCITA = os.path.join(DIR, "LISTA.md")

RUOLI = [("P", "Portieri"), ("D", "Difensori"), ("C", "Centrocampisti"), ("A", "Attaccanti")]
PER_RUOLO = 26


def valore_atteso(p):
    pr = p["proiezione"]
    return pr["fantavoto"] * pr["p_gioca"]


def carica():
    with open(FONTE, encoding="utf-8") as f:
        return json.load(f)


def battitori(dati):
    """(squadra, nome) dei battitori numero 1, per tipo."""
    rigori, piazzati = set(), set()
    for blocco in dati.get("set_pieces", []):
        for t in blocco.get("takers", []):
            if t.get("priorita") != 1:
                continue
            chiave = (blocco["squadra"], t["nome"])
            if blocco["tipo"] == "RIGORI":
                rigori.add(chiave)
            else:
                piazzati.add(chiave)
    return rigori, piazzati


def riga(p, rigori, piazzati):
    pr = p["proiezione"]
    c = p.get("contesto_allenatore") or {}
    av = c.get("avanzate") or {}
    chiave = (p["squadra"], p["nome"])
    scarto = av.get("scarto_gol_xg")
    molt = c.get("moltiplicatore")
    return "| **%.2f** | %.2f | %.2f | %d | %s | %s | %s | %s | %s | %s | %s | %s |" % (
        valore_atteso(p),
        pr["fantavoto"],
        pr["p_gioca"],
        p["quotazioni"]["attuale"],
        p["nome"],
        p["squadra"],
        (p.get("guida_asta_fascia") or "-").replace("_", " "),
        p["disponibilita"]["status"][:12].capitalize(),
        "**R**" if chiave in rigori else "",
        "p" if chiave in piazzati else "",
        ("**%+d%%**" % round((molt - 1) * 100)) if molt is not None else "-",
        ("%+.1f" % scarto) if scarto is not None else "-",
    )


def main():
    dati = carica()
    giocatori = [p for p in dati["players"] if p["disponibilita"]["status"] != "NON_CLASSIFICATO"]
    rigori, piazzati = battitori(dati)

    out = io.StringIO()
    w = out.write

    w("# LISTA — Asta Fantacalcio 2026/27\n\n")
    w("> Generata il %s da `genera_lista.py`. **Non modificare a mano**: si rigenera.\n\n"
      % datetime.date.today().isoformat())

    w("## Regole\n\n")
    w("Classico · **10 squadre** · **500 crediti** · rosa **25** (P3 D8 C8 A6) · "
      "**modificatore difesa attivo**: servono almeno 4 difensori, conta la media del "
      "**voto puro** di portiere + migliori 3 difensori (+1 da 6.0, +2 da 6.5, +3 da 7.0).\n\n")
    w("Budget di partenza: **A 250 · C 125 · D 90 · P 35**.\n\n")

    w("## Come si legge\n\n")
    w("| Colonna | Significato |\n|---|---|\n")
    w("| **VA** | valore atteso = fantavoto × probabilità di giocare. **È la colonna su cui ordinare.** |\n")
    w("| FV / pg | fantavoto proiettato / probabilità di giocare |\n")
    w("| Qt.A | quotazione attuale del listone |\n")
    w("| Fascia | guida d'asta SosFanta |\n")
    w("| **R** / p | rigorista designato n.1 / batte punizioni o corner |\n")
    w("| **xAll** | correzione per contesto allenatore (+ aiuta, − penalizza) |\n")
    w("| gol−xG | scarto fra gol segnati e occasioni create nel 25/26. **Molto positivo = difficile da ripetere.** |\n\n")

    w("⚠️ **I dati di formazione sono del 22-23/08/2026**, cioè *precedenti alla chiusura "
      "del mercato*. Su un nome caldo verifica i trasferimenti di fine mercato prima di puntare.\n\n")

    # --- i due estratti che servono davvero, prima delle tabelle lunghe ---
    def scarto_di(p):
        av = (p.get("contesto_allenatore") or {}).get("avanzate") or {}
        return av.get("scarto_gol_xg") or 0.0  # la chiave puo' esistere valorizzata None

    trappole = [p for p in giocatori
                if (p.get("contesto_allenatore") or {}).get("moltiplicatore") is not None
                and p["contesto_allenatore"]["moltiplicatore"] < 0.95
                and scarto_di(p) >= 2.0]
    trappole.sort(key=lambda p: -p["quotazioni"]["attuale"])
    if trappole:
        w("## 🔴 Trappole — contesto sfavorevole *e* gol sopra le occasioni\n\n")
        w("Due segnali indipendenti che puntano nella stessa direzione: il sistema non li aiuta "
          "e il rendimento passato era già oltre il merito.\n\n")
        for p in trappole[:8]:
            c = p["contesto_allenatore"]
            av = c["avanzate"]
            w("- **%s** (%s, Qt %d) — contesto **%+d%%** con %s, e %d gol su %s xG (**%+.1f**)\n"
              % (p["nome"], p["squadra"], p["quotazioni"]["attuale"],
                 round((c["moltiplicatore"] - 1) * 100), c["allenatore"],
                 av["gol"], av["xG"], av["scarto_gol_xg"]))
        w("\n")

    occasioni = [p for p in giocatori
                 if p["quotazioni"]["attuale"] <= 15
                 and (p.get("contesto_allenatore") or {}).get("moltiplicatore", 1) >= 1.0]
    occasioni.sort(key=valore_atteso, reverse=True)
    if occasioni:
        w("## 🟢 Occasioni — quotazione ≤ 15 e contesto non sfavorevole\n\n")
        w("| VA | Qt.A | Nome | Squadra | R | xAll |\n|---:|---:|---|---|:-:|---:|\n")
        for p in occasioni[:14]:
            c = p["contesto_allenatore"]
            w("| **%.2f** | %d | %s | %s | %s | %+d%% |\n"
              % (valore_atteso(p), p["quotazioni"]["attuale"], p["nome"], p["squadra"],
                 "**R**" if (p["squadra"], p["nome"]) in rigori else "",
                 round((c.get("moltiplicatore", 1) - 1) * 100)))
        w("\n")

    intestazione = ("| VA | FV | pg | Qt.A | Nome | Squadra | Fascia | Status | R | p | xAll | gol−xG |\n"
                    "|---:|---:|---:|---:|---|---|---|---|:-:|:-:|---:|---:|\n")
    for ruolo, etichetta in RUOLI:
        gruppo = [p for p in giocatori if p["ruolo"] == ruolo]
        gruppo.sort(key=valore_atteso, reverse=True)
        w("## %s\n\n" % etichetta)
        w(intestazione)
        for p in gruppo[:PER_RUOLO]:
            w(riga(p, rigori, piazzati) + "\n")
        w("\n")

    testo = out.getvalue()
    with open(USCITA, "w", encoding="utf-8") as f:
        f.write(testo)

    con_contesto = sum(1 for p in giocatori if p.get("contesto_allenatore"))
    con_avanzate = sum(1 for p in giocatori if (p.get("contesto_allenatore") or {}).get("avanzate"))
    print("LISTA.md: %d giocatori | contesto %d | avanzate %d | trappole %d | occasioni %d"
          % (len(giocatori), con_contesto, con_avanzate, len(trappole), len(occasioni)))


if __name__ == "__main__":
    main()
