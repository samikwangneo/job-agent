### Google Sheets Integration Setup Guide for Intern Agent

This guide will walk you through setting up the necessary Google Cloud project, credentials, and Google Sheet to allow the Intern Agent to save job listings.

---

#### Step 1: Set Up Your Google Cloud Project & Service Account

1.  **Create a Google Cloud Project:**
    *   Go to the [Google Cloud Console](https://console.cloud.google.com/).
    *   Click the project dropdown in the top bar and select "New Project".
    *   Give it a name (e.g., "Intern Agent Project") and click "Create".

2.  **Enable the Google Sheets API:**
    *   Make sure your new project is selected.
    *   In the search bar, type "Google Sheets API" and select it.
    *   Click the "Enable" button.

3.  **Create a Service Account:**
    *   In the search bar, navigate to "APIs & Services" > "Credentials".
    *   Click "+ CREATE CREDENTIALS" and choose "Service account".
    *   Fill in the details:
        *   **Service account name:** `intern-agent-sheets-writer` (or a name of your choice).
        *   **Service account ID:** This will be generated for you.
        *   **Description:** "Service account for the Intern Agent to write to Google Sheets."
    *   Click "CREATE AND CONTINUE".
    *   **Grant access:** In the "Role" dropdown, select "Editor". This gives the account permission to edit your sheets.
    *   Click "CONTINUE", then "DONE".

4.  **Generate a JSON Key:**
    *   In the "Credentials" screen, find the service account you just created and click on it.
    *   Go to the "KEYS" tab.
    *   Click "ADD KEY" > "Create new key".
    *   Select "JSON" as the key type and click "CREATE".
    *   A JSON file will be downloaded to your computer. **This is your credential file. Keep it safe and do not share it publicly.**

---

#### Step 2: Configure Your Local Environment

1.  **Place the JSON Key File:**
    *   Move the downloaded JSON key file into the project's root directory (`job-agent/`). You can rename it for simplicity (e.g., `google-credentials.json`).

2.  **Create and Update the `.env` File:**
    *   In the root directory of the project (`job-agent/`), create a file named `.env` if it doesn't already exist.
    *   Add the following variables to your `.env` file:

    ```env
    # Path to your downloaded service account JSON key.
    # If you placed it in the root folder and renamed it, the path is just the filename.
    GOOGLE_APPLICATION_CREDENTIALS="google-credentials.json"

    # The ID of the Google Sheet you want to write to.
    # You can find this in your Google Sheet's URL:
    # https://docs.google.com/spreadsheets/d/THIS_IS_THE_SPREADSHEET_ID/edit
    SPREADSHEET_ID="YOUR_SPREADSHEET_ID_HERE"

    # (Optional) The name of the specific sheet (tab) to use.
    # Defaults to 'Sheet1' if not set.
    DEFAULT_SHEET_NAME="Sheet1"
    ```
    *   Replace `YOUR_SPREADSHEET_ID_HERE` with the actual ID of your spreadsheet.

---

#### Step 3: Prepare and Share Your Google Sheet

1.  **Create a Google Sheet:**
    *   Go to [sheets.google.com](https://sheets.google.com) and create a new blank spreadsheet.

2.  **Share the Sheet with the Service Account:**
    *   Open your service account's JSON key file (e.g., `google-credentials.json`) in a text editor.
    *   Find the value associated with the `"client_email"` key. It will look something like `intern-agent-sheets-writer@your-project-id.iam.gserviceaccount.com`.
    *   In your Google Sheet, click the "Share" button in the top right corner.
    *   Paste the `client_email` into the "Add people and groups" field.
    *   Ensure "Editor" is selected as the role.
    *   Click "Send".

3.  **Set Up the Header Row:**
    *   In the first row of your sheet (e.g., in cell A1), you **must** set up the following headers exactly as shown, in this order:

| A | B | C | D | E | F |
|---|---|---|---|---|---|
| Date Added | Company | Role | Location | URL | Status |

---

You are now all set! When you run the agent, it will automatically find this sheet and start populating it with the internship data it discovers. 