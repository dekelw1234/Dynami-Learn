import sys
import os
import json
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def api_full_flow():
    url_modal = "http://127.0.0.1:8000/shear-building/modal"

    print(f"🚀 Connecting to API at: {url_modal}")

    payload = {
        "Hc": [[3.0, 3.0], [3.0, 3.0]],
        "Ec": [[30.0, 30.0], [30.0, 30.0]],  # 30 GPa
        "Ic": [[0.005, 0.005], [0.005, 0.005]],
        "Lb": [[6.0, 6.0], [6.0, 6.0]],
        "depth": 6.0,
        "floor_mass": 20.0,  # tons per floor
        "base_condition": 1,
    }

    try:
        response = requests.post(url_modal, json=payload)

        if response.status_code == 200:
            print("✅ Server responded [200 OK]")
            data = response.json()

            freqs = data["frequencies"]
            print("\n📊 Received Frequencies (rad/s):")
            print(freqs)

            first_freq = freqs[0]
            if 10.0 < first_freq < 20.0:
                print(f"✅ Sanity Check Passed: {first_freq:.2f} rad/s is realistic!")
            else:
                print(f"⚠️  Warning: Frequency {first_freq} seems unexpected.")

            print("\n📝 Full JSON Response (Partial):")
            print(json.dumps(data, indent=2)[:500] + "\n... (more data) ...")

        else:
            print(f"❌ Server Error {response.status_code}:")
            print(response.text)

    except requests.exceptions.ConnectionError:
        print("❌ Connection Refused!")
        print("   👉 Run 'uvicorn api.main:app --reload' first, then retry.")


if __name__ == "__main__":
    api_full_flow()
