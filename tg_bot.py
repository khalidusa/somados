import requests, subprocess, os, time

TOKEN = "8856103719:AAGiK2kxxR-7j0nYyBpSJrtmbsFV6_RjwJs"
CHAT_ID = "725243049"
WORK_DIR = os.path.expanduser("~/Documents/somados")

def send(msg):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

def update_cookies(session, unique):
    cookie = (f"FlightTimeOut=ProductTypeId=0&Unique={unique}"
              f"&EndTime=2026-12-31T23:59:59&PaymentEndTime=; "
              f"ASP.NET_SessionId={session}; SERVERID=s21; "
              f"pvisitor=d1042b9e-d85c-4166-852c-a87748c01465")
    with open(f"{WORK_DIR}/cookies.txt", "w") as f:
        f.write(cookie)

def run_update():
    result = subprocess.run(
        ["python3", f"{WORK_DIR}/update_flights.py"],
        cwd=WORK_DIR, capture_output=True, text=True
    )
    return result.stdout + result.stderr

def main():
    send("🤖 البوت شغّال!\n\n✅ الجلسة تتجدد تلقائياً\n\nأوامر:\n/update — تحديث الرحلات\n/status — حالة البوت\n\nأو أرسل SESSION وUNIQUE يدوياً إن احتجت")
    print("✅ البوت شغّال...")
    offset = 0
    while True:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                params={"offset": offset, "timeout": 30},
                timeout=35
            )
            updates = r.json().get("result", [])
            for update in updates:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                text = msg.get("text", "").strip()
                chat = str(msg.get("chat", {}).get("id", ""))
                if chat != CHAT_ID:
                    continue
                session = unique = None
                for line in text.split("\n"):
                    if "SESSION=" in line:
                        session = line.split("SESSION=")[1].strip()
                    if "UNIQUE=" in line:
                        unique = line.split("UNIQUE=")[1].strip()
                if session and unique:
                    send("🔄 استلمت الكوكيز - جاري التحديث...")
                    update_cookies(session, unique)
                    send("✅ الكوكيز محدّثة - يبدأ البحث...")
                    output = run_update()
                    if "رُفع" in output or "Total" in output:
                        send("🎉 تم التحديث ورُفع للموقع!")
                    else:
                        send(f"⚠️ مشكلة:\n{output[-400:]}")
                elif text == "/status":
                    ok = os.path.exists(f"{WORK_DIR}/cookies.txt")
                    send("✅ البوت شغّال" if ok else "⚠️ cookies.txt غير موجود")
                elif text == "/update":
                    send("🔄 يشغّل التحديث...")
                    output = run_update()
                    send("✅ تم!" if "رُفع" in output else f"⚠️ {output[-300:]}")
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
