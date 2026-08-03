import requests, time, sys, json, base64, os, re, threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# أسعار ثابتة للخطوط الجوية العراقية — الذهاب (تركيا→العراق) فقط، حسب (مطار المغادرة، مطار الوصول)
# العودة (العراق→تركيا) تبقى بالتسعير الافتراضي
IRAQI_FIXED_PRICE = {
    ('IST', 'BGW'): 315,   # اسطنبول → بغداد
    ('SAW', 'BGW'): 265,   # صبيحة → بغداد
    ('IST', 'BSR'): 315,   # اسطنبول → البصرة
    ('IST', 'EBL'): 300,   # اسطنبول → أربيل
    ('IST', 'NJF'): 265,   # اسطنبول → النجف
    ('IST', 'KIK'): 305,   # اسطنبول → كركوك
    ('SZF', 'BGW'): 220,   # سامسون → بغداد
    ('ESB', 'BGW'): 285,   # أنقرة → بغداد
    ('AYT', 'BGW'): 270,   # أنطاليا → بغداد
    ('ESB', 'KIK'): 250,   # أنقرة → كركوك
}

AIRPORTS_AR = {
    'BGW': 'بغداد',    'EBL': 'أربيل',    'BSR': 'البصرة',
    'NJF': 'النجف',    'KIK': 'كركوك',    'ISU': 'السليمانية',
    'IST': 'إسطنبول',  'SAW': 'إسطنبول (صبيحة)', 'AYT': 'أنطاليا',
    'ESB': 'أنقرة',    'SZF': 'سامسون',   'TZX': 'طرابزون',
    'ADB': 'إزمير',    'DLM': 'دالامان',  'BJV': 'بودروم',
    'GZT': 'غازي عنتاب', 'KYA': 'قونية', 'VAN': 'وان', 'ERZ': 'أرضروم',
}

AIRLINES_AR = {
    'AJet': 'أناضول جت',        'ajet': 'أناضول جت',
    'Ajet': 'أناضول جت',        'AJET': 'أناضول جت',       'VF': 'أناضول جت',
    'Pegasus Airlines': 'بيغاسوس', 'Pegasus': 'بيغاسوس',  'PC': 'بيغاسوس',
    'Turkish Airlines': 'الخطوط التركية',                   'TK': 'الخطوط التركية',
    'Iraqi Airways': 'الخطوط الجوية العراقية',              'IA': 'الخطوط الجوية العراقية',
    'Fly Baghdad': 'فلاي بغداد',                            'IF': 'فلاي بغداد',
    'Basra Airlines': 'طيران البصرة', 'Basra': 'طيران البصرة', 'BH': 'طيران البصرة',
    'UR Airlines': 'طيران اور', 'Ur Airlines': 'طيران اور',
    'UR': 'طيران اور', 'UD': 'طيران اور',
    'SunExpress': 'صن إكسبريس',                             'XQ': 'صن إكسبريس',
    'Air Arabia': 'العربية للطيران',                         'G9': 'العربية للطيران',
    'FlyDubai': 'فلاي دبي', 'flydubai': 'فلاي دبي',        'FZ': 'فلاي دبي',
    'Qatar Airways': 'الخطوط القطرية',                       'QR': 'الخطوط القطرية',
    'Emirates': 'طيران الإمارات',                            'EK': 'طيران الإمارات',
    'Tailwind Airlines': 'تيل ويند',                        'TI': 'تيل ويند',
    'Corendon Airlines': 'كورندون',                         'XC': 'كورندون',
}

ROUTES = [
    {'from': 'IST', 'to': 'BGW', 'name': 'Istanbul - Baghdad', 'also': [('SAW', 'BGW')]},
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
                 "User-Agent": USER_AGENT}, timeout=15)
    token = r.json().get('token')
    if not token:
        print(f"❌ فشل تسجيل الدخول")
        sys.exit(1)
    print(f"✅ تسجيل دخول b2bcheetah (وكيل)")
    return token


# ─── مدير Token مشترك بين الـ workers (يعيد تسجيل الدخول عند انتهاء الصلاحية) ───
_token_lock = threading.Lock()
_token_box  = {'val': None}

