# NekúpHlúposť 0.4.2

Webová aplikácia FastAPI. Odkazy na Bazoš načítava server; portál môže prístup obmedziť.

## Spustenie lokálne

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Otvoriť http://localhost:8000 (nie HTML súbor samostatne).

## Render

1. V GitHube vytvor nový repozitár a nahraj súbory z koreňa tohto ZIP (app.py, static/, requirements.txt, render.yaml).
2. Na https://dashboard.render.com zvoľ New > Blueprint a prepoj repozitár.
3. Skontroluj plán Free a potvrď vytvorenie služby.
4. Po nasadení otvor pridelenú HTTPS adresu a otestuj URL inzerátu.

Živé načítanie Bazoša nie je garantované. Ak ho Bazoš zablokuje, funguje ručné vloženie textu.
