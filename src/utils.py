import datetime
from zoneinfo import ZoneInfo
import re
from bs4 import BeautifulSoup
import requests
import streamlit as st

from src.config import LIVEAGENT_API_URL

# Timezone configuration
LOCAL_TIMEZONE = ZoneInfo('Europe/Bratislava')
UTC_TIMEZONE = ZoneInfo('UTC')

def convert_utc_to_local(utc_datetime_str):
    """Converts UTC datetime string to local timezone."""
    if not utc_datetime_str:
        return None
    
    try:
        # Parse the datetime string (format: 2025-12-04 09:48:23)
        dt = datetime.datetime.strptime(utc_datetime_str, '%Y-%m-%d %H:%M:%S')
        # Assume it's UTC and convert to local timezone
        dt_utc = dt.replace(tzinfo=UTC_TIMEZONE)
        dt_local = dt_utc.astimezone(LOCAL_TIMEZONE)
        # Return as string without timezone info
        return dt_local.strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError) as e:
        # If parsing fails, return original
        return utc_datetime_str

def get_agents(api_key):
    """Fetches list of agents from LiveAgent API."""
    headers = {"apikey": api_key}
    try:
        # Note: API defaults to 10 records, we need all agents
        response = requests.get(
            f"{LIVEAGENT_API_URL}/agents", 
            headers=headers,
            params={"_perPage": 100}
        )
        response.raise_for_status()
        agents_data = response.json()
        # Create a mapping of agent ID to full name
        agents_map = {}
        if isinstance(agents_data, list):
            for agent in agents_data:
                agent_id = agent.get('id') or agent.get('userid')
                if agent_id:
                    # Try to get full name, fallback to firstname + lastname, then email
                    full_name = agent.get('name') or agent.get('full_name')
                    if not full_name:
                        firstname = agent.get('firstname', '')
                        lastname = agent.get('lastname', '')
                        full_name = f"{firstname} {lastname}".strip()
                    if not full_name:
                        full_name = agent.get('email', f"Agent {agent_id}")
                    agents_map[str(agent_id)] = full_name
        return agents_map
    except requests.exceptions.RequestException as e:
        st.warning(f"Error fetching agents: {e}")
        return {}

def get_users(api_key):
    """Fetches list of users/contacts from LiveAgent API."""
    headers = {"apikey": api_key}
    try:
        # Note: API defaults to 10 records, we need more contacts
        response = requests.get(
            f"{LIVEAGENT_API_URL}/contacts", 
            headers=headers,
            params={"_perPage": 500}
        )
        response.raise_for_status()
        users_data = response.json()
        # Create a mapping of user ID to full name
        users_map = {}
        if isinstance(users_data, list):
            for user in users_data:
                user_id = user.get('id') or user.get('contactid')
                if user_id:
                    # Try to get full name, fallback to firstname + lastname, then email
                    full_name = user.get('name') or user.get('full_name')
                    if not full_name:
                        firstname = user.get('firstname', '')
                        lastname = user.get('lastname', '')
                        full_name = f"{firstname} {lastname}".strip()
                    if not full_name:
                        full_name = user.get('email', f"User {user_id}")
                    users_map[str(user_id)] = full_name
        return users_map
    except requests.exceptions.RequestException as e:
        st.warning(f"Error fetching users: {e}")
        return {}

def get_author_name(userid, agents_map, users_map):
    """Get author name from userid using agents and users maps."""
    if not userid:
        return "Unknown"
    
    userid_str = str(userid)
    
    # Check if it's an agent first
    if userid_str in agents_map:
        return agents_map[userid_str]
    
    # Then check if it's a user/contact
    if userid_str in users_map:
        return users_map[userid_str]
    
    # If not found in either, return the ID
    return f"User {userid_str}"

def extract_author_from_message(message_html):
    """Extract author name from From: header in message HTML."""
    if not message_html:
        return None
    
    try:
        soup = BeautifulSoup(message_html, 'html.parser')
        text = soup.get_text()
        
        # Look for 'From:' pattern
        from_match = re.search(r'From:\s*(.+?)(?:\n|$)', text)
        if from_match:
            from_value = from_match.group(1).strip()
            
            # Extract name from format like 'Name <email@example.com>'
            name_match = re.match(r'^([^<]+)', from_value)
            if name_match:
                name = name_match.group(1).strip()
                if name:
                    return name
            
            # If no name part, return the whole From value
            return from_value
    except Exception:
        pass
    
    return None

