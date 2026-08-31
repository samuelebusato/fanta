"""Ricognizione: cosa espone Sofascore su squadre e allenatori."""
import json
from curl_cffi import requests

H = {'accept': '*/*', 'origin': 'https://www.sofascore.com', 'referer': 'https://www.sofascore.com/'}
BASE = 'https://api.sofascore.com/api/v1'


def get(path):
    r = requests.get(BASE + path, headers=H, impersonate='chrome124', timeout=25)
    return r.json() if r.status_code == 200 else None


SERIE_A, S2627, S2526 = 23, 95836, 76457

st = get(f'/unique-tournament/{SERIE_A}/season/{S2627}/standings/total')
squadre = [(r['team']['id'], r['team']['name']) for r in st['standings'][0]['rows']]
tid, tnome = squadre[0]
print(f'squadra di prova: {tnome} (id {tid})\n')

print('=' * 60)
print('1. DETTAGLIO SQUADRA (include allenatore?)')
d = get(f'/team/{tid}')
if d:
    t = d['team']
    print('   chiavi disponibili:', ', '.join(sorted(t.keys()))[:400])
    mgr = t.get('manager')
    if mgr:
        print(f"   ALLENATORE: {mgr.get('name')} | id {mgr.get('id')} | naz. {(mgr.get('country') or {}).get('name')}")

print('\n2. PROFILO ALLENATORE')
if d and d['team'].get('manager'):
    mid = d['team']['manager']['id']
    m = get(f'/manager/{mid}')
    if m:
        mm = m['manager']
        print('   chiavi:', ', '.join(sorted(mm.keys()))[:400])
        for k in ['name', 'nationality', 'preferredFormation', 'dateOfBirthTimestamp']:
            if k in mm:
                print(f'      {k} = {mm[k]}')
        if 'performance' in mm:
            print(f"      performance = {mm['performance']}")
    # storico squadre allenate
    car = get(f'/manager/{mid}/career-history')
    if car:
        print('   CARRIERA (ultime voci):')
        for c in (car.get('careerHistory') or [])[:6]:
            team = (c.get('team') or {}).get('name')
            print(f"      {team} | da {c.get('startTimestamp')} a {c.get('endTimestamp')} | {c.get('appearances')} panchine, {c.get('wins')}V {c.get('draws')}N {c.get('losses')}P")

print('\n3. STATISTICHE DI SQUADRA PER STAGIONE')
ts = get(f'/team/{tid}/unique-tournament/{SERIE_A}/season/{S2526}/statistics/overall')
if ts:
    s = ts.get('statistics', {})
    print(f'   campi disponibili: {len(s)}')
    interessanti = ['goalsScored', 'goalsConceded', 'shots', 'shotsOnTarget', 'bigChancesCreated',
                    'cleanSheets', 'averageBallPossession', 'fouls', 'yellowCards',
                    'accuratePassesPercentage', 'ballRecovery', 'tacklesWon', 'matches']
    for k in interessanti:
        if k in s:
            print(f'      {k:30} = {s[k]}')

print('\n4. MODULI USATI DALLA SQUADRA')
lu = get(f'/team/{tid}/unique-tournament/{SERIE_A}/season/{S2526}/top-players/overall')
print('   top-players:', 'presente' if lu else 'assente')
