"""NekúpHlúposť 0.4 — server-side Bazoš listing inspection."""
import ipaddress
import re
import socket
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

app = FastAPI(title="NekúpHlúposť", docs_url=None, redoc_url=None)
MAX_BYTES = 1_500_000

class AnalyzeInput(BaseModel):
    url: str = Field(default="", max_length=700)
    text: str = Field(default="", max_length=30000)
    price: str = Field(default="", max_length=100)


def safe_url(raw):
    try:
        u = urlsplit(raw.strip())
        if u.scheme != 'https' or u.hostname not in ('mobil.bazos.sk', 'www.bazos.sk', 'bazos.sk', 'pc.bazos.sk', 'elektro.bazos.sk', 'sport.bazos.sk', 'auto.bazos.sk'):
            raise ValueError('Podporované sú iba HTTPS odkazy na vybrané domény Bazoš.sk.')
        if u.username or u.password or u.port not in (None, 443):
            raise ValueError('Neplatný odkaz.')
        if not re.fullmatch(r'/inzerat/\d+/[a-zA-Z0-9-]+\.php', u.path):
            raise ValueError('Odkaz musí smerovať na konkrétny inzerát Bazoša.')
        # Avoid URLs that redirect to unrelated hosts. IP check protects against DNS rebinding on initial lookup.
        ips = socket.getaddrinfo(u.hostname, 443, type=socket.SOCK_STREAM)
        if not ips or any(not ipaddress.ip_address(row[4][0]).is_global for row in ips):
            raise ValueError('Nepovolená cieľová adresa.')
        return f'https://{u.hostname}{u.path}'
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError:
        raise HTTPException(status_code=502, detail='Doména momentálne nie je dostupná.')


def parse_listing(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script','style','nav','footer','header']): tag.decompose()
    h = soup.select_one('h1')
    title = h.get_text(' ', strip=True) if h else ''
    desc = soup.select_one('.popisdetail') or soup.select_one('[itemprop="description"]')
    if desc:
        description = desc.get_text(' ', strip=True)
    else:
        # Fallback: metadata, but do not pretend it is the full listing.
        meta = soup.find('meta', attrs={'name':'description'})
        description = meta.get('content','') if meta else ''
    price_el = soup.select_one('.inzeratycena') or soup.select_one('[itemprop="price"]')
    price = price_el.get_text(' ',strip=True) if price_el else ''
    images = []
    for img in soup.select('img'):
        src = img.get('data-src') or img.get('src') or ''
        if 'bazos' in src and ('.jpg' in src.lower() or '.webp' in src.lower()):
            if src.startswith('https://') and src not in images: images.append(src)
    return {'title':title[:250], 'description':description[:16000], 'price':price[:80], 'images':images[:12], 'source':url}


def normalize(text):
    import unicodedata
    return ''.join(c for c in unicodedata.normalize('NFKD',text.lower()) if not unicodedata.combining(c))


def analyze(title, description, price=''):
    text = normalize(title+' '+description)
    def has(*patterns): return any(re.search(p,text,re.I) for p in patterns)
    checks = [
        {'label':'Model zariadenia', 'found':has(r'\b(?:samsung|galaxy|iphone|xiaomi|pixel|honor|motorola|huawei)\b.{0,28}\b[a-z]?\d{1,3}(?:\s*\+|\s*plus|\s*ultra)?\b',r'\bs2[0-9]\s*\+\b'), 'detail':'Model je v texte uvedený; presnú variantu over na zariadení.'},
        {'label':'Opis stavu', 'found':has(r'bez poskoden',r'bez skraban',r'plne funkc',r'ako nov',r'\bstav\b',r'poskod',r'skraban'), 'detail':'Stav uvádza predávajúci; nie je nezávisle overený.'},
        {'label':'Pôvod alebo záruka', 'found':has(r'\bnay\b',r'\balza\b',r'kupovan',r'kupen',r'zaruk',r'faktur',r'doklad'), 'detail':'Zmienený pôvod či záruka nie sú dôkazom existencie dokladu.'},
        {'label':'Odovzdanie', 'found':has(r'osobn.{0,12}odber',r'osobn.{0,12}prevz',r'dobierk',r'posielam',r'zasielam'), 'detail':'Spôsob odovzdania neznamená možnosť zariadenie vyskúšať.'}
    ]
    questions = ['Môžem vidieť pôvodný doklad o kúpe a overiť sériové číslo alebo IMEI?', 'Môžem zariadenie pred zaplatením zapnúť, vyskúšať a skontrolovať všetky funkcie?', 'Aká je reálna kondícia batérie a ako bola meraná?']
    notes = []
    if has(r'vystaven',r'predvadzac',r'demo kus'):
        notes.append('Predávajúci spomína vystavený/predvádzací kus. Over používanie, batériu, displej a podmienky záruky.')
    if has(r'4900\s*mah',r'typick.{0,12}kapacit'):
        notes.append('Údaj 4900 mAh je nominálna kapacita modelu, nie dôkaz o aktuálnom zdraví batérie.')
    if has(r'zaruk'):
        notes.append('Uvádzanú záruku si over podľa nákupného dokladu a podmienok predajcu.')
    if price:
        notes.append('Uvedená cena nebola porovnaná s aktuálnymi ponukami na trhu.')
    return {'checks':checks,'matched':sum(x['found'] for x in checks),'total':len(checks),'notes':notes,'questions':questions,'disclaimer':'Ide o kontrolu tvrdení v inzeráte, nie o potvrdenie pravdivosti, bezpečnosti predaja alebo výhodnosti ceny.'}


@app.get('/')
def home(): return FileResponse('static/index.html')


@app.post('/api/analyze')
async def api_analyze(data: AnalyzeInput):
    listing = None
    if data.url.strip():
        url = safe_url(data.url)
        try:
            async with httpx.AsyncClient(timeout=12,follow_redirects=False,trust_env=False,headers={'User-Agent':'Mozilla/5.0 (compatible; NekupHlupostPrototype/0.4)','Accept':'text/html'}) as client:
                async with client.stream('GET',url) as r:
                    if r.status_code != 200:
                        raise HTTPException(status_code=502,detail=f'Bazoš nevrátil inzerát (HTTP {r.status_code}). Skús vložiť text inzerátu.')
                    if 'text/html' not in r.headers.get('content-type',''):
                        raise HTTPException(status_code=502,detail='Odpoveď stránky nie je HTML.')
                    content = bytearray()
                    async for chunk in r.aiter_bytes():
                        content.extend(chunk)
                        if len(content)>MAX_BYTES: raise HTTPException(status_code=413,detail='Stránka je príliš veľká.')
                    html = content.decode(r.encoding or 'utf-8',errors='replace')
            listing = parse_listing(html,url)
            if not listing['description']:
                raise HTTPException(status_code=422,detail='Text inzerátu sa nepodarilo načítať. Vlož ho ručne.')
        except httpx.RequestError:
            raise HTTPException(status_code=502,detail='Inzerát sa nepodarilo načítať. Skús vložiť text inzerátu.')
    else:
        if len(data.text.strip())<30:
            raise HTTPException(status_code=400,detail='Vlož odkaz alebo aspoň 30 znakov textu inzerátu.')
        listing={'title':'Ručne vložený inzerát','description':data.text.strip(),'price':data.price.strip(),'images':[],'source':'Ručný vstup'}
    return {'listing':listing,'analysis':analyze(listing['title'],listing['description'],listing['price'])}
