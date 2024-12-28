# https://claude.ai/chat/230fd208-927f-4f7e-b646-9d96c72c542e
# test_fec_monitor.py
import os
from dotenv import load_dotenv
from flask import Request
from werkzeug.test import EnvironBuilder

# Import the main function from your original script
from fec_monitor import monitor_contributions

def create_test_request():
    """Create a test request object similar to what Cloud Run would receive"""
    builder = EnvironBuilder(method='POST')
    return Request(builder.get_environ())

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Check for required environment variables
    required_vars = [
        'PROJECT_ID',
        'NOTIFICATION_EMAIL',
        'SMTP_SERVER',
        'SMTP_PORT',
        'SMTP_USERNAME',
        'FROM_EMAIL'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print("Missing required environment variables:")
        for var in missing_vars:
            print(f"- {var}")
        return
    
    # Create test request
    request = create_test_request()
    
    # Run the function
    try:
        response, status_code = monitor_contributions(request)
        print(f"Response (status {status_code}):", response)
    except Exception as e:
        print(f"Error running monitor_contributions: {str(e)}")

if __name__ == "__main__":
    main()
