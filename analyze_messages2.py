import requests
import json
from collections import Counter
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://plotbase.ladesk.com/api/v3"
API_KEY = os.getenv("LIVEAGENT_API_KEY", "")

headers = {"apikey": API_KEY}

# Get tickets with Answered/Resolved status
response = requests.get(f"{API_URL}/tickets", headers=headers, params={"_perPage": 20})
tickets = response.json()

group_types = Counter()
msg_types = Counter()
system_patterns = []

print("=" * 80)
print("ANALÝZA TYPOV SPRÁV")
print("=" * 80)

for ticket in tickets:
    ticket_id = ticket.get('id')
    status = ticket.get('status')
    
    # Only analyze Answered/Resolved tickets
    if status not in ['A', 'R', 'W']:
        continue
    
    msg_response = requests.get(f"{API_URL}/tickets/{ticket_id}/messages", headers=headers)
    messages = msg_response.json()
    
    for group in messages:
        group_type = group.get('type', 'N/A')
        userid = group.get('userid', '')
        group_types[f"{group_type} (user: {userid[:8] if userid else 'N/A'})"] += 1
        
        if 'messages' in group:
            for msg in group['messages']:
                msg_type = msg.get('type', 'N/A')
                msg_text = msg.get('message', '')[:50] if msg.get('message') else ''
                msg_types[msg_type] += 1
                
                # Collect system message patterns
                if userid == 'system00' or msg_type == 'T':
                    if msg_text and msg_text not in [p[0] for p in system_patterns]:
                        system_patterns.append((msg_text, group_type, msg_type))

print("\n📊 GROUP TYPES (group.type):")
print("-" * 40)
for t, count in group_types.most_common():
    print(f"  {t}: {count}x")

print("\n📊 MESSAGE TYPES (msg.type):")
print("-" * 40)
for t, count in msg_types.most_common():
    print(f"  {t}: {count}x")

print("\n📝 SYSTEM/NOTIFICATION PATTERNS:")
print("-" * 40)
for text, gtype, mtype in system_patterns[:15]:
    print(f"  [{gtype}/{mtype}] {text}...")

print("\n" + "=" * 80)
print("LEGENDA:")
print("  Group Type 4 = Odoslaná správa (agent -> zákazník)")
print("  Group Type 7 = Prijatá správa (zákazník -> agent)")
print("  Group Type I = Interná notifikácia/aktivita")
print("  Group Type R = Resolved akcia")
print("  Group Type T = Transfer/Assignment")
print("  Msg Type H = HTML content (skutočná správa)")
print("  Msg Type T = Text notification (systémová správa)")
