import requests
from datetime import datetime
import pytz
import logging
import sys
import os
import json
import gzip
import shutil
import csv




# Setup logging
logging.basicConfig(level=logging.INFO, filename="zendesk_weekend_check.log", 
                    format="%(asctime)s - %(levelname)s - %(message)s")

# Zendesk API details
ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN")
ZENDESK_EMAIL = os.getenv("ZENDESK_EMAIL")
ZENDESK_API_TOKEN = os.getenv("ZENDESK_API_TOKEN")
ZENDESK_VIEW_ID = "40051527319577"
CHECKBOX_FIELD_ID = "custom_fields.39218804884633"

#ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN")
#ZENDESK_EMAIL = os.getenv("ZENDESK_EMAIL")
#ZENDESK_API_TOKEN = os.getenv("ZENDESK_API_TOKEN")


# Toggle between test and production mode
TEST_MODE = False  # Set to False in production

# Timezone
IST = pytz.timezone("Asia/Kolkata")

# Persistent storage for ticket IDs
TICKET_STORE = "processed_tickets.json"

# Save processed ticket IDs to a file
def save_processed_tickets(ticket_ids):
    with open(TICKET_STORE, "w") as file:
        json.dump(ticket_ids, file)

# Load processed ticket IDs from the file
def load_processed_tickets():
    if os.path.exists(TICKET_STORE):
        with open(TICKET_STORE, "r") as file:
            return json.load(file)
    return []

# Authenticate with Zendesk
def zendesk_request(method, endpoint, data=None):
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2{endpoint}"
    auth = (ZENDESK_EMAIL, ZENDESK_API_TOKEN)
    headers = {"Content-Type": "application/json"}

    try:
        if method.lower() == "get":
            response = requests.get(url, auth=auth, headers=headers)
        elif method.lower() == "put":
            response = requests.put(url, auth=auth, headers=headers, json=data)
        else:
            raise ValueError("Unsupported HTTP method")

        response.raise_for_status()
        # Log only the necessary details
        logging.info(f"Zendesk API request to {endpoint} succeeded.")
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Zendesk API request failed: {e}")
        return None

# Retrieve all pending tickets from the specified view
def get_pending_tickets():
    all_tickets = []
    endpoint = f"/views/{ZENDESK_VIEW_ID}/tickets.json"
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2{endpoint}"
    
    while url:
        response = zendesk_request("get", url.replace(f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2", ""))
        if response:
            tickets = response.get("tickets", [])
            all_tickets.extend(tickets)
            
            # Log how many tickets were retrieved in the current page
            logging.info(f"Retrieved {len(tickets)} tickets from current page.")
            print(f"Retrieved {len(tickets)} tickets from current page.")
            
            # Check if there is a next page
            url = response.get("next_page")
        else:
            # Stop if there was an error with the request
            url = None

    logging.info(f"Total tickets retrieved: {len(all_tickets)}")
    print(f"Total tickets retrieved: {len(all_tickets)}")
    return all_tickets

# Update the checkbox field on a ticket
def update_ticket_checkbox(ticket_id, value):
    data = {
        "ticket": {
            "custom_fields": [
                {
                    "id": 39218804884633,
                    "value": value
                }
            ]
        }
    }
    if TEST_MODE:
        print(f"[TEST MODE] Would update ticket {ticket_id} checkbox to {value}")
        logging.info(f"[TEST MODE] Would update ticket {ticket_id} checkbox to {value}")
    else:
        endpoint = f"/tickets/{ticket_id}.json"
        response = zendesk_request("put", endpoint, data)
        if response:
            logging.info(f"Successfully updated Ticket ID: {ticket_id} to {'True' if value else 'False'}")
        else:
            logging.error(f"Failed to update Ticket ID: {ticket_id}")

# Main function to perform actions based on the scheduler
def main(action):
    if action == "set_true":
        print("Performing action: set_true")
        # Fetch tickets from Zendesk view and set the custom field to True
        pending_tickets = get_pending_tickets()
        processed_ticket_ids = []
        for ticket in pending_tickets:
            ticket_id = ticket["id"]
            update_ticket_checkbox(ticket_id, value=True)  # Set custom field to True
            processed_ticket_ids.append(ticket_id)

        # Save the ticket IDs to the file for later use
        save_processed_tickets(processed_ticket_ids)
        print(f"Processed and stored {len(processed_ticket_ids)} tickets.")

    elif action == "set_false":
        print("Performing action: set_false")
        # Load the processed ticket IDs
        processed_ticket_ids = load_processed_tickets()
        if not processed_ticket_ids:
            print("No tickets found to set to False.")
            return

        for ticket_id in processed_ticket_ids:
            update_ticket_checkbox(ticket_id, value=False)  # Set custom field to False

        # Clear the stored tickets after processing
        save_processed_tickets([])
        print(f"Processed and cleared {len(processed_ticket_ids)} tickets.")

    else:
        print("No valid action specified.")

if __name__ == "__main__":
    try:
        # Test the main function with a manual action
        action = sys.argv[1] if len(sys.argv) > 1 else None
        if action:
            main(action)
        else:
            print("Please specify an action (set_true or set_false).")
    except Exception as e:
        logging.error(f"Script encountered an error: {e}")
        sys.exit(1)
