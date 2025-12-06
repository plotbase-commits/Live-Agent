---
description: Logika hodnotenia agentov na dashboarde - výpočty, ikony, metriky
---

# Hodnotenie agentov - Logika

## Prehľad

Dashboard zobrazuje mesačné hodnotenia agentov na základe AI analýzy ich tiketov.

---

## 1. Zdroj dát

```
Google Sheets: "LiveAgent Tickets"
Sheet: "Raw_Tickets"
Filter: Date_Changed[:7] == aktuálny mesiac
```

### Relevantné stĺpce

| Stĺpec | Použitie |
|--------|----------|
| `Agent` | Grupovanie (skip "Nepriradený", "Unknown") |
| `Date_Changed` | Filter aktuálneho mesiaca |
| `QA_Data` | JSON s hodnoteniami |
| `Is_Critical` | Počítanie kritických tiketov |

### Štruktúra QA_Data

```json
{
  "overall_score": 85,
  "criteria": {
    "empathy": 90,
    "expertise": 80,
    "problem_solving": 85,
    "error_rate": 5
  },
  "verbal_summary": "Agent bol profesionálny..."
}
```

---

## 2. Agregácia per agent

```python
agent_stats[agent] = {
    "tickets": int,            # Všetky tikety
    "analyzed_tickets": int,   # Tikety s QA_Data
    "total_score": float,      # Suma overall_score
    "critical_count": int,     # Počet Is_Critical=TRUE
    "criteria": {              # Priemery kritérií
        "empathy": float,
        "expertise": float,
        "problem_solving": float,
        "error_rate": float
    },
    "summaries": list          # Všetky verbal_summary
}
```

---

## 3. Výpočty

### Per-agent metriky

```python
# Priemerné skóre (len z analyzovaných tiketov!)
avg_score = total_score / analyzed_tickets

# Kritický pomer
critical_ratio = critical_count / tickets  # 0.0 - 1.0

# Kritériá (priemer zo všetkých hodnotení)
empathy_avg = sum(empathy_values) / len(empathy_values)
```

### Globálne metriky

```python
# Váhovaný priemer (podľa počtu tiketov, nie agentov)
global_avg = sum(all_total_scores) / sum(all_analyzed_tickets)

# Toto je SPRÁVNE:
# Agent A: 100 tiketov, suma 8500 → avg = 85
# Agent B: 10 tiketov, suma 600 → avg = 60
# Globálny: (8500 + 600) / (100 + 10) = 82.7%

# NESPRÁVNE by bolo:
# (85 + 60) / 2 = 72.5% ← agent B má neprimeraný vplyv
```

---

## 4. Vizuálna logika

### Ikona a farba

| Podmienka | Ikona | Farba | Hex |
|-----------|-------|-------|-----|
| critical_ratio > 10% | 🚨 | Červená | #ff4b4b |
| critical_ratio > 5% | ⚠️ | Oranžová | #ffaa00 |
| score ≥ 80 | ✅ | Zelená | #00cc66 |
| score ≥ 60 | ⚠️ | Oranžová | #ffaa00 |
| score < 60 | 🔴 | Červená | #ff4b4b |

**Priorita:** Critical ratio má prednosť pred skóre!

### Príklady

```
Adam: score=85, critical_ratio=0.12 (12%)
→ 🚨 (critical > 10% overrides score)

Boris: score=70, critical_ratio=0.02 (2%)
→ ⚠️ (score 60-79)

Cyril: score=85, critical_ratio=0.01 (1%)
→ ✅ (score ≥ 80, low critical)
```

---

## 5. Agent Card

```
┌────────────────────────────────────────┐
│ ✅ Adam Novák                          │  ← Ikona + meno
│ Analyzed: 15/18 | Critical: 1 (6%)     │  ← Pomer + kritické
├────────────────────────────────────────┤
│ ▓▓▓▓▓▓▓▓░░░░░░░░ 82%                  │  ← Progress bar
│ Overall Score: 82%                     │
├────────────────────────────────────────┤
│ [Bar Chart: empathy, expertise, ...]   │  ← Kritériá
├────────────────────────────────────────┤
│ [📝 Latest Summary] ▼                  │  ← Expandér
└────────────────────────────────────────┘
```

---

## 6. Globálne metriky (horný panel)

| Metrika | Výpočet |
|---------|---------|
| 👥 Agents | `len(agent_stats)` |
| 🎫 Tickets Analyzed | `{analyzed}/{total}` |
| 🔴 Critical Issues | `sum(critical_count)` |
| 📈 Avg Score | Váhovaný priemer |

---

## 7. Filtrovanie

### Mesačné

```python
current_month = datetime.now().strftime("%Y-%m")  # "2024-12"
row_month = date_changed[:7]

if row_month != current_month:
    continue  # Skip
```

### Agent

```python
if agent in ["Unknown", "Nepriradený", "", None]:
    continue  # Skip
```

---

## 8. Zoradenie

```python
agents = sorted(agent_stats.keys())  # Abecedne
```

---

## 9. Súvisiace súbory

| Súbor | Funkcia |
|-------|---------|
| `Home.py` | `load_agent_stats()` - agregácia |
| `Home.py` | `get_status_icon()` - ikona |
| `Home.py` | `get_status_color()` - farba |
| `Home.py` | `create_agent_card()` - UI |
| `src/ai_service.py` | Generuje QA_Data |

---

## 10. Potenciálne problémy

### Riešené
- ✅ avg_score delilo všetkými tiketmi (opravené: len analyzed)
- ✅ has_critical binárne (opravené: critical_ratio)
- ✅ Globálny avg nevážený (opravené: váhovaný)
- ✅ Žiadny mesačný filter (opravené: current_month)
- ✅ Náhodné poradie (opravené: abecedne)

### Potenciálne zlepšenia
- Trend vs minulý mesiac (▲▼)
- Drill-down na jednotlivé tikety
- Export do PDF

---

*Posledná aktualizácia: 2024-12-06*
