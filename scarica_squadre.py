"""Scarica squadre e allenatori di Serie A 2026/27, con le stagioni precedenti.

Per ogni squadra: statistiche delle ultime 3 stagioni + quella corrente.
Per ogni allenatore: modulo preferito, performance in carriera, storico squadre.

🔑 Il pezzo che serve alla richiesta dell'utente — "le punte di questo allenatore
segnano?" — si ottiene incrociando la carriera dell'allenatore con le statistiche
della squadra che allenava in quella stagione. Qui si raccolgono i mattoni;
l'incrocio si fa in analisi.
"""
import json
import os
import time
from curl_cffi import requests

H = {
    'accept': '*/*',
    'accept-language': 'it-IT,it;q=0.9,en;q=0.8',
    'origin': 'https://www.sofascore.com',
    'referer': 'https://www.sofascore.com/',
}
BASE = 'https://api.sofascore.com/api/v1'
PAUSA = 0.6  # generosa: gira in parallelo allo scraper dei giocatori

SERIE_A = 23
STAGIONI = {'26/27': 95836, '25/26': 76457, '24/25': 63515, '23/24': 52760}

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dati')

CAMPI_SQUADRA = [
    'matches', 'goalsScored', 'goalsConceded', 'shots', 'shotsOnTarget',
    'bigChancesCreated', 'bigChancesMissed', 'cleanSheets', 'averageBallPossession',
    'fouls', 'yellowCards', 'redCards', 'accuratePassesPercentage',
    'ballRecovery', 'tacklesWon', 'interceptions', 'clearances',
    'corners', 'offsides', 'penaltyGoals', 'penaltiesTaken',
    'accurateLongBallsPercentage', 'errorsLeadingToGoal',
]


def get(path, tentativi=3):
    for i in range(tentativi):
        try:
            r = requests.get(BASE + path, headers=H, impersonate='chrome124', timeout=25)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
            if r.status_code == 429:
                time.sleep(6 * (i + 1))
                continue
            return None
        except Exception:
            time.sleep(2 * (i + 1))
    return None


def main():
    os.makedirs(OUT, exist_ok=True)
    risultato = {}

    st = get(f'/unique-tournament/{SERIE_A}/season/{STAGIONI["26/27"]}/standings/total')
    squadre = [(r['team']['id'], r['team']['name']) for r in st['standings'][0]['rows']]
    print(f'squadre in Serie A 26/27: {len(squadre)}', flush=True)

    for tid, tnome in squadre:
        time.sleep(PAUSA)
        det = get(f'/team/{tid}')
        team = (det or {}).get('team', {})
        mgr = team.get('manager') or {}

        rec = {
            'id': tid,
            'nome': tnome,
            'stadio': (team.get('venue') or {}).get('stadium', {}).get('name'),
            'allenatore': None,
            'stagioni': {},
        }

        if mgr.get('id'):
            time.sleep(PAUSA)
            m = get(f"/manager/{mgr['id']}")
            mm = (m or {}).get('manager', {})
            time.sleep(PAUSA)
            car = get(f"/manager/{mgr['id']}/career-history")
            carriera = []
            for c in ((car or {}).get('careerHistory') or []):
                carriera.append({
                    'squadra': (c.get('team') or {}).get('name'),
                    'squadra_id': (c.get('team') or {}).get('id'),
                    'dal': c.get('startTimestamp'),
                    'al': c.get('endTimestamp'),
                })
            rec['allenatore'] = {
                'id': mgr['id'],
                'nome': mgr.get('name'),
                'nazionalita': mm.get('nationality'),
                'modulo_preferito': mm.get('preferredFormation'),
                'nascita_ts': mm.get('dateOfBirthTimestamp'),
                'performance_carriera': mm.get('performance'),
                'carriera': carriera,
            }

        for anno, sid in STAGIONI.items():
            time.sleep(PAUSA)
            ts = get(f'/team/{tid}/unique-tournament/{SERIE_A}/season/{sid}/statistics/overall')
            s = (ts or {}).get('statistics')
            if s:
                rec['stagioni'][anno] = {k: s.get(k) for k in CAMPI_SQUADRA if k in s}

        risultato[str(tid)] = rec
        all_nome = (rec['allenatore'] or {}).get('nome', '—')
        modulo = (rec['allenatore'] or {}).get('modulo_preferito', '—')
        print(f'  {tnome:22} all. {all_nome:24} modulo {modulo:8} stagioni {list(rec["stagioni"].keys())}', flush=True)

        with open(os.path.join(OUT, 'squadre.json'), 'w', encoding='utf-8') as f:
            json.dump(risultato, f, ensure_ascii=False, indent=1)

    print(f'\nFATTO: {len(risultato)} squadre', flush=True)


if __name__ == '__main__':
    main()
