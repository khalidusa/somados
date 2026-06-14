"""
السكربت الرئيسي المحدّث
- يقرأ الكوكيز من Safari تلقائياً (بدون تدخل)
- يبحث عن الرحلات
- يرفع النتائج لـ GitHub كـ JSON
- شغّله كل 4 ساعات عبر launchd
"""

import requests
import yaml
import time
import sys
import json
import base64
import sqlite3
import shutil
import tempfile
import os
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re

# ============================================================
# الإعدادات - عدّلها مرة واحدة
# ============================================================

# GitHub
GITHUB_TOKEN = "PASTE_GITHUB_TOKEN_HERE"   # ← Personal Access Token
GITHUB_REPO = "PASTE_USERNAME/somados"      # ← مثال: khaledsameer/somados
GITHUB_BRANCH = "main"
GITHUB_FILE = "data/flights.json"

# واتساب
WA_NUMBER = "905345231711"

# إعدادات الأسعار
IQD_TO_USD = 1400
COMMISSION = 0.07

USER_AGENT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) "
              "Version/26.4 Safari/605.1.15")

# ============================================================
# قراءة الكوكيز من Safari تلقائياً
# ============================================================

def get_safari_cookies():
    """يقرأ الكوكيز من Safari مباشرة بدون تدخل"""
    safari_cookies_db = os.path.expanduser(
        "~/Library/Containers/com.apple.Safari/Data/Library/Cookies/Cookies.binarycookies"
    )
    
    if not os.path.exists(safari_cookies_db):
        # جرّب المكان البديل
        safari_cookies_db = os.path.expanduser("~/Library/Cookies/Cookies.binarycookies")
    
    if not os.path.exists(safari_cookies_db):
        print("⚠️ ما قدرنا نلاقي كوكيز Safari")
        print("   تأكد إنك مسجّل دخول على b2b.alsafarigate.com بـ Safari")
        return None
    
    # نسخ مؤقت (Safari قد يكون مفتوح)
    tmp = tempfile.mktemp(suffix='.binarycookies')
    shutil.copy2(safari_cookies_db, tmp)
    
    try:
        cookies = parse_binary_cookies(tmp)
        # فلتر كوكيز alsafarigate
        relevant = {k: v for k, v in cookies.items() 
                   if 'alsafarigate' in k[0].lower()}
        
        if not relevant:
            print("⚠️ ما لقينا كوكيز alsafarigate في Safari")
            print("   سجّل دخول أولاً على: https://b2b.alsafarigate.com")
            return None
        
        # بناء cookie string
        cookie_dict = {}
        for (domain, path, name), value in relevant.items():
            cookie_dict[name] = value
        
        if 'ASP.NET_SessionId' not in cookie_dict:
            print("⚠️ ASP.NET_SessionId مو موجود - الجلسة منتهية")
            print("   سجّل دخول مجدداً على b2b.alsafarigate.com")
            return None
        
        print(f"✅ قرأنا {len(cookie_dict)} كوكي من Safari")
        return cookie_dict
        
    except Exception as e:
        print(f"⚠️ خطأ في قراءة الكوكيز: {e}")
        return None
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def parse_binary_cookies(filepath):
    """تحليل ملف binary cookies الخاص بـ Safari"""
    cookies = {}
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
        
        # Magic header check
        if data[:4] != b'cook':
            return cookies
        
        import struct
        num_pages = struct.unpack('>I', data[4:8])[0]
        page_sizes = []
        offset = 8
        
        for i in range(num_pages):
            size = struct.unpack('>I', data[offset:offset+4])[0]
            page_sizes.append(size)
            offset += 4
        
        page_data_start = offset
        
        for page_size in page_sizes:
            page = data[page_data_start:page_data_start + page_size]
            page_data_start += page_size
            
            if len(page) < 8:
                continue
            
            num_cookies = struct.unpack('<I', page[4:8])[0]
            cookie_offsets = []
            for i in range(num_cookies):
                off = struct.unpack('<I', page[8 + i*4:12 + i*4])[0]
                cookie_offsets.append(off)
            
            for cookie_offset in cookie_offsets:
                try:
                    cookie = page[cookie_offset:]
                    if len(cookie) < 56:
                        continue
                    
                    # Extract offsets
                    url_off = struct.unpack('<I', cookie[16:20])[0]
                    name_off = struct.unpack('<I', cookie[20:24])[0]
                    path_off = struct.unpack('<I', cookie[24:28])[0]
                    value_off = struct.unpack('<I', cookie[28:32])[0]
                    
                    def read_str(data, off):
                        end = data.find(b'\x00', off)
                        if end == -1:
                            return data[off:off+100].decode('utf-8', errors='ignore')
                        return data[off:end].decode('utf-8', errors='ignore')
                    
                    domain = read_str(cookie, url_off)
                    name = read_str(cookie, name_off)
                    path = read_str(cookie, path_off)
                    value = read_str(cookie, value_off)
                    
                    cookies[(domain, path, name)] = value
                except Exception:
                    continue
    except Exception as e:
        print(f"Cookie parse error: {e}")
    
    return cookies


