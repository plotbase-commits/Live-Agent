---
description: Prehľad architektúry a všetkých modulov projektu LiveAgent QA Dashboard
---

# Architektúra projektu

## Prehľad

LiveAgent QA Dashboard je Streamlit aplikácia na automatickú kontrolu kvality zákazníckej podpory.

## Komponenty

```
┌─────────────────────────────────────────────────────────────┐
│                     STREAMLIT UI                            │
├─────────────────────────────────────────────────────────────┤
│  Home.py (Dashboard)    │    pages/Settings.py (Admin)     │
└─────────────┬───────────┴───────────────┬───────────────────┘
              │                           │
              ▼                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     BACKEND SERVICES                        │
├──────────────────┬──────────────────┬──────────────────────┤
│   ETLService     │  AnalysisService │  ArchivingService    │
│   (backend.py)   │  (backend.py)    │  (backend.py)        │
└────────┬─────────┴────────┬─────────┴──────────┬───────────┘
         │                  │                    │
         ▼                  ▼                    ▼
┌────────────────┐  ┌───────────────┐  ┌─────────────────────┐
│  LiveAgent API │  │   Gemini AI   │  │   Google Sheets     │
│   (api.py)     │  │ (ai_service)  │  │  (sheets_manager)   │
└────────────────┘  └───────────────┘  └─────────────────────┘
         │                  │
         ▼                  ▼
┌────────────────────────────────────┐
│         SUPPORT SERVICES           │
├──────────────────┬─────────────────┤
│   Scheduler      │   Email Alerts  │
│  (scheduler.py)  │  (alerting.py)  │
└──────────────────┴─────────────────┘
```

---

## Moduly

### 1. Home.py
**Hlavná stránka - QA Dashboard**

- Zobrazuje karty agentov s QA skóre
- Agregované metriky (počet tiketov, kritické problémy)
- Auto-start scheduler pri načítaní

```python
@st.cache_resource
def init_scheduler():
    # Inicializuje scheduler s ETL a Analysis jobmi
```

### 2. pages/Settings.py
**Admin nastavenia**

- Taby: Manual Controls, Scheduler, Configuration
- Real-time status refresh (@st.fragment)
- Job logs (najnovšie hore)

### 3. src/backend.py
**Hlavné služby**

```python
class ETLService:
    def run_etl_cycle(self):
        # 1. Fetch tickets from LiveAgent
        # 2. Filter non-human (SYSTEM_SENDERS)
        # 3. Process transcript
        # 4. Save to Raw_Tickets

class AnalysisService:
    def run_analysis_cycle(self):
        # 1. Get unprocessed tickets
        # 2. Call AI (QA + Alert prompts)
        # 3. Update sheet
        # 4. Send email alerts

class ArchivingService:
    def run_archiving(self):
        # Move old tickets to Archive_YYYY-MM
```

### 4. src/utils.py
**Pomocné funkcie**

```python
def is_human_interaction(messages, agents_map):
    """
    Filtruje tikety bez ľudskej interakcie.
    
    Kontroluje:
    1. Message group type (3,4,5,7 = komunikácia)
    2. From: header vs SYSTEM_SENDERS
    3. Reply-to header pre no-reply vzory
    """
    SYSTEM_SENDERS = [
        # Vlastné domény
        'plotbase.sk', 'plotbase.cz', ...
        # Platobné brány
        'payu.com', 'gopay.cz', 'stripe.com', ...
        # Dopravcovia
        'dhl.com', 'dpd.sk', 'packeta.com', ...
        # Partneri
        'justprint.sk',
        # No-reply vzory
        'no-reply@', 'noreply@', ...
    ]

def process_transcript(messages, agents_map, users_map):
    """Konvertuje API správy na čitateľný transcript."""

def get_agents(api_key):
    """Vráti mapu agent_id → agent_name (s _perPage=100)."""
```

### 5. src/api.py
**LiveAgent API**

```python
def get_liveagent_tickets(api_key, page, per_page):
    """Fetch tickets with retry logic."""

def get_ticket_messages(api_key, ticket_id):
    """Fetch messages for a ticket."""
```

### 6. src/ai_service.py
**Gemini AI**

```python
class AIService:
    def analyze_qa(self, transcript, qa_prompt):
        """Returns QA JSON with criteria scores."""
    
    def analyze_alert(self, transcript, alert_prompt):
        """Returns {is_critical, reason}."""
```

### 7. src/alerting.py
**Email notifikácie**

```python
class EmailService:
    def send_alert(self, recipients, subject, body):
        """
        Odošle HTML email.
        Podporuje **bold** a *italic* formátovanie.
        """
```

### 8. src/scheduler.py
**APScheduler**

```python
class SchedulerService:
    def add_etl_job(self, func):
        # Mon-Fri, 7:30-18:30, every hour at :30
    
    def add_analysis_job(self, func):
        # Mon-Fri, 7:35-18:35, every hour at :35
```

### 9. src/job_status.py
**Status tracking**

```python
def set_status(job_name, status, progress, message):
    """Zapíše stav do job_status.json"""

def add_log(message):
    """Pridá log do job_logs.txt (max 100 riadkov)"""
```

---

## Dátový tok

### ETL Cycle
```
LiveAgent API → get_liveagent_tickets() → filter is_human_interaction()
                                        → process_transcript()
                                        → SheetSyncManager.append_raw_tickets()
```

### Analysis Cycle
```
Raw_Tickets → AIService.analyze_qa() → update QA_Score, QA_Data
            → AIService.analyze_alert() → update Is_Critical, Alert_Reason
            → if critical: EmailService.send_alert()
```

---

## Konfiguračné súbory

| Súbor | Účel |
|-------|------|
| `.env` | API kľúče, credentials |
| `prompts.json` | QA a Alert prompty |
| `email_config.json` | Email recipients, templates |
| `credentials.json` | Google Service Account |

---

## Časté úlohy

### Pridať novú ignorovanú doménu
```python
# src/utils.py, SYSTEM_SENDERS list
'nova-domena.sk',
```

### Upraviť AI prompt
1. Edituj `prompts.json` alebo cez Settings → Configuration
2. Pushni zmeny do Git

### Debug tiket
```python
python3 -c "
from src.config import VAS_API_KLUC
import requests
ticket_id = 'abc123'
r = requests.get(f'https://plotbase.ladesk.com/api/v3/tickets/{ticket_id}', 
                 headers={'apikey': VAS_API_KLUC})
print(r.json())
"
```

---

*Posledná aktualizácia: 2024-12-05*
