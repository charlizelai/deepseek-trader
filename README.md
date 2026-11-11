# deepseek-trader

Paper-trading crypto bot skeleton: **DeepSeek proposes, code disposes.**

The LLM only has "proposal power" — a strictly-schema'd `TradeIntent`
(side / symbol / confidence / reason, no position-size field at all). A
deterministic, hard-coded Risk Engine holds the "veto power" and sits between
the model output and any execution. All trades settle on an in-memory
paper ledger. ccxt is used **read-only** (public market data); this repo never
places a real order.

## Layout

| File | Role |
| --- | --- |
| `config.py` | All hard risk numbers as code constants (never prompt text) |
| `llm_proposal.py` | DeepSeek (beta endpoint, strict mode) -> structured intent |
| `risk_engine.py` | Hard veto: position cap, order cap, daily drawdown, loss streak, SL/TP |
| `paper_exchange.py` | Paper fills; SL/TP exits by price comparison only |
| `main.py` | Fail-closed loop; skips the round if data source fails |

## Hard limits (edit in `config.py`)

- Max single position: 10% of equity
- Max single order: $500
- Daily drawdown circuit breaker: 5% -> no new entries
- Consecutive-loss breaker: 3 losses -> trading paused
- Stop loss 2% attached at entry; take profit 6% (1:3 RR)

## Run

```bash
pip install -r requirements.txt
cp .env.example .env        # add DEEPSEEK_API_KEY
python main.py
```

## Pre-production checklist (before ANY real funds)

1. **Hard veto, not soft advice** — temporarily set `MAX_ORDER_USD=50`,
   confirm the RiskEngine trims the approved amount instead of the model's wish.
2. **Loss-streak breaker** — temporarily set `MAX_CONSECUTIVE_LOSSES=1`,
   trigger one stop-loss, confirm the next `evaluate()` returns `allowed=False`.
3. **Fail-closed on data loss** — make `fetch_snapshot` raise, confirm the loop
   skips the round instead of trading on stale/reconstructed data.

Only after all three pass: swap `paper_exchange` for an exchange **sandbox**,
run with minimal funds, then scale gradually. The risk constants are designed
to protect real money — don't loosen them to "test faster".

## Production hardening roadmap

- WebSocket price feed instead of 1-minute REST polling
- Persist state (SQLite) so restarts don't wipe the ledger
- Docker + healthcheck for unattended runs
- Exchange testnet mode behind an explicit `LIVE=false` flag

## Disclaimer

Educational software. **No profitability is implied or guaranteed.**
This code does not execute real trades. Do not connect real funds without
independent review; automated crypto trading involves substantial risk of
total loss including liquidation in leveraged settings.