# ============================================================
# Session + Search
# ============================================================

def make_session(cookie_dict):
    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT})
    for k, v in cookie_dict.items():
        session.cookies.set(k, v, domain='.alsafarigate.com')
        session.cookies.set(k, v, domain='www.alsafarigate.com')
    return session


def search_flights(session, dep, arr, date, adults=1):
    data = {
        'HasMultiPoint': 'True',
        'DisplayOnlyDirectFlights': 'True',
        'DisplayOnlyRefundableFlights': 'False',
        'DisplayAdvancedSearch': 'False',
        'HideCabinType': 'False',
        'HideProductInfo': 'False',
        'HideRuleFlag': 'False',
        'DepartureName': dep + ' Airport',
        'DepartureCode': dep,
        'ArrivalName': arr + ' Airport',
        'ArrivalCode': arr,
        'DepartureDate': date,
        'MultiLegCount': '2',
        'MultiPointCount': '4',
        'SearchType': '0',
        'CabinClassType': 'All',
        'AdultCount': str(adults),
        'ChildCount': '0',
        'InfantCount': '0',
        'IsDirectFlightsChecked': 'false',
    }
    for i in range(4):
        for field in ['DepartureName', 'DepartureCode', 'ArrivalName', 'ArrivalCode', 'DepartureDate']:
            data[f'FlightSearchFilterLegs[{i}].{field}'] = ''

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'Accept': '*/*',
        'Referer': 'https://www.alsafarigate.com/',
        'Origin': 'https://www.alsafarigate.com',
        'X-Requested-With': 'XMLHttpRequest',
    }

    try:
        r1 = session.post('https://www.alsafarigate.com/Air/SearchAir',
                          data=data, headers=headers, timeout=30)
        if r1.status_code != 200:
            return None, f"HTTP {r1.status_code}"

        r2 = session.get('https://www.alsafarigate.com/Air/FlightResult',
                         headers={'Referer': 'https://www.alsafarigate.com/'},
                         timeout=30)
        if r2.status_code != 200:
            return None, f"HTTP {r2.status_code}"

        if 'Log-in' in r2.text[:5000] or 'Login.aspx' in r2.url:
            return None, "Session expired"

        return r2.text, None
    except Exception as e:
        return None, str(e)


def get_price_usd(row, airline):
    all_prices = {}
    for el in row.find_all(attrs={'data-amount': True}):
        code = el.get('data-code', '').strip().upper()
        try:
            val = float(el.get('data-amount', '0'))
            if val > 0:
                all_prices[code] = val
        except Exception:
            pass

    is_iraqi = 'iraqi' in airline.lower()
    raw = 0.0

    if 'USD' in all_prices:
        raw = all_prices['USD']
    elif 'IQD' in all_prices:
        raw = round(all_prices['IQD'] / IQD_TO_USD, 2)
    elif all_prices:
        raw = list(all_prices.values())[0]

    if raw <= 0:
        return ''

    if not is_iraqi:
        raw = round(raw * (1 + COMMISSION), 2)
    else:
        raw = round(raw, 2)

    return str(raw)


def is_direct(row):
    # 1. Flight number with comma = connecting (e.g. "G9284,G9...")
    logo = row.find(class_='booking-item-airline-logo')
    if logo:
        num_el = logo.find(class_='mt0')
        if num_el:
            flight_num = num_el.get_text(strip=True)
            if ',' in flight_num:
                return False

    # 2. Site marks it as direct explicitly
    if row.find(class_='flight-info__segments--direct'):
        return True

    # 3. More than 2 airport codes = transit
    bolds = [el.get_text(strip=True) for el in row.find_all(class_='bold')]
    codes = [t for t in bolds if len(t) == 3 and t.isupper() and t.isalpha()]
    if len(codes) > 2:
        return False

    # 4. Suspiciously long duration for known routes (>5h for Turkey-Iraq)
    all_text = row.get_text(separator=' ', strip=True)
    import re as _re
    dm = _re.search(r'(\d+)\s+\d+\s*M', all_text)
    if dm:
        hours = int(dm.group(1))
        if hours >= 5:
            return False

    # 5. Stop/transit keywords
    text = row.get_text().lower()
    for kw in ['stop', 'transit', 'layover', 'via', 'aktarma']:
        if kw in text:
            return False

    return True