def get_token():
    if _token_box['val'] is None:
        with _token_lock:
            if _token_box['val'] is None:
                _token_box['val'] = b2b_login()
    return _token_box['val']

def refresh_token(old):
    """يعيد تسجيل الدخول مرة واحدة فقط حتى لو ناداها أكثر من worker بنفس الوقت"""
    with _token_lock:
        if _token_box['val'] == old or _token_box['val'] is None:
            _token_box['val'] = b2b_login()
    return _token_box['val']


# ─── منظّم معدّل الطلبات العام (يمنع تجاوز حد السيرفر ~60 طلب/دقيقة لكل حساب) ───
# كل طلبات الـ workers تمر من هنا: فاصل ≥1.1 ثانية بين أي طلبين = ~55 طلب/دقيقة (تحت الحد)
_rate_lock = threading.Lock()
_last_call = {'t': 0.0}
MIN_INTERVAL = 1.1

def _throttle():
    with _rate_lock:
        wait = MIN_INTERVAL - (time.time() - _last_call['t'])
        if wait > 0:
            time.sleep(wait)
        _last_call['t'] = time.time()


def _start_search(dep, arr, date_str):
    """يبدأ البحث ويرجع (poll_url, error). يعالج 401 (تجديد token) و429 (تجاوز الحد)."""
    for attempt in range(5):
        token = get_token()
        hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                "Accept": "application/json", "Origin": "https://b2bcheetah.com", "User-Agent": USER_AGENT}
        try:
            _throttle()
            r = requests.post(f"{B2B_BASE}/api/search-progressive",
                json={"from_flight": dep, "to_flight": arr, "date_flight": date_str,
                      "cabin": "economy", "adult": 1, "child": 0, "infant": 0},
                headers=hdrs, timeout=30)
            if r.status_code in (401, 403):
                refresh_token(token)          # انتهت صلاحية الـ token → جدّده وأعد المحاولة
                continue
            if r.status_code == 429:          # تجاوز حد الطلبات → انتظر ثم أعد المحاولة
                retry_after = int(r.headers.get('Retry-After', 0)) or 30
                time.sleep(min(retry_after, 60))
                continue
            if r.status_code != 200:
                return None, hdrs, f"HTTP {r.status_code}"
            poll_url = r.json().get('poll_url')
            if poll_url:
                return poll_url, hdrs, None
            time.sleep(2)                     # لا يوجد poll_url → مهلة قصيرة وأعد المحاولة
        except Exception as e:
            time.sleep(2)
            if attempt >= 4:
                return None, hdrs, str(e)
    return None, hdrs, "429/no poll_url"


def b2b_search(dep, arr, date_str):
    poll_url, hdrs, err = _start_search(dep, arr, date_str)
    if err:
        return [], err

    # انتظر أولي 5s قبل أول استفسار
    time.sleep(5)

    best_results = []
    last_err = None
    for attempt in range(20):
        try:
            _throttle()
            resp = requests.get(poll_url, headers=hdrs, timeout=15)
            if resp.status_code == 429:       # تجاوز الحد → انتظر بدون احتساب محاولة فعلية
                time.sleep(5)
                continue
            result = resp.json()
            current = result.get('results', [])
            if len(current) > len(best_results):
                best_results = current
            completed = result.get('completed') or result.get('progress', {}).get('percentage', 0) >= 100
            # ⚠️ الـ API يعلن الاكتمال مبكراً ثم النتائج تتدفق بعده —
            # لا نثق بالاكتمال إلا بعد وصول نتائج فعلية، أو بعد 8 محاولات للتأكد أنه فارغ حقاً
            if completed and (len(best_results) > 0 and attempt >= 3):
                return best_results, None
            if completed and attempt >= 8:
                return best_results, None
        except Exception as e:
            last_err = str(e)
            if attempt >= 5:
                return best_results, last_err
        time.sleep(2)
    return best_results, None


def _normalize_time(t):
    """توحيد الوقت إلى HH:MM — يقبل: '10:30', '2026-06-27 10:30', '10:30:00'"""
    if not t:
        return ''
    # خذ آخر جزء بعد المسافة (إذا كان تاريخ + وقت)
    part = t.strip().split(' ')[-1]
    # خذ أول جزءين مفصولين بـ : (HH:MM فقط بدون ثواني)
    hm = ':'.join(part.split(':')[:2])
    return hm


