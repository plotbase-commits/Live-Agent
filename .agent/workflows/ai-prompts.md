---
description: Dokumentácia QA a Alert promptov pre AI analýzu tiketov
---

# AI Prompty - QA a Alert Analysis

## Prehľad

Aplikácia používa dva AI prompty na analýzu tiketov:
1. **QA Prompt** - hodnotenie kvality práce agenta (skóre 0-100)
2. **Alert Prompt** - detekcia kritických situácií (is_critical: true/false)

Prompty sú uložené v súbore `prompts.json` a dajú sa editovať cez Settings → Prompt Editor.

---

## 1. QA Prompt

### Účel
Hodnotí výkon agenta v komunikácii so zákazníkom. Vracia skóre 0-100 a slovné hodnotenie.

### Rola
> Senior QA Špecialista so zameraním na Customer Experience

### Hodnotiace kritériá

| Kritérium | Váha | Popis |
|-----------|------|-------|
| **Empatia a ľudský prístup** | 0-100 | Autentický záujem, validácia emócií, prispôsobenie tónu |
| **Odbornosť a znalosť produktu** | 0-100 | Presné odpovede, vysvetlenie jednoduchým jazykom |
| **Riešenie problému a úplnosť** | 0-100 | Zodpovedanie VŠETKÝCH otázok, proaktivita |
| **Presnosť a bezchybovosť** | 0-100 | Žiadne chyby, dodržanie postupov |

### Penalizácie

**Ignorovanie otázky zákazníka:**
- Ak agent **nezodpovedal** čo i len jednu otázku → max 40 bodov v kategórii "Riešenie problému"
- Toto je považované za **kritické zlyhanie**

### Očakávaný výstup

```json
{
  "verbal_summary": "Stručné zhrnutie komunikácie",
  "criteria": {
    "empathy": 85,
    "expertise": 90,
    "problem_solving": 75,
    "error_rate": 100
  },
  "overall_score": 87
}
```

---

## 2. Alert Prompt

### Účel
Identifikuje rizikové situácie vyžadujúce pozornosť manažéra. Vracia `is_critical: true/false` a dôvod.

### Rola
> Risk Manager a Supervisor

### Kategórie rizík

#### 2.1 Logistické problémy

| Situácia | Kritické? |
|----------|-----------|
| Stratený balík | ✅ ÁNO |
| Zákazník sa sťažuje na meškanie | ✅ ÁNO |
| Agent informuje o meškaní, zákazník akceptuje | ❌ NIE |

#### 2.2 Reklamácie a kvalita

| Situácia | Kritické? |
|----------|-----------|
| Zákazník reklamuje hotový produkt | ✅ ÁNO |
| Zákazník žiada výmenu/opravu | ✅ ÁNO |
| Zákazník dáva feedback na návrh (pred výrobou) | ❌ NIE |
| Agent upozorňuje na nízku kvalitu súborov | ❌ NIE |

#### 2.3 Eskalácia a financie

| Situácia | Kritické? |
|----------|-----------|
| Zmienka o právnikoch, SOI, polícii | ✅ ÁNO |
| Vulgarizmy, vyhrážky | ✅ ÁNO |
| Žiadosť o refund (nespokojnosť) | ✅ ÁNO |
| Žiadosť o refund (duplicitná platba) | ❌ NIE |

---

## 3. Pravidlá pre predchádzanie falošne pozitívnym

### ⚠️ KĽÚČOVÉ: PRED vs PO objednávku

| Fáza | Typ komunikácie | Kritické? |
|------|-----------------|-----------|
| **PRED** objednávkou | Otázky na kvalitu súborov | ❌ NIE |
| **PRED** objednávkou | Žiadosť o expresnú výrobu | ❌ NIE |
| **PRED** objednávkou | Grafické korektúry návrhu | ❌ NIE |
| **PO** objednávke | Sťažnosť na kvalitu produktu | ✅ ÁNO |
| **PO** objednávke | Meškanie dodávky | ✅ ÁNO |
| **PO** objednávke | Reklamácia | ✅ ÁNO |

### Príklady rozhodnutí

#### ❌ NIE JE kritické:
- "Is this file quality OK for print?" (otázka pred objednávkou)
- "Stíhate to expresne do piatku?" (dopyt pred objednávkou)
- "Zväčšite text a zmeňte farbu" (korektúra návrhu)
- Agent: "Kvalita dát je nízka, nemôžeme garantovať ostrosť" (proaktívne upozornenie)

#### ✅ JE kritické:
- "The print quality is terrible, colors are wrong" (sťažnosť po dodaní)
- "Balík som nedostal, kde je?" (meškanie)
- "Chcem vrátenie peňazí, produkt je zlý" (reklamácia)
- "Dám to na Facebook ak to nevyriešite" (vyhrážka)

---

## 4. Očakávaný výstup Alert Prompt

```json
{
  "is_critical": true,
  "reason": "Reklamácie a Kvalita - Grafika: Zákazník reklamuje rozmazanú tlač na plátne"
}
```

alebo

```json
{
  "is_critical": false,
  "reason": ""
}
```

---

## 5. Súvisiace súbory

| Súbor | Popis |
|-------|-------|
| `prompts.json` | Definícia promptov (editovateľné) |
| `src/ai_service.py` | AI služba volaná na analýzu |
| `pages/Settings.py` | UI Prompt Editor |

---

## 6. História zmien

| Dátum | Zmena |
|-------|-------|
| 2025-12-05 | Pridané pravidlá pre PRED vs PO objednávku |
| 2025-12-05 | Pridané pravidlá pre grafické korektúry |
| 2025-12-05 | Pridané pravidlá pre proaktívne upozornenia agenta |
| 2025-12-05 | Pridané pravidlá pre expresné požiadavky |

---

*Posledná aktualizácia: 2025-12-05*
