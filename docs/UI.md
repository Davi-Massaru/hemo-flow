# HemoFlow user interface

The application defaults to English and uses **Blood center network** as its network terminology. It retains Flask SSR, IRIS WSGI, CSRF protection, institution scopes, FHIR resource contracts, AI Hub decision enums and human approval workflows. Canonical routes are `/dashboard`, `/blood-center-network`, `/blood-transfers`, `/donation-campaigns` and `/audit-analytics`, under `/csp/hemoflow`. Previous Portuguese routes redirect permanently and preserve query parameters. Login identifiers remain stable.

## Visual system

`web/static/app.css` is the single theme source. Primary `#C8102E`, background `#FFFFFF`, surface `#F8FAFC`, text `#172033`. Shared tokens cover secondary text, borders, alerts, chart colors, typography and spacing. White text on primary red has approximately 5.9:1 contrast; primary actions are solid red. Critical messages use a dark red border, pale background, an exclamation mark and an alert role. Demo notices are amber and are conditional on demo mode.

Navigation, forms, cards, tables and charts adapt at 1200, 950 and 650 pixels. Keyboard focus is visible; navigation includes a skip link and current-page semantics. ECharts uses SVG, ARIA descriptions and patterned forecast series. Each chart has a keyboard-accessible data table. Reduced-motion preferences disable chart animation.

## Language resources

All application presentation copy lives in `web/static/locales/en.json`, loaded by `python/hemoflow/ui.py` and `web/static/app.js`. `copy.*` keys retain the existing screen content; semantic keys cover navigation, charts, statuses and new UI. Jinja uses `t()`, `label` and `display_name`. Existing seeded names are mapped for display; new seed names are English. Login IDs such as `gestor-a`, domain identifiers, FHIR values and raw audit evidence are intentionally preserved. New AI decision reasons are requested in English. Historical source evidence is not rewritten.

## Local chart assets

Apache ECharts **5.6.0** is the only charting library. `package-lock.json` pins installation. Run `npm ci --ignore-scripts` then `npm run vendor` to regenerate `web/static/vendor/echarts/echarts.min.js`, LICENSE and NOTICE. Docker copies these local assets; Node and npm are not runtime requirements. No CDN, frontend framework or chart-specific dependency is required. The existing self-only CSP remains in effect.

## Data pipeline and permissions

`GET /api/analytics/<page>?center=ALL&days=30&blood_type=O%2B` returns chart projections. Valid pages: `panel`, `network`, `transfers`, `campaigns`, `audit`. Periods: 7, 30, 90 and 180 days. Blood types: O−, O+, A−, A+, B−, B+, AB− and AB+; campaigns and audit also accept `ALL`. URL-encode plus signs. The HTTP layer authenticates the session, and `AnalyticsOperation` re-resolves the actor and enforces role/scope checks before reading IRIS. It runs alongside the existing Production operations; **no extra SQL grants are added to the web role**. Charts do not invoke the LLM or change inventory/workflows. Federated reads and analytics requests use the existing interoperability trace infrastructure.

Admin and auditor analytics use network scope; manager workflow/history data is institution scoped. Managers retain the network stock visibility needed for redistribution. Partners see their campaign cohort and donors see only linked campaign schedules; inventory and audit charts are denied. Reads are bounded to 1,000 recent records per entity and the UI discloses this limitation.

Demo-marked records are excluded when `HEMOFLOW_DEMO` is off, including old fixture IDs, demo center decision scopes and demo events. Demo-trained predictions are suppressed outside demo mode when seeded consumption history is present. Chart metadata always identifies demo mode. The UI never creates random or fallback demonstration series.

| Screen | Charts and sources |
| --- | --- |
| Blood Supply Dashboard | Five summary indicators; stock vs seven-day IntegratedML forecast; FEFO stock/shortage trajectory; eight-type distribution; expiry exposure; network matrix; pending action links and source timestamps. Live federated FHIR, ConsumptionDaily and the trained IRIS model. |
| Blood Center Network | Available/transferable heatmap and blood type comparison. Live federated FHIR. |
| Blood Transfers | Current shortage vs hypothetical requested receipt; recorded transfer events; current transferable expiry distribution. FHIR, IntegratedML, Transfer and EventAudit. |
| Donation Campaigns | Matched historical conversion cohort, recorded outcomes and planned schedule. Planning cards expose need, expected release, approval responsibility and persisted Vector Search evidence. Separate invitation consent and completed outcome sections. CampaignExperience and scoped Campaign records. |
| Audit & Analytics | Seven-day actual/predicted validation consumption, decision distribution and recorded operational counts. DemandFeature/PREDICT, DecisionAudit and delivery transition events. |

