"""Produce la lista d'asta: consigliati, crediti, commento e dati.

🔑 IL PRINCIPIO, che è la richiesta dell'utente: i dati devono LEGARSI.
Un attaccante con pochi gol in una squadra che produceva poco, che passa a un
allenatore le cui punte segnano molto, SALE. Un attaccante con cattiva
conversione tiri-gol in una squadra il cui allenatore non produce gol, SCENDE.

ARCHITETTURA (rivista il 2026-08-31, dopo il blocco di Sofascore)
  base       listone.json      chi è acquistabile, con che ruolo e a che prezzo
  storico    fantacalcio.json  FANTAMEDIA, presenze, gol, assist, cartellini,
                               rigori — 4 stagioni, tutte e 20 le squadre
  contesto   squadre.json + allenatori.json
  extra      giocatori.json    xG/xA da Sofascore, dove disponibili (6 squadre)

La fantamedia è la metrica con cui si fanno i punti: è lei la base, non le
statistiche grezze. Sofascore serve solo a dire chi ha segnato sopra o sotto
le attese.

Lega: Classico, 10 squadre, 500 crediti, MODIFICATORE DIFESA ATTIVO.
"""
import json
import os
import unicodedata

DIR = os.path.dirname(os.path.abspath(__file__))
DATI = os.path.join(DIR, 'dati')

# Stagione in corso + le tre precedenti, coi rispettivi pesi.
ANNO_CORRENTE = '2026-27'
PESI = {'2025-26': 1.0, '2024-25': 0.55, '2023-24': 0.30}

# Fantamedia di riferimento per ruolo: un portiere a 5,4 NON è peggio di un
# attaccante a 7,2 — fanno mestieri diversi. Ogni giocatore si confronta con
# la mediana del PROPRIO ruolo, calcolata dai dati reali.
RUOLI = ['G', 'D', 'M', 'F']

CREDITI_LEGA = 10 * 500
SLOT = {'G': 30, 'D': 80, 'M': 80, 'F': 60}

SIGLE = {
    'ATA': 'Atalanta', 'BOL': 'Bologna', 'CAG': 'Cagliari', 'COM': 'Como',
    'FIO': 'Fiorentina', 'FRO': 'Frosinone', 'GEN': 'Genoa', 'INT': 'Inter',
    'JUV': 'Juventus', 'LAZ': 'Lazio', 'LEC': 'Lecce', 'MIL': 'AC Milan',
    'MON': 'Monza', 'NAP': 'SSC Napoli', 'PAR': 'Parma', 'ROM': 'AS Roma',
    'SAS': 'Sassuolo', 'TOR': 'Torino', 'UDI': 'Udinese', 'VEN': 'Venezia',
}
RUOLO_LISTONE = {'p': 'G', 'd': 'D', 'c': 'M', 'a': 'F'}

TRADUZIONI = str.maketrans({
    'ı': 'i', 'İ': 'i', 'ø': 'o', 'Ø': 'o', 'đ': 'd', 'Đ': 'd', 'ð': 'd',
    'ł': 'l', 'Ł': 'l', 'ħ': 'h', 'ŧ': 't', 'ə': 'e', 'ß': 's', 'æ': 'a',
    'œ': 'o', 'å': 'a', 'Å': 'a', "'": ' ', '-': ' ',
})


