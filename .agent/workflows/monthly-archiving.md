---
description: Architektúra mesačných dát - Raw_Tickets a Stats sheety
---

# Mesačná archivácia

## Prehľad

Archivácia presúva tikety z predchádzajúcich mesiacov do samostatných sheetov.

---

## 1. Sheets štruktúra

| Sheet | Obsah | Životnosť |
|-------|-------|-----------|
| `Raw_Tickets` | Tikety aktuálneho mesiaca | Vymaže sa každý mesiac |
| `Archive_YYYY-MM` | Staré tikety podľa mesiaca | 12 mesiacov, potom zmazať |
| `Daily_Stats` | Denné súhrny | Permanentné |

---

## 2. Kedy beží

| Trigger | Spôsob |
|---------|--------|
| Manuálne | Settings → Manual Controls → Run Archiving |
| Automaticky | Plánované (odporúčané: 1× mesačne) |

---

## 3. Logika archivácie

```
Pre každý riadok v Raw_Tickets:

1. Ak Agent = "Nepriradený" alebo prázdny:
   → DELETE (nezachováva sa)

2. Ak Date_Changed[:7] != aktuálny mesiac:
   → MOVE do Archive_{YYYY-MM}

3. Inak:
   → KEEP v Raw_Tickets
```

### Príklad (december 2024):
```
Raw_Tickets pred archiváciou:
| Ticket_ID | Agent | Date_Changed |
| ABC | Adam | 2024-12-05 |      ← KEEP (december)
| DEF | Boris | 2024-11-28 |     ← ARCHIVE to Archive_2024-11
| GHI | Nepriradený | ... |      ← DELETE

Raw_Tickets po archivácii:
| ABC | Adam | 2024-12-05 |

Archive_2024-11:
| DEF | Boris | 2024-11-28 |
```

---

## 4. Cleanup starých archívov

```python
for sheet in worksheets:
    if sheet.title.startswith("Archive_"):
        month = sheet.title.replace("Archive_", "")
        age_months = calculate_age(month)
        
        if age_months > 12:
            delete_sheet(sheet)
```

---

## 5. Súvisiace súbory

| Súbor | Funkcia |
|-------|---------|
| `src/backend.py` | `ArchivingService.run_archiving()` |
| `src/backend.py` | `ArchivingService._cleanup_old_archives()` |
| `src/sheets_manager.py` | `archive_rows_to_month()` |
| `src/sheets_manager.py` | `rewrite_raw_tickets()` |

---

*Posledná aktualizácia: 2024-12-06*
