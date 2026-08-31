# Fantacalcio Serie A — Asta 2026/27

> ⚠️ **Deroga esplicita ai framework, autorizzata dall'utente il 2026-08-31.**
> Questo **non è un progetto software**: è un lavoro di raccolta dati e analisi per preparare un'asta. Su richiesta esplicita dell'utente **non si applicano** [`Rule/regole-sviluppo-sicuro.md`](../../Rule/regole-sviluppo-sicuro.md) né [`Rule/regole-sviluppo-progetto.md`](../../Rule/regole-sviluppo-progetto.md): niente `History.md`/`Architecture.md`/`threat-model.md`, niente repo separato, niente submodule.
> **La deroga vale solo per questo progetto.** Non è un precedente per progetti software.

---

## Le regole della lega (confermate dall'utente il 2026-08-31)

| | |
|---|---|
| **Formato** | **Classico** — quattro ruoli: P, D, C, A |
| **Partecipanti** | 10 |
| **Crediti** | **500** a testa |
| **Modificatore difesa** | ✅ **attivo** |
| **Asta** | Entro pochi giorni dal 2026-08-31 |

**Cosa implicano, in concreto:**

- 🔑 **Il modificatore difesa cambia la strategia più di ogni altra regola.** Non conta il singolo difensore, conta il **reparto**: conviene concentrare 3-4 difensori della stessa squadra solida, perché il modificatore premia la media dei voti della difesa schierata. Alza il valore dei difensori di squadre che subiscono poco, e lo alza **più** del loro potenziale di bonus.
- **10 squadre da 25 giocatori = 250 giocatori assegnati** su circa 500 disponibili. Metà del listone resta fuori: la profondità della rosa conta meno che in una lega da 8, ma i titolari veri finiscono tutti.
- **500 crediti / 25 giocatori = 20 di media**, ma la spesa reale è a coda lunga: pochi giocatori sopra i 60 e una massa di riempitivi da 1-3.

## Perimetro del lavoro (richiesto dall'utente)

1. Dati delle ultime 3 stagioni per ogni giocatore — anagrafica, infortuni, cartellini, gol, assist, xG, xA, over/under-performance, posizione media, ruolo, presenze, minuti, titolarità.
2. Dati delle ultime 3 stagioni per ogni allenatore — gol fatti/subiti, tiri prodotti, altezza della difesa, moduli, posizioni medie per ruolo, falli, stile di gioco.
3. Consigli d'asta 2026/27 e rassegna stampa per giocatore: quanto "interessa" ai giornali e che idea se ne sono fatta.
4. Rassegna stampa per squadra: che campionato ci si aspetta (scudetto / Europa / salvezza).
5. **Il deliverable**: lista di giocatori raccomandati con **stima in crediti**, un **commento** e i dati che la sostengono.

🔑 **Il vincolo che tiene insieme tutto** (parole dell'utente): *i dati devono legarsi*. Un attaccante con pochi gol in una squadra che produceva poco, che passa a un allenatore le cui punte segnano molto, **sale**; un attaccante con cattiva conversione tiri-gol in una squadra il cui allenatore non produce gol, **scende**.

## ⚠️ Vincolo tecnico verificato il 2026-08-31

Le fonti dati automatizzabili sono in gran parte chiuse. Verificato direttamente, non supposto:

| Fonte | Esito |
|---|---|
| **Sofascore API** | ❌ **403 Forbidden** — l'approccio usato da [MarketPriceRegressor](https://github.com/MatteoMorellini/MarketPriceRegressor) (2024) non funziona più |
| **FBref** | ❌ **403 Forbidden** |
| **Understat** | ⚠️ risponde 200, ma **non serve più `playersData` nell'HTML**: i dati non sono estraibili con un fetch semplice |

**Conseguenza sulla strategia**: costruire uno scraper affidabile richiederebbe giorni che l'asta non concede. Si procede con ricerca mirata su fonti aggregate e si concentra la profondità sui giocatori che l'asta decide davvero — non su tutti i 500 del listone.

## Struttura

```
dati/          raccolta grezza (squadre, allenatori, giocatori)
analisi/       elaborazioni e incroci
LISTA.md       il deliverable: consigliati, crediti, commento
```
