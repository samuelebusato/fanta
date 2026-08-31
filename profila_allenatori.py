"""Costruisce il profilo di ogni allenatore di Serie A 26/27.

La domanda a cui questo file risponde, ed è quella che l'utente ha posto:
«le punte di questo allenatore segnano, o no?»

Metodo: si incrocia la CARRIERA dell'allenatore (che dice dove era in ogni
periodo) con le STATISTICHE della squadra che allenava in quella stagione e coi
suoi MARCATORI. Dove l'allenatore veniva da un campionato estero il dato di
squadra non è recuperabile allo stesso modo: in quel caso si usa la performance
di carriera aggregata, e lo si dichiara invece di far finta di niente.
"""
import json
import os
import time
from datetime import datetime, timezone
from curl_cffi import requests

H = {'accept': '*/*', 'origin': 'https://www.sofascore.com', 'referer': 'https://www.sofascore.com/'}
BASE = 'https://api.sofascore.com/api/v1'
PAUSA = 0.5
SERIE_A = 23
STAGIONI = {'25/26': 76457, '24/25': 63515, '23/24': 52760}

DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(DIR, 'dati')

# Finestre temporali delle stagioni (agosto -> giugno)
FINESTRE = {
    '23/24': (datetime(2023, 8, 1, tzinfo=timezone.utc), datetime(2024, 6, 30, tzinfo=timezone.utc)),
    '24/25': (datetime(2024, 8, 1, tzinfo=timezone.utc), datetime(2025, 6, 30, tzinfo=timezone.utc)),
    '25/26': (datetime(2025, 8, 1, tzinfo=timezone.utc), datetime(2026, 6, 30, tzinfo=timezone.utc)),
}


def get(path):
    for i in range(3):
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
            time.sleep(2)
    return None


def ts(x):
    return datetime.fromtimestamp(x, tz=timezone.utc) if x else None


def dove_era(carriera, anno):
    """Quale squadra allenava in quella stagione (sovrapposizione col periodo)."""
    ini, fin = FINESTRE[anno]
    for c in carriera:
        d, a = ts(c.get('dal')), ts(c.get('al'))
        if not d:
            continue
        if a is None:
            a = datetime.now(timezone.utc)
        # sovrapposizione di almeno 3 mesi con la stagione
        inizio = max(d, ini)
        fine = min(a, fin)
        if (fine - inizio).days > 90:
            return c
    return None


def main():
    with open(os.path.join(OUT, 'squadre.json'), encoding='utf-8') as f:
        squadre = json.load(f)

    # mappa id squadra -> statistiche già scaricate (evita richieste inutili)
    stat_note = {int(k): v['stagioni'] for k, v in squadre.items()}

    profili = {}
    for tid, sq in squadre.items():
        al = sq.get('allenatore')
        if not al:
            continue
        prof = {
            'nome': al['nome'],
            'squadra_attuale': sq['nome'],
            'modulo': al.get('modulo_preferito'),
            'carriera_totale': al.get('performance_carriera'),
            'stagioni': {},
            'note': [],
        }

        for anno in ['25/26', '24/25', '23/24']:
            c = dove_era(al.get('carriera', []), anno)
            if not c or not c.get('squadra_id'):
                prof['stagioni'][anno] = {'squadra': None}
                continue
            sq_id, sq_nome = c['squadra_id'], c['squadra']
            voce = {'squadra': sq_nome}

            # statistiche di squadra: se è di Serie A le ho già
            st = stat_note.get(sq_id, {}).get(anno)
            if not st:
                time.sleep(PAUSA)
                r = get(f'/team/{sq_id}/unique-tournament/{SERIE_A}/season/{STAGIONI[anno]}/statistics/overall')
                st = (r or {}).get('statistics')
            if st and st.get('matches'):
                m = st['matches']
                voce['partite'] = m
                voce['gol_fatti_pg'] = round((st.get('goalsScored') or 0) / m, 2)
                voce['gol_subiti_pg'] = round((st.get('goalsConceded') or 0) / m, 2)
                voce['tiri_pg'] = round((st.get('shots') or 0) / m, 1)
                voce['tiri_porta_pg'] = round((st.get('shotsOnTarget') or 0) / m, 1)
                voce['big_chances_pg'] = round((st.get('bigChancesCreated') or 0) / m, 2)
                voce['falli_pg'] = round((st.get('fouls') or 0) / m, 1)
                voce['possesso'] = round(st.get('averageBallPossession') or 0, 1)
                voce['clean_sheet'] = st.get('cleanSheets')
                voce['recuperi_pg'] = round((st.get('ballRecovery') or 0) / m, 1)
            else:
                prof['note'].append(f'{anno}: {sq_nome} — statistiche di squadra non recuperabili (campionato estero o dato assente)')

            # marcatori di quella squadra in quella stagione
            time.sleep(PAUSA)
            tp = get(f'/team/{sq_id}/unique-tournament/{SERIE_A}/season/{STAGIONI[anno]}/top-players/overall')
            if tp and tp.get('topPlayers', {}).get('goals'):
                marcatori = []
                for e in tp['topPlayers']['goals'][:4]:
                    marcatori.append({
                        'nome': e['player']['name'],
                        'ruolo': e['player'].get('position'),
                        'gol': e['statistics'].get('goals'),
                    })
                voce['marcatori'] = marcatori
                voce['gol_miglior_marcatore'] = marcatori[0]['gol'] if marcatori else None
                # quanti gol ha fatto il miglior ATTACCANTE (ruolo F)
                punte = [m for m in marcatori if m['ruolo'] == 'F']
                voce['gol_miglior_punta'] = punte[0]['gol'] if punte else None

            prof['stagioni'][anno] = voce

        profili[al['nome']] = prof
        stag_ok = [a for a, v in prof['stagioni'].items() if v.get('partite')]
        print(f"  {al['nome']:24} ({sq['nome']:14}) modulo {prof['modulo'] or '—':8} dati: {stag_ok}", flush=True)

    with open(os.path.join(OUT, 'allenatori.json'), 'w', encoding='utf-8') as f:
        json.dump(profili, f, ensure_ascii=False, indent=1)
    print(f'\nFATTO: {len(profili)} allenatori profilati', flush=True)


if __name__ == '__main__':
    main()