def process_transcript(message_groups, agents_map, users_map):
    """Processes message groups into a structured transcript."""
    transcript_parts = []
    
    # Process each group to extract From: header and associate it with message body
    processed_messages = []
    
    if isinstance(message_groups, list):
        for group in message_groups:
            if 'messages' in group and isinstance(group['messages'], list):
                group_messages = group['messages']
                
                # Extract From: header from Type H messages in this group
                group_from_author = None
                for msg in group_messages:
                    if msg.get('type') == 'H':  # Header type
                        from_author = extract_author_from_message(msg.get('message', ''))
                        if from_author:
                            group_from_author = from_author
                            break
                
                # Add group_from_author to each message in the group
                for msg in group_messages:
                    # Copy the message and add extracted author
                    msg_copy = msg.copy()
                    if group_from_author:
                        msg_copy['_extracted_from_author'] = group_from_author
                    
                    # Also copy user_full_name from group if missing
                    if 'user_full_name' not in msg_copy and 'user_full_name' in group:
                        msg_copy['user_full_name'] = group['user_full_name']
                    
                    processed_messages.append(msg_copy)
            else:
                # Fallback if it's a flat structure or different format
                processed_messages.append(group)
    
    # Sort by datecreated
    try:
        sorted_messages = sorted(processed_messages, key=lambda x: x.get('datecreated', ''))
    except Exception:
        sorted_messages = processed_messages

    for msg in sorted_messages:
        # Try to get readable name from the message first
        author = msg.get('user_full_name')
        
        # If not available, try to get it from userid using our maps
        if not author:
            userid = msg.get('userid')
            author = get_author_name(userid, agents_map, users_map)
        
        # If author is still just a user ID, try to use extracted From: from group headers
        if author and author.startswith('User '):
            extracted_author = msg.get('_extracted_from_author')
            if extracted_author:
                author = extracted_author
            else:
                # Fallback: try to extract from this specific message
                body_html = msg.get('message', '')
                extracted_author = extract_author_from_message(body_html)
                if extracted_author:
                    author = extracted_author
            
        date_created = msg.get('datecreated', 'Unknown Date')
        
        # Process body
        body_html = msg.get('message', '')
        
        # Skip completely empty messages (sometimes system messages are empty)
        if not body_html:
            continue

        # Format header
        header = f"\n--------------------------------------------------\n[AUTOR: {author} | ČAS: {date_created}]\n"
        
        soup = BeautifulSoup(body_html, "html.parser")
        text_body = soup.get_text(separator="\n").strip()
        
        # Remove excessive newlines
        text_body = "\n".join([line.strip() for line in text_body.splitlines() if line.strip()])
        
        transcript_parts.append(header + text_body)
    
    full_transcript = "\n".join(transcript_parts)
    
    # Limit to 49,000 characters (Google Sheets cell limit is 50k)
    if len(full_transcript) > 49000:
        full_transcript = full_transcript[:49000] + "\n\n[WARNING: Transcript truncated due to size limit]"
        
    return full_transcript

def is_human_interaction(message_groups, agents_map):
    """
    Determines if the ticket contains human communication (Agent or Customer).
    
    Uses MESSAGE GROUP TYPE as the primary filter:
    - Type 3: Incoming Email (new ticket from customer)
    - Type 4: Outgoing Email (agent reply)
    - Type 5: Offline message (contact form)
    - Type 7: Incoming Email reply (customer reply)
    
    System types are IGNORED:
    - Type I: Internal notifications (SLA, fields)
    - Type T: Transfer/assignment
    - Type G: Tag operations
    - Type R: Resolve operations
    
    Additionally filters out own-domain notifications (e.g. plotbase@plotbase.sk).
    """
    if not message_groups or not isinstance(message_groups, list):
        return False

    # Communication types (human interaction)
    COMMUNICATION_TYPES = {'3', '4', '5', '7'}
    
    # Domains to ignore (own shop automated notifications)
    IGNORED_DOMAINS = ['plotbase.sk', 'plotbase.cz', 'plotbase.at', 'plotbase.de', 'plotbase.hu']

    for group in message_groups:
        # PRIMARY FILTER: Check group type
        group_type = str(group.get('type', ''))
        
        # Skip non-communication types (I, T, G, R, etc.)
        if group_type not in COMMUNICATION_TYPES:
            continue
        
        # SECONDARY FILTER: Check for own-domain notifications
        # Extract From: header from the group's messages
        from_email = ''
        has_valid_content = False
        is_from_ignored_domain = False
        
        if 'messages' in group and isinstance(group['messages'], list):
            for msg in group['messages']:
                msg_type = msg.get('type', '')
                body = msg.get('message', '') or ''
                
                # Extract From: header (type H messages contain headers)
                if msg_type == 'H' and body.lower().startswith('from:'):
                    from_email = body.lower()
                    # Check if From: contains ignored domain
                    if any(domain in from_email for domain in IGNORED_DOMAINS):
                        is_from_ignored_domain = True
                
                # Check userid and author_name as fallback
                userid = str(msg.get('userid', ''))
                author_name = msg.get('user_full_name', '') or msg.get('name', '') or ''
                
                if any(domain in userid.lower() for domain in IGNORED_DOMAINS):
                    is_from_ignored_domain = True
                if any(domain in author_name.lower() for domain in IGNORED_DOMAINS):
                    is_from_ignored_domain = True
                
                # Check for actual content (type M = message body)
                if msg_type == 'M' and body:
                    try:
                        soup = BeautifulSoup(body, 'html.parser')
                        text = soup.get_text().strip()
                        if text:
                            has_valid_content = True
                    except:
                        if body.strip():
                            has_valid_content = True
            
            # If this group has content but is from ignored domain, skip it
            if is_from_ignored_domain:
                continue
            
            # If we have valid content from non-ignored domain, it's human communication
            if has_valid_content:
                return True

    return False
