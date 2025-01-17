import sqlite3
import logging
import requests
import pytz
import os
from datetime import datetime
import csv
import gzip
import shutil

# Setup logging
LOG_FILE = "/data/zendesk_weekend_check.log"
DB_PATH = "/data/tickets.db"
ARCHIVE_FOLDER = "/data/archives"

os.makedirs(ARCHIVE_FOLDER, exist_ok=True) #ensure archives folder exists 


logging.basicConfig(
    level=logging.INFO,
    filename=LOG_FILE,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Database file for persistent storage
#DB_PATH = "tickets.db"


ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN")
ZENDESK_EMAIL = os.getenv("ZENDESK_EMAIL")
ZENDESK_API_TOKEN = os.getenv("ZENDESK_API_TOKEN")
ZENDESK_VIEW_ID = "40051527319577"
CHECKBOX_FIELD_ID = "custom_fields.39218804884633"

# Timezone
IST = pytz.timezone("Asia/Kolkata")

# Toggle between test and production mode
TEST_MODE = False  # Set to False in production

# Initialize the database
def initialize_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS processed_tickets (
        ticket_id INTEGER PRIMARY KEY
    )
    """)
    conn.commit()
    conn.close()

# Save processed ticket IDs to the database
def save_processed_tickets(ticket_ids):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executemany("INSERT OR IGNORE INTO processed_tickets (ticket_id) VALUES (?)", [(ticket_id,) for ticket_id in ticket_ids])
    conn.commit()
    conn.close()
    logging.info("Ticket Ids saved to Database successfully.")
    print("Ticket Ids saved to Database successfully.")

# Load processed ticket IDs from the database
def load_processed_tickets_and_archive():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Fetch all ticket IDs
    cursor.execute("SELECT ticket_id FROM processed_tickets")
    tickets = [row[0] for row in cursor.fetchall()]
    
    # If there are tickets, write them to a CSV file
    if tickets:
        archive_file = os.path.join(ARCHIVE_FOLDER, f"processed_tickets_archive.csv")
        # Get the current date
        current_date = datetime.now().strftime('%Y-%m-%d')
        with open(archive_file, "w", newline="") as csv_file:
            writer = csv.writer(csv_file)
            # Add headers for the columns
            writer.writerow(["ticket_id", "date_processed"])
            writer.writerows([[ticket_id, current_date] for ticket_id in tickets])
        
        logging.info(f"Archived {len(tickets)} tickets to {archive_file}")
        print(f"Archived {len(tickets)} tickets to {archive_file}")
    else:
        logging.info("No tickets to archive.")
        print("No tickets to archive.")

    conn.close()
    return tickets

# Clear all processed tickets from the database
def clear_processed_tickets():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM processed_tickets")
    conn.commit()
    conn.close()
    logging.info("Database cleared.")
    print("Database cleared.")

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


# Compress and rotate the log file
def rotate_log_file():
    archive_file = os.path.join(ARCHIVE_FOLDER, f"zendesk_weekend_check_{datetime.now().strftime('%Y-%m')}.log.gz")

    # Compress the current log file
    with open(LOG_FILE, "rb") as log_file:
        with gzip.open(archive_file, "wb") as archive:
            shutil.copyfileobj(log_file, archive)

    logging.info(f"Archived log file to {archive_file}.")

    # Clear the log file
    open(LOG_FILE, "w").close()
    logging.info(f"Cleared log file: {LOG_FILE}.")


# Rotate both database and log files
def rotate_logs():
    logging.info("Starting log rotation...")
    print("Starting log rotation...")
    rotate_log_file()
    logging.info("Log rotation completed.")
    print("Log rotation completed.")


# Main function to perform actions based on the scheduler
def main(action):
    initialize_db()  # Ensure the database and table are initialized

    if action == "set_true":
        logging.info("Performing action: set_true")
        print("Performing action: set_true")
        # Fetch tickets from Zendesk view and set the custom field to True
        pending_tickets = get_pending_tickets()
        processed_ticket_ids = []
        for ticket in pending_tickets:
            ticket_id = ticket["id"]
            update_ticket_checkbox(ticket_id, value=True)  # Set custom field to True
            processed_ticket_ids.append(ticket_id)

        # Save the ticket IDs to the database
        save_processed_tickets(processed_ticket_ids)
        logging.info(f"Processed and stored {len(processed_ticket_ids)} tickets.")

    elif action == "set_false":
        logging.info("Performing action: set_false")
        print("Performing action: set_false")
        # Load the processed ticket IDs from the database
        processed_ticket_ids = load_processed_tickets_and_archive()
        if not processed_ticket_ids:
            logging.info("No tickets found to set to False.")
            return

        for ticket_id in processed_ticket_ids:
            update_ticket_checkbox(ticket_id, value=False)  # Set custom field to False

        # Clear the stored tickets after processing
        clear_processed_tickets()
        logging.info(f"Processed and cleared {len(processed_ticket_ids)} tickets.")

    else:
        logging.warning("No valid action specified.")

