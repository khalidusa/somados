import requests, subprocess, os, time

TOKEN    = "8856103719:AAGiK2kxxR-7j0nYyBpSJrtmbsFV6_RjwJs"
CHAT_ID  = "725243049"
WORK_DIR = os.path.expanduser("~/Documents/somados")

def send(msg):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                  data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})

def run_update():
    result = subprocess.run(
        ["python3", f"{WORK_DIR}/update_flights.py"],
        cwd=WORK_DIR, capture_output=True, text=True
    )
    return result.stdout + result.stderr

def main():
    send(
        "🤖 <b>البوت شغّال!</b>\n\n"
        "📡 المصدر: b2bcheetah (وكيل) — لا تحتاج كوكيز\n"
        "🔄 التحديث تلقائي كل 3 ساعات\n\n"
        "الأوامر:\n"
        "/update — تحديث فوري\n"
        "/status — حالة البوت"
    )
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
                msg  = update.get("message", {})
                text = msg.get("text", "").strip()
                chat = str(msg.get("chat", {}).get("id", ""))
                if chat != CHAT_ID:
                    continue

                if text == "/update":
                    send("🔄 يبدأ التحديث...")
                    output = run_update()
                    if "رُفع" in output:
                        send("✅ تم التحديث ورُفع للموقع!")
                    else:
                        send(f"⚠️ مشكلة:\n{output[-400:]}")

                elif text == "/status":
                    send("✅ البوت شغّال\n📡 المصدر: b2bcheetah\n🔄 تحديث كل 3 ساعات")

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
