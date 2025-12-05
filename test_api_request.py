import requests
import json
import numpy as np


def test_api_full_flow():
    # כתובת ה-API המקומי
    url_modal = "http://127.0.0.1:8000/shear-building/modal"

    print(f"🚀 Connecting to API at: {url_modal}")

    # נתונים (Payload) - בדיוק מה שהפרונט ישלח
    # יחידות: GPa, kN, Meter, Ton
    payload = {
        "Hc": [[3.0, 3.0], [3.0, 3.0]],
        "Ec": [[30.0, 30.0], [30.0, 30.0]],  # 30 GPa
        "Ic": [[0.005, 0.005], [0.005, 0.005]],  # Ic ריאליסטי
        "Lb": [[6.0, 6.0], [6.0, 6.0]],
        "depth": 6.0,
        "floor_load": 20.0,  # 20 kN/m^2
        "base_condition": 1
    }

    try:
        # שליחת בקשת POST
        response = requests.post(url_modal, json=payload)

        # בדיקת סטטוס
        if response.status_code == 200:
            print("✅ Server responded [200 OK]")
            data = response.json()

            # הצגת התוצאות
            freqs = data["frequencies"]
            print("\n📊 Received Frequencies (rad/s):")
            print(freqs)

            # בדיקה אוטומטית שהמספרים הגיוניים (סביב 15.8 כמו בטסט הקודם)
            first_freq = freqs[0]
            if 10.0 < first_freq < 20.0:
                print(f"✅ Sanity Check Passed: {first_freq:.2f} rad/s is realistic!")
            else:
                print(f"⚠️ Warning: Frequency {first_freq} seems unexpected.")

            print("\n📝 Full JSON Response (Partial):")
            # מדפיס רק את ההתחלה כדי לא להציף את המסך
            print(json.dumps(data, indent=2)[:500] + "\n... (more data) ...")

        else:
            print(f"❌ Server Error {response.status_code}:")
            print(response.text)

    except requests.exceptions.ConnectionError:
        print("❌ Connection Refused!")
        print("   👉 Did you forget to run 'uvicorn api.main:app --reload' in another terminal?")


if __name__ == "__main__":
    test_api_full_flow()