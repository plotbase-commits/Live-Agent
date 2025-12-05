# LiveAgent QA Dashboard

Streamlit aplikácia pre automatizovanú kontrolu kvality zákazníckej podpory integrovaná s LiveAgent a Google Sheets.

## 📁 Štruktúra projektu

```
Live Agent/
├── Home.py                    # Hlavná stránka - QA Dashboard
├── pages/
│   └── Settings.py            # Admin nastavenia, manuálne ovládanie
├── src/
│   ├── api.py                 # LiveAgent API volania
│   ├── utils.py               # Pomocné funkcie (transcript, filtrovanie)
│   ├── backend.py             # Hlavná logika (ETL, AI Analysis)
│   ├── sheets_manager.py      # Google Sheets operácie
│   ├── ai_service.py          # Gemini AI integrácia
│   ├── alerting.py            # Email notifikácie (HTML s formátovaním)
│   ├── scheduler.py           # APScheduler pre automatizáciu
│   ├── job_status.py          # Status tracking pre background joby
│   └── config.py              # Konfiguračné premenné
├── .agent/workflows/          # Znalostná báza pre AI asistenta
│   ├── ai-prompts.md          # Dokumentácia QA a Alert promptov
│   ├── ticket-sync-logic.md   # Logika filtrovania tiketov
│   └── daily-stats-aggregation.md  # Logika denných štatistík
├── credentials.json           # Google Service Account (NEZAHŔŇAŤ DO GIT!)
├── vertex-credentials.json    # Vertex AI credentials (NEZAHŔŇAŤ DO GIT!)
├── prompts.json               # AI prompty (QA + Alert)
├── email_config.json          # Email konfigurácia
├── job_status.json            # Aktuálny stav jobov (runtime)
├── job_logs.txt               # Logy z background jobov
├── requirements.txt           # Python závislosti
└── .env                       # Environment premenné (NEZAHŔŇAŤ DO GIT!)
```

---

## 🔧 Moduly

### `src/backend.py`
Obsahuje hlavné služby:

| Trieda | Účel |
|--------|------|
| `ETLService` | Sťahuje tikety z LiveAgent API, filtruje a ukladá do Raw_Tickets |
| `AnalysisService` | Analyzuje tikety pomocou AI, aktualizuje hodnotenia |
| `ArchivingService` | Archivuje staré tikety do mesačných sheétov |

**Dôležité:**
- Všetky dlhodobé operácie používajú `set_status()` a `add_log()` pre tracking
- Agent attribution používa `ticket.agentid` z API (nie z messages)
- Threading používaný pre manuálne tlačidlá

### `src/utils.py`
Pomocné funkcie:

| Funkcia | Účel |
|---------|------|
| `process_transcript()` | Konvertuje API správy na čitateľný transcript |
| `is_human_interaction()` | Filtruje tikety bez ľudskej interakcie |
| `get_agents()`, `get_users()` | Mapovanie ID na mená (s `_perPage=100/500`) |
| `convert_utc_to_local()` | Časová konverzia UTC → local |

**SYSTEM_SENDERS blacklist** v `is_human_interaction()`:
- Vlastné domény: plotbase.sk, plotbase.cz, plotbase.at, plotbase.de, plotbase.hu
- Platobné brány: PayU, GoPay, Stripe, PayPal, Comgate, ThePay
- Dopravcovia: DHL, DPD, GLS, UPS, FedEx, Packeta, Pošta
- Partneri: justprint.sk
- No-reply vzory: no-reply@, noreply@, notification@, atď.

### `src/sheets_manager.py`
Google Sheets operácie:

| Metóda | Účel |
|--------|------|
| `connect()` | Pripojenie ku Google Sheets |
| `ensure_qa_sheets()` | Vytvorenie potrebných sheétov |
| `append_raw_tickets()` | Pridanie nových tiketov |
| `update_daily_stats()` | Aktualizácia denných štatistík |
| `archive_rows_to_month()` | Archivácia do mesačných sheétov |

### `src/alerting.py`
Email notifikácie:

| Funkcia | Účel |
|---------|------|
| `send_alert()` | Odošle HTML email s formátovaním |
| `_convert_to_html()` | Konvertuje **bold** a *italic* na HTML |

**Formátovanie v emailoch:**
- `**text**` → **bold**
- `*text*` → *italic*

### `src/scheduler.py`
Automatizácia pomocou APScheduler:

| Metóda | Účel |
|--------|------|
| `add_etl_job()` | ETL job: Po-Pi, 7:30-18:30, každú hodinu |
| `add_analysis_job()` | Analysis job: Po-Pi, 7:35-18:35, každú hodinu |
| `add_daily_aggregation_job()` | Agregácia: Po-Pi o 17:00 |

