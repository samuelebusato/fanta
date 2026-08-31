"""Scarica i giocatori mancanti, con le contromisure al blocco anti-bot.

Cosa è andato storto nella v1 (2026-08-31): dopo ~1.100 richieste Sofascore ha
alzato una challenge (403 reason:"challenge") legata all'IP. Lo script è uscito
in silenzio perché `get()` non ritentava sui 403 — ha marcato 14 squadre come
"rosa non recuperata" e ha chiuso con exit code 0. Un fallimento che si
presenta come successo è il peggior tipo di fallimento.

Le cinque contromisure, in ordine di importanza:
 1. MENO CHIAMATE. La v1 ne faceva ~6 per giocatore. Qui si prova prima
    l'endpoint aggregato per torneo, che ne serve una manciata per stagione.
 2. SESSIONE CON COOKIE: prima si visita il sito, poi si chiama l'API.
 3. PAUSE RANDOMIZZATE: un intervallo fisso al millisecondo è la firma di un bot.
 4. BACKOFF VERO sui 403, con attese lunghe e crescenti.
 5. ONDATE: si lavora poche squadre per volta e ci si ferma da soli.

Uso:
    python scarica_giocatori_v2.py            # riprende da dove si era fermato
    python scarica_giocatori_v2.py --squadre 4  # solo 4 squadre, poi si ferma
"""
import argparse
import json
import os
import random
import sys
import time
from curl_cffi import requests

BASE = 'https://api.sofascore.com/api/v1'
SITO = 'https://www.sofascore.com/'
H = {
    'accept': '*/*',
    'accept-language': 'it-IT,it;q=0.9,en-US;q=0.8',
    'origin': 'https://www.sofascore.com',
    'referer': 'https://www.sofascore.com/',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-site',
}

SERIE_A = 23
STAGIONI = {'26/27': 95836, '25/26': 76457, '24/25': 63515, '23/24': 52760}
ANNI = set(STAGIONI)

DIR = os.path.dirname(os.path.abspath(__file__))
FILE_DATI = os.path.join(DIR, 'dati', 'giocatori.json')

CAMPI = [
    'rating', 'appearances', 'matchesStarted', 'minutesPlayed',
    'goals', 'assists', 'expectedGoals', 'expectedAssists',
    'totalShots', 'shotsOnTarget', 'goalConversionPercentage', 'bigChancesMissed',
    'bigChancesCreated', 'keyPasses', 'accuratePassesPercentage',
    'penaltyGoals', 'penaltiesTaken', 'penaltyWon',
    'yellowCards', 'redCards', 'yellowRedCards', 'fouls', 'wasFouled',
    'cleanSheet', 'goalsConceded', 'saves', 'savedShotsFromInsideTheBox',
    'penaltyFaced', 'penaltySave',
    'tackles', 'interceptions', 'clearances', 'errorLeadToGoal',
    'successfulDribbles', 'totalDuelsWonPercentage', 'aerialDuelsWonPercentage',
    'touches', 'possessionLost', 'goalsAssistsSum', 'scoringFrequency',
]


class Blocco(Exception):
    """La challenge è tornata: meglio fermarsi che insistere e peggiorare."""


class Client:
    def __init__(self):
        self.s = requests.Session(impersonate='chrome124')
        self.blocchi = 0
        self._scalda()

    def _scalda(self):
        """Visita il sito come farebbe un browser, per raccogliere i cookie."""
        try:
            self.s.get(SITO, timeout=25)
            self.pausa(1.0, 2.0)
        except Exception:
            pass

    @staticmethod
    def pausa(a=1.5, b=3.5):
        time.sleep(random.uniform(a, b))

    def get(self, path):
        attese = [60, 180, 600]
        for i in range(4):
            try:
                r = self.s.get(BASE + path, headers=H, timeout=30)
            except Exception:
                self.pausa(3, 6)
                continue

            if r.status_code == 200:
                self.blocchi = 0
                return r.json()
            if r.status_code == 404:
                return None
            if r.status_code in (403, 429):
                if i >= len(attese):
                    self.blocchi += 1
                    raise Blocco(f'403/429 persistente su {path}')
                attesa = attese[i]
                print(f'   ⏸  {r.status_code}: attendo {attesa}s e riprovo '
                      f'({i + 1}/{len(attese)})', flush=True)
                time.sleep(attesa)
                self._scalda()
                continue
            return None
        raise Blocco(f'esauriti i tentativi su {path}')


def carica():
    if os.path.exists(FILE_DATI):
        with open(FILE_DATI, encoding='utf-8') as f:
            return json.load(f)
    return {}