def extract(html, route_name, search_date):
    soup = BeautifulSoup(html, 'html.parser')
    buttons = soup.find_all(class_='btnFlightSelect')
    flights = []

    for btn in buttons:
        parent = btn
        row = None
        for _ in range(15):
            parent = parent.parent
            if parent is None:
                break
            if parent.find(class_='booking-item-container'):
                row = parent
                break
        if not row:
            continue

        if not is_direct(row):
            continue

        logo = row.find(class_='booking-item-airline-logo')
        airline = ''
        flight_num = ''
        if logo:
            img = logo.find('img')
            if img:
                airline = img.get('alt', '') or img.get('title', '')
            num_el = logo.find(class_='mt0')
            if num_el:
                flight_num = num_el.get_text(strip=True)

        bolds = [el.get_text(strip=True) for el in row.find_all(class_='bold')]
        dep_code = dep_time = arr_time = arr_code = ''
        for txt in bolds:
            if len(txt) == 3 and txt.isupper() and txt.isalpha():
                if not dep_code:
                    dep_code = txt
                else:
                    arr_code = txt
            elif len(txt) == 5 and txt[2] == ':' and txt[:2].isdigit() and txt[3:].isdigit():
                if not dep_time:
                    dep_time = txt
                else:
                    arr_time = txt

        all_text = row.get_text(separator=' ', strip=True)
        duration = ''
        dm = re.search(r'(\d+)\s+(\d+)\s*M', all_text)
        if dm:
            duration = dm.group(1) + 'h ' + dm.group(2) + 'm'

        price = get_price_usd(row, airline)

        quota = row.find(class_='spn-quota')
        seats = quota.get_text(strip=True) if quota else ''

        cls_el = row.find(class_='mb0')
        flight_class = cls_el.get_text(strip=True) if cls_el else ''

        fare_el = row.find(class_='btn-theme')
        fare_type = fare_el.get_text(strip=True) if fare_el else ''

        flights.append({
            'route': route_name,
            'search_date': search_date,
            'airline': airline,
            'flight_number': flight_num,
            'from_code': dep_code,
            'departure_time': dep_time,
            'to_code': arr_code,
            'arrival_time': arr_time,
            'duration': duration,
            'price': price,
            'currency': 'USD',
            'seats_available': seats,
            'class': flight_class,
            'fare_type': fare_type,
        })

    return flights


# ============================================================
# Upload to GitHub
# ============================================================

def push_to_github(json_data):
    """يرفع ملف JSON لـ GitHub"""
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json',
        'Content-Type': 'application/json',
    }
    
    api_url = f'https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}'
    
    # احصل على SHA الحالي
    sha = None
    r = requests.get(api_url, headers=headers)
    if r.status_code == 200:
        sha = r.json().get('sha')
    
    # ارفع الملف
    content = base64.b64encode(json.dumps(json_data, ensure_ascii=False, indent=2).encode()).decode()
    
    payload = {
        'message': f'Update flights - {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        'content': content,
        'branch': GITHUB_BRANCH,
    }
    if sha:
        payload['sha'] = sha
    
    r = requests.put(api_url, headers=headers, json=payload)
    if r.status_code in [200, 201]:
        print(f"✅ تم الرفع لـ GitHub!")
        return True
    else:
        print(f"❌ فشل الرفع: {r.status_code} - {r.text[:200]}")
        return False


# ============================================================
# Main
# ============================================================

