# fishertiger — codice di terze parti, vendorizzato

Questa cartella **non è nostra**: è una copia di un progetto esterno, inserita qui
dentro (*vendorizzata*) e modificata. Serve come **motore di proiezioni e di asta**
per il progetto `fantacalcio-asta-2026-27`.

## Provenienza

| | |
|---|---|
| Origine | https://github.com/Zannael/fishertiger |
| Commit | `64145d85f25ba88144b4bf54d12496beb4a1ffda` (`64145d8`, 2026-09-03, *"Fix auction simulation report props"*) |
| Copiata il | 2026-09-03 |
| Licenza codice | **MIT** (vedi `LICENSE`) |
| Licenza dati in `data/raw/` | **CC BY 4.0** (vedi `DATA_LICENSE.md`) — l'attribuzione va mantenuta |

## Perché senza `.git`

È stata copiata **senza la sua cartella `.git`**, di proposito.

`Projects/fantacalcio-asta-2026-27` è già un repo autonomo, agganciato al brain come
submodule. Clonarci dentro un secondo repo git avrebbe creato un repo **annidato** —
l'errore che [`CLAUDE.md`](../../../CLAUDE.md) §4.1 e §7 vietano esplicitamente.

E soprattutto: **noi questo codice lo modifichiamo**. Le patch qui sotto devono vivere
nel repo `fanta`, versionate insieme al resto del progetto. In un submodule di terze
parti non potremmo committarle.

Il costo accettato: **non si aggiorna più con `git pull`**. Per allinearsi a una
versione nuova va rifatta la copia e riapplicate le modifiche elencate qui.

## Modifiche applicate (da riapplicare in caso di aggiornamento)

### 1. `advisor/pipeline.py` — `NaN` in `gerarchia_portiere`

**Sintomo**: la pipeline calcolava tutto e poi moriva alla scrittura del JSON con
`ValueError: Out of range float values are not JSON compliant: nan`.

**Causa**: in `titolari.csv` la colonna `gerarchia_portiere` è **vuota per tutti i
non-portieri**. pandas la legge come `NaN` (float), che arriva intatto al `json.dump`
fatto con `allow_nan=False`. Erano 363 valori, **tutti** in quel campo.

**Perché è un difetto loro e non nostro**: fallisce identico con il **loro** profilo di
default, non solo col nostro.

**Correzione** (dopo la riga `hierarchy = starter_entry.iloc[0].gerarchia_portiere ...`):

```python
hierarchy = None if hierarchy is None or pd.isna(hierarchy) else hierarchy
```

Corretto alla radice invece di disattivare la guardia: `allow_nan=True` avrebbe prodotto
un `NaN` letterale, che **non è JSON valido** e che la loro stessa UI avrebbe rifiutato.

### 2. `config/default_profile.json` — profilo della nostra lega

Il profilo di default è stato **sostituito** con quello della lega (500 crediti,
10 squadre). L'originale è conservato in `config/default_profile.originale.json`.

Motivo: il `select` dei profili nella UI è un componente React controllato e non
accetta la selezione via script; rendere il nostro profilo quello predefinito era
la via più semplice e stabile. Lo stesso profilo sta anche in
`config/profiles/lega_2026_27.json`, dove l'API lo espone (`--profiles-dir` punta a
`config/profiles`, **non** a `config/`).

### 3. Contesto allenatore + statistiche avanzate (aggiunta nostra)

fishertiger proietta il rendimento individuale ma **non sa chi allena**. In una
stagione con Sarri all'Atalanta, Gasperini alla Roma, Allegri al Napoli e Spalletti
alla Juve, quello è il fattore più pesante. Aggiunto quindi:

**File nuovo** — `advisor/contesto_allenatore.py`: riusa `contesto_squadra()` e
`moltiplicatore()` di `../analizza.py` (importati, **non** duplicati) e incrocia con
`../dati/giocatori.json` (Sofascore) per xG, xA e scarto gol−xG. Assorbe ogni errore:
un arricchimento non deve poter far fallire la generazione dei dati.

**Aggancio in `advisor/pipeline.py`** — tre righe subito prima di `payload = {...}`:

```python
    # NOSTRO (vedi ../FONTE.md): contesto allenatore + statistiche avanzate.
    from .contesto_allenatore import arricchisci as _arricchisci_contesto
    players = _arricchisci_contesto(players)
```

**UI** — in `web/src/auction-advice.jsx` il componente `ContestoAllenatore` e la firma
`AdviceDetail({ advice, player })`; nei due chiamanti (`web/src/views/auction.jsx` e
`web/src/views/players.jsx`) si passa `player={player}`.

⚠️ **Trappola incontrata**: nel **testo JSX grezzo** le sequenze `·` **non** sono
escape — vengono stampate alla lettera. Valgono solo dentro stringhe o template
literal. Usare i caratteri veri (`·`, `—`).

Copertura risultante: **531 giocatori su 531** hanno il contesto allenatore, **285**
anche le statistiche avanzate (solo le squadre scaricate da Sofascore prima del blocco).

## Cosa NON è versionato

`.venv/` e `web/node_modules/` sono in `.gitignore`. Si ricreano con:

```bash
python -m venv .venv && ./.venv/Scripts/pip install -r requirements.txt
cd web && npm install
```
