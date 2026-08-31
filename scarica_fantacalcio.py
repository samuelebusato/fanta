"""Scarica statistiche e quotazioni da Fantacalcio.it — la fonte giusta.

Perché questa e non Sofascore (deciso il 2026-08-31 dopo il blocco):
  - Sofascore dà xG/xA, che sono ottimi per la previsione ma NON sono le
    metriche del fantacalcio, e ci blocca dopo ~1.100 richieste.
  - Fantacalcio.it dà FANTAMEDIA, media voto, partite a voto, gol, assist,
    ammonizioni, espulsioni, rigori — cioè esattamente ciò con cui si fanno i
    punti — per tutti i ~600 giocatori in UNA richiesta per stagione, e non
    blocca. Quattro richieste totali invece di tremila.

Sofascore resta utile come arricchimento (xG/xA per capire chi ha segnato
sopra o sotto le attese), non come base.
"""
import json
import os
import re
import time
from curl_cffi import requests

H = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'accept-language': 'it-IT,it;q=0.9',
}
DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(DIR, 'dati')

STAGIONI = ['2026-27', '2025-26', '2024-25', '2023-24']
RUOLI = {'p': 'G', 'd': 'D', 'c': 'M', 'a': 'F'}

RIGA = re.compile(r'<tr class="player-row[^"]*"(.*?)</tr>', re.S)
ATTR = re.compile(r'data-([a-z-]+)="([^"]*)"')
CELLA = re.compile(r'<t[dh][^>]*>(.*?)</t[dh]>', re.S)
# Il nome sta DENTRO il link, non nella cella: <th class="player-name"><a …>Nome</a>
# La prima versione si fermava sul <th> e non trovava testo prima del tag <a>.
NOME = re.compile(r'<a[^>]*class="[^"]*player-link[^"]*"[^>]*>\s*([^<]+)', re.S)
TAG = re.compile(r'<[^>]+>')


def testo(html):
    return TAG.sub('', html).replace('&nbsp;', ' ').strip()


def numero(s):
    if not s or s in ('-', ''):
        return None
    s = s.replace(',', '.').strip()
    try:
        return float(s) if '.' in s else int(s)
    except ValueError:
        return None


def scarica(stagione):
    url = ('https://www.fantacalcio.it/statistiche-serie-a'
           if stagione == '2026-27'
           else f'https://www.fantacalcio.it/statistiche-serie-a/{stagione}')
    s = requests.Session(impersonate='chrome124')
    r = s.get(url, headers=H, timeout=40)
    if r.status_code != 200:
        print(f'  {stagione}: HTTP {r.status_code}')
        return {}

    out = {}
    for m in RIGA.finditer(r.text):
        blocco = m.group(1)
        attrs = dict(ATTR.findall(blocco))
        celle = [c for c in (testo(x) for x in CELLA.findall(blocco)) if c != '']
        if len(celle) < 10:
            continue
        # Le celle non vuote sono già, in ordine:
        #   [nome, Sq, PV, MV, FM, Gol, GS, Rig(x/y), RP, Ass, Amm, Esp]
        # Il nome è la prima: la regex sul link era superflua e restituiva vuoto,
        # perché fra il tag <a> e il testo c'erano altri elementi.
        nome = celle[0]
        # sicurezza: se il nome del data-attribute c'è, si preferisce quello
        nome = attrs.get('filter-keywords') or nome
        v = celle[1:]
        rig = v[6] if len(v) > 6 else ''
        rig_segnati, rig_calciati = None, None
        if '/' in rig:
            parti = rig.split('/')
            rig_segnati, rig_calciati = numero(parti[0]), numero(parti[1])

        ruolo = RUOLI.get(attrs.get('filter-role-classic'))
        rig_parati = numero(v[7]) if len(v) > 7 else None

        rec = {
            'nome': nome,
            'squadra': v[0] if v else None,
            'ruolo': ruolo,
            'mantra': attrs.get('filter-role-mantra'),
            'presenze_pct': numero(attrs.get('filter-playeds')),
            'indice_rigorista': numero(attrs.get('penalties')),
            'pv': numero(v[1]) if len(v) > 1 else None,      # partite a voto
            'mv': numero(v[2]) if len(v) > 2 else None,      # media voto
            'fm': numero(v[3]) if len(v) > 3 else None,      # FANTAMEDIA
            'gol': numero(v[4]) if len(v) > 4 else None,
            'gol_subiti': numero(v[5]) if len(v) > 5 else None,
            'rigori_segnati': rig_segnati,
            'rigori_calciati': rig_calciati,
            'rigori_parati': rig_parati,
            'assist': numero(v[8]) if len(v) > 8 else None,
            'ammonizioni': numero(v[9]) if len(v) > 9 else None,
            'espulsioni': numero(v[10]) if len(v) > 10 else None,
        }

        # 🔑 RIGORISTI — richiesta dell'utente (2026-08-31).
        # Al fanta un rigorista vale molto: +3 quasi garantito a ogni penalty.
        # Ma conta CHI li tira e QUANTO li segna: chi ne sbaglia due su cinque
        # è un rigorista che vale meno di uno che ne segna cinque su cinque.
        if rec['rigori_calciati']:
            rec['rigori_pct'] = round(100 * (rec['rigori_segnati'] or 0)
                                      / rec['rigori_calciati'])
        else:
            rec['rigori_pct'] = None

        # PORTIERI — ⚠️ verificato il 2026-08-31: questa fonte NON dà i rigori
        # affrontati. La colonna "Rig" conta i rigori CALCIATI dal giocatore,
        # e per un portiere è sempre "0 / 0"; l'unico dato è "RP", i rigori
        # parati in assoluto. Senza il denominatore la percentuale di parate
        # su rigore non è calcolabile, e inventarla sarebbe peggio che non
        # averla: resta `None` finché non arriva da Sofascore (`penaltyFaced`),
        # che ce l'ha ma al momento ci blocca.
        if ruolo == 'G':
            rec['rigori_pct'] = None            # non ha senso per un portiere
            rec['rigori_affrontati'] = None     # dato non disponibile qui
            rec['rigori_parati_pct'] = None
            # Quello che si può dire con certezza: quanti ne ha parati, e
            # ogni rigore parato al fanta vale +3.
            rec['rigori_parati_per_stagione'] = rig_parati

        out[nome] = rec
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    tutto = {}
    for st in STAGIONI:
        print(f'{st} …', end=' ', flush=True)
        d = scarica(st)
        tutto[st] = d
        print(f'{len(d)} giocatori', flush=True)
        time.sleep(2.5)

    with open(os.path.join(OUT, 'fantacalcio.json'), 'w', encoding='utf-8') as f:
        json.dump(tutto, f, ensure_ascii=False, indent=1)

    print(f'\nsalvato dati/fantacalcio.json')
    # controllo a campione
    for nome in ['Malen', 'Martinez L.', 'Dimarco', 'Orsolini']:
        for st in STAGIONI:
            v = tutto[st].get(nome)
            if v and v.get('pv'):
                print(f"  {nome:14} {st}  {v['squadra']} {v['ruolo']} "
                      f"PV {v['pv']} MV {v['mv']} FM {v['fm']} "
                      f"gol {v['gol']} ass {v['assist']} amm {v['ammonizioni']}")


if __name__ == '__main__':
    main()
