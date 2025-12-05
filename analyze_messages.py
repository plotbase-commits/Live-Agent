import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://plotbase.ladesk.com/api/v3"
API_KEY = os.getenv("LIVEAGENT_API_KEY", "")

headers = {"apikey": API_KEY}

# Get a few tickets
response = requests.get(f"{API_URL}/tickets", headers=headers, params={"_perPage": 5})
tickets = response.json()

print("=" * 80)
print("ANALÝZA ŠTRUKTÚRY SPRÁV")
print("=" * 80)

for ticket in tickets[:3]:
    ticket_id = ticket.get('id')
    subject = ticket.get('subject', 'N/A')[:50]
    status = ticket.get('status')
    
    print(f"\n{'='*80}")
    print(f"TICKET: {ticket_id} | Status: {status}")
    print(f"Subject: {subject}")
    print("-" * 80)
    
    # Get messages
    msg_response = requests.get(f"{API_URL}/tickets/{ticket_id}/messages", headers=headers)
    messages = msg_response.json()
    
    for i, group in enumerate(messages):
        print(f"\n  GROUP {i+1}:")
        print(f"    Keys: {list(group.keys())}")
        
        # Check group-level info
        group_type = group.get('type', 'N/A')
        group_userid = group.get('userid', 'N/A')
        group_fullname = group.get('user_full_name', 'N/A')
        
        print(f"    Type: {group_type}")
        print(f"    UserID: {group_userid}")
        print(f"    FullName: {group_fullname}")
        
        if 'messages' in group:
            for j, msg in enumerate(group['messages'][:2]):  # First 2 messages only
                msg_type = msg.get('type', 'N/A')
                msg_userid = msg.get('userid', 'N/A')
                msg_fullname = msg.get('user_full_name', 'N/A')
                msg_text = msg.get('message', '')[:100] if msg.get('message') else 'EMPTY'
                
                print(f"\n      MSG {j+1}:")
                print(f"        Type: {msg_type}")
                print(f"        UserID: {msg_userid}")
                print(f"        FullName: {msg_fullname}")
                print(f"        Message preview: {msg_text[:80]}...")
        
    print("\n")

