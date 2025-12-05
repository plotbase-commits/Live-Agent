---
description: Logika dennej agregácie štatistík agentov (Daily Stats Aggregation)
---

# Daily Stats Aggregation - Logika

## Prehľad

Daily Stats Aggregation je proces, ktorý agreguje denné štatistiky výkonu agentov z `Raw_Tickets` sheetu a ukladá ich do `Daily_Stats` sheetu. Beží automaticky každý pracovný deň o 17:00.

---

## 1. Kedy beží

| Parameter | Hodnota |
|-----------|---------|
| **Job ID** | `aggregation_job` |
| **Názov** | Daily Stats Aggregation |
| **Čas** | Pon-Pia o 17:00 |
| **Trigger** | CronTrigger |

**Kód v `scheduler.py`:**
```python
self.scheduler.add_job(
    aggregation_func,
    CronTrigger(
        day_of_week='mon-fri',
        hour=17,
        minute=0
    ),
    id="aggregation_job",
    name="Daily Stats Aggregation",
)
```

---

## 2. Vstupné dáta (Raw_Tickets)

Agregácia číta zo sheetu `Raw_Tickets` s týmito stĺpcami:

| Stĺpec | Použitie v agregácii |
|--------|---------------------|
| `Date_Changed` | Grupovanie podľa dňa (YYYY-MM-DD) |
| `Agent` | Grupovanie podľa agenta |
| `QA_Data` | JSON s hodnoteniami (overall_score, empathy, expertise, verbal_summary) |
| `Is_Critical` | Počítanie kritických tiketov |

---

## 3. Výstupné dáta (Daily_Stats)

Agregované dáta sa ukladajú do `Daily_Stats` sheetu:

| Stĺpec | Typ | Popis |
|--------|-----|-------|
| `Date` | TEXT | Dátum (YYYY-MM-DD) |
| `Agent` | TEXT | Meno agenta |
| `Avg_Score` | NUMBER | Priemerné QA skóre (0-100) |
| `Critical_Count` | NUMBER | Počet kritických tiketov |
| `Avg_Empathy` | NUMBER | Priemerné skóre empatie |
| `Avg_Expertise` | NUMBER | Priemerné skóre odbornosti |
| `Verbal_Summary` | TEXT | Posledné slovné zhrnutie |

---

## 4. Logika agregácie

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGREGAČNÝ PROCES                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Načítaj všetky záznamy z Raw_Tickets                                    │
│                                                                             │
│  2. Pre každý záznam:                                                       │
│     a) Extrahuj dátum z Date_Changed (YYYY-MM-DD)                           │
│     b) Extrahuj meno agenta                                                 │
│     c) Parsuj QA_Data JSON                                                  │
│                                                                             │
│  3. Grupuj podľa (Date, Agent)                                              │
│                                                                             │
│  4. Pre každú skupinu vypočítaj:                                            │
│     - Avg_Score = SUM(overall_score) / COUNT                                │
│     - Avg_Empathy = SUM(empathy) / COUNT                                    │
│     - Avg_Expertise = SUM(expertise) / COUNT                                │
│     - Critical_Count = COUNT(Is_Critical = TRUE)                            │
│     - Verbal_Summary = posledné verbal_summary zo skupiny                   │
│                                                                             │
│  5. Ulož do Daily_Stats (s deduplikáciou)                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 5. Deduplikácia

Pri zápise do `Daily_Stats` sa existujúce záznamy pre rovnakú kombináciu **(Date, Agent)** prepíšu novými hodnotami.

**Logika v `sheets_manager.py`:**
```python
def update_daily_stats(self, new_stats):
    # Vytvor set kľúčov (Date, Agent) z nových dát
    keys_to_update = set((row[0], row[1]) for row in new_stats)
    
    # Odfiltruj staré záznamy s rovnakými kľúčmi
    filtered_rows = [row for row in existing if (row[0], row[1]) not in keys_to_update]
    
    # Spoj staré (nekonfliktné) + nové
    final_rows = [headers] + filtered_rows + new_stats
    
    # Prepíš sheet
    ws.clear()
    ws.update("A1", final_rows)
```

---

## 6. Parsovanie QA_Data

`QA_Data` je JSON stĺpec s touto štruktúrou:

```json
{
  "overall_score": 85,
  "criteria": {
    "empathy": 90,
    "expertise": 80,
    "response_time": 85,
    "solution_quality": 85
  },
  "verbal_summary": "Agent bol profesionálny a empatický..."
}
```

**Extrahovanie hodnôt:**
```python
qa_data = json.loads(row.get("QA_Data", "{}"))
score = qa_data.get("overall_score", 0)
criteria = qa_data.get("criteria", {})
empathy = criteria.get("empathy", 0)
expertise = criteria.get("expertise", 0)
summary = qa_data.get("verbal_summary", "")
```

---

## 7. Príklad

### Vstup (Raw_Tickets):
| Date_Changed | Agent | Is_Critical | QA_Data |
|--------------|-------|-------------|---------|
| 2025-12-05 10:30:00 | Marika | FALSE | {"overall_score": 90, "criteria": {"empathy": 95, "expertise": 85}} |
| 2025-12-05 14:20:00 | Marika | FALSE | {"overall_score": 80, "criteria": {"empathy": 85, "expertise": 75}} |
| 2025-12-05 11:00:00 | Peter | TRUE | {"overall_score": 60, "criteria": {"empathy": 50, "expertise": 70}} |

### Výstup (Daily_Stats):
| Date | Agent | Avg_Score | Critical_Count | Avg_Empathy | Avg_Expertise |
|------|-------|-----------|----------------|-------------|---------------|
| 2025-12-05 | Marika | 85.0 | 0 | 90.0 | 80.0 |
| 2025-12-05 | Peter | 60.0 | 1 | 50.0 | 70.0 |

---

## 8. Manuálne spustenie

Agregáciu je možné spustiť manuálne cez UI:

**Settings page → Daily Stats Aggregation → "Run Daily Stats Now"**

```python
# pages/Settings.py
if st.button("Run Daily Stats Now"):
    with st.spinner("Aggregating Daily Stats..."):
        analysis_service.run_daily_aggregation()
```

---

## 9. Chybové stavy

| Chyba | Príčina | Riešenie |
|-------|---------|----------|
| "No data in Raw_Tickets" | Sheet je prázdny | Spusti najprv ETL |
| "Failed to connect" | Google Sheets nedostupné | Skontroluj credentials |
| JSON parse error | Poškodený QA_Data | Skontroluj AI Analysis output |

---

## 10. Súvisiace súbory

| Súbor | Funkcia |
|-------|---------|
| `src/backend.py` | `AnalysisService.run_daily_aggregation()` |
| `src/scheduler.py` | `SchedulerService.add_daily_aggregation_job()` |
| `src/sheets_manager.py` | `SheetSyncManager.update_daily_stats()` |
| `pages/Settings.py` | UI pre manuálne spustenie |

---

## 11. Závislosť na iných procesoch

```
ETL Cycle → AI Analysis → Daily Stats Aggregation
    ↓              ↓                  ↓
Raw_Tickets   QA_Data filled    Daily_Stats updated
```

Daily Stats vyžaduje aby boli tikety:
1. ✅ Stiahnuté (ETL)
2. ✅ Analyzované (AI Analysis) - aby mali QA_Data

---

*Posledná aktualizácia: 2025-12-05*
