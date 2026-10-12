# NekúpHlúposť 0.5

FastAPI prototyp. Pridané textové upozornenia na predvádzací kus, chýbajúce doklady, poškodenie, platbu vopred a blokovanie. Upozornenia nie sú overením pravdivosti ani hodnotením predávajúceho.

## Render
Build: `pip install -r requirements.txt`
Start: `uvicorn app:app --host 0.0.0.0 --port $PORT`

## Aktualizácia existujúceho GitHub repozitára
Nahraj obsah tohto ZIP (nie samotný ZIP) do koreňa repozitára; zachovaj `static/index.html` v priečinku `static`. GitHub commit spustí automatický deploy, ak je na Renderi nastavený Auto Deploy.