# Routes to search
ROUTES = [
    # Turkey → Iraq
    {'from': 'ISTALL', 'to': 'BGW', 'name': 'Istanbul - Baghdad'},
    {'from': 'ISTALL', 'to': 'EBL', 'name': 'Istanbul - Erbil'},
    {'from': 'ISTALL', 'to': 'BSR', 'name': 'Istanbul - Basra'},
    {'from': 'ISTALL', 'to': 'NJF', 'name': 'Istanbul - Najaf'},
    {'from': 'ISTALL', 'to': 'KIK', 'name': 'Istanbul - Kirkuk'},
    {'from': 'ISTALL', 'to': 'ISU', 'name': 'Istanbul - Sulaymaniyah'},
    {'from': 'AYT',    'to': 'BGW', 'name': 'Antalya - Baghdad'},
    {'from': 'AYT',    'to': 'EBL', 'name': 'Antalya - Erbil'},
    {'from': 'SZF',    'to': 'BGW', 'name': 'Samsun - Baghdad'},
    {'from': 'ESB',    'to': 'BGW', 'name': 'Ankara - Baghdad'},
    {'from': 'ESB',    'to': 'KIK', 'name': 'Ankara - Kirkuk'},
    # Iraq → Turkey
    {'from': 'BGW', 'to': 'ISTALL', 'name': 'Baghdad - Istanbul'},
    {'from': 'EBL', 'to': 'ISTALL', 'name': 'Erbil - Istanbul'},
    {'from': 'BSR', 'to': 'ISTALL', 'name': 'Basra - Istanbul'},
    {'from': 'NJF', 'to': 'ISTALL', 'name': 'Najaf - Istanbul'},
    {'from': 'KIK', 'to': 'ISTALL', 'name': 'Kirkuk - Istanbul'},
    {'from': 'ISU', 'to': 'ISTALL', 'name': 'Sulaymaniyah - Istanbul'},
    {'from': 'BGW', 'to': 'AYT',    'name': 'Baghdad - Antalya'},
    {'from': 'EBL', 'to': 'AYT',    'name': 'Erbil - Antalya'},
    {'from': 'BGW', 'to': 'SZF',    'name': 'Baghdad - Samsun'},
    {'from': 'BGW', 'to': 'ESB',    'name': 'Baghdad - Ankara'},
    {'from': 'KIK', 'to': 'ESB',    'name': 'Kirkuk - Ankara'},
]


def main():
    print('=' * 70)
    print(f'  Somados Flight Updater - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('=' * 70)

    if 'PASTE' in GITHUB_TOKEN:
        print('❌ ضع GitHub Token في GITHUB_TOKEN')
        sys.exit(1)

    if 'PASTE' in GITHUB_REPO:
        print('❌ ضع اسم الـ Repo في GITHUB_REPO (مثال: khaledsameer/somados)')
        sys.exit(1)

    # اقرأ الكوكيز من Safari
    print('\n🍪 يقرأ الكوكيز من Safari...')
    cookie_dict = get_safari_cookies()
    
    if not cookie_dict:
        print('\n❌ ما قدرنا نقرأ الكوكيز')
        print('   الحل: افتح Safari → سجّل دخول على b2b.alsafarigate.com → حاول مجدداً')
        sys.exit(1)

    session = make_session(cookie_dict)

    # بناء التواريخ (من الغد)
    start = datetime.now() + timedelta(days=1)
    dates = [(start + timedelta(days=i)).strftime('%d.%m.%Y') for i in range(10)]
    
    print(f'\n📅 الأيام: {dates[0]} → {dates[-1]}')
    print(f'🛫 المسارات: {len(ROUTES)}\n')

    all_routes_data = {}
    total = 0

    for ri, route in enumerate(ROUTES, 1):
        route_name = route['name']
        print(f'[{ri}/{len(ROUTES)}] {route_name}')
        
        route_flights = []
        for di, date in enumerate(dates, 1):
            print(f'  [{di}/10] {date}... ', end='', flush=True)
            
            html, err = search_flights(session, route['from'], route['to'], date)
            
            if err:
                print(f'ERR: {err}')
                if 'expired' in err.lower():
                    print('\n⚠️ الجلسة انتهت - سجّل دخول بـ Safari مجدداً')
                    sys.exit(1)
                continue
            
            flights = extract(html, route_name, date)
            route_flights.extend(flights)
            print(f'OK {len(flights)}')
            time.sleep(3)
        
        all_routes_data[route_name] = route_flights
        total += len(route_flights)

    # ارفع لـ GitHub
    output = {
        'updated_at': datetime.now().isoformat(),
        'total_flights': total,
        'routes': all_routes_data,
    }

    print(f'\n📤 يرفع {total} رحلة لـ GitHub...')
    push_to_github(output)
    print(f'✅ اكتمل في {datetime.now().strftime("%H:%M:%S")}')


if __name__ == '__main__':
    main()