**Auto-start:** Scheduler sa automaticky spúšťa pri načítaní Home.py

### `src/job_status.py`
Status tracking:

| Funkcia | Účel |
|---------|------|
| `set_status(job, status, progress, msg)` | Nastaví stav jobu |
| `add_log(message)` | Pridá log záznam |
| `get_status()` | Vráti aktuálny stav všetkých jobov |
| `get_logs()` | Vráti všetky logy |

---

## 📊 Google Sheets štruktúra

### Raw_Tickets
| Stĺpec | Typ | Popis |
|--------|-----|-------|
| Ticket_ID | string | Unikátny ID tiketu |
| Link | string | URL na tiket v LiveAgent |
| Agent | string | Meno priradeného agenta |
| Date_Changed | datetime | Dátum poslednej zmeny |
| Date_Created | datetime | Dátum vytvorenia |
| Transcript | string | Kompletný prepis konverzácie |
| AI_Processed | boolean | Či bol analyzovaný AI |
| Is_Critical | boolean | Či obsahuje kritický problém |
| QA_Score | number | Celkové skóre (0-100) |
| QA_Data | JSON | Detailné hodnotenie |
| Alert_Reason | string | Dôvod alertu (ak je kritický) |

### Daily_Stats
Agregované denné štatistiky pre každého agenta.

---

## 🚀 Spustenie

```bash
# Inštalácia závislostí
pip install -r requirements.txt

# Spustenie
streamlit run Home.py

# Alebo s portom
streamlit run Home.py --server.port 8501
```

---

## ⚙️ Konfigurácia

### .env
```env
LIVEAGENT_API_KEY=your_api_key
GOOGLE_AI_API_KEY=your_gemini_key
GMAIL_USER=your_email@gmail.com
GMAIL_APP_PASSWORD=your_app_password
```

### prompts.json
Obsahuje AI prompty pre QA hodnotenie a detekciu alertov.
Viď `.agent/workflows/ai-prompts.md` pre detailnú dokumentáciu.

### email_config.json
```json
{
    "recipients": ["admin@example.com"],
    "subject_template": "🚨 KRITICKÝ ALERT: Ticket {ticket_id} ({agent_name})",
    "body_template": "**Kritický problém**\n\nTicket: {ticket_id}\nAgent: **{agent_name}**\nDôvod: *{alert_reason}*\n\nOdkaz: {ticket_url}"
}
```

**Premenné:** `{ticket_id}`, `{agent_name}`, `{alert_reason}`, `{ticket_url}`, `{date_changed}`
**Formátovanie:** `**bold**`, `*italic*`

---

## 🔄 Workflow

```
1. ETL (každú hodinu o :30)
   └── Stiahne tikety z LiveAgent
   └── Filtruje systémové správy (SYSTEM_SENDERS)
   └── Uloží do Raw_Tickets

2. AI Analysis (každú hodinu o :35)
   └── Analyzuje nespracované tikety
   └── QA Prompt → Skóre 0-100
   └── Alert Prompt → Is_Critical true/false
   └── Posiela email alerty pre kritické tikety

3. Daily Stats (17:00)
   └── Agreguje denné štatistiky
   └── Aktualizuje Daily_Stats sheet

4. Archiving (manuálne)
   └── Presunie tikety staršie ako 2 dni
   └── Do mesačných archívov (Archive_2024-12, atď.)
```

---

## 📝 Pravidlá pre úpravy

1. **Pred úpravou** si prečítaj tento README a `.agent/workflows/`
2. **Po každej zmene** commitni a pushni do Git
3. **Threading** používaj len pre manuálne tlačidlá
4. **Logging** - každá dlhodobá operácia musí volať `set_status()` a `add_log()`
5. **Error handling** - vždy ošetri exceptions a nastav `status="error"`
6. **SYSTEM_SENDERS** - ak treba filtrovať novú doménu, pridaj do `src/utils.py`

---

## 🐛 Známe problémy a riešenia

| Problém | Riešenie |
|---------|----------|
| Tiket od partnera sa stiahol | Pridaj doménu do SYSTEM_SENDERS v `utils.py` |
| Email sa neodoslal | Over `email_config.json` a Gmail App Password |
| Agent je "Nepriradený" | Over že tiket má `agentid` v LiveAgent API |
| Scheduler nebeží | Reštartuj aplikáciu (auto-start v Home.py) |

---

## 📚 Znalostná báza

Pre detailnú dokumentáciu funkcií pozri:
- `/ai-prompts` - QA a Alert prompt dokumentácia
- `/ticket-sync-logic` - Logika filtrovania tiketov
- `/daily-stats-aggregation` - Logika denných štatistík

---

*Posledná aktualizácia: 2024-12-05*