def extract_flights(results, route_name, date_str):
    flights = []
    for item in results:
        try:
            journeys = item.get('journeys') or []
            if not journeys:
                continue
            journey = journeys[0]

            # مباشر فقط: stops=0 و segment واحد فقط
            if (journey.get('stops') or 0) > 0:
                continue
            segments = journey.get('segments') or []
            if len(segments) != 1:
                continue
            seg = segments[0]

            # كود الخط — المصدر الموثوق: segment.airline.code ثم airline_code (لا validating_airline)
            seg_airline = seg.get('airline') or {}
            airline_code = (seg_airline.get('code') or item.get('airline_code') or '').strip()

            # اسم الخط: القاموس العربي أولاً، ثم name_ar من الـ segment، ثم الاسم الخام
            item_airline = (item.get('airline') or '').strip()
            airline = (AIRLINES_AR.get(item_airline)
                       or AIRLINES_AR.get(airline_code)
                       or (seg_airline.get('name_ar') or '').strip()
                       or (seg_airline.get('name') or '').strip()
                       or item_airline or airline_code)
            if not airline:
                continue  # تخطّ الرحلات بدون اسم خط

            # رقم الرحلة — وحّده: شِل أي بادئة حروف من الرقم ثم أضف كود الخط دائماً (يوقف التكرارات)
            seg_num = str(seg.get('number') or '').strip()
            num_only = re.sub(r'^[A-Za-z]+', '', seg_num)   # "UD162"→"162" و "131"→"131"
            flight_num = f"{airline_code}{num_only}".strip() or seg_num

            # الأوقات — توحيد التنسيق إلى HH:MM
            dep_time = (journey.get('departure') or {}).get('time', '')
            arr_time = (journey.get('arrival') or {}).get('time', '')
            dep_time_short = _normalize_time(dep_time)
            arr_time_short = _normalize_time(arr_time)

            # المطارات — كود إنجليزي للفلترة + عربي للعرض
            from_code = ((journey.get('departure') or {}).get('airport') or {}).get('code', '')
            to_code   = ((journey.get('arrival')   or {}).get('airport') or {}).get('code', '')
            from_name = AIRPORTS_AR.get(from_code, from_code)
            to_name   = AIRPORTS_AR.get(to_code,   to_code)

            duration = (journey.get('duration') or {}).get('text', '')

            base_price = float(item.get('usd') or item.get('netprice') or 0)
            if base_price <= 0:
                continue
            # التسعير حسب الخط:
            if airline == 'الخطوط الجوية العراقية' and (from_code, to_code) in IRAQI_FIXED_PRICE:
                price_usd = float(IRAQI_FIXED_PRICE[(from_code, to_code)])   # سعر ثابت للذهاب تركيا→العراق
            elif airline == 'طيران اور':
                price_usd = round(base_price, 2)                            # بدون عمولة
            elif airline == 'طيران البصرة':
                price_usd = round(base_price * 1.03, 2)                     # عمولة 3%
            else:
                price_usd = round(base_price * (1 + COMMISSION), 2)         # الافتراضي 8%

            # الأمتعة
            bag_info  = seg.get('baggage') or {}
            bag_kg    = str(bag_info.get('allowance', '')).strip()
            bag_unit  = str(bag_info.get('unit', '')).strip()
            if bag_kg and bag_kg not in ('0', '0 ', ''):
                baggage = f"{bag_kg} {bag_unit}".strip()
            else:
                baggage = 'Hand Bag'

            seats = seg.get('seats_remaining', '')
            cls   = seg.get('class', 'Economy')

            flights.append({
                'route':          route_name,
                'search_date':    datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y'),
                'airline':        airline,
                'flight_number':  flight_num,
                'from_code':      from_code,
                'from_name':      from_name,
                'departure_time': dep_time_short,
                'to_code':        to_code,
                'to_name':        to_name,
                'arrival_time':   arr_time_short,
                'duration':       duration,
                'price':          str(price_usd),
                'currency':       'USD',
                'seats_available': str(seats) if seats else '',
                'class':          cls,
                'baggage':        baggage,
            })
        except Exception:
            continue   # رحلة واحدة تفشل لا توقف الباقي
    return flights


