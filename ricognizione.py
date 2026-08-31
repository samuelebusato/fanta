"""Ricognizione: verifica quali dati Sofascore espone davvero, prima di costruire lo scraper.

Il 403 del primo tentativo non era l'API chiusa: era fingerprinting TLS.
curl_cffi con impersonate='chrome124' lo supera.
"""
import json
from curl_cffi import requests

H = {
    'accept': '*/*',
    'accept-language': 'it-IT,it;q=0.9,en;q=0.8',
    'origin': 'https://www.sofascore.com',
    'referer': 'https://www.sofascore.com/',
}
IMP = 'chrome124'
BASE = 'https://api.sofascore.com/api/v1'


def get(path):
    r = requests.get(BASE + path, headers=H, impersonate=IMP, timeout=25)
    if r.status_code != 200:
        return None
    return r.json()


print('=' * 70)
print('1. TORNEO')
j = get('/search/all?q=Serie%20A&page=0')
tid = None
for res in (j or {}).get('results', []):
    e = res.get('entity', {})
    if e.get('category', {}).get('name') == 'Italy' or 'Italy' in str(e.get('category', {})):
        tid = e.get('id')
        print(f"   trovato: {e.get('name')} (Italia) -> id {tid}")
        break
if not tid:
    e = (j or {}).get('results', [{}])[0].get('entity', {})
    tid = e.get('id')
    print(f"   primo risultato: {e.get('name')} -> id {tid}")

print('\n2. STAGIONI DISPONIBILI')
seasons = get(f'/unique-tournament/{tid}/seasons')
slist = (seasons or {}).get('seasons', [])[:5]
for s in slist:
    print(f"   {s['year']:10} -> season id {s['id']}   ({s['name']})")

if not slist:
    raise SystemExit('nessuna stagione trovata')

sid_corrente = slist[0]['id']

print('\n3. SQUADRE (stagione corrente)')
st = get(f'/unique-tournament/{tid}/season/{sid_corrente}/standings/total')
teams = []
if st:
    for row in st['standings'][0]['rows']:
        teams.append((row['team']['id'], row['team']['name']))
    print(f"   {len(teams)} squadre: " + ', '.join(t[1] for t in teams[:6]) + ' ...')

print('\n4. ROSA (prima squadra)')
if teams:
    pl = get(f'/team/{teams[0][0]}/players')
    players = [(p['player']['id'], p['player']['name'], p['player'].get('position')) for p in (pl or {}).get('players', [])]
    print(f"   {teams[0][1]}: {len(players)} giocatori")
    for p in players[:5]:
        print(f"      {p[1]} ({p[2]}) id={p[0]}")

print('\n5. STATISTICHE DI UN GIOCATORE')
if teams and players:
    pid = players[0][0]
    st_seasons = get(f'/player/{pid}/statistics/seasons')
    tornei = (st_seasons or {}).get('uniqueTournamentSeasons', [])
    print(f"   {players[0][1]}: presente in {len(tornei)} tornei")
    for t in tornei[:3]:
        anni = ', '.join(s['year'] for s in t['seasons'][:4])
        print(f"      {t['uniqueTournament']['name']}: {anni}")
    # statistiche vere
    if tornei:
        t0 = tornei[0]
        stat = get(f"/player/{pid}/unique-tournament/{t0['uniqueTournament']['id']}/season/{t0['seasons'][0]['id']}/statistics/overall")
        if stat:
            s = stat['statistics']
            print(f"\n   CAMPI STATISTICI DISPONIBILI: {len(s)}")
            interessanti = ['goals', 'assists', 'expectedGoals', 'expectedAssists', 'minutesPlayed',
                            'appearances', 'matchesStarted', 'yellowCards', 'redCards', 'rating',
                            'totalShots', 'goalConversionPercentage', 'keyPasses', 'cleanSheet']
            for k in interessanti:
                if k in s:
                    print(f"      {k:32} = {s[k]}")

print('\n6. DATI ANAGRAFICI E INFORTUNI')
if teams and players:
    pid = players[0][0]
    p = get(f'/player/{pid}')
    if p:
        pp = p['player']
        print(f"   nome: {pp.get('name')} | ruolo: {pp.get('position')} | maglia: {pp.get('jerseyNumber')}")
        print(f"   nascita(ts): {pp.get('dateOfBirthTimestamp')} | altezza: {pp.get('height')} | piede: {pp.get('preferredFoot')}")
        print(f"   valore mercato: {pp.get('proposedMarketValue')} | squadra: {pp.get('team', {}).get('name')}")
    # infortuni / disponibilità
    for endpoint in ['/player/%d/transfers' % pid]:
        d = get(endpoint)
        print(f"   {endpoint.split('/')[-1]}: {'presente' if d else 'assente'}")
