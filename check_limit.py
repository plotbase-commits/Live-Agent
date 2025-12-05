import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

LIVEAGENT_API_URL = "https://plotbase.ladesk.com/api/v3"
VAS_API_KLUC = os.getenv("LIVEAGENT_API_KEY", "")

def check_page_5_date():
    headers = {"apikey": VAS_API_KLUC}
    params = {
        "_page": 5,
        "_perPage": 20,
        "_sortField": "date_created",
        "_sortDir": "DESC"
    }
    try:
        response = requests.get(f"{LIVEAGENT_API_URL}/tickets", headers=headers, params=params)
        response.raise_for_status()
        tickets = response.json()
        
        if tickets:
            last_ticket = tickets[-1]
            print(f"Last ticket on page 5 (Ticket #100):")
            print(f"ID: {last_ticket.get('id')}")
            print(f"Date Created: {last_ticket.get('date_created')}")
        else:
            print("Page 5 is empty.")
            
    except Exception as e:
        print(f"Error: {e}")

check_page_5_date()
