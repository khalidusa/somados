import requests, time, sys, json, base64, os
from datetime import datetime, timedelta

WORK_DIR = os.path.dirname(os.path.abspath(__file__))

_env_path = os.path.join(WORK_DIR, '.env')
if os.path.exists(_env_path):
    for _line in open(_env_path):
        _line = _line.strip()
        if _line and not _line.startswith('#') and '=' in _line:
            _k, _v = _line.split('=', 1)
            os.environ.setdefault(_k.strip(), _v.strip())

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
GITHUB_REPO  = "khalidusa/somados"
GITHUB_FILE  = "data/flights.json"
TG_TOKEN     = os.environ.get('TG_TOKEN', '8856103719:AAGiK2kxxR-7j0nYyBpSJrtmbsFV6_RjwJs')
TG_CHAT      = os.environ.get('TG_CHAT',  '725243049')

B2B_BASE     = "https://admin.b2bcheetah.com"
B2B_EMAIL    = os.environ.get('B2B_EMAIL', 'bluemoontravell21@gmail.com')
B2B_PASSWORD = os.environ.get('B2B_PASSWORD', 'B123456@B')
USER_AGENT   = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
COMMISSION   = 0.08

AIRPORTS_AR = {
    'BGW': 'بغداد',
    'EBL': 'أربيل',
    'BSR': 'البصرة',
    'NJF': 'النجف',
    'KIK': 'كركوك',
    'ISU': 'السليمانية',
    'IST': 'إسطنبول',
    'SAW': 'إسطنبول (صبيحة)',
    'AYT': 'أنطاليا',
    'ESB': 'أنقرة',
    'SZF': 'سامسون',
    'TZX': 'طرابزون',
    'ADB': 'إزمير',
    'DLM': 'دالامان',
    'BJV': 'بودروم',
    'GZT': 'غازي عنتاب',
    'KYA': 'قونية',
    'VAN': 'وان',
    'ERZ': 'أرضروم',
}

AIRLINES_AR = {
    'AJet': 'أناضول جت',
    'ajet': 'أناضول جت',
    'Ajet': 'أناضول جت',
    'AJET': 'أناضول جت',
    'VF': 'أناضول جت',
    'Pegasus Airlines': 'بيغاسوس',
    'Pegasus': 'بيغاسوس',
    'PC': 'بيغاسوس',
    'Turkish Airlines': 'الخطوط التركية',
    'TK': 'الخطوط التركية',
    'Iraqi Airways': 'الخطوط الجوية العراقية',
    'IA': 'الخطوط الجوية العراقية',
    'Fly Baghdad': 'فلاي بغداد',
    'IF': 'فلاي بغداد',
    'SunExpress': 'صن إكسبريس',
    'XQ': 'صن إكسبريس',
    'Air Arabia': 'العربية للطيران',
    'G9': 'العربية للطيران',
    'FlyDubai': 'فلاي دبي',
    'flydubai': 'فلاي دبي',
    'FZ': 'فلاي دبي',
    'Qatar Airways': 'الخطوط القطرية',
    'QR': 'الخطوط القطرية',
    'Emirates': 'طيران الإمارات',
    'EK': 'طيران الإمارات',
    'Tailwind Airlines': 'تيل ويند',
    'TI': 'تيل ويند',
    'Corendon Airlines': 'كورندون',
    'XC': 'كورندون',
}

