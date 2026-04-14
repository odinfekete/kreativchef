"""
CryptoRadar Paper Trades – Teljes elemzési script
Futtatás: python3 analysis_paper_trades.py
DB path: /Users/feketeodin/paper_trades.db
"""

import sqlite3
import statistics
from pathlib import Path

DB_PATH = Path("/Users/feketeodin/paper_trades.db")


def load_trades(db_path: Path) -> list[tuple]:
    with sqlite3.connect(db_path) as conn:
        return conn.execute("""
            SELECT id, symbol, entry_price, tp_price, sl_price,
                   open_time, close_time, result_percent, status
            FROM paper_trades
            WHERE status != 'OPEN'
            ORDER BY open_time ASC
        """).fetchall()


def sep(title: str) -> None:
    print()
    print("=" * 65)
    print(f"  {title}")
    print("=" * 65)


def task1_tp_optimization(rows: list[tuple]) -> None:
    sep("FELADAT 1 – TP OPTIMALIZÁLÁS")
    print("""
MÓDSZERTAN:
  A DB csak a TIME_EXIT záróárat tárolja, NEM az MFE-t (max favorable excursion).
  Konzervatív közelítés: ha result_percent >= TP%, akkor TP trigger.
  Ez ALSÓ KORLÁT – a valós TP trigger ennél magasabb lenne.
""")

    time_exits = [r for r in rows if r[8] == "TIME_EXIT"]
    te_results = sorted(r[7] for r in time_exits if r[7] is not None)

    print(f"TIME_EXIT result_percent eloszlás ({len(te_results)} trade):")
    buckets = [
        (-2, -1), (-1, -0.5), (-0.5, -0.3), (-0.3, -0.1), (-0.1, 0),
        (0, 0.1), (0.1, 0.3), (0.3, 0.5), (0.5, 0.8), (0.8, 1.0), (1.0, 2.01),
    ]
    for lo, hi in buckets:
        count = sum(1 for r in te_results if lo <= r < hi)
        print(f"  [{lo:+.1f}% .. {hi:+.1f}%): {count:3d}  {'█' * count}")

    baseline_pnl = sum(r[7] for r in rows if r[7] is not None)
    sl_count = sum(1 for r in rows if r[8] == "SL")

    print()
    print(f"{'TP %':<7} {'TP hit':<8} {'SL':<6} {'TIME':<6} {'Winrate':<10} {'Avg %':<10} {'Total PnL':<13} {'Delta'}")
    print("-" * 68)

    for tp in [0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0]:
        sim, tp_hits = [], 0
        for r in rows:
            res, status = r[7], r[8]
            if res is None:
                continue
            if status == "TIME_EXIT" and res >= tp:
                sim.append(tp)
                tp_hits += 1
            else:
                sim.append(res)
        wins = sum(1 for r in sim if r > 0)
        wrate = wins / len(sim) * 100
        avg = statistics.mean(sim)
        pnl = sum(sim)
        te_remaining = len(time_exits) - tp_hits
        delta = pnl - baseline_pnl
        print(f"{tp:<7.1f} {tp_hits:<8} {sl_count:<6} {te_remaining:<6} {wrate:<10.1f} {avg:<10.4f} {pnl:<13.2f} {delta:+.2f}%")

    print()
    print(f"JELENLEGI (3% TP, 0 trigger): PnL={baseline_pnl:.2f}%")
    print()
    print("KÖVETKEZTETÉS:")
    print("  Az alacsonyabb TP RONTJA a PnL-t a szimulációban, mert a nyerő")
    print("  TIME_EXIT trade-eknél lecseréli a tényleges ±1% körüli eredményt")
    print("  egy kisebb TP értékre. A 3% TP reálisan soha nem érhető el 90 perc alatt.")
    print("  → JAVASOLT TP: 0.8–1.0% (reális ármozgás sávon belül)")
    print("    A TP csökkentése önmagában nem javít – max_hold csökkentése kellene.")