def dedup_flights(flights):
    """احذف التكرارات المطابقة تماماً (نفس كل شيء بما فيه السعر والأمتعة)"""
    seen = set()
    result = []
    for f in flights:
        key = (f['airline'], f['flight_number'], f['departure_time'],
               f['search_date'], f['price'], f['baggage'])
        if key not in seen:
            seen.add(key)
            result.append(f)
    return result


def send_telegram(msg):
    try:
        requests.post(f'https://api.telegram.org/bot{TG_TOKEN}/sendMessage',
            data={'chat_id': TG_CHAT, 'text': msg, 'parse_mode': 'HTML'}, timeout=10)
    except Exception:
        pass


def push_github(data):
    hdrs = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
    url  = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}'
    sha  = None
    r    = requests.get(url, headers=hdrs)
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


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def main():
    # منع تشغيل نسختين في نفس الوقت — مع تجاهل الأقفال العالقة (عملية ميتة)
    lock_file = f'{WORK_DIR}/.update.lock'
    if os.path.exists(lock_file):
        try:
            old_pid = int(open(lock_file).read().strip() or 0)
        except Exception:
            old_pid = 0
        if old_pid and _pid_alive(old_pid):
            print('⚠️ تحديث آخر يعمل حالياً — تخطّي')
            sys.exit(0)
        # القفل عالق (العملية ميتة مثلاً بعد إعادة تشغيل) → أزِله وتابع
        print(f'🔓 قفل عالق (PID {old_pid} ميت) — إزالة ومتابعة')
        os.remove(lock_file)
    open(lock_file, 'w').write(str(os.getpid()))

    try:
        _run()
    finally:
        if os.path.exists(lock_file):
            os.remove(lock_file)


def _run():
    print('=' * 70)
    print(f'  Somados Updater (b2bcheetah) — {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70)

    get_token()   # سجّل الدخول مرة واحدة (مشترك بين الـ workers)
    start = datetime.now() + timedelta(days=1)
    dates = [(start + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(15)]
    print(f'\n📅 {dates[0]} → {dates[-1]} | 🛫 {len(ROUTES)} مسار\n')

    all_data = {}
    total    = 0
    t_start  = time.time()

    def search_route(args):
        ri, route = args
        name = route['name']
        # مطارات المصدر: الأساسي + أي مطارات إضافية (مثل صبيحة SAW لبغداد)
        pairs = [(route['from'], route['to'])] + route.get('also', [])
        raw_flights = []
        for di, date in enumerate(dates, 1):
            for frm, to in pairs:
                results, err = b2b_search(frm, to, date)
                got = extract_flights(results, name, date) if not err else []
                # شبكة أمان: يوم يرجع صفر (فراغ مؤقت) أو خطأ تجاوز حد (429) → أعد المحاولة
                if (not got and not err) or (err and '429' in str(err)):
                    time.sleep(30 if err else 1.5)   # تجاوز الحد يحتاج انتظار أطول
                    results, err = b2b_search(frm, to, date)
                    got = extract_flights(results, name, date) if not err else []
                if err:
                    print(f'  ⚠️ {name} ({frm}→{to}) {date}: {err}')
                raw_flights.extend(got)
        flights = dedup_flights(raw_flights)
        now_t = datetime.now().strftime('%H:%M')
        send_telegram(f'✅ {name} — {len(flights)} رحلة [{ri}/{len(ROUTES)}] {now_t}')
        print(f'[{ri}/{len(ROUTES)}] {name} → {len(flights)} رحلة')
        return name, flights

    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {ex.submit(search_route, (ri, route)): route for ri, route in enumerate(ROUTES, 1)}
        for future in as_completed(futures):
            name, flights = future.result()
            all_data[name] = flights
            total += len(flights)

    elapsed   = round(time.time() - t_start)
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
        send_telegram(f'❌ <b>somados.com — فشل الرفع</b>\n🕐 {now_str}')


if __name__ == '__main__':
    main()
