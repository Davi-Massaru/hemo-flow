# HemoFlow demonstration

Use the local application at `http://localhost:52774/csp/hemoflow/dashboard`. All demonstration records are synthetic, served by IRIS and three independent institutional simulators. Leave demo mode enabled for this walkthrough. The public demo password is documented in the README; never use it outside the demo.

## Walkthrough

1. Sign in as `gestor-a`. On **Blood Supply Dashboard**, select Aurora Blood Center and change **Focus blood type** between O− and A+. Compare confirmed usable stock, seven-day forecast, FEFO deficit, 72-hour expiry exposure and reachable centers. Inspect the eight-type distribution and network heatmap. Open a chart's accessible table and source evidence. The daily trajectory is a simulation derived from the total forecast, not seven independent predictions.
2. Open **Blood Center Network**. Compare all eight groups across the three centers. Availability belongs to each institution. A missing source appears as not reported, never zero. Changing filters only reads data; it does not reserve units.
3. Open **Blood Transfers**. Inspect the requested group, source, destination, required-by time, hypothetical shortage and recorded timeline. With a pending source request, sign in as its source manager, confirm handling, approve and dispatch. Sign in as the target manager and confirm receipt. A received unit is not automatically a used unit. When source availability cannot support a projection, the hypothetical result remains missing.
4. Open **Donation Campaigns**, selecting all groups when comparing activities. Read **Planning & expected supply**, then inspect the required-by date, proposed window, expected release, next responsible actor and stored similar-campaign evidence. A center manager authorizes the plan; the named partner accepts its invitation. Interest does not establish eligibility or available blood. After processing, record actual attendance and collection/release/use counts, or use the explicitly labelled demo simulation. Completed results feed the searchable campaign history; missing attendance is not fabricated for the funnel.
5. Sign in as `auditor` for **Audit & Analytics**. Compare actual vs predicted consumption on chronological holdout data, AI Hub decision distribution and recorded operational trends. Correlations link to retained source evidence. MAE on synthetic data is not clinical validation.

## Controlled workflow scenarios

Administrator dashboard controls generate the original O− scenarios: transfer, future campaign, sufficient coverage, expiry constraints, remote unavailability, shortage, declined supply and expired invitation. These controls restore owned inventory snapshots and close open synthetic plans; run them before a presentation, not while another person is approving a plan. They retain the audit and invitation ledger. Other groups remain available for independent analysis and real exact-group workflows.

For automated acceptance:

```powershell
Get-Content tools/test.script | docker compose exec -T iris iris session IRIS -U USER
docker compose exec -T iris python3 /opt/hemoflow/tools/test_ui_http.py
Get-Content tools/demo_e2e.script | docker compose exec -T iris iris session IRIS -U USER
```

The final command invokes the real configured AI Hub model and may incur API costs. It exercises transfer, campaign, NO_ACTION, refusal, expiry, automatic TTL and safe restoration. Results are stored under `/durable/hemoflow-evidence`. Seed installation/migration is idempotent and preserves later activity; restoration is a separate action.

After acceptance, `tools/prepare_demo_presentation.script` verifies an A+ transfer without changing O− stock, then prepares a real pending campaign and a pending A+ transfer. It uses the real AI Hub, restores owned demo stock and closes previous open demo plans. Use it only when preparing an isolated presentation, with the same execution pattern as the other `.script` files. It preserves the audit trail and records its results in `presentation-acceptance.json`.

## Presentation checklist

- Show the demo notice, source timestamp, measurement unit and period before interpreting a chart.
- Show the difference between confirmed stock, forecast and hypothetical receipt.
- Show institutional approval and the audit correlation for both workflows.
- Use actual UI states; do not describe cancelled/expired plans as active.
- Use the canonical English URLs. Old Portuguese bookmarks redirect with their query filters preserved.

See [UI implementation and interpretation rules](UI.md) and [screenshots](screenshots/README.md).
