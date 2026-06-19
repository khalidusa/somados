import requests, time, sys, json, base64, os, re, random
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

# تحميل المتغيرات من .env إن وُجد
_env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(_env_path):
    for _line in open(_env_path):
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip())

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO  = "khalidusa/somados"
GITHUB_FILE  = "data/flights.json"
IQD_TO_USD   = 1400
COMMISSION   = 0.07
USER_AGENT   = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.4 Safari/605.1.15"

ROUTES = [
    {'from':'ISTALL','to':'BGW','name':'Istanbul - Baghdad'},
    {'from':'ISTALL','to':'EBL','name':'Istanbul - Erbil'},
    {'from':'ISTALL','to':'BSR','name':'Istanbul - Basra'},
    {'from':'ISTALL','to':'NJF','name':'Istanbul - Najaf'},
    {'from':'ISTALL','to':'KIK','name':'Istanbul - Kirkuk'},
    {'from':'ISTALL','to':'ISU','name':'Istanbul - Sulaymaniyah'},
    {'from':'AYT','to':'BGW','name':'Antalya - Baghdad'},
    {'from':'AYT','to':'EBL','name':'Antalya - Erbil'},
    {'from':'SZF','to':'BGW','name':'Samsun - Baghdad'},
    {'from':'ESB','to':'BGW','name':'Ankara - Baghdad'},
    {'from':'ESB','to':'KIK','name':'Ankara - Kirkuk'},
    {'from':'BGW','to':'ISTALL','name':'Baghdad - Istanbul'},
    {'from':'EBL','to':'ISTALL','name':'Erbil - Istanbul'},
    {'from':'BSR','to':'ISTALL','name':'Basra - Istanbul'},
    {'from':'NJF','to':'ISTALL','name':'Najaf - Istanbul'},
    {'from':'KIK','to':'ISTALL','name':'Kirkuk - Istanbul'},
    {'from':'ISU','to':'ISTALL','name':'Sulaymaniyah - Istanbul'},
    {'from':'BGW','to':'AYT','name':'Baghdad - Antalya'},
    {'from':'EBL','to':'AYT','name':'Erbil - Antalya'},
    {'from':'BGW','to':'SZF','name':'Baghdad - Samsun'},
    {'from':'BGW','to':'ESB','name':'Baghdad - Ankara'},
    {'from':'KIK','to':'ESB','name':'Kirkuk - Ankara'},
]

def load_cookies():
    if not os.path.exists('cookies.txt'):
        print('❌ cookies.txt غير موجود'); sys.exit(1)
    d = {}
    for item in open('cookies.txt').read().strip().split(';'):
        item = item.strip()
        if '=' in item:
            k,v = item.split('=',1)
            d[k.strip()] = v.strip()
    if 'ASP.NET_SessionId' not in d:
        print('❌ الكوكيز منتهية - حدّث cookies.txt'); sys.exit(1)
    print(f'✅ {len(d)} كوكي محمّل')
    return d

def make_session(cookies):
    s = requests.Session()
    s.headers['User-Agent'] = USER_AGENT
    for k,v in cookies.items():
        s.cookies.set(k,v,domain='.alsafarigate.com')
        s.cookies.set(k,v,domain='www.alsafarigate.com')
    return s

def search(session, dep, arr, date):
    data = {
        'HasMultiPoint':'True','DisplayOnlyDirectFlights':'True',
        'DisplayOnlyRefundableFlights':'False','DisplayAdvancedSearch':'False',
        'HideCabinType':'False','HideProductInfo':'False','HideRuleFlag':'False',
        'DepartureName':dep+' Airport','DepartureCode':dep,
        'ArrivalName':arr+' Airport','ArrivalCode':arr,
        'DepartureDate':date,'MultiLegCount':'2','MultiPointCount':'4',
        'SearchType':'0','CabinClassType':'All',
        'AdultCount':'1','ChildCount':'0','InfantCount':'0',
        'IsDirectFlightsChecked':'false',
    }
    for i in range(4):
        for f in ['DepartureName','DepartureCode','ArrivalName','ArrivalCode','DepartureDate']:
            data[f'FlightSearchFilterLegs[{i}].{f}'] = ''
    hdrs = {'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8',
            'Accept':'*/*','Referer':'https://www.alsafarigate.com/',
            'Origin':'https://www.alsafarigate.com','X-Requested-With':'XMLHttpRequest'}
    try:
        r1 = session.post('https://www.alsafarigate.com/Air/SearchAir',data=data,headers=hdrs,timeout=30)
        if r1.status_code != 200: return None, f'HTTP {r1.status_code}'
        r2 = session.get('https://www.alsafarigate.com/Air/FlightResult',
                         headers={'Referer':'https://www.alsafarigate.com/'},timeout=30)
        if r2.status_code != 200: return None, f'HTTP {r2.status_code}'
        if 'Log-in' in r2.text[:5000]: return None, 'Session expired'
        return r2.text, None
    except Exception as e: return None, str(e)