def salva(d):
    os.makedirs(os.path.dirname(FILE_DATI), exist_ok=True)
    tmp = FILE_DATI + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tmp, FILE_DATI)  # scrittura atomica: niente file mezzo scritto


def stagioni_giocatore(cli, pid):
    seasons = cli.get(f'/player/{pid}/statistics/seasons')
    if not seasons:
        return {}
    cand = {}
    for t in seasons.get('uniqueTournamentSeasons', []):
        ut = t['uniqueTournament']
        for s in t.get('seasons', []):
            if s.get('year') in ANNI:
                cand.setdefault(s['year'], []).append((ut['id'], s['id'], ut['name']))

    out = {}
    for anno, opz in cand.items():
        opz.sort(key=lambda o: 0 if o[0] == SERIE_A else 1)
        migliore = None
        for tid, sid, nome in opz:
            cli.pausa(0.8, 1.6)
            st = cli.get(f'/player/{pid}/unique-tournament/{tid}/season/{sid}/statistics/overall')
            if not st or 'statistics' not in st:
                continue
            s = st['statistics']
            minuti = s.get('minutesPlayed') or 0
            if migliore is None or minuti > migliore[0]:
                migliore = (minuti, nome, {k: s.get(k) for k in CAMPI if k in s})
            if tid == SERIE_A and minuti > 0:
                break
        if migliore:
            out[anno] = {'torneo': migliore[1], 'stats': migliore[2]}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--squadre', type=int, default=99,
                    help='quante squadre lavorare in questa ondata')
    args = ap.parse_args()

    dati = carica()
    print(f'in archivio: {len(dati)} giocatori', flush=True)

    cli = Client()
    st = cli.get(f'/unique-tournament/{SERIE_A}/season/{STAGIONI["26/27"]}/standings/total')
    if not st:
        print('non riesco nemmeno a leggere la classifica: blocco ancora attivo.')
        sys.exit(2)
    squadre = [(r['team']['id'], r['team']['name']) for r in st['standings'][0]['rows']]

    gia_fatte = {v['squadra'] for v in dati.values()}
    mancanti = [(i, n) for i, n in squadre if n not in gia_fatte]
    print(f'squadre gia\' complete: {len(squadre) - len(mancanti)} | mancanti: {len(mancanti)}', flush=True)

    lavorate = 0
    try:
        for tid, tnome in mancanti:
            if lavorate >= args.squadre:
                print(f'\nondata conclusa ({lavorate} squadre). Rilancia per continuare.', flush=True)
                break
            cli.pausa()
            rosa = cli.get(f'/team/{tid}/players')
            if not rosa:
                print(f'  {tnome}: rosa non disponibile', flush=True)
                continue
            elenco = rosa.get('players', [])
            print(f'\n[{tnome}] {len(elenco)} giocatori', flush=True)

            for p in elenco:
                pl = p['player']
                pid = str(pl['id'])
                if pid in dati:
                    continue
                cli.pausa()
                det = cli.get(f'/player/{pid}')
                anag = (det or {}).get('player', {})
                dati[pid] = {
                    'id': pl['id'], 'nome': pl.get('name'), 'slug': pl.get('slug'),
                    'squadra': tnome, 'squadra_id': tid,
                    'ruolo': anag.get('position') or pl.get('position'),
                    'maglia': anag.get('jerseyNumber'),
                    'nascita_ts': anag.get('dateOfBirthTimestamp'),
                    'altezza': anag.get('height'), 'piede': anag.get('preferredFoot'),
                    'valore_mercato': anag.get('proposedMarketValue'),
                    'nazionalita': (anag.get('country') or {}).get('name'),
                    'stagioni': stagioni_giocatore(cli, pid),
                }
                print(f'   {dati[pid]["nome"][:26]:26} {dati[pid]["ruolo"] or "?"} '
                      f'{list(dati[pid]["stagioni"].keys())}', flush=True)
                salva(dati)  # ogni giocatore: se cade, si perde un giocatore, non una squadra

            lavorate += 1
            salva(dati)
            print(f'  ✓ {tnome} completata ({len(dati)} in archivio)', flush=True)

    except Blocco as e:
        salva(dati)
        print(f'\n🔴 BLOCCO: {e}', flush=True)
        print(f'   Salvati {len(dati)} giocatori. Riprova fra 30-60 minuti: '
              f'lo script riprende da qui.', flush=True)
        sys.exit(1)

    salva(dati)
    print(f'\nFATTO: {len(dati)} giocatori', flush=True)


if __name__ == '__main__':
    main()