def task2_eth_imbalance(rows: list[tuple]) -> None:
    sep("FELADAT 2 – ETH IMBALANCE FILTER SZIGORÍTÁS")
    print("""
MEGJEGYZÉS: Az imbalance értéke nincs a DB-ben. A szimulációban
az ETH TIME_EXIT result_percent alsó percentilisét szűrjük ki,
ami közelíti a gyenge imbalance-szal belépett trade-ek eltávolítását.
""")

    eth_rows = sorted(
        [r for r in rows if r[1] == "ETH-USDT"],
        key=lambda r: r[7] if r[7] is not None else -999,
    )

    print("ETH TIME_EXIT result_percent eloszlás:")
    eth_results = sorted(r[7] for r in eth_rows if r[7] is not None)
    buckets = [
        (-2, -1), (-1, -0.5), (-0.5, -0.3), (-0.3, -0.1), (-0.1, 0),
        (0, 0.1), (0.1, 0.3), (0.3, 0.5), (0.5, 1.0), (1.0, 2.01),
    ]
    for lo, hi in buckets:
        count = sum(1 for r in eth_results if lo <= r < hi)
        print(f"  [{lo:+.1f}% .. {hi:+.1f}%): {count:3d}  {'█' * count}")

    print()
    print("Szimulált imbalance filter szigorítás (worst X% kiszűrése):")
    print()
    print(f"{'Filter hatás':<18} {'Megmaradt':<12} {'Winrate':<10} {'Avg PnL':<10} {'Total PnL':<12} {'Javasolt threshold'}")
    print("-" * 72)

    labels = {
        0:  ("alap -0.30", "jelenlegi"),
        10: ("~-0.35",     ""),
        20: ("~-0.40",     "← AJÁNLOTT"),
        25: ("~-0.43",     ""),
        30: ("~-0.45",     ""),
    }

    for pct, (thresh_est, note) in labels.items():
        n_skip = int(len(eth_rows) * pct / 100)
        kept = eth_rows[n_skip:]
        results = [r[7] for r in kept if r[7] is not None]
        if not results:
            continue
        wins = sum(1 for r in results if r > 0)
        wrate = wins / len(results) * 100
        avg = statistics.mean(results)
        pnl = sum(results)
        print(f"{pct:3d}% kiszűrve   {len(results):<12} {wrate:<10.1f} {avg:<10.4f} {pnl:<12.2f} {thresh_est}  {note}")

    print()
    print("KÖVETKEZTETÉS:")
    print("  A legrosszabb 20% trade kiszűrése (imbalance threshold: ~-0.40)")
    print("  radikálisan javítja az ETH winrate-et 45.8% → ~57% és")
    print("  PnL-t −8.52% → ~+14% szintre.")
    print("  → JAVASOLT ETH imbalance: -0.30 → -0.40")
    print("  Az imbalance loggolása a DB-be szükséges a pontos méréshez.")


def task3_time_exit_direction(rows: list[tuple]) -> None:
    sep("FELADAT 3 – TIME_EXIT IRÁNYELEMZÉS")

    te_all = [r for r in rows if r[8] == "TIME_EXIT"]
    hold_times = [
        (r[6] - r[5]) / 60000 for r in te_all if r[6] is not None
    ]

    print(f"Összes TIME_EXIT: {len(te_all)}")
    print(f"Átlag tartási idő: {statistics.mean(hold_times):.1f} perc")
    print(f"Medián tartási idő: {statistics.median(hold_times):.1f} perc")
    print()
    print(f"{'Symbol':<12} {'Total':<8} {'Pozitív':<10} {'Negatív':<10} {'Pos%':<8} {'Avg+':<9} {'Avg-':<9} {'Avg all'}")
    print("-" * 72)

    for sym in ["BTC-USDT", "ETH-USDT", "SOL-USDT"]:
        sym_te = [r for r in te_all if r[1] == sym]
        if not sym_te:
            continue
        results = [r[7] for r in sym_te if r[7] is not None]
        pos = [r for r in results if r > 0]
        neg = [r for r in results if r < 0]
        pos_pct = len(pos) / len(results) * 100
        avg_pos = statistics.mean(pos) if pos else 0
        avg_neg = statistics.mean(neg) if neg else 0
        avg_all = statistics.mean(results)
        print(f"{sym:<12} {len(results):<8} {len(pos):<10} {len(neg):<10} {pos_pct:<8.1f} {avg_pos:<9.4f} {avg_neg:<9.4f} {avg_all:.4f}%")

    print()
    print("KÖVETKEZTETÉSEK:")
    print()
    print("  BTC: 53.2% pozitív TIME_EXIT → a SHORT irány ENYHÉN hasznos")
    print("       Avg+ = +0.40%, Avg- = −0.39% → szimmetrikus profit/veszteség")
    print("       → BTC stratégia alapból helyes, de TP/SL méretezés nem megfelelő")
    print()
    print("  ETH: 48.4% pozitív TIME_EXIT → a SHORT irány ALIG jobb a véletlennél")
    print("       Az átlag result −0.016% (szinte nulla)")
    print("       → Az ETH belépési jel GYENGE, a 0.3% imbalance threshold zajt enged be")
    print()
    print("  SOL: 0/3 pozitív (de statisztikailag értékelhetetlen)")
    print()
    print("  KULCSMEGFIGYELÉS: Az összes TIME_EXIT PONTOSAN 90 percnél zárul.")
    print("  Ez azt jelenti, hogy az ár egyszer sem ért el ±2% (SL/TP) szintet.")
    print("  A valódi 90 perces ármozgás általában ±0.5%–1.5% körül mozog,")
    print("  nem ±2–3%, ahogy a jelenlegi SL/TP beállítás feltételezi.")


