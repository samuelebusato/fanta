"""Scarica i dati di tutti i giocatori di Serie A 2026/27 dalle API Sofascore.

Per ogni giocatore raccoglie:
  - anagrafica (nascita, altezza, piede, valore di mercato, ruolo, squadra)
  - statistiche delle ultime 3 stagioni PIU' quella in corso
  - se una stagione non l'ha giocata in Serie A, prende i dati dal campionato
    dove effettivamente giocava (richiesta esplicita dell'utente)

Salva in modo INCREMENTALE: se si interrompe, ripartendo non riscarica ciò che ha già.
"""
import json
import os
import sys
import time
from curl_cffi import requests

H = {
    'accept': '*/*',
    'accept-language': 'it-IT,it;q=0.9,en;q=0.8',
    'origin': 'https://www.sofascore.com',
    'referer': 'https://www.sofascore.com/',
}
IMP = 'chrome124'
BASE = 'https://api.sofascore.com/api/v1'
PAUSA = 0.35

SERIE_A_ID = 23
# Stagioni volute: la corrente + le 3 precedenti
STAGIONI_SERIE_A = {
    '26/27': 95836,
    '25/26': 76457,
    '24/25': 63515,
    '23/24': 52760,
}
ANNI_VOLUTI = set(STAGIONI_SERIE_A.keys())

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_DATI = os.path.join(OUT_DIR, 'dati', 'giocatori.json')

# I campi che servono davvero al fantacalcio, dai 115 disponibili.
CAMPI = [
    'rating', 'appearances', 'matchesStarted', 'minutesPlayed',
    'goals', 'assists', 'expectedGoals', 'expectedAssists',
    'totalShots', 'shotsOnTarget', 'goalConversionPercentage', 'bigChancesMissed',
    'bigChancesCreated', 'keyPasses', 'accuratePassesPercentage',
    'penaltyGoals', 'penaltiesTaken', 'penaltyWon',
    'yellowCards', 'redCards', 'yellowRedCards', 'fouls', 'wasFouled',
    'cleanSheet', 'goalsConceded', 'saves', 'savedShotsFromInsideTheBox',
    'tackles', 'interceptions', 'clearances', 'errorLeadToGoal',
    'successfulDribbles', 'totalDuelsWonPercentage', 'aerialDuelsWonPercentage',
    'touches', 'possessionLost', 'goalsAssistsSum', 'scoringFrequency',
]


def get(path, tentativi=3):
    for i in range(tentativi):
        try:
            r = requests.get(BASE + path, headers=H, impersonate=IMP, timeout=25)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                time.sleep(5 * (i + 1))
                continue
            return None
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def carica_esistenti():
    if os.path.exists(FILE_DATI):
        with open(FILE_DATI, encoding='utf-8') as f:
            return json.load(f)
    return {}


def salva(dati):
    os.makedirs(os.path.dirname(FILE_DATI), exist_ok=True)
    with open(FILE_DATI, 'w', encoding='utf-8') as f:
        json.dump(dati, f, ensure_ascii=False, indent=1)


def statistiche_giocatore(pid):
    """Ritorna {anno: {torneo, stats}} per gli anni voluti.

    Se in una stagione il giocatore NON era in Serie A, prende il torneo
    con piu' minuti giocati fra quelli in cui compare.
    """
    seasons = get(f'/player/{pid}/statistics/seasons')
    if not seasons:
        return {}
    candidati = {}  # anno -> lista di (tournament_id, season_id, nome_torneo)
    for t in seasons.get('uniqueTournamentSeasons', []):
        ut = t['uniqueTournament']
        for s in t.get('seasons', []):
            anno = s.get('year')
            if anno in ANNI_VOLUTI:
                candidati.setdefault(anno, []).append((ut['id'], s['id'], ut['name']))

    risultato = {}
    for anno, opzioni in candidati.items():
        # Serie A ha la precedenza; altrimenti si prende quello con piu' minuti.
        opzioni.sort(key=lambda o: 0 if o[0] == SERIE_A_ID else 1)
        migliore = None
        for tid, sid, nome in opzioni:
            time.sleep(PAUSA)
            st = get(f'/player/{pid}/unique-tournament/{tid}/season/{sid}/statistics/overall')
            if not st or 'statistics' not in st:
                continue
            s = st['statistics']
            minuti = s.get('minutesPlayed', 0) or 0
            if migliore is None or minuti > migliore[0]:
                migliore = (minuti, nome, {k: s.get(k) for k in CAMPI if k in s})
            if tid == SERIE_A_ID and minuti > 0:
                break  # Serie A trovata con minuti reali: basta
        if migliore:
            risultato[anno] = {'torneo': migliore[1], 'stats': migliore[2]}
    return risultato


def main():
    dati = carica_esistenti()
    print(f'gia\' in archivio: {len(dati)} giocatori', flush=True)

    st = get(f'/unique-tournament/{SERIE_A_ID}/season/{STAGIONI_SERIE_A["26/27"]}/standings/total')
    squadre = [(r['team']['id'], r['team']['name']) for r in st['standings'][0]['rows']]
    print(f'squadre: {len(squadre)}', flush=True)

    for idx, (team_id, team_nome) in enumerate(squadre, 1):
        time.sleep(PAUSA)
        rosa = get(f'/team/{team_id}/players')
        if not rosa:
            print(f'[{idx}/{len(squadre)}] {team_nome}: rosa non recuperata', flush=True)
            continue
        elenco = rosa.get('players', [])
        print(f'[{idx}/{len(squadre)}] {team_nome}: {len(elenco)} giocatori', flush=True)

        for p in elenco:
            pl = p['player']
            pid = str(pl['id'])
            if pid in dati:
                continue

            time.sleep(PAUSA)
            det = get(f'/player/{pid}')
            anag = (det or {}).get('player', {})

            record = {
                'id': pl['id'],
                'nome': pl.get('name'),
                'slug': pl.get('slug'),
                'squadra': team_nome,
                'squadra_id': team_id,
                'ruolo': anag.get('position') or pl.get('position'),
                'maglia': anag.get('jerseyNumber'),
                'nascita_ts': anag.get('dateOfBirthTimestamp'),
                'altezza': anag.get('height'),
                'piede': anag.get('preferredFoot'),
                'valore_mercato': anag.get('proposedMarketValue'),
                'nazionalita': (anag.get('country') or {}).get('name'),
                'stagioni': statistiche_giocatore(pid),
            }
            dati[pid] = record
            print(f'    {record["nome"]:28} {record["ruolo"] or "?"} | stagioni: {list(record["stagioni"].keys())}', flush=True)

        salva(dati)  # salvataggio dopo ogni squadra, per non perdere il lavoro

    salva(dati)
    print(f'\nFATTO: {len(dati)} giocatori in {FILE_DATI}', flush=True)


if __name__ == '__main__':
    main()