def carica(nome):
    p = os.path.join(DATI, nome)
    if not os.path.exists(p):
        return {}
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def num(x, d=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def norm(s):
    if not s:
        return ''
    s = s.translate(TRADUZIONI)
    s = unicodedata.normalize('NFD', s)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    return ' '.join(''.join(c for c in s.lower() if c.isalnum() or c == ' ').split())


# --------------------------------------------------------------------------
# 1. STORICO — la fantamedia pesata sulle stagioni
# --------------------------------------------------------------------------

def storico(nome, fanta):
    """Media pesata di fantamedia, presenze e bonus sulle ultime 3 stagioni.

    Le stagioni con meno di 8 partite a voto si scartano: una fantamedia su
    tre partite è rumore, e all'asta il rumore costa crediti.
    """
    acc = {'fm': 0.0, 'mv': 0.0, 'gol': 0.0, 'assist': 0.0,
           'amm': 0.0, 'esp': 0.0, 'pv': 0.0}
    peso_tot = 0.0
    dettaglio = []

    for anno, peso in PESI.items():
        v = fanta.get(anno, {}).get(nome)
        if not v:
            continue
        pv = num(v.get('pv'))
        if pv < 8:
            continue
        acc['fm'] += num(v.get('fm')) * peso
        acc['mv'] += num(v.get('mv')) * peso
        acc['gol'] += num(v.get('gol')) * peso
        acc['assist'] += num(v.get('assist')) * peso
        acc['amm'] += num(v.get('ammonizioni')) * peso
        acc['esp'] += num(v.get('espulsioni')) * peso
        acc['pv'] += pv * peso
        peso_tot += peso
        dettaglio.append({
            'stagione': anno, 'squadra': v.get('squadra'), 'pv': pv,
            'mv': v.get('mv'), 'fm': v.get('fm'), 'gol': v.get('gol'),
            'assist': v.get('assist'), 'amm': v.get('ammonizioni'),
            'rigori': (f"{v.get('rigori_segnati')}/{v.get('rigori_calciati')}"
                       if v.get('rigori_calciati') else None),
            'rigori_pct': v.get('rigori_pct'),
            'rigori_parati': v.get('rigori_parati') or None,
        })

    if peso_tot == 0:
        return None, []
    for k in acc:
        acc[k] /= peso_tot
    acc['stagioni_valide'] = len(dettaglio)
    return acc, dettaglio


def stagione_corrente(nome, fanta):
    v = fanta.get(ANNO_CORRENTE, {}).get(nome)
    if not v:
        return None
    return {'pv': num(v.get('pv')), 'fm': v.get('fm'), 'mv': v.get('mv'),
            'gol': v.get('gol'), 'assist': v.get('assist'),
            'presenze_pct': v.get('presenze_pct')}


# --------------------------------------------------------------------------
# 2. CONTESTO — allenatore e squadra di QUEST'ANNO
# --------------------------------------------------------------------------

def contesto_squadra(sq_nome, squadre, allenatori):
    sq = next((v for v in squadre.values() if v['nome'] == sq_nome), None)
    if not sq:
        return None
    al = sq.get('allenatore') or {}
    prof = allenatori.get(al.get('nome') or '', {})

    gf = gs = bc = 0.0
    n = 0.0
    gol_punta = []
    for anno, peso in [('25/26', 1.0), ('24/25', 0.55), ('23/24', 0.30)]:
        v = prof.get('stagioni', {}).get(anno) or {}
        if not v.get('partite'):
            continue
        gf += v['gol_fatti_pg'] * peso
        gs += v['gol_subiti_pg'] * peso
        bc += v.get('big_chances_pg', 0) * peso
        n += peso
        if v.get('gol_miglior_punta'):
            gol_punta.append(v['gol_miglior_punta'])

    base = {'allenatore': al.get('nome'), 'modulo': al.get('modulo_preferito')}
    if n == 0:
        base.update({'dati': False, 'gol_fatti_pg': None, 'gol_subiti_pg': None,
                     'gol_miglior_punta_media': None})
        return base
    base.update({
        'dati': True,
        'gol_fatti_pg': round(gf / n, 2),
        'gol_subiti_pg': round(gs / n, 2),
        'big_chances_pg': round(bc / n, 2),
        'gol_miglior_punta_media': (round(sum(gol_punta) / len(gol_punta), 1)
                                    if gol_punta else None),
    })
    return base


def moltiplicatore(ruolo, ctx):
    """🔑 Il contesto corregge il dato individuale, e dice perché."""
    if not ctx or not ctx.get('dati'):
        return 1.0, ['contesto allenatore non disponibile: nessuna correzione']

    m, motivi = 1.0, []

    if ruolo in ('F', 'M'):
        gf = ctx['gol_fatti_pg']
        k = max(0.75, min(1.28, 1.0 + (gf - 1.35) * 0.28))
        m *= k
        if k > 1.05:
            motivi.append(f"squadra che produce ({gf} gol/partita con {ctx['allenatore']}) → {(k-1)*100:+.0f}%")
        elif k < 0.95:
            motivi.append(f"squadra che produce poco ({gf} gol/partita con {ctx['allenatore']}) → {(k-1)*100:+.0f}%")

    if ruolo == 'F':
        gp = ctx.get('gol_miglior_punta_media')
        if gp is not None:
            k = max(0.72, min(1.30, 1.0 + (gp - 12.0) * 0.026))
            m *= k
            if k > 1.05:
                motivi.append(f"le punte di {ctx['allenatore']} segnano (miglior punta {gp} gol di media) → {(k-1)*100:+.0f}%")
            elif k < 0.95:
                motivi.append(f"🔴 le punte di {ctx['allenatore']} segnano poco (miglior punta {gp} gol di media) → {(k-1)*100:+.0f}%")

    if ruolo in ('D', 'G'):
        gs = ctx['gol_subiti_pg']
        k = max(0.70, min(1.35, 1.0 + (1.30 - gs) * 0.40))
        m *= k
        if k > 1.05:
            motivi.append(f"difesa solida ({gs} gol subiti/partita con {ctx['allenatore']}) → {(k-1)*100:+.0f}% — pesa sul modificatore")
        elif k < 0.95:
            motivi.append(f"difesa che subisce ({gs} gol subiti/partita con {ctx['allenatore']}) → {(k-1)*100:+.0f}%")

    return m, motivi


# --------------------------------------------------------------------------
# 3. PUNTEGGIO
# --------------------------------------------------------------------------

def mediane_ruolo(valutabili):
    """La fantamedia di riferimento per ogni ruolo, dai dati reali."""
    out = {}
    for r in RUOLI:
        v = sorted(x['storico']['fm'] for x in valutabili if x['ruolo'] == r)
        out[r] = v[len(v) // 2] if v else 6.0
    return out


def punteggio(v, mediane):
    """Quanto rende sopra il proprio ruolo, corretto per affidabilità."""
    st = v['storico']
    note = []
    # scarto dalla mediana del ruolo: è il "sovrappiù" che quel giocatore dà
    scarto = st['fm'] - mediane[v['ruolo']]
    base = 100 + scarto * 55

    # AFFIDABILITÀ: una fantamedia su poche presenze vale meno.
    pv = st['pv']
    if pv < 25:
        aff = 0.55 + 0.45 * (pv / 25)
        base *= aff
        if pv < 15:
            note.append(f'⚠️ solo {pv:.0f} presenze medie: dato poco affidabile, è una scommessa')

    # TITOLARITÀ DI QUEST'ANNO: il segnale più fresco che esiste.
    cur = v.get('corrente')
    if cur and cur['presenze_pct'] is not None:
        p = cur['presenze_pct'] / 100.0
        if v['ruolo'] == 'G':
            # Per un portiere non esiste la rotazione: o para o non fa punti.
            base *= (0.10 + 0.90 * p)
            if p < 0.5:
                note.append('⚠️ non è il portiere titolare: al fanta vale 1 credito')
        else:
            base *= (0.55 + 0.45 * p)
            if p < 0.4:
                note.append(f'⚠️ finora in campo nel {cur["presenze_pct"]:.0f}% delle partite')

    # RIGORISTA: al fanta è quasi un bonus garantito, ma conta la percentuale.
    rig = v.get('rigori')
    if rig and rig['calciati'] >= 2:
        pct = rig['pct'] or 0
        # 5/5 vale molto più di 4/6
        k = 1.0 + 0.030 * rig['calciati'] * (pct / 100.0)
        base *= min(k, 1.22)
        if pct >= 90:
            note.append(f"rigorista affidabile ({rig['segnati']}/{rig['calciati']} = {pct}%)")
        elif pct < 75:
            note.append(f"🔴 rigorista ma ne sbaglia ({rig['segnati']}/{rig['calciati']} = {pct}%)")
        else:
            note.append(f"rigorista ({rig['segnati']}/{rig['calciati']} = {pct}%)")

    # CARTELLINI: -0,5 ad ammonizione, e chi ne prende 10 a stagione lo sente.
    if st['amm'] >= 7:
        base *= 0.96
        note.append(f"{st['amm']:.0f} ammonizioni di media a stagione")

    return max(1.0, base), note


# --------------------------------------------------------------------------
# 4. CREDITI — si parte dal mercato e lo si corregge
# --------------------------------------------------------------------------

def scala_listone(listone):
    fvm = sorted((num(v.get('fvm')) for v in listone), reverse=True)
    top = [x for x in fvm if x > 0][:250]
    return (CREDITI_LEGA * 0.92) / sum(top) if sum(top) > 0 else None


def in_crediti(valutati, k):
    """🔑 La correzione è RELATIVA, non assoluta.

    Errore della prima versione: moltiplicavo il prezzo di mercato per il mio
    punteggio assoluto. Ma il FVM incorpora GIÀ quanto è forte un giocatore —
    rimoltiplicarlo contava due volte la stessa cosa, e infatti quasi tutti
    finivano saturati a +45%: un'analisi che alza tutto non dice niente.

    Il segnale utile è un altro: a parità di prezzo, chi rende più della
    media? Si calcola il rapporto punteggio/prezzo di ogni giocatore, lo si
    confronta con la MEDIANA del suo ruolo, e lo scostamento è il consiglio.
    Sopra la mediana = il mercato lo paga poco per quello che dà.
    """
    # 1. prezzo di mercato in crediti della nostra lega
    for v in valutati:
        fvm = num(v['listone'].get('fvm'))
        v['_fvm'] = fvm
        v['crediti_listone'] = max(1, round(fvm * k)) if (fvm and k) else 1

    # 2. 🔑 Confronto per PERCENTILE, dentro il ruolo.
    #
    #    Il rapporto punteggio/prezzo non funziona: la resa per credito
    #    decresce col prezzo (un riempitivo da 1 credito ha sempre resa
    #    altissima), quindi la mediana è dominata dai giocatori economici e
    #    tutti i top finiscono a -45%. Era lo stesso errore di prima
    #    rovesciato: un'analisi che abbassa tutto non dice niente come una
    #    che alza tutto.
    #
    #    Il confronto giusto è fra posizioni: se un giocatore sta al 90°
    #    percentile per rendimento ma solo al 60° per prezzo, il mercato lo
    #    paga poco PER QUELLO CHE VALE FRA I SUOI PARI. Quella differenza è
    #    il consiglio d'asta.
    def percentili(gruppo, chiave):
        ordinati = sorted(gruppo, key=chiave)
        n = len(ordinati)
        return {id(v): (i / (n - 1) if n > 1 else 0.5)
                for i, v in enumerate(ordinati)}

    for r in RUOLI:
        gruppo = [x for x in valutati if x['ruolo'] == r]
        if not gruppo:
            continue
        p_rend = percentili(gruppo, lambda x: x['punteggio'] * x['moltiplicatore'])
        p_prez = percentili(gruppo, lambda x: x['crediti_listone'])
        for v in gruppo:
            delta = p_rend[id(v)] - p_prez[id(v)]     # da -1 a +1
            corr = max(0.55, min(1.45, 1.0 + delta * 0.75))
            v['percentile_rendimento'] = round(p_rend[id(v)] * 100)
            v['percentile_prezzo'] = round(p_prez[id(v)] * 100)
            v['correzione'] = round(corr, 3)
            v['crediti'] = max(1, round(v['crediti_listone'] * corr))
            v['scostamento'] = round((corr - 1) * 100)
            v.pop('_fvm', None)
    return valutati


def main():
    listone = carica('listone.json')
    fanta = carica('fantacalcio.json')
    squadre = carica('squadre.json')
    allenatori = carica('allenatori.json')
    if not listone or not fanta:
        print('mancano listone.json o fantacalcio.json'); return

    ctx_cache = {}
    valutabili, senza_storico = [], []

    for L in listone:
        squadra = SIGLE.get(L['squadra'], L['squadra'])
        ruolo = RUOLO_LISTONE.get(L['ruolo'])
        if not ruolo:
            continue
        st, dett = storico(L['nome'], fanta)
        cur = stagione_corrente(L['nome'], fanta)

        if not st:
            # Nessuno storico in Serie A: è un nuovo arrivo. Non si butta —
            # si segnala che il prezzo è quello di mercato senza conferme.
            senza_storico.append({
                'nome': L['nome'], 'ruolo': ruolo, 'squadra': squadra,
                'listone': L, 'corrente': cur,
                'nota': 'nessuno storico in Serie A: nuovo arrivo, '
                        'valutazione basata solo su quotazione e contesto',
            })
            continue

        if squadra not in ctx_cache:
            ctx_cache[squadra] = contesto_squadra(squadra, squadre, allenatori)

        # rigori: si prende la stagione più recente in cui ne ha calciati
        rigori = None
        for d in dett:
            if d.get('rigori'):
                s, c = d['rigori'].split('/')
                rigori = {'segnati': int(float(s)), 'calciati': int(float(c)),
                          'pct': d.get('rigori_pct'), 'stagione': d['stagione']}
                break

        valutabili.append({
            'nome': L['nome'], 'ruolo': ruolo, 'squadra': squadra,
            'listone': L, 'storico': st, 'dettaglio': dett,
            'corrente': cur, 'rigori': rigori,
            'contesto': ctx_cache[squadra],
        })

    med = mediane_ruolo(valutabili)
    for v in valutabili:
        p, note = punteggio(v, med)
        m, motivi = moltiplicatore(v['ruolo'], v['contesto'])
        v['punteggio'] = round(p, 1)
        v['moltiplicatore'] = round(m, 3)
        v['note'] = note
        v['motivi_contesto'] = motivi

    in_crediti(valutabili, scala_listone(listone))
    valutabili.sort(key=lambda x: -x['crediti'])

    with open(os.path.join(DATI, 'valutazioni.json'), 'w', encoding='utf-8') as f:
        json.dump({'valutati': valutabili, 'senza_storico': senza_storico,
                   'mediane_fm_per_ruolo': med}, f, ensure_ascii=False, indent=1)

    print(f'valutati {len(valutabili)} giocatori con storico '
          f'({len(senza_storico)} nuovi arrivi senza storico in Serie A)')
    print('fantamedia mediana per ruolo:', {k: round(x, 2) for k, x in med.items()})
    print()
    for ruolo, et in [('F', 'ATTACCANTI'), ('M', 'CENTROCAMPISTI'),
                      ('D', 'DIFENSORI'), ('G', 'PORTIERI')]:
        print(f'--- {et} ---')
        for v in [x for x in valutabili if x['ruolo'] == ruolo][:10]:
            sc = v['scostamento']
            segno = f" [{sc:+d}%]" if abs(sc) >= 8 else '     '
            print(f"  {v['crediti']:4}cr {v['nome'][:20]:20} {v['squadra'][:11]:11} "
                  f"FM {v['storico']['fm']:.2f} pv {v['storico']['pv']:4.1f} "
                  f"| mercato {v['crediti_listone']:3}cr{segno}")
        print()


if __name__ == '__main__':
    main()
