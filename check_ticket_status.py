import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

LIVEAGENT_API_URL = "https://plotbase.ladesk.com/api/v3"
VAS_API_KLUC = os.getenv("LIVEAGENT_API_KEY", "")
TICKET_ID = "kp4ijcmh"

def check_ticket(ticket_id):
    headers = {"apikey": VAS_API_KLUC}
    try:
        # Fetch specific ticket details
        # Note: The endpoint might be /tickets/{ticketId}
        response = requests.get(f"{LIVEAGENT_API_URL}/tickets/{ticket_id}", headers=headers)
        response.raise_for_status()
        data = response.json()
        
        print(f"Ticket ID: {data.get('id')}")
        print(f"Status Code: {data.get('status')}")
        print(f"Date Created: {data.get('date_created')}")
        print(f"Subject: {data.get('subject')}")
        
    except Exception as e:
        print(f"Error fetching ticket: {e}")
        # Try searching for it if direct access fails (though ID access should work)

check_ticket(TICKET_ID)