ROUTES = [
    {'from': 'IST', 'to': 'BGW', 'name': 'Istanbul - Baghdad'},
    {'from': 'IST', 'to': 'EBL', 'name': 'Istanbul - Erbil'},
    {'from': 'IST', 'to': 'BSR', 'name': 'Istanbul - Basra'},
    {'from': 'IST', 'to': 'NJF', 'name': 'Istanbul - Najaf'},
    {'from': 'IST', 'to': 'KIK', 'name': 'Istanbul - Kirkuk'},
    {'from': 'IST', 'to': 'ISU', 'name': 'Istanbul - Sulaymaniyah'},
    {'from': 'AYT', 'to': 'BGW', 'name': 'Antalya - Baghdad'},
    {'from': 'AYT', 'to': 'EBL', 'name': 'Antalya - Erbil'},
    {'from': 'SZF', 'to': 'BGW', 'name': 'Samsun - Baghdad'},
    {'from': 'ESB', 'to': 'BGW', 'name': 'Ankara - Baghdad'},
    {'from': 'ESB', 'to': 'KIK', 'name': 'Ankara - Kirkuk'},
    {'from': 'BGW', 'to': 'IST', 'name': 'Baghdad - Istanbul'},
    {'from': 'EBL', 'to': 'IST', 'name': 'Erbil - Istanbul'},
    {'from': 'BSR', 'to': 'IST', 'name': 'Basra - Istanbul'},
    {'from': 'NJF', 'to': 'IST', 'name': 'Najaf - Istanbul'},
    {'from': 'KIK', 'to': 'IST', 'name': 'Kirkuk - Istanbul'},
    {'from': 'ISU', 'to': 'IST', 'name': 'Sulaymaniyah - Istanbul'},
    {'from': 'BGW', 'to': 'AYT', 'name': 'Baghdad - Antalya'},
    {'from': 'EBL', 'to': 'AYT', 'name': 'Erbil - Antalya'},
    {'from': 'BGW', 'to': 'SZF', 'name': 'Baghdad - Samsun'},
    {'from': 'BGW', 'to': 'ESB', 'name': 'Baghdad - Ankara'},
    {'from': 'KIK', 'to': 'ESB', 'name': 'Kirkuk - Ankara'},
]


def b2b_login():
    r = requests.post(f"{B2B_BASE}/v2/login",
        json={"email": B2B_EMAIL, "password": B2B_PASSWORD},
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": USER_AGENT},
        timeout=15)
    data = r.json()
    token = data.get('token')
    if not token:
        print(f"❌ فشل تسجيل الدخول: {data}")
        sys.exit(1)
    print(f"✅ تسجيل دخول b2bcheetah (وكيل)")
    return token


def b2b_search(token, dep, arr, date_str):
    hdrs = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://b2bcheetah.com",
        "User-Agent": USER_AGENT,
    }
    try:
        r = requests.post(f"{B2B_BASE}/api/search-progressive",
            json={"from_flight": dep, "to_flight": arr, "date_flight": date_str,
                  "cabin": "economy", "adult": 1, "child": 0, "infant": 0},
            headers=hdrs, timeout=30)
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        data = r.json()
        poll_url = data.get('poll_url')
        if not poll_url:
            return None, "no poll_url"
    except Exception as e:
        return None, str(e)

    for _ in range(10):
        time.sleep(3)
        try:
            r2 = requests.get(poll_url, headers=hdrs, timeout=15)
            result = r2.json()
            if result.get('completed') or result.get('progress', {}).get('percentage', 0) >= 100:
                return result.get('results', []), None
        except Exception as e:
            return None, str(e)
    try:
        return result.get('results', []), None
    except:
        return None, "timeout"


def extract_flights(results, route_name, date_str):
    flights = []
    for item in results:
        journeys = item.get('journeys', [])
        if not journeys:
            continue
        journey = journeys[0]

        if journey.get('stops', 0) > 0:
            continue

        segments = journey.get('segments', [])
        if not segments:
            continue
        seg = segments[0]

        airline_en = item.get('airline', '') or item.get('validating_airline', {}).get('en', '')
        airline_code = item.get('validating_airline', {}).get('abb', '')
        airline = AIRLINES_AR.get(airline_en) or AIRLINES_AR.get(airline_code) or airline_en

        seg_num = seg.get('number', '')
        if airline_code and seg_num.startswith(airline_code):
            flight_num = seg_num
        else:
            flight_num = f"{airline_code}{seg_num}".strip()

        dep_time = journey.get('departure', {}).get('time', '')
        arr_time = journey.get('arrival', {}).get('time', '')
        dep_time_short = dep_time.split(' ')[-1] if ' ' in dep_time else dep_time
        arr_time_short = arr_time.split(' ')[-1] if ' ' in arr_time else arr_time

        # أكواد المطارات بالإنجليزي (للفلترة في الموقع) + الاسم العربي للعرض
        from_code = journey.get('departure', {}).get('airport', {}).get('code', '')
        to_code = journey.get('arrival', {}).get('airport', {}).get('code', '')
        from_name = AIRPORTS_AR.get(from_code, from_code)
        to_name = AIRPORTS_AR.get(to_code, to_code)

        duration = journey.get('duration', {}).get('text', '')

        price_usd = float(item.get('usd') or item.get('netprice') or 0)
        if price_usd <= 0:
            continue
        price_usd = round(price_usd * (1 + COMMISSION), 2)

        baggage_info = seg.get('baggage', {})
        baggage_kg = str(baggage_info.get('allowance', '')).strip()
        baggage_unit = baggage_info.get('unit', '')
        baggage = f"{baggage_kg} {baggage_unit}".strip() if baggage_kg and baggage_kg != '0' else 'Hand Bag'

        seats = seg.get('seats_remaining', '')
        cls = seg.get('class', 'Economy')

        flights.append({
            'route': route_name,
            'search_date': datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y'),
            'airline': airline,
            'flight_number': flight_num,
            'from_code': from_code,    # كود إنجليزي للفلترة (IST, BGW...)
            'from_name': from_name,    # اسم عربي للعرض
            'departure_time': dep_time_short,
            'to_code': to_code,        # كود إنجليزي للفلترة
            'to_name': to_name,        # اسم عربي للعرض
            'arrival_time': arr_time_short,
            'duration': duration,
            'price': str(price_usd),
            'currency': 'USD',
            'seats_available': str(seats) if seats else '',
            'class': cls,
            'fare_type': '',
            'baggage': baggage,
        })
    return flights


