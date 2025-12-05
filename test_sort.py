import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

LIVEAGENT_API_URL = "https://plotbase.ladesk.com/api/v3"
VAS_API_KLUC = os.getenv("LIVEAGENT_API_KEY", "")

def test_sort(field):
    headers = {"apikey": VAS_API_KLUC}
    params = {
        "_page": 1,
        "_perPage": 5,
        "_sortField": field,
        "_sortDir": "DESC"
    }
    print(f"Testing sort by: {field}")
    try:
        response = requests.get(f"{LIVEAGENT_API_URL}/tickets", headers=headers, params=params)
        if response.status_code == 200:
            tickets = response.json()
            print("Success!")
            for t in tickets:
                print(f"ID: {t.get('id')} | {field}: {t.get(field)}")
        else:
            print(f"Failed with status: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Error: {e}")
    print("-" * 20)

test_sort("date_changed")
test_sort("date_resolved")
