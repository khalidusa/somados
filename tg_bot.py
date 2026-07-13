import requests, subprocess, os, time, sys, threading
from datetime import datetime

TOKEN    = "8856103719:AAGiK2kxxR-7j0nYyBpSJrtmbsFV6_RjwJs"
CHAT_ID  = "725243049"
WORK_DIR = os.path.expanduser("~/somados")
INTERVAL = 3 * 60 * 60   # 3 ساعات

_last_auto = {'ts': None}

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=15)
    except Exception:
        pass

def run_update():
    result = subprocess.run(
        [sys.executable, f"{WORK_DIR}/update_flights.py"],
        cwd=WORK_DIR, capture_output=True, text=True
    )
    return result.stdout + result.stderr

def _report(output):
    if "رُفع" in output:
        send("✅ تم التحديث ورُفع للموقع!")
    elif "تحديث آخر يعمل" in output:
        send("⚠️ يوجد تحديث آخر يعمل حالياً — سيُعاد لاحقاً")
    else:
        last = [l for l in output.split('\n') if l.strip()][-3:]
        send(f"⚠️ مشكلة:\n{chr(10).join(last)}")

def auto_update_loop():
    """تحديث تلقائي كل 3 ساعات — يعمل داخل البوت (عنده صلاحية Documents)."""
    while True:
        time.sleep(INTERVAL)
        try:
            send("⏰ <b>تحديث تلقائي</b> (كل 3 ساعات) — يبدأ الآن…")
            output = run_update()
            _last_auto['ts'] = datetime.now().strftime('%Y-%m-%d %H:%M')
            _report(output)
        except Exception as e:
            send(f"⚠️ فشل التحديث التلقائي: {e}")

def main():
    send(
        "🤖 <b>البوت شغّال!</b>\n\n"
        "📡 المصدر: b2bcheetah (وكيل) — لا تحتاج كوكيز\n"
        "🔄 تحديث تلقائي كل 3 ساعات (من داخل البوت)\n\n"
        "الأوامر:\n"
        "/update — تحديث فوري\n"
        "/status — حالة البوت"
    )
    print("✅ البوت شغّال...")

    # شغّل المجدول التلقائي في خيط منفصل
    threading.Thread(target=auto_update_loop, daemon=True).start()

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
                    send("🔄 يبدأ التحديث…")
                    output = run_update()
                    _report(output)

                elif text == "/status":
                    nxt = "بعد ساعات قليلة"
                    last = _last_auto['ts'] or "لم يعمل بعد منذ التشغيل"
                    send(
                        "✅ البوت شغّال\n"
                        "📡 المصدر: b2bcheetah\n"
                        "🔄 تحديث تلقائي كل 3 ساعات\n"
                        f"🕐 آخر تحديث تلقائي: {last}"
                    )

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
