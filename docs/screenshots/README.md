# HemoFlow UI screenshots

Captured from the real local IRIS application on 2026-10-30. Demo mode is enabled; values are synthetic observations from the seeded institutional simulators, not clinical outcomes. English routes and the white/blood-red theme are active. Exact values and workflow states evolve as the demonstration runs.

| Screen | Capture |
| --- | --- |
| Sign in | [Desktop](login.jpg) |
| Blood Supply Dashboard | [Desktop](dashboard.jpg) · [Mobile](dashboard-mobile.jpg) |
| Blood Center Network | [Desktop](blood-center-network.jpg) |
| Blood Transfers | [Desktop, O− focus](blood-transfers.jpg) |
| Donation Campaigns | [Desktop](donation-campaigns.jpg) · [Planning](campaign-planning.jpg) · [Mobile](campaigns-mobile.jpg) |
| Audit & Analytics | [Desktop](audit-analytics.jpg) |
| IRIS Visual Trace — AI Hub → TransferBPL | [Session 4427](iris-visual-trace-transfer.jpg) |
| IRIS Visual Trace — AI Hub → CampaignBPL | [Session 4480](iris-visual-trace-campaign.jpg) |

The original desktop captures used a 1440 × 1000 responsive test viewport; mobile captures use 390 × 844. During this review, dashboard, network, transfers and campaigns were refreshed with loaded charts using the browser's default desktop layout (1536-pixel-wide captures). Dashboard, transfers and campaigns show the first 1200 pixels of page content; the network capture includes the full page. Audit, campaign planning and mobile views retain their earlier same-day captures. Screenshots retain source metadata, demo notices and the distinction between measured stock, forecasts and hypothetical outcomes. [Demonstration workflow](../DEMONSTRATION.md) · [UI documentation](../UI.md).

## Updated AI Hub workflow traces

The two Visual Trace screenshots were refreshed from the real local Management Portal on 2026-10-30, namespace `USER`, using its printable view. They replace the earlier isolated command captures (2568 and 2284). Sign-in was also captured during this README review; UI capture provenance is described above.

| Workflow | Native session | Business correlation | Checked message headers |
| --- | --- | --- | --- |
| Transfer | 4427 | `67b6a658-02d5-4591-923d-2eb806e9265d` | 32 |
| Campaign | 4480 | `386df328-e3f8-47e0-aff9-d75eaead0304` | 42 |

Both images show `InventoryEventService` → `DecisionBPL` → context preparation → `AIHubDecisionOperation` → `AIReadOperation`, including Java PEX `FederatedInventoryOperation` calls, then the domain guard, selected BPL and initial Workflow approval task. The campaign includes repeated tool reads; tool invocations are not limited to one call per tool.

The transfer portal shows 33 visual items because it also displays an event marker; these are not 33 message headers. The campaign printable view has a fixed-height embedded diagram: its screenshot shows the investigation, routing and approval task, while the final return/alarm continuation is below the frame. All 42 message headers, including the alarm response, are retained in the [complete JSON trace](../orchestration-trace.json).

These are initial decision/proposal sessions, not the entire multi-session lifecycle through receipt or collection. Subsequent approval, dispatch, delivery and outcome commands retain the business correlation. The read-only `tools/test_orchestration.py` check passed again during this review; no LLM workflow was rerun to obtain the captures. Session IDs, application-clock dates and values belong to this synthetic environment.
