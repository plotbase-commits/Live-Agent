# LiveAgent QA Dashboard

Streamlit aplikácia pre automatizovanú kontrolu kvality zákazníckej podpory integrovaná s LiveAgent a Google Sheets.

## 📁 Štruktúra projektu

```
Live Agent/
├── Home.py                 # Hlavná stránka - QA Dashboard
├── pages/
│   └── Settings.py         # Admin nastavenia, manuálne ovládanie
├── src/
│   ├── api.py              # LiveAgent API volania
│   ├── utils.py            # Pomocné funkcie (transcript, filtrovanie)
│   ├── backend.py          # Hlavná logika (ETL, AI Analysis)
│   ├── sheets_manager.py   # Google Sheets operácie
│   ├── ai_service.py       # Gemini AI integrácia
│   ├── alerting.py         # Email notifikácie
│   ├── scheduler.py        # APScheduler pre automatizáciu
│   ├── job_status.py       # Status tracking pre background joby
│   └── config.py           # Konfiguračné premenné
├── credentials.json        # Google Service Account (NEZAHŔŇAŤ DO GIT!)
├── prompts.json            # AI prompty (QA + Alert)
├── email_config.json       # Email konfigurácia
├── job_status.json         # Aktuálny stav jobov (runtime)
├── job_logs.txt            # Logy z background jobov
├── requirements.txt        # Python závislosti
└── .env                    # Environment premenné (NEZAHŔŇAŤ DO GIT!)
```

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
- Threading používaný pre manuálne tlačidlá, nie pre scheduler joby

### `src/utils.py`
Pomocné funkcie:

| Funkcia | Účel |
|---------|------|
| `process_transcript()` | Konvertuje API správy na čitateľný transcript |
| `is_human_interaction()` | Filtruje tikety bez ľudskej interakcie |
| `get_agents()`, `get_users()` | Mapovanie ID na mená |
| `convert_utc_to_local()` | Časová konverzia |

### `src/sheets_manager.py`
Google Sheets operácie:

| Metóda | Účel |
|--------|------|
| `connect()` | Pripojenie ku Google Sheets |
| `ensure_qa_sheets()` | Vytvorenie potrebných sheétov |
| `append_raw_tickets()` | Pridanie nových tiketov |
| `update_daily_stats()` | Aktualizácia denných štatistík |
| `archive_rows_to_month()` | Archivácia do mesačných sheétov |

### `src/job_status.py`
Status tracking:

| Funkcia | Účel |
|---------|------|
| `set_status(job, status, progress, msg)` | Nastaví stav jobu |
| `add_log(message)` | Pridá log záznam |
| `get_status()` | Vráti aktuálny stav |
| `display_status_sidebar()` | Zobrazí stav v sidebar |
| `display_log_window()` | Zobrazí scrollovacie okno s logmi |

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

## 🚀 Spustenie

```bash
# Inštalácia závislostí
pip install -r requirements.txt

# Spustenie
streamlit run Home.py
```

## ⚙️ Konfigurácia

### .env
```
LIVEAGENT_API_KEY=your_api_key
GOOGLE_AI_API_KEY=your_gemini_key
GMAIL_USER=your_email
GMAIL_APP_PASSWORD=your_app_password
```

### prompts.json
Obsahuje AI prompty pre QA hodnotenie a detekciu alertov.

### email_config.json
```json
{
    "recipients": ["admin@example.com"],
    "subject_template": "🚨 Alert: Ticket {ticket_id}",
    "body_template": "..."
}
```

## 🔄 Workflow

1. **ETL** → Stiahne tikety z LiveAgent, filtruje systémové, uloží do Raw_Tickets
2. **AI Analysis** → Analyzuje nespracované tikety, uloží hodnotenie
3. **Alerting** → Posiela emaily pre kritické tikety
4. **Archiving** → Presunie staré tikety do mesačných archívov
5. **Daily Stats** → Agreguje denné štatistiky

## 📝 Pravidlá pre úpravy

1. **Pred úpravou** si prečítaj tento README
2. **Threading** používaj len pre manuálne tlačidlá
3. **Logging** - každá dlhodobá operácia musí volať `set_status()` a `add_log()`
4. **Error handling** - vždy ošetri exceptions a nastav `status="error"`
5. **Testy** - po úprave spusti aplikáciu a over funkčnosť
