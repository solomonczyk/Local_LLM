# 📊 Director Daily Report: 2026-01-07

## 📈 Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 70 |
| Director Calls | 70 (100.0% usage) |
| Overrides Applied | 39 |
| Override Rate | 55.7% |
| Override Precision | 100.0% |
| Missed Override Rate | 30.0% |
| Missed Overrides (shadow_mode) | 3 (25.0%) |
| Missed Overrides (risk_gate) | 0 (0.0%) |
| Shadow Soft-Allow Rate | 3/5 (60.0%) |
| Errors | 0 |

## 💰 Economics

| Metric | Value |
|--------|-------|
| Daily Cost | $0.001341 |
| Avg Cost/Call | $0.000019 |
| Budget Status | ✅ Under $0.01 |

## 🎯 Tokens

| Metric | Value |
|--------|-------|
| Avg Tokens/Call | 2430 |
| P50 Tokens | 2378 |
| P95 Tokens | 4313 |
| Target | 1200-1500 |
| Status | ⚠️ Over target |

## ⏱️ Latency

| Metric | Value |
|--------|-------|
| Avg Latency | 2.97s |
| P50 Latency | 2.88s |
| P95 Latency | 4.22s |
| Limit | 6.0s |
| Status | ✅ OK |

## 🔄 Mode Changes (12)

| Time | From | To | Reason |
|------|------|----|---------|
| 14:40:52 | active | shadow | Circuit breaker triggered: override_rate... |
| 14:41:06 | shadow | active | Metrics stabilized (override<0.65, error... |
| 14:44:36 | active | shadow | Circuit breaker triggered: override_rate... |
| 14:44:49 | shadow | active | Metrics stabilized (override<0.65, error... |
| 15:12:07 | active | shadow | Circuit breaker triggered: override_rate... |
| 15:12:26 | shadow | active | Metrics stabilized (override<0.65, error... |
| 15:19:35 | active | shadow | Circuit breaker triggered: override_rate... |
| 15:19:48 | shadow | active | Metrics stabilized (override<0.65, error... |
| 15:24:59 | active | shadow | Circuit breaker triggered: override_rate... |
| 15:25:13 | shadow | active | Metrics stabilized (override<0.65, error... |
| 15:27:18 | active | shadow | Circuit breaker triggered: override_rate... |
| 15:27:31 | shadow | active | Metrics stabilized (override<0.65, error... |

## 🎯 Top Override Reasons

| Reason | Count | % |
|--------|-------|---|
| high_risk | 39 | 100% |

## 📁 Domain Breakdown

| Domain | Calls | Overrides | Override Rate |
|--------|-------|-----------|---------------|
| architect | 16 | 12 | 75% |
| dev | 60 | 33 | 55% |
| qa | 6 | 0 | 0% |
| security | 60 | 39 | 65% |
| ux | 6 | 3 | 50% |

---

## 🔒 Health Status

### Issues Detected:
- ⚠️ 12 mode changes (possible flapping)

---
_Generated: 2026-01-07 15:27:38_
