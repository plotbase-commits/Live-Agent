---
description: Logika sťahovania tiketov z LiveAgent do Google Sheets
---

# LiveAgent Ticket Sync - Logika filtrovania

## Prehľad

Aplikácia sťahuje tikety z LiveAgent API a ukladá ich do Google Sheets. Používa inteligentnú logiku filtrovania založenú na **type skupiny správ (group type)** a **doméne odosielateľa**.

---

## 1. Typy správ (Message Group Types) - PRIMÁRNY FILTER

LiveAgent API vracia správy v "skupinách" (groups). Každá skupina má `type`.

### 1.1 Komunikačné typy (zahŕňame do transkriptu) ✅

| Type | Názov | Popis |
|------|-------|-------|
| `3` | Incoming Email (nový tiket) | Zákazník vytvoril tiket emailom |
| `4` | Outgoing Email | Agent odpovedal zákazníkovi |
| `5` | Offline | Zákazník cez kontaktný formulár |
| `7` | Incoming Email (odpoveď) | Zákazník odpovedal na email |

### 1.2 Systémové typy (IGNORUJEME) ❌

| Type | Názov | Popis |
|------|-------|-------|
| `I` | Internal | Interná notifikácia (SLA, polia) |
| `T` | Transfer | Priradenie/preradenie tiketu |
| `G` | Tag | Pridanie značky |
| `R` | Resolve | Vyriešenie tiketu |

### 1.3 Kategorizácia v kóde (`src/utils.py`)

```python
# Komunikačné typy (human interaction)
COMMUNICATION_TYPES = {'3', '4', '5', '7'}

# Systémové typy sú AUTOMATICKY PRESKOČENÉ
# ak group_type not in COMMUNICATION_TYPES -> skip
```

---

## 2. Filtrovanie vlastných domén - SEKUNDÁRNY FILTER

Tikety s automatickými notifikáciami z vlastného e-shopu (napr. "Objednávka bola expedovaná") sú **PRESKOČENÉ**.

```python
# Domény na ignorovanie
IGNORED_DOMAINS = ['plotbase.sk', 'plotbase.cz']

# Ak userid alebo author_name obsahuje tieto domény -> skip
```

---

## 3. Rozhodovacia logika (is_human_interaction)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ROZHODOVACÍ STROM                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Je group.type v {3, 4, 5, 7}?                                           │
│     │                                                                       │
│     ├── NIE (I, T, G, R, ...) → PRESKOČIŤ skupinu ❌                         │
│     │   (Systémové notifikácie - SLA, transfer, tagy, resolve)              │
│     │                                                                       │
│     └── ÁNO → Pokračuj na krok 2                                            │
│                                                                             │
│  2. Je odosielateľ z vlastnej domény (plotbase.sk/cz)?                      │
│     │                                                                       │
│     ├── ÁNO → PRESKOČIŤ správu ❌                                            │
│     │   (Automatická notifikácia z e-shopu)                                 │
│     │                                                                       │
│     └── NIE → Pokračuj na krok 3                                            │
│                                                                             │
│  3. Má správa neprázdny obsah?                                              │
│     │                                                                       │
│     ├── NIE → PRESKOČIŤ správu ❌                                            │
│     │                                                                       │
│     └── ÁNO → IMPORTOVAŤ TIKET ✅                                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Kód v `src/utils.py`:**
```python
def is_human_interaction(message_groups, agents_map):
    """
    Determines if the ticket contains human communication.
    Uses MESSAGE GROUP TYPE as the primary filter.
    """
    COMMUNICATION_TYPES = {'3', '4', '5', '7'}
    IGNORED_DOMAINS = ['plotbase.sk', 'plotbase.cz']

    for group in message_groups:
        # PRIMARY FILTER: Check group type
        group_type = str(group.get('type', ''))
        if group_type not in COMMUNICATION_TYPES:
            continue
        
        # SECONDARY FILTER: Check for own-domain notifications
        for msg in group.get('messages', []):
            userid = str(msg.get('userid', ''))
            author_name = msg.get('user_full_name', '') or ''
            
            # Skip own domain emails
            if any(domain in userid.lower() for domain in IGNORED_DOMAINS):
                continue
            if any(domain in author_name.lower() for domain in IGNORED_DOMAINS):
                continue
            
            # Check for actual content
            if msg.get('message', '').strip():
                return True

    return False
```

---

## 4. Príklady

### Príklad A: Tiket sa IMPORTUJE ✅ (zákazník + agent)
```
Tiket ID: 3jor4368
Skupiny správ:
  - Type 7: Zákazník napísal email
  - Type 4: Agent odpovedal

→ Type 7 je v COMMUNICATION_TYPES ✅
→ Type 4 je v COMMUNICATION_TYPES ✅
→ IMPORTUJE SA
```

### Príklad B: Tiket sa IMPORTUJE ✅ (len zákazník)
```
Tiket ID: reklamacia123
Skupiny správ:
  - Type 3: Zákazník napísal reklamáciu

→ Type 3 je v COMMUNICATION_TYPES ✅
→ IMPORTUJE SA
```

### Príklad C: Tiket sa NEIMPORTUJE ❌ (len systémové)
```
Tiket ID: f7jrt2t0
Skupiny správ:
  - Type I: SLA notifikácia
  - Type T: Transfer (viackrát)
  - Type G: Pridanie značiek

→ Žiadny type nie je v COMMUNICATION_TYPES ❌
→ NEIMPORTUJE SA (len automatické notifikácie)
```

### Príklad D: Tiket sa NEIMPORTUJE ❌ (vlastná doména)
```
Tiket ID: shop-notification
Skupiny správ:
  - Type 3: Email od plotbase@plotbase.sk

→ Type 3 je v COMMUNICATION_TYPES ✅
→ ALE autor je z IGNORED_DOMAINS ❌
→ NEIMPORTUJE SA (automatická notifikácia z e-shopu)
```

---

## 5. Bug Fix History

### 2025-12-05: Oprava filtrovania systémových notifikácií

**Problém:** Tiket `f7jrt2t0` bol nesprávne importovaný, hoci obsahoval len systémové notifikácie (SLA, transfer, tagy).

**Príčina:** Pôvodná funkcia `is_human_interaction()` kontrolovala len **obsah správy** a **userid**, ale NIE **group type**. Systémové správy s type=I, T, G mali `userid: system00`, ale funkcia to nesprávne vyhodnotila.

**Riešenie:** Nová logika používa **group.type** ako primárny filter:
- Len typy 3, 4, 5, 7 sú považované za komunikáciu
- Všetky ostatné typy (I, T, G, R, ...) sú automaticky preskočené

---

## 6. API Endpoints

```
GET /api/v3/tickets
  - Parametre: _page, _perPage, _sortField, _sortDir
  - Vracia zoznam tiketov

GET /api/v3/tickets/{id}/messages
  - Vracia skupiny správ pre konkrétny tiket
  - Každá skupina má "type" pole (3, 4, 5, 7, I, T, G, R, ...)
```

---

## 7. Súvisiace súbory

- `src/utils.py` - Funkcia `is_human_interaction()` (hlavná logika filtrovania)
- `src/backend.py` - `ETLService.run_etl_cycle()` (volá is_human_interaction)
- `pages/Settings.py` - UI pre manuálne spustenie ETL

---

*Posledná aktualizácia: 2025-12-05 (fix: group type filtering)*
