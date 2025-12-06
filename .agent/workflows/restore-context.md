---
description: Načíta kontext z predchádzajúcich session a pokračuje v práci
---

# Obnovenie kontextu

Pri začiatku novej konverzácie urob:

1. Prečítaj posledný conversation log:
   ```
   ls ~/.gemini/conversations/
   cat ~/.gemini/conversations/[najnovší]/*.md
   ```

2. Prečítaj architektúru projektu:
   ```
   cat .agent/workflows/architecture.md
   ```

3. Pozri posledné zmeny v Git:
   ```
   git log --oneline -10
   ```

4. Pokračuj v práci podľa "Otvorené úlohy" v logu.

## Pravidlá pre logging

- Po každom commite aktualizuj conversation log
- Rozdeľ témy do samostatných súborov
- Ukladaj do `~/.gemini/conversations/YYYY-MM-DD_projekt/`
- Formát: USER/ASSISTANT výmeny + výsledky

## Štruktúra logov

```
~/.gemini/conversations/
├── YYYY-MM-DD_projekt.md          # Súhrn
└── YYYY-MM-DD_projekt/            # Detaily
    ├── 01_tema.md
    ├── 02_tema.md
    └── ...
```
