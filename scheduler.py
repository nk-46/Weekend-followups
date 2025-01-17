import schedule
import time
from backup_file import main, rotate_logs  # Import the main function from your_main_script.py

# Schedule the main function
schedule.every().saturday.at("05:00").do(main, action="set_true")  # Runs main() at 5:00 AM on Saturdays
schedule.every().monday.at("05:00").do(main, action="set_false")    # Runs main() at 5:00 AM on Mondays

# Schedule log rotation on the 1st of every month at midnight
schedule.every().month.at("00:00").do(rotate_logs)


# Start the scheduler
if __name__ == "__main__":
    print("Scheduler is running...")
    while True:
        schedule.run_pending()  # Check if a scheduled job needs to run
        time.sleep(60)          # Wait for a minute before checking again
