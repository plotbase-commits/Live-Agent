---
description: Architektúra mesačných dát - Raw_Tickets a Stats sheety
---

# Mesačná archivácia - Návrh

## Prehľad novej architektúry

```
┌─────────────────────────────────────────────────────────────────────┐
│                    AKTUÁLNY MESIAC (December 2024)                  │
├─────────────────────────────────────────────────────────────────────┤
│  Raw_Tickets     = Len tikety z aktuálneho mesiaca                 │
│  Stats_2024-12   = Agregované hodnotenia za december               │
└─────────────────────────────────────────────────────────────────────┘

Pri prechode na nový mesiac (1. januára):
1. Raw_Tickets → presun do Archive_2024-12
2. Raw_Tickets = prázdny (len hlavička)
3. Stats_2024-12 zostáva (read-only historické dáta)
4. Stats_2025-01 = nový sheet pre nový mesiac
```

## Sheets štruktúra

| Sheet | Obsah | Životnosť |
|-------|-------|-----------|
| `Raw_Tickets` | Tikety aktuálneho mesiaca | Vymaže sa každý mesiac |
| `Stats_{YYYY-MM}` | Mesačné hodnotenia | Permanentné |
| `Archive_{YYYY-MM}` | Staré tikety | 12 mesiacov, potom zmazať |

## Kedy beží archivácia

1. **Automaticky** - pri prvom ETL jobu v novom mesiaci
2. **Manuálne** - tlačidlo v Settings

## Logika kontroly mesiaca

```python
def check_and_archive_if_new_month():
    last_month = get_saved_month()  # z config súboru
    current_month = datetime.now().strftime("%Y-%m")
    
    if current_month != last_month:
        # Nový mesiac!
        archive_raw_tickets(last_month)
        clear_raw_tickets()
        save_current_month(current_month)
```

## Implementácia

### 1. Konfiguračný súbor `month_state.json`
```json
{
    "current_month": "2024-12",
    "last_archive": "2024-12-01T00:00:00"
}
```

### 2. Backend funkcie
- `check_month_change()` - kontrola či sme v novom mesiaci
- `archive_current_month()` - presun Raw_Tickets do Archive
- `ensure_monthly_stats()` - vytvorenie Stats_{month} sheetu

### 3. Home.py zmeny
- Čítať z `Stats_{current_month}` pre historické dáta
- Alebo z `Raw_Tickets` pre real-time (ak Stats ešte neexistujú)

---

*Vytvorené: 2024-12-05*
