# UI validation — 2026-10-30

The final local Docker build completed successfully. All four HemoFlow services are healthy; no obsolete project containers remain. The Blood Supply Dashboard is open in the application browser.

## Verified results

- 44 native tests passed.
- All 12 end-to-end acceptance scenarios passed, including transfers, campaigns, offline centers, expiry, rejection, invitation TTL and safe restoration.
- HTTP validation passed for all 16 charts across the five screens, local assets, forms, access controls, English routes and multitype projections.
- All 24 center/blood-type combinations returned IntegratedML forecasts without quality flags; seed idempotency passed.
- A real demonstration A+ transfer delivered seven units without changing O-negative inventory; a completed campaign was indexed for evidence retrieval.
- Desktop and mobile layouts were inspected, including chart loading completion and horizontal overflow checks.

## Delivered behavior

English navigation and canonical URLs use the centralized white and blood-red design system. The locally served Apache ECharts components expose source, unit, period and update metadata. Confirmed stock, forecasts and hypothetical transfer effects remain distinguishable. Unreachable centers are represented as unavailable, never as zero stock.

The demonstration seed covers eight blood types and 4,320 consumption observations. Synthetic observations are restricted to demo mode. Forecast validation metrics describe this demonstration dataset, not clinical validation. Seven-day projections distribute the model total over the horizon and account for expiry; they are not daily AutoML predictions.

## Evidence and walkthrough

- [UI architecture and routes](UI.md)
- [Demonstration walkthrough](DEMONSTRATION.md)
- [Desktop and mobile screenshots](screenshots/README.md)
- [Native test status](native-test-status.json)
- [End-to-end acceptance](demo-acceptance.json)
- [Multitype transfer and presentation acceptance](presentation-acceptance.json)
- [Final 24 forecasts](product-forecasts.json)

Controlled demonstration workflows were exercised before the final rebuild. The final rebuild was followed by native tests, HTTP checks and forecast/seed verification; it did not repeat workflow mutations. Audit records and demonstration evidence were preserved.
