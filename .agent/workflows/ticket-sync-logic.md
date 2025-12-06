---
description: Logika sťahovania tiketov z LiveAgent do Google Sheets
---

# Ticket Sync Logic (ETL)

## Prehľad

ETL proces sťahuje tikety z LiveAgent API a ukladá ich do Google Sheets pomocou **upsert** logiky.

---

## 1. Spúšťanie

| Trigger | Čas |
|---------|-----|
| Automaticky | Po-Pi, 7:30-18:30, každú hodinu o :30 |
| Manuálne | Settings → Manual Controls → Run ETL |

---

## 2. Upsert logika

### Kľúč
```
(Ticket_ID, Agent) = unikátny kľúč
```

### Pravidlá
```
1. Ak existuje riadok s rovnakým (Ticket_ID, Agent):
   → UPDATE celý riadok
   → AI_Processed = FALSE (trigger re-evaluation)

2. Ak neexistuje:
   → INSERT nový riadok
```

### Prečo (Ticket_ID, Agent)?

**Scenár:** Tiket preradený na iného agenta
```
10:00 - Tiket ABC → Agent Adam → Hodnotenie 80
14:00 - Tiket preradený → Agent Boris
15:00 - ETL: (ABC, Boris) neexistuje → INSERT

Výsledok:
Row 1: ABC | Adam  | Score 80  (zachované!)
Row 2: ABC | Boris | AI=FALSE  (nové hodnotenie)
```

**Scenár:** Tiket späť u pôvodného agenta
```
16:00 - Tiket ABC späť → Agent Adam
17:00 - ETL: (ABC, Adam) existuje → UPDATE

Výsledok:
Row 1: ABC | Adam | AI=FALSE (prepísané, re-evaluate)
Row 2: ABC | Boris | Score 70 (zachované!)
```

---

## 3. Filtrovanie tiketov

### 3.1 Skip "Nepriradený"
```python
if agent_name == 'Nepriradený':
    continue  # Skip
```

### 3.2 Human Interaction Check
```python
if not is_human_interaction(messages, agents_map):
    continue  # Skip
```

### 3.3 SYSTEM_SENDERS Blacklist
Tikety od týchto odosielateľov sú ignorované:

| Kategória | Príklady |
|-----------|----------|
| Vlastné domény | plotbase.sk, plotbase.cz |
| Platobné brány | payu.com, gopay.cz, stripe.com |
| Dopravcovia | dhl.com, dpd.sk, packeta.com |
| Partneri | justprint.sk |
| No-reply | no-reply@, noreply@, notification@ |

---

## 4. Batch spracovanie

```python
# 1. Batch read všetkých existujúcich riadkov
all_data = ws.get_all_values()

# 2. Build index (Ticket_ID, Agent) → row_index
existing_keys = {(row[0], row[2]): idx for idx, row in enumerate(existing_rows)}

# 3. Process v pamäti
for ticket in new_tickets:
    if key in existing_keys:
        updated_rows[idx] = ticket  # UPDATE
    else:
        new_rows.append(ticket)  # INSERT

# 4. Batch write
ws.clear()
ws.update("A1", [headers] + updated_rows + new_rows)
```

**Výhoda:** 2 API calls namiesto 2×N

---

## 5. Výstupná štruktúra

| Stĺpec | Typ | Popis |
|--------|-----|-------|
| Ticket_ID | string | ID tiketu |
| Link | string | URL na tiket |
| Agent | string | Meno agenta |
| Date_Changed | datetime | Posledná zmena |
| Date_Created | datetime | Vytvorenie |
| Transcript | string | Prepis konverzácie |
| AI_Processed | boolean | FALSE = čaká na analýzu |
| Is_Critical | boolean | Kritický problém |
| QA_Score | number | 0-100 |
| QA_Data | JSON | Detailné hodnotenie |
| Alert_Reason | string | Dôvod alertu |

---

## 6. Error handling

| Chyba | Správanie |
|-------|-----------|
| API timeout | Retry s exponential backoff |
| Invalid JSON | Skip tiket |
| Sheet not found | Vytvorí automaticky |
| Rate limit | Delay medzi stránkami |

---

## 7. Súvisiace súbory

| Súbor | Funkcia |
|-------|---------|
| `src/backend.py` | `ETLService.run_etl_cycle()` |
| `src/sheets_manager.py` | `upsert_raw_tickets()` |
| `src/api.py` | `get_liveagent_tickets()`, `get_ticket_messages()` |
| `src/utils.py` | `is_human_interaction()`, `process_transcript()` |

---

*Posledná aktualizácia: 2024-12-06*
