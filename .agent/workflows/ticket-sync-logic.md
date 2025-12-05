---
description: Logika sťahovania tiketov z LiveAgent do Google Sheets
---

# LiveAgent Ticket Sync - Logika filtrovania

## Prehľad

Aplikácia sťahuje tikety z LiveAgent API a ukladá ich do Google Sheets. Používa inteligentnú logiku filtrovania založenú na **statuse tiketu** a **type komunikácie**.

---

## 1. Povolené statusy tiketov

| Kód | Názov | Sťahujeme? | Vyžaduje odpoveď agenta? |
|-----|-------|------------|--------------------------|
| `N` | New | ✅ ÁNO | ❌ NIE (agent ešte neotvoril) |
| `C` | Open | ✅ ÁNO | ❌ NIE (agent pracuje) |
| `A` | Answered | ✅ ÁNO | ✅ ÁNO (agent už odpovedal - definícia) |
| `R` | Resolved | ✅ ÁNO | ❌ NIE (môže byť auto-resolved) |
| `W` | Postponed | ✅ ÁNO | ❌ NIE (odložené) |
| `I` | Init | ❌ NIE | - |
| `T` | Chatting | ❌ NIE | - |
| `P` | Calling | ❌ NIE | - |
| `X` | Deleted | ❌ NIE | - |
| `B` | Spam | ❌ NIE | - |

**Kód v `app.py`:**
```python
# Statusy kde VYŽADUJEME odpoveď agenta
REQUIRES_AGENT_RESPONSE = ['A']  # Answered = agent odpovedal (definícia)

# Statusy kde STAČÍ správa od zákazníka (agent nemusel odpovedať)
CUSTOMER_ONLY_OK = ['N', 'C', 'W', 'R']  # New, Open, Postponed, Resolved

# Všetky povolené statusy
ALLOWED_STATUSES = REQUIRES_AGENT_RESPONSE + CUSTOMER_ONLY_OK
```

---

## 2. Typy správ (Message Group Types)

LiveAgent API vracia správy v "skupinách" (groups). Každá skupina má `type`.

### 2.1 Komunikačné typy (zahŕňame do transkriptu)

| Type | Názov | Popis |
|------|-------|-------|
| `3` | Incoming Email (nový tiket) | Zákazník vytvoril tiket emailom |
| `4` | Outgoing Email | Agent odpovedal zákazníkovi |
| `5` | Offline | Zákazník cez kontaktný formulár |
| `7` | Incoming Email (odpoveď) | Zákazník odpovedal na email |

### 2.2 Systémové typy (ignorujeme)

| Type | Názov | Popis |
|------|-------|-------|
| `I` | Internal | Interná notifikácia (SLA, polia) |
| `T` | Transfer | Priradenie/preradenie tiketu |
| `G` | Tag | Pridanie značky |
| `R` | Resolve | Vyriešenie tiketu |

### 2.3 Kategorizácia v kóde

```python
# Typy zákazníka (incoming)
CUSTOMER_TYPES = ['3', '5', '7']

# Typy agenta (outgoing)
AGENT_TYPES = ['4']

# Všetky komunikačné typy
COMMUNICATION_TYPES = {'3', '4', '5', '7'}
```

---

## 3. Rozhodovacia logika

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ROZHODOVACÍ STROM                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Status tiketu je N, C, A, R alebo W?                                    │
│     │                                                                       │
│     ├── NIE (I, T, P, X, B) → PRESKOČIŤ tiket ❌                             │
│     │   (Init, Chatting, Calling, Deleted, Spam - nesťahujeme)              │
│     │                                                                       │
│     └── ÁNO → Pokračuj na krok 2                                            │
│                                                                             │
│  2. Tiket má správu od zákazníka (type 3, 5, alebo 7)?                      │
│     │                                                                       │
│     ├── NIE → PRESKOČIŤ tiket (len systémové notifikácie)                   │
│     │                                                                       │
│     └── ÁNO → Pokračuj na krok 3                                            │
│                                                                             │
│  3. Aký je status tiketu?                                                   │
│     │                                                                       │
│     ├── N, C, W, R (nové/otvorené/odložené/vyriešené):                      │
│     │   └── IMPORTOVAŤ ✅ (stačí správa od zákazníka)                       │
│     │                                                                       │
│     └── A (answered):                                                       │
│         │                                                                   │
│         ├── Má odpoveď agenta (type 4)?                                     │
│         │   └── ÁNO → IMPORTOVAŤ ✅                                         │
│         │                                                                   │
│         └── NIE → PRESKOČIŤ ❌ (status "Answered" ale chýba                 │
│                                  odpoveď = nekonzistentné dáta)             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Kód v `app.py`:**
```python
def should_import_ticket(message_groups, status_code):
    """
    Rozhoduje či tiket importovať na základe statusu a komunikácie.
    """
    group_types = [g.get('type') for g in message_groups]
    has_customer = any(t in CUSTOMER_TYPES for t in group_types)
    has_agent = any(t in AGENT_TYPES for t in group_types)
    
    # Ak nie je žiadna správa od zákazníka, preskočiť
    if not has_customer:
        return False
    
    # Pre statusy N, C, W, R: stačí zákazník
    if status_code in CUSTOMER_ONLY_OK:
        return True
    
    # Pre status A: vyžadujeme aj agenta
    if status_code in REQUIRES_AGENT_RESPONSE:
        return has_agent
    
    return False
```