def send_telegram(msg):
    try:
        requests.post(
            f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage',
            data={'chat_id': TG_CHAT, 'text': msg, 'parse_mode': 'HTML'},
            timeout=10
        )
    except Exception:
        pass


def push_github(data):
    hdrs = {'Authorization': f'token {GITHUB_TOKEN}',
            'Accept': 'application/vnd.github.v3+json'}
    url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}'
    sha = None
    r = requests.get(url, headers=hdrs)
    if r.status_code == 200:
        sha = r.json().get('sha')
    content = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode()
    payload = {'message': f'Update {datetime.now().strftime("%Y-%m-%d %H:%M")}',
               'content': content, 'branch': 'main'}
    if sha:
        payload['sha'] = sha
    r = requests.put(url, headers=hdrs, json=payload)
    if r.status_code in [200, 201]:
        print('✅ رُفع لـ GitHub')
        return True
    print(f'❌ فشل: {r.status_code} {r.text[:100]}')
    return False


def main():
    print('=' * 70)
    print(f'  Somados Updater (b2bcheetah) - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70)

    token = b2b_login()

    start = datetime.now() + timedelta(days=1)
    dates = [(start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(10)]
    print(f'\n📅 {dates[0]} → {dates[-1]} | 🛫 {len(ROUTES)} مسار\n')

    all_data = {}
    total = 0
    t_start = time.time()

    for ri, route in enumerate(ROUTES, 1):
        name = route['name']
        print(f'[{ri}/{len(ROUTES)}] {name}')
        flights = []
        for di, date in enumerate(dates, 1):
            print(f'  [{di}/10] {date}... ', end='', flush=True)
            results, err = b2b_search(token, route['from'], route['to'], date)
            if err:
                print(f'ERR: {err}')
                continue
            f = extract_flights(results, name, date)
            flights.extend(f)
            print(f'OK {len(f)}')

        # Dedup: نفس الخط+رقم+وقت+تاريخ+أمتعة → الأرخص
        dedup = {}
        for f in flights:
            has_bag = f['baggage'] != 'Hand Bag' and not f['baggage'].startswith('0')
            bag_key = 'bag' if has_bag else 'nobag'
            key = f"{f['airline']}|{f['flight_number']}|{f['departure_time']}|{f['search_date']}|{bag_key}"
            if key not in dedup or float(f['price'] or 9999) < float(dedup[key]['price'] or 9999):
                dedup[key] = f
        flights = list(dedup.values())

        all_data[name] = flights
        total += len(flights)

    elapsed = round(time.time() - t_start)
    mins, secs = divmod(elapsed, 60)
    output = {'updated_at': datetime.now().isoformat(), 'total': total, 'routes': all_data}
    print(f'\n📤 يرفع {total} رحلة...')
    ok = push_github(output)

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    if ok:
        send_telegram(
            f'✅ <b>somados.com — تحديث ناجح</b>\n'
            f'🕐 {now_str}\n'
            f'✈️ {total} رحلة عبر {len(ROUTES)} مسار\n'
            f'⏱ الوقت: {mins}د {secs}ث\n'
            f'📡 المصدر: b2bcheetah (وكيل)'
        )
        print('📱 تم إرسال إشعار تيليجرام')
    else:
        send_telegram(
            f'❌ <b>somados.com — فشل الرفع</b>\n'
            f'🕐 {now_str}\n'
            f'راجع اللوق للتفاصيل'
        )


if __name__ == '__main__':
    main()