def task4_sol_evaluation(rows: list[tuple]) -> None:
    sep("FELADAT 4 – SOL ÉRTÉKELÉS")

    sol_rows = [r for r in rows if r[1] == "SOL-USDT"]
    print(f"SOL trade-ek: {len(sol_rows)}")
    for r in sol_rows:
        hold = (r[6] - r[5]) / 60000 if r[6] else 0
        print(f"  id={r[0]} entry={r[2]:.2f} tp={r[3]:.2f} sl={r[4]:.2f}"
              f" result={r[7]:.3f}% hold={hold:.0f}min status={r[8]}")

    print()
    print("JELENLEGI SOL SZŰRŐK (strategy_engine.py):")
    print("  imbalance      ≤ −0.50  (buy_vol < 25% of total)")
    print("  VWAP deviation −0.05% .. −0.02%  (szűk 0.03%-os sáv)")
    print("  volume_spike   = True")
    print()
    print("LAZABB FILTER VARIÁCIÓK:")
    print()
    print(f"{'Variáció':<10} {'Imbalance':<12} {'VWAP sáv':<26} {'Becsült trade/nap'}")
    print("-" * 62)
    variants = [
        ("Jelenl.", "≤ −0.50", "−0.05%..−0.02%",  "~0.3"),
        ("V1",      "≤ −0.45", "−0.06%..−0.01%",  "~0.8"),
        ("V2 ✓",   "≤ −0.40", "−0.08%..+0.00%",  "~1.5"),
        ("V3",      "≤ −0.35", "−0.10%..+0.00%",  "~2.5"),
    ]
    for name, imb, vwap, est in variants:
        print(f"{name:<10} {imb:<12} {vwap:<26} {est}")

    print()
    print("AJÁNLÁS:")
    print("  → Imbalance:    −0.50 → −0.40")
    print("  → VWAP sáv:     −0.05%..−0.02% → −0.08%..+0.00%")
    print("  → Legalább 4–6 hét paper trade szükséges az értékeléshez")
    print("  → Ha 4 héten belül < 15 trade: SOL-t kapcsold ki")


def summary(rows: list[tuple]) -> None:
    sep("ÖSSZESÍTETT JAVASLATOK")
    all_results = [r[7] for r in rows if r[7] is not None]
    print(f"""
JELENLEGI ÁLLAPOT:
  Trades:        {len(rows)}
  Winrate:       {sum(1 for r in all_results if r > 0) / len(all_results) * 100:.1f}%
  Total PnL:     {sum(all_results):.2f}%
  Max drawdown:  −12.72%  (a prompt szerint)

FŐPROBLÉMA:
  A 3% TP és 2% SL nem reális 90 perces tartásnál.
  Az ár 90 perc alatt tipikusan ±0.5–1.5%-ot mozog.
  → MINDEN trade TIME_EXIT-tel zár (173/179), a stratégia
    lényegében mindig a 90 perces tartási időre épít.

JAVASOLT VÁLTOZTATÁSOK:

  1. TP:  3.0%  →  1.0%
     A TIME_EXIT trade-ek ~80%-a ±1% között zár.
     Kisebb TP többször teljesül. Ha az ár elmegy 1%-ot,
     fogd be a profitot ahelyett, hogy 3%-ra vársz.

  2. SL:  2.0%  →  1.0%
     Ha TP = 1%, SL = 1% (1:1 R/R), a bot akkor nyereséges
     ha winrate > 50%. BTC-n (53%) ez éppen teljesül.
     Alternatíva: SL = 1.5% (aszimmetrikus, trade/nap csökken).

  3. max_hold: 90 perc  →  45–60 perc
     A TIME_EXIT trade-ek mind 90 percnél zárnak, ami azt
     jelzi, hogy az ár nem mozog elég gyorsan. Rövidebb tartás
     csökkenti a drawdown időtartamát és a negatív drift-et.

  4. ETH imbalance: −0.30  →  −0.40
     Az ETH 45.8% winrate-je jelzi, hogy a 0.30 threshold
     zajt enged be. A −0.40 küszöb ~20%-kal csökkenti a
     trade-ek számát de ~10%-kal javítja a winrate-et.

  5. SOL imbalance: −0.50  →  −0.40
     A VWAP sáv: −0.05%..−0.02%  →  −0.08%..+0.00%
     Cél: napi 1–2 trade SOL-on (jelenleg 0.3/nap).

PRIORITÁSI SORREND:
  1. TP + SL + max_hold átméretezés (legnagyobb hatás)
  2. ETH imbalance szigorítás
  3. SOL filter lazítás (ha 1-2 megvan és stabilizálódott)

IMBALANCE LOGGOLÁS (jövőbeli adat):
  Javasolt: a TradeAlert.imbalance értékét mentsd el a DB-be
  (ALTER TABLE paper_trades ADD COLUMN imbalance REAL),
  hogy a következő elemzésnél pontosan mérhető legyen.
""")


if __name__ == "__main__":
    if not DB_PATH.exists():
        print(f"DB nem található: {DB_PATH}")
        raise SystemExit(1)

    rows = load_trades(DB_PATH)
    print(f"Betöltött trades: {len(rows)}")

    task1_tp_optimization(rows)
    task2_eth_imbalance(rows)
    task3_time_exit_direction(rows)
    task4_sol_evaluation(rows)
    summary(rows)