---

## 4. Príklady

### Príklad A: Tiket sa IMPORTUJE ✅ (agent odpovedal)
```
Tiket ID: 3jor4368
Status: A (Answered)
Skupiny správ:
  - Type 7: Zákazník napísal email
  - Type 4: Agent odpovedal

→ Status A vyžaduje agenta ✅
→ Má zákazníka (type 7) ✅
→ Má agenta (type 4) ✅
→ IMPORTUJE SA
```

### Príklad B: Tiket sa IMPORTUJE ✅ (nový tiket bez odpovede)
```
Tiket ID: reklamacia123
Status: N (New)
Skupiny správ:
  - Type 3: Zákazník napísal reklamáciu

→ Status N nevyžaduje agenta ✅
→ Má zákazníka (type 3) ✅
→ IMPORTUJE SA (zákazník napísal, agent ešte neodpovedal)
```

### Príklad C: Tiket sa IMPORTUJE ✅ (vyriešené bez odpovede)
```
Tiket ID: autoclose789
Status: R (Resolved)
Skupiny správ:
  - Type 3: Zákazník napísal otázku
  - Type R: Automaticky vyriešené pravidlom

→ Status R nevyžaduje agenta ✅
→ Má zákazníka (type 3) ✅
→ IMPORTUJE SA (vyriešené, aj keď agent neodpovedal)
```

### Príklad D: Tiket sa NEIMPORTUJE ❌ (len systémové notifikácie)
```
Tiket ID: 8u6xyvkw
Status: R (Resolved)
Skupiny správ:
  - Type I: SLA notifikácia
  - Type T: Transfer
  - Type R: Auto-resolved

→ Nemá zákazníka (type 3/5/7) ❌
→ NEIMPORTUJE SA (len systémové notifikácie, žiadna ľudská komunikácia)
```

### Príklad E: Tiket sa NEIMPORTUJE ❌ (status A bez odpovede)
```
Tiket ID: inconsistent456
Status: A (Answered)
Skupiny správ:
  - Type 7: Zákazník napísal
  - Type I: Interná poznámka

→ Status A vyžaduje agenta
→ Má zákazníka (type 7) ✅
→ Nemá agenta (type 4) ❌
→ NEIMPORTUJE SA (nekonzistentné - status hovorí Answered ale type 4 chýba)
```

---

## 5. Prečo táto logika?

| Status | Logika | Dôvod |
|--------|--------|-------|
| **A** | Vyžaduje agenta | "Answered" = agent odpovedal (definícia statusu) |
| **N** | Stačí zákazník | Nový tiket, agent ho ešte nevidel |
| **C** | Stačí zákazník | Agent pracuje, ešte neodpovedal |
| **W** | Stačí zákazník | Odložené, možno čaká na info |
| **R** | Stačí zákazník | Môže byť auto-resolved bez odpovede |

---

## 6. Čo sa IMPORTUJE vs NEIMPORTUJE

| Scenár | Importuje sa? | Dôvod |
|--------|---------------|-------|
| Zákazník napíše reklamáciu, agent neodpovie (status N) | ✅ ÁNO | Chceme zachytiť čakajúce tikety |
| Zákazník napíše, agent odloží (status W) | ✅ ÁNO | Odložené tikety sú relevantné |
| Zákazník napíše, auto-resolved (status R) | ✅ ÁNO | Môže byť užitočné pre analýzu |
| Agent odpovie zákazníkovi (status A) | ✅ ÁNO | Štandardná komunikácia |
| Automatická notifikácia (expedícia) bez zákazníka | ❌ NIE | Nie je ľudská komunikácia |
| Status A ale chýba type 4 | ❌ NIE | Nekonzistentné dáta |

---

## 7. API Endpoints

```
GET /api/v3/tickets
  - Parametre: _page, _perPage, _sortField, _sortDir
  - Vracia zoznam tiketov

GET /api/v3/tickets/{id}/messages
  - Vracia skupiny správ pre konkrétny tiket
```

---

## 8. Súvisiace súbory

- `app.py` - Hlavná sync logika (standalone verzia)
- `Home.py` - Streamlit UI (modulárna verzia)
- `src/liveagent.py` - LiveAgent API client
- `src/sheets.py` - Google Sheets integrácia

---

*Posledná aktualizácia: 2025-12-05*
