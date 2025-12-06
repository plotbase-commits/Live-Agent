---
description: Prehľad architektúry a všetkých modulov projektu LiveAgent QA Dashboard
---

# Architektúra projektu

## Prehľad

LiveAgent QA Dashboard je Streamlit aplikácia na automatickú kontrolu kvality zákazníckej podpory.

## Dátový tok

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LIVEAGENT API                                      │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ ETL (každú hodinu o :30)
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          RAW_TICKETS (len aktuálny mesiac)                  │
│  Kľúč: (Ticket_ID, Agent) - upsert logika                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ Ticket_ID │ Agent │ Date_Changed │ Transcript │ AI_Processed │ QA_Data ... │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ AI Analysis (každú hodinu o :35)
                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          AI ANALYSIS                                        │
│  1. Nájde AI_Processed = FALSE                                             │
│  2. Analyzuje cez Gemini (QA + Alert prompt)                               │
│  3. Update: QA_Score, QA_Data, Is_Critical                                 │
│  4. Ak Is_Critical → Email alert                                           │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────────┐
│   Home.py       │   │  Daily_Stats    │   │  Archive_YYYY-MM    │
│  (Dashboard)    │   │ (Denné súhrny)  │   │ (Mesačné archívy)   │
│                 │   │                 │   │                     │
│ Filter: mesiac  │   │ Agregované dáta │   │ Staré tikety        │
│ Sort: abeceda   │   │ per agent/day   │   │ >12 mesiacov=zmazať │
└─────────────────┘   └─────────────────┘   └─────────────────────┘
```

---

## Kľúčové koncepty

### 1. Upsert logika (ETL)

```python
Kľúč = (Ticket_ID, Agent)

Ak existuje riadok s rovnakým kľúčom:
    → UPDATE (prepíše celý riadok, AI_Processed = FALSE)
Inak:
    → INSERT (nový riadok)
```

**Prečo (Ticket_ID, Agent)?**
- Jeden tiket môže mať viacerých agentov (preradenie)
- Každý agent dostane vlastné hodnotenie
- Ak sa agent vráti na tiket → prepíše sa jeho staré hodnotenie

### 2. AI Re-evaluation

```
ETL upsert → AI_Processed = FALSE
AI Analysis → Analyzuje len FALSE → QA_Score, AI_Processed = TRUE

Výsledok: Každá zmena tiketu = nové hodnotenie
```

### 3. Mesačná archivácia

```
Raw_Tickets: len Date_Changed = aktuálny mesiac
Archive_2024-12: tikety z decembra
Archive_2024-11: tikety z novembra
...
Archive staršie ako 12 mesiacov = AUTO DELETE
```

### 4. Agent Evaluation (Dashboard)

```
critical_ratio = critical_count / tickets

Ikona:
- 🚨 ak critical_ratio > 10%
- ⚠️ ak critical_ratio > 5%
- ✅ ak score >= 80%
- ⚠️ ak score >= 60%
- 🔴 ak score < 60%

Metriky:
- avg_score = total_score / analyzed_tickets (váhovaný)
- Zobrazenie: "Analyzed: 15/18 | Critical: 2 (11%)"
```

---

## Moduly

### `src/backend.py`

| Trieda | Funkcie |
|--------|---------|
| `ETLService` | `run_etl_cycle()` - stiahne tikety, upsert do Raw_Tickets |
| `AnalysisService` | `run_analysis_cycle()` - AI analýza, emaily |
| `ArchivingService` | `run_archiving()` - mesačná archivácia |

### `src/sheets_manager.py`

| Metóda | Popis |
|--------|-------|
| `upsert_raw_tickets()` | Batch upsert podľa (Ticket_ID, Agent) |
| `append_raw_tickets()` | DEPRECATED - volá upsert |
| `rewrite_raw_tickets()` | Prepíše celý sheet |
| `archive_rows_to_month()` | Pridá riadky do Archive_* sheetu |

### `src/utils.py`

| Funkcia | Popis |
|---------|-------|
| `is_human_interaction()` | Filtruje systémové správy (SYSTEM_SENDERS) |
| `process_transcript()` | Konvertuje správy na čitateľný text |
| `get_agents()` | Mapovanie agent_id → meno |

### `src/alerting.py`

| Funkcia | Popis |
|---------|-------|
| `send_alert()` | HTML email s **bold** a *italic* podporou |

### `src/scheduler.py`

| Job | Čas |
|-----|-----|
| ETL | Po-Pi, 7:30-18:30, každú hodinu o :30 |
| Analysis | Po-Pi, 7:35-18:35, každú hodinu o :35 |

---

## Konfigurácia

### Súbory

| Súbor | Obsah |
|-------|-------|
| `.env` | API kľúče (LIVEAGENT_API_KEY, atď.) |
| `prompts.json` | QA a Alert prompty |
| `email_config.json` | Email recipients, templates |
| `credentials.json` | Google Service Account |

### Premenné prostredia

```env
LIVEAGENT_API_KEY=...
LIVEAGENT_API_URL=https://your-instance.ladesk.com/api/v3
LIVEAGENT_AGENT_URL=https://your-instance.ladesk.com/agent
GOOGLE_AI_API_KEY=...
GMAIL_USER=...
GMAIL_APP_PASSWORD=...
```

---

## Workflows

| Príkaz | Súbor | Popis |
|--------|-------|-------|
| `/architecture` | architecture.md | Tento dokument |
| `/ticket-sync-logic` | ticket-sync-logic.md | Filtrovanie tiketov |
| `/ai-prompts` | ai-prompts.md | QA a Alert prompt dokumentácia |
| `/daily-stats-aggregation` | daily-stats-aggregation.md | Denné štatistiky |
| `/monthly-archiving` | monthly-archiving.md | Mesačná archivácia |
| `/restore-context` | restore-context.md | Obnovenie kontextu session |

---

## Časté operácie

### Pridať novú ignorovanú doménu
```python
# src/utils.py, SYSTEM_SENDERS list
'nova-domena.sk',
```

### Spustiť ETL manuálne
Settings → Manual Controls → Run ETL

### Archivovať staré tikety
Settings → Manual Controls → Run Archiving

### Debug tiket
```bash
python3 -c "
from src.api import get_ticket_messages
from src.config import VAS_API_KLUC
msgs = get_ticket_messages(VAS_API_KLUC, 'ticket_id_here')
print(msgs)
"
```

---

## Sheets štruktúra

### Raw_Tickets
```
Ticket_ID | Link | Agent | Date_Changed | Date_Created | Transcript |
AI_Processed | Is_Critical | QA_Score | QA_Data | Alert_Reason
```

### Daily_Stats
```
Date | Agent | Avg_Score | Critical_Count | Avg_Empathy | Avg_Expertise | Verbal_Summary
```

### Archive_YYYY-MM
Rovnaká štruktúra ako Raw_Tickets

---

*Posledná aktualizácia: 2024-12-06*
