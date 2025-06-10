import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Load environment variables
from dotenv import load_dotenv
load_dotenv() # Loads variables from .env in the current or parent directory. 
              # If adk-backend/.env exists, it will be used when running from adk-backend.

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
DEFAULT_SHEET_NAME = os.getenv('DEFAULT_SHEET_NAME', 'Sheet1')

def get_spreadsheet_id():
    spreadsheet_id = os.getenv('SPREADSHEET_ID')
    if not spreadsheet_id:
        print("Error: SPREADSHEET_ID environment variable not set.")
        raise ValueError("SPREADSHEET_ID not configured in .env file. Please add it to adk-backend/.env")
    return spreadsheet_id

def get_google_credentials():
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not creds_path:
        print("Error: GOOGLE_APPLICATION_CREDENTIALS environment variable not set.")
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS not configured. Please add it to adk-backend/.env pointing to your service account JSON key file.")
    if not os.path.isabs(creds_path):
        # Attempt to resolve relative to adk-backend directory if not absolute
        # This assumes the script or its caller (agent.py) is effectively running with adk-backend as context
        possible_path = os.path.join(os.path.dirname(__file__), creds_path)
        if os.path.exists(possible_path):
            creds_path = possible_path
        elif os.path.exists(os.path.join(os.path.dirname(__file__), '..', creds_path)): # one level up (e.g. project root)
             creds_path = os.path.join(os.path.dirname(__file__), '..', creds_path)
        # else, we hope the original creds_path (if relative) is resolvable from CWD

    if not os.path.exists(creds_path):
        print(f"Error: Credentials file not found at the resolved path: {creds_path}")
        print(f"Original path specified: {os.getenv('GOOGLE_APPLICATION_CREDENTIALS')}")
        raise FileNotFoundError(f"Service account key file not found at {creds_path}")
    
    try:
        credentials = service_account.Credentials.from_service_account_file(
            creds_path, scopes=SCOPES)
        return credentials
    except Exception as e:
        print(f"Error loading service account credentials from {creds_path}: {e}")
        raise

def save_jobs_to_google_sheet(jobs_data: list[dict]):
    """
    Saves a list of job data to the configured Google Spreadsheet.
    Assumes the first row of the sheet contains headers:
    ["Date Added", "Title", "Company", "Location", "URL"]
    Args:
        jobs_data (list[dict]): A list of job dictionaries.
    """
    if not jobs_data:
        print("Google Sheets: No job data provided to save.")
        return

    try:
        spreadsheet_id = get_spreadsheet_id()
        credentials = get_google_credentials()
        service = build('sheets', 'v4', credentials=credentials)
    except (ValueError, FileNotFoundError) as e:
        print(f"Google Sheets: Error initializing service: {e}")
        return
    except HttpError as e:
        print(f"Google Sheets: HttpError during API client build: {e}. Check credentials/API enablement.")
        return
    except Exception as e:
        print(f"Google Sheets: Unexpected error during service initialization: {e}")
        return

    current_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    values_to_append = []
    for job in jobs_data:
        values_to_append.append([
            current_timestamp,                      # Date Added
            job.get('title', 'N/A'),            # Title
            job.get('company', 'N/A'),          # Company
            job.get('location', 'N/A'),         # Location
            job.get('url', 'N/A')               # URL
        ])

    body = {'values': values_to_append}
    sheet_name_to_use = DEFAULT_SHEET_NAME

    try:
        print(f"Google Sheets: Appending {len(values_to_append)} rows to ID: {spreadsheet_id}, Sheet: {sheet_name_to_use} (Source Page column removed).")
        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name_to_use}!A1",
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()
        print(f"Google Sheets: {result.get('updates', {}).get('updatedCells', 0)} cells appended.")
    except HttpError as error:
        print(f"Google Sheets: API error: {error}. Details: {error.resp.status} {error.resp.reason} - {error.content}")
    except Exception as e:
        print(f"Google Sheets: Unexpected error during append: {e}")

if __name__ == '__main__':
    print("Testing Google Sheets utility (ensure adk-backend/.env is configured)...")
    # For this direct test to work, you need GOOGLE_APPLICATION_CREDENTIALS and SPREADSHEET_ID in .env
    # The .env should be in adk-backend/ or the project root.
    # The path in GOOGLE_APPLICATION_CREDENTIALS should be resolvable.
    
    # Check if essential env vars are loaded for the test
    if not os.getenv('SPREADSHEET_ID') or not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
        print("Missing SPREADSHEET_ID or GOOGLE_APPLICATION_CREDENTIALS in environment for testing.")
        print("Please ensure adk-backend/.env is correctly set up.")
        print(f"Attempted to load .env from: {os.getcwd()} and parent directories.")
    else:
        print(f"Using Spreadsheet ID: {os.getenv('SPREADSHEET_ID')}")
        resolved_creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        if not os.path.isabs(resolved_creds_path):
            # Simple relative path resolution for testing if __name__ == '__main__'
            # This assumes .env is in adk-backend and creds file path is relative to adk-backend
            # or it's relative to project root if .env is in project root.
            # A more robust test setup might be needed for complex pathing.
            print(f"Note: GOOGLE_APPLICATION_CREDENTIALS path '{resolved_creds_path}' is relative.")
            print("For direct script testing, ensure it's resolvable from current working directory or use an absolute path in .env")

        print(f"Using Credentials Path: {resolved_creds_path} (ensure this path is correct)")
        print(f"Default sheet name: {DEFAULT_SHEET_NAME}")
        
        sample_jobs = [
            {'title': 'Dev Test A', 'company': 'Test Corp A', 'location': 'Remote', 'url': 'http://example.com/a'},
            {'title': 'Dev Test B', 'company': 'Test Corp B', 'location': 'Local', 'url': 'http://example.com/b'}
        ]
        save_jobs_to_google_sheet(sample_jobs)
        print("Google Sheets test complete. Please verify your spreadsheet.") 