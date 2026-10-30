# Order Block (SMC) — note di progetto

Riferimento personale per il futuro indicatore Order Block.
Creato il 30/10/2026. Codice: `order_blocks.py` (repo **waves**), fonte
`order_block_signal_source.py` (repo **broker-engine.**).

---

## 1. Stato attuale

| Voce | Stato |
|---|---|
| Rilevatore OB a regole oggettive | ✅ `waves/order_blocks.py` |
| Endpoint segnale live | ✅ `POST /order-block-signal` `{symbol, tf}` — solo H1/H4 |
| Endpoint backtest | ✅ `GET /order-block-backtest` (cache 6h, `?refresh=1`) |
| Broker-engine | ✅ fonte `orderblock`, **solo registro ombra** (`SHADOW_SOURCES=orderblock`) |
| Trading automatico | ❌ **NO** — backtest su dati reali non superato (vedi §4) |

Il registro ombra salva ogni segnale OB con esito virtuale in R. I risultati
compaiono nel trade review insieme alle altre strategie. Nessun ordine viene
inviato.

---

## 2. Regole (identiche in live e backtest, nessun lookahead)

1. **Swing a frattale**: pivot con `K=3` candele per lato. È confermato solo
   3 candele dopo il pivot, perché prima non si conosce.
2. **BOS**: una candela **chiude** oltre l'ultimo swing confermato e non ancora rotto.
3. **Displacement**: la gamba d'impulso va dall'estremo opposto, tra lo swing
   rotto e il BOS, fino alla chiusura del BOS, ed è ≥ `DISP_ATR=2.0 × ATR(14)`.
4. **FVG**: almeno un fair value gap nella gamba
   - long: `low[j+1] > high[j-1]`
   - short: `high[j+1] < low[j-1]`
5. **Order block**: ultima candela di colore opposto (ribassista per il long)
   entro `OB_LOOKBACK=3` candele prima dell'estremo della gamba.
   - Zona long  = `[min(low da OB a estremo), high(OB)]`
   - Zona short = `[low(OB), max(high da OB a estremo)]`
6. **Filtro trend** (opzionale, `OB_TREND_FILTER=1`): long solo con close > SMA200,
   short solo con close < SMA200, sullo stesso timeframe.
7. **Validità**: solo al **primo ritorno** in zona (non mitigato), entro
   `MAX_WAIT=48` candele dal BOS. Se la candela chiude oltre lo stop, la zona è violata.
8. **Esecuzione**:
   - ingresso al bordo della zona (top per il long, bottom per lo short),
     oppure all'apertura se il prezzo apre già dentro la zona
   - stop = estremo opposto della zona ± `STOP_ATR=0.1 × ATR`
   - target = `RR × rischio` (`OB_RR`, default 2)

### Parametri

| Parametro | Default | Dove |
|---|---|---|
| `K` | 3 | `order_blocks.py` |
| `DISP_ATR` | 2.0 | `order_blocks.py` |
| `OB_LOOKBACK` | 3 | `order_blocks.py` |
| `STOP_ATR` | 0.1 | `order_blocks.py` |
| `MAX_WAIT` | 48 candele | `order_blocks.py` |
| `MAX_HOLD` (solo backtest) | 120 candele | `order_blocks.py` |
| `OB_TREND_FILTER` | 1 | env Railway (waves) |
| `OB_RR` | 2 | env Railway (waves) |
| `OB_TIMEFRAMES` | `H1 (1-Hour),H4 (4-Hour)` | env Railway (broker-engine) |
| `SHADOW_SOURCES` | `orderblock` | env Railway (broker-engine) |

---

## 3. Metodo di backtest

- **Dati reali Yahoo**, lo stesso feed dei segnali live: 1h, 730 giorni
  (15/01/2024 → 30/10/2026). H4 ottenuto per resample dell'1h.
- **Universo**: GER40, US500, USTEC, UK100, XAU/USD, WTI, EUR/USD, GBP/USD,
  USD/JPY, AUD/USD, NZD/USD, USD/CHF.
- **Costi**: spread stimato per strumento, sottratto in R su ogni trade.
- **Regole conservative**: stop e target nella stessa candela contano come
  perdita, il target non viene valutato sulla candela d'ingresso, una sola
  posizione per simbolo alla volta.
- **Split temporale 50/50**: IS = prima metà, OOS = seconda metà. Una
  configurazione vale solo se è positiva in **entrambe** le metà.
- **Griglia piccola e fissa**: tf {H1, H4} × trend {sì, no} × RR {1.5, 2, 3},
  cioè 12 combinazioni.
- **Controllo del motore**: su un random walk costruito da un percorso continuo
  il win rate a 2R è circa 33% e l'aspettativa circa 0R. Il motore quindi non
  ha bias. Con circa 200 trade la banda di rumore è circa ±0,15R. Con 20 trade
  è circa ±0,3–0,4R.

---

## 4. Risultati (portafoglio, 12 strumenti)

| TF | Trend | RR | IS n | IS exp R | IS PF | OOS n | OOS exp R | OOS PF |
|---|---|---|---|---|---|---|---|---|
| H1 | sì | 1.5 | 990 | −0.056 | 0.91 | 1020 | −0.100 | 0.85 |
| H1 | sì | 2.0 | 956 | +0.006 | 1.01 | 986 | −0.083 | 0.88 |
| H1 | sì | 3.0 | 911 | +0.079 | 1.10 | 936 | −0.073 | 0.91 |
| H1 | no | 1.5 | 1468 | −0.070 | 0.89 | 1489 | −0.099 | 0.85 |
| H1 | no | 2.0 | 1388 | −0.037 | 0.95 | 1435 | −0.085 | 0.88 |
| H1 | no | 3.0 | 1290 | +0.050 | 1.07 | 1327 | −0.076 | 0.91 |
| H4 | sì | 1.5 | 278 | +0.009 | 1.02 | 293 | −0.098 | 0.85 |
| H4 | sì | 2.0 | 268 | +0.061 | 1.09 | 282 | −0.127 | 0.82 |
| H4 | sì | 3.0 | 245 | +0.107 | 1.15 | 268 | −0.088 | 0.89 |
| H4 | no | 1.5 | 423 | +0.000 | 1.00 | 431 | −0.135 | 0.80 |
| H4 | no | 2.0 | 407 | +0.064 | 1.10 | 410 | −0.153 | 0.79 |
| H4 | no | 3.0 | 372 | +0.109 | 1.15 | 377 | −0.135 | 0.83 |

**Verdetto: nessuna configurazione è positiva fuori campione.** La migliore in
IS (H4, trend, RR3: +0,107R) diventa −0,088R in OOS. Il filtro SMA200 aiuta poco.

### Per strumento: configurazioni positive sia in IS sia in OOS (su 12)

| Strumento | Positive | Strumento | Positive |
|---|---|---|---|
| **XAU/USD** | **10/12** | USTEC | 4/12 |
| UK100 | 7/12 | USD/CHF | 4/12 |
| US500 | 6/12 | EUR/USD | 3/12 |
| GER40 | 2/12 | USD/JPY | 2/12 |
| AUD/USD | 0/12 | GBP/USD | 0/12 |
| NZD/USD | 0/12 | WTI | 0/12 |

**Oro, dettaglio**

| Config | IS n | IS exp | OOS n | OOS exp |
|---|---|---|---|---|
| H1, trend, RR3 | 72 | +0.455 | 71 | +0.058 |
| H4, trend, RR3 | 20 | +0.452 | 21 | +0.473 |

Attenzione: su H1 il vantaggio sparisce quasi del tutto in OOS. Su H4 ci sono
solo circa 20 trade per metà, dentro la banda di rumore. L'oro nel periodo è in
un forte trend rialzista, quindi la sovraperformance può essere beta del trend
e non merito dell'OB. **Non basta per andare in automatico.**

FX "puri" (AUD, NZD, GBP) e WTI: 0/12. Su questi strumenti la regola OB così
definita non funziona.

---

## 5. Cosa provare prima di riconsiderarlo

In ordine. Ogni variante va validata con lo stesso split IS/OOS, senza
aggiungere libertà a caso:

1. **Liquidity sweep obbligatorio**: l'OB vale solo se prima del BOS il prezzo
   ha preso liquidità, cioè ha superato un minimo/massimo precedente o equal lows/highs.
2. **Target sulla liquidità** (swing opposto) invece di RR fisso.
3. **Mean threshold**: ingresso al 50% della zona invece che al bordo.
   Meno fill, R:R migliore.
4. **Conferma su timeframe inferiore**: zona H4, ingresso solo dopo un CHoCH su M15/M30.
5. **Contesto EW**: solo OB lasciati dall'impulso di onda 1 o di onda 3,
   usati come area di fine onda 2 o onda 4, con confluenza Fibonacci
   (0.618 per la 2, 0.382 per la 4) dal motore `ew_server.py`.
6. **Solo oro / solo indici**, ma solo con un periodo che includa fasi laterali
   o ribassiste. Serve uno storico più lungo di 730 giorni: le candele 1h di
   Yahoo non vanno oltre, quindi servono H4 da un'altra fonte gratuita oppure D1.

**Criterio di promozione in automatico** (stesso della RSI(2)):
- aspettativa > 0 in IS e in OOS dopo i costi
- PF OOS ≥ 1,2
- almeno 100 trade OOS sul portafoglio
- poi 20–30 segnali nel registro ombra coerenti con il backtest
- solo allora `SIGNAL_SOURCES=...,orderblock`

---

## 6. Per l'indicatore (TradingView / sito)

Struttura consigliata, valida anche per Pine Script v5:

1. **Swing**: `ta.pivothigh(high, K, K)` / `ta.pivotlow(low, K, K)`. Il valore
   arriva con K barre di ritardo, ed è corretto così (nessun repaint).
2. **Stato**: ultimo swing high/low e flag "rotto".
3. **BOS**: `close > swingHigh and not broken`. Si cerca l'estremo della gamba
   con un loop sulle barre tra lo swing e il BOS, poi l'ultima candela opposta.
4. **Filtri**: impulso ≥ 2 ATR, FVG nella gamba, SMA200 opzionale.
5. **Disegno**: `box.new()` dalla candela OB verso destra, finché non è mitigata
   (primo tocco) o scaduta. Poi il box si ferma e diventa grigio. Le linee FVG
   sono opzionali.
6. **Input esposti**: K, DISP_ATR, OB_LOOKBACK, MAX_WAIT, trend filter on/off,
   mostra mitigati sì/no, colori long/short.
7. **Alert**: `alertcondition` sul primo tocco di una zona attiva. È la stessa
   condizione di `live_signal()`.
8. **Limiti Pine**: massimo 500 box per script, quindi conviene eliminare i box
   vecchi o mitigati. I loop all'indietro vanno limitati, per esempio a 100 barre.

Per tenere indicatore e sistema allineati: **stesse regole di
`order_blocks.py`**. Se cambi un parametro nell'indicatore, cambialo anche lì
e rifai il backtest.

---

## 7. Comandi utili

- Rifare il backtest:
  - imposta `OB_BACKTEST_ON_START=1` sul servizio Railway **waves**
    (fa un redeploy)
  - risultati nei log, filtro `ob_backtest`, circa 2 minuti dopo l'avvio
  - poi rimetti `OB_BACKTEST_ON_START=0`
- Oppure via HTTP: `GET /order-block-backtest?refresh=1` (circa 1–2 minuti).
- Spegnere l'OB anche in ombra: `SHADOW_SOURCES=` (vuoto) sul broker-engine.
- Metterlo in automatico (solo dopo aver superato il §5): aggiungere `orderblock`
  a `SIGNAL_SOURCES` e toglierlo da `SHADOW_SOURCES`.