def is_direct(row):
    logo = row.find(class_='booking-item-airline-logo')
    if logo:
        num = logo.find(class_='mt0')
        if num and ',' in num.get_text(): return False
    if row.find(class_='flight-info__segments--direct'): return True
    bolds = [e.get_text(strip=True) for e in row.find_all(class_='bold')]
    codes = [t for t in bolds if len(t)==3 and t.isupper() and t.isalpha()]
    if len(codes) > 2: return False
    dm = re.search(r'(\d+)\s+\d+\s*M', row.get_text(separator=' '))
    if dm and int(dm.group(1)) >= 5: return False
    return True

def get_price(row, airline):
    prices = {}
    for el in row.find_all(attrs={'data-amount':True}):
        code = el.get('data-code','').strip().upper()
        try:
            v = float(el.get('data-amount','0'))
            if v > 0: prices[code] = v
        except: pass
    raw = prices.get('USD') or (prices.get('IQD',0)/IQD_TO_USD) or (list(prices.values())[0] if prices else 0)
    if raw <= 0: return ''
    if 'iraqi' not in airline.lower(): raw = round(raw * (1+COMMISSION), 2)
    return str(round(raw, 2))

def get_baggage(row):
    """استخراج معلومات الأمتعة من صف الرحلة.
    - رحلات بأمتعة: <i class="fa fa-suitcase"></i> ثم text node "15 KG"
    - رحلات حقيبة يد فقط: <i class="fa fa-suitcase"></i> ثم <res data-key="HandLuggage"></res>
    """
    for icon in row.find_all('i', class_=lambda c: c and 'fa-suitcase' in c):
        sibling = icon.next_sibling
        while sibling is not None:
            # عنصر HandLuggage → حقيبة يد فقط
            if hasattr(sibling, 'get') and sibling.get('data-key','').lower() == 'handluggage':
                return 'Hand Bag'
            text = str(sibling).strip()
            if text:
                m = re.search(r'(\d+\s*(?:KG|PC))', text, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
            sibling = sibling.next_sibling
    # احتياط: regex على نص الصف كاملاً
    m = re.search(r'(Hand Bag|\d+\s*(?:KG|PC))', row.get_text(separator=' '), re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ''

def extract(html, route, date):
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    for btn in soup.find_all(class_='btnFlightSelect'):
        p = btn
        row = None
        for _ in range(15):
            p = p.parent
            if p is None: break
            if p.find(class_='booking-item-container'): row=p; break
        if not row or not is_direct(row): continue
        logo = row.find(class_='booking-item-airline-logo')
        airline = fnum = ''
        if logo:
            img = logo.find('img')
            if img: airline = img.get('alt','') or img.get('title','')
            n = logo.find(class_='mt0')
            if n: fnum = n.get_text(strip=True)
        bolds = [e.get_text(strip=True) for e in row.find_all(class_='bold')]
        dc=dt=at=ac=''
        for t in bolds:
            if len(t)==3 and t.isupper() and t.isalpha():
                if not dc: dc=t
                else: ac=t
            elif len(t)==5 and t[2]==':' and t[:2].isdigit() and t[3:].isdigit():
                if not dt: dt=t
                else: at=t
        dur = ''
        dm = re.search(r'(\d+)\s+(\d+)\s*M', row.get_text(separator=' '))
        if dm: dur = f"{dm.group(1)}h {dm.group(2)}m"
        quota = row.find(class_='spn-quota')
        cls = row.find(class_='mb0')
        fare = row.find(class_='btn-theme')
        baggage = get_baggage(row)
        results.append({
            'route':route,'search_date':date,'airline':airline,
            'flight_number':fnum,'from_code':dc,'departure_time':dt,
            'to_code':ac,'arrival_time':at,'duration':dur,
            'price':get_price(row,airline),'currency':'USD',
            'seats_available':quota.get_text(strip=True) if quota else '',
            'class':cls.get_text(strip=True) if cls else '',
            'fare_type':fare.get_text(strip=True) if fare else '',
            'baggage':baggage,
        })
    return results

TG_TOKEN = os.environ.get('TG_TOKEN', '8856103719:AAGiK2kxxR-7j0nYyBpSJrtmbsFV6_RjwJs')
TG_CHAT  = os.environ.get('TG_CHAT',  '725243049')

def send_telegram(msg):
    try:
        requests.post(
            f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage',
            data={'chat_id': TG_CHAT, 'text': msg, 'parse_mode': 'HTML'},
            timeout=10
        )
    except Exception: pass

def push_github(data):
    hdrs = {'Authorization':f'token {GITHUB_TOKEN}',
            'Accept':'application/vnd.github.v3+json'}
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}'
    sha = None
    r = requests.get(url, headers=hdrs)
    if r.status_code == 200: sha = r.json().get('sha')
    content = base64.b64encode(json.dumps(data,ensure_ascii=False,indent=2).encode()).decode()
    payload = {'message':f'Update {datetime.now().strftime("%Y-%m-%d %H:%M")}',
               'content':content,'branch':'main'}
    if sha: payload['sha'] = sha
    r = requests.put(url, headers=hdrs, json=payload)
    if r.status_code in [200,201]: print('✅ رُفع لـ GitHub'); return True
    print(f'❌ فشل: {r.status_code} {r.text[:100]}'); return False

def fetch_date(cookies, dep, arr, date, route_name):
    """بحث تاريخ واحد بـ session مستقل — يُستدعى من thread."""
    time.sleep(random.uniform(0.2, 0.7))
    s = make_session(cookies)
    html, err = search(s, dep, arr, date)
    if err:
        return date, None, err
    return date, extract(html, route_name, date), None

def main():
    print('='*70)
    print(f'  Somados Updater - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('='*70)
    cookies = load_cookies()
    start = datetime.now() + timedelta(days=1)
    dates = [(start+timedelta(days=i)).strftime('%d.%m.%Y') for i in range(10)]
    print(f'\n📅 {dates[0]} → {dates[-1]} | 🛫 {len(ROUTES)} مسار\n')
    all_data = {}
    total = 0
    t_start = time.time()
    for ri, route in enumerate(ROUTES, 1):
        name = route['name']
        print(f'[{ri}/{len(ROUTES)}] {name}')
        flights = []
        results = {}

        with ThreadPoolExecutor(max_workers=8) as ex:
            future_map = {
                ex.submit(fetch_date, cookies, route['from'], route['to'], date, name): (di, date)
                for di, date in enumerate(dates, 1)
            }
            for future in as_completed(future_map):
                di, date = future_map[future]
                d, f, err = future.result()
                if err:
                    if 'expired' in err.lower():
                        print(f'\n⚠️ الجلسة منتهية'); sys.exit(1)
                    results[di] = (date, None, err)
                else:
                    results[di] = (date, f, None)

        for di in sorted(results):
            date, f, err = results[di]
            if err:
                print(f'  [{di}/10] {date}... ERR: {err}')
            else:
                print(f'  [{di}/10] {date}... OK {len(f)}')
                flights.extend(f)

        all_data[name] = flights
        total += len(flights)

    elapsed = round(time.time() - t_start)
    mins, secs = divmod(elapsed, 60)
    output = {'updated_at': datetime.now().isoformat(), 'total': total, 'routes': all_data}
    print(f'\n📤 يرفع {total} رحلة...')
    ok = push_github(output)

    # إشعار Telegram
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    if ok:
        send_telegram(
            f'✅ <b>somados.com — تحديث ناجح</b>\n'
            f'🕐 {now_str}\n'
            f'✈️ {total} رحلة عبر {len(ROUTES)} مسار\n'
            f'⏱ الوقت: {mins}د {secs}ث'
        )
        print(f'📱 تم إرسال إشعار تيليجرام')
    else:
        send_telegram(
            f'❌ <b>somados.com — فشل الرفع</b>\n'
            f'🕐 {now_str}\n'
            f'راجع اللوق للتفاصيل'
        )

if __name__=='__main__':
    main()