## Interpretation rules

- The application supports eight ABO/Rh groups for **red blood cells only**. Inventory queries, reservations, shipments, receipts, campaigns and consumption history carry the exact requested group. No compatibility calculation or group substitution is performed. Legacy records default to O−. Existing FHIR component codes and AI decision enums remain unchanged; the product coding identifies the selected blood group.
- Unreachable institutions remain missing; no zero substitution. Totals explicitly cover reachable sources. Numeric zero means an observed zero.
- Baseline estimates are never labelled AutoML. Unavailable model predictions remain empty.
- Stock is a current observation. Forecasts span seven future days. The period filter affects historical charts, not the inventory observation time.
- The seven-day trajectory allocates the model's total demand evenly across seven daily FEFO steps; this is a derived simulation, not a separately trained daily forecast. Transfer “after” values require a reachable source and sufficient current transferable stock, respect arrival lead time and expiry, and remain hypothetical. Same-day receipts enter the first applicable interval. Insufficient/unavailable evidence leaves the after-value missing. Delivered transfers are excluded to avoid double counting. Current stock may no longer include reserved/shipped units, so an unavailable after-projection is not evidence that an approved shipment was cancelled.
- Expiry charts show current transferable source buckets, not shipment-level expiry or avoided waste. The current application does not retain a shipment expiry history.
- The funnel uses a historical cohort with all five stages reported. Invited/attended are people; collected/released/used are RBC units. No cross-unit percentage is calculated; missing attendance is not invented. Completed campaigns are indexed with actual recorded metrics and real embeddings; indexing failures are audited separately.
- Campaign schedule dates are planned windows, including the same selected number of days into the future. Expected release is not stock.
- Actual/predicted consumption is retrospective chronological holdout evaluation, not historical forecast issuance. Censored labels remain excluded.
- Timelines use recorded events only. Missing event dates are never invented and missing days are not interpolated.

All charts include source, unit, reporting period, refresh timestamp, interpretation notes, legends/tooltips where applicable, filters, loading/empty/error states and retry. Source timestamps remain available in analytics observation metadata.

## Verification and screenshots

Run the native suite using `tools/test.script`, then `python3 /opt/hemoflow/tools/test_ui_http.py` inside the IRIS container. Tests cover authentication, five SSR pages, all 16 chart specifications, local assets, unchanged form enum values, invalid filters and role boundaries. `tests/test_analytics.py`, `tests/test_projections.py` and `tests/test_simulator.py` cover missing stock, baseline exclusion, demo isolation, same-day receipt arithmetic and blood-group isolation through reservation, dispatch and receipt.

## Implementation map

| Responsibility | Files |
| --- | --- |
| Routes, authorization, SSR | `python/hemoflow/web.py`, `web/templates/` |
| Language and design | `python/hemoflow/ui.py`, `web/static/locales/en.json`, `web/static/app.css` |
| Shared chart rendering | `web/templates/charts.html`, `web/static/app.js`, `web/static/vendor/echarts/` |
| Analytics and projection | `python/hemoflow/analytics.py`, `python/hemoflow/projections.py`, `iris/HemoFlow/AnalyticsOperation.cls` |
| Exact product identity | `python/hemoflow/products.py`, `fhir.py`, `federation.py`, `service.py`, `simulators/center.py` |
| Historical features and seed migration | `python/hemoflow/intelligence.py`, `demo.py`, `iris/HemoFlow/ConsumptionDaily.cls`, `iris/HemoFlow/DemandFeature.cls`, `tools/migrate_multitype.script` |

Seed version 2 extends the original owned dataset additively: 3 centers × 8 groups × 180 days = 4,320 consumption observations and 72 initial historical experiences. Migration snapshots are saved before changes. A completed migration is idempotent and does not reset subsequent workflows. The active pooled AutoML model uses features derived independently per center/group; the legacy model remains available. Demo restore is a separate explicit operation that closes open synthetic plans and preserves the audit ledger.

The two persistent history classes include explicit storage maps. The migration detects the original v1 consumption layout by its exact owned identifier and date, backs it up, remaps the original values and retrains derived features. Unexpected layouts are rejected. `tools/verify_products.script` validates real AutoML inference for all 24 center/group pairs and checks seed idempotency.

Screenshots in `docs/screenshots/` capture the real local application with seeded IRIS data. They are visual evidence of the demo UI, not clinical outcomes.

References: [ECharts accessibility](https://echarts.apache.org/handbook/en/best-practices/aria/), [responsive chart sizing](https://echarts.apache.org/handbook/en/concepts/chart-size/).
