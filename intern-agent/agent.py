import platform
import asyncio
import os
import json
import re

if platform.system() == "Windows":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        print("Intern Agent (Module Load): WindowsSelectorEventLoopPolicy set.")
    except Exception as e:
        print(f"Intern Agent (Module Load): Info/Error setting event loop policy: {e}.")

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from google.adk.agents import Agent
from google.generativeai import types as genai_types
import google.generativeai as genai
from dotenv import load_dotenv
from google.generativeai import GenerativeModel

from .google_sheets_utils import save_jobs_to_google_sheet

load_dotenv()

def parse_internship_table(html_content: str) -> list[dict]:
    """
    Parses the HTML content of the GitHub internship README to extract internship postings from the table.
    """
    soup = BeautifulSoup(html_content, 'lxml')
    internships = []
    
    # The table is inside a div with class 'markdown-body'
    markdown_body = soup.find('article', class_='markdown-body')
    if not markdown_body:
        print("Intern Agent Parser: Could not find the 'markdown-body' article tag.")
        return []

    table = markdown_body.find('table')
    if not table or not table.find('tbody'):
        print("Intern Agent Parser: Could not find the internship table or its tbody.")
        return []

    last_company = ""
    rows = table.tbody.find_all('tr')
    print(f"Intern Agent Parser: Found {len(rows)} rows in the internship table.")

    for row in rows:
        cells = row.find_all('td')
        if len(cells) < 4:
            continue

        company = cells[0].text.strip()
        if company == '↳':
            company = last_company
        else:
            last_company = company

        role = cells[1].text.strip().replace('🛂', '').replace('🇺🇸', '').strip()
        location_cell = cells[2]
        location = ' | '.join([part.strip() for part in location_cell.stripped_strings])
        
        # Define URL first
        application_cell = cells[3]
        link_tag = application_cell.find('a')
        url = "Closed"
        if link_tag and link_tag.has_attr('href'):
            url = link_tag['href']
        elif '🔒' in application_cell.text:
            continue # Skip closed applications
        else:
            url = application_cell.text.strip()
        
        # Now, check the URL
        if not url.startswith('http'): 
            continue

        date_posted = cells[4].text.strip() if len(cells) > 4 else "N/A"

        internships.append({
            "company": company,
            "role": role,
            "location": location,
            "date_posted": date_posted,
            "url": url,
        })
        
    return internships

async def find_and_apply_for_internships(github_url: str) -> list[dict]:
    """
    Scrapes internship postings from a GitHub README, saves them to a Google Sheet,
    and then attempts to autofill applications for up to 5 of them.
    Args:
        github_url (str): The URL of the GitHub repository's README page.
    Returns:
        A list of internship data that was scraped.
    """
    print(f"Intern Agent: Starting Stage 1 - Discovery from {github_url}")
    
    # --- Part 1: Scrape the main list from GitHub ---
    initial_internships = []
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(github_url, timeout=60000, wait_until='domcontentloaded')
            html_content = await page.content()
            await browser.close()
            initial_internships = parse_internship_table(html_content)
            print(f"Intern Agent: Discovered {len(initial_internships)} potential internships from GitHub.")
    except Exception as e:
        print(f"Intern Agent: Failed to scrape GitHub list. Error: {e}")
        return [{"error": "Failed to scrape primary GitHub list.", "details": str(e)}]

    if not initial_internships:
        print("Intern Agent: No internships found on GitHub page.")
        return []

    # --- Part 2: Save to Google Sheets (Enrichment disabled) ---
    for job in initial_internships:
        job['status'] = "Discovered"

    if initial_internships:
        print("\nIntern Agent: Skipping Google Sheets save as per current configuration.")
        # print(f"\nIntern Agent: Saving {len(initial_internships)} processed internships to Google Sheets...")
        # try:
        #     await asyncio.to_thread(save_jobs_to_google_sheet, initial_internships)
        #     print("Intern Agent: Saving to Google Sheets initiated.")
        # except Exception as e:
        #     print(f"Intern Agent: Error initiating saving to Google Sheets: {e}")

    # --- Part 3: Loop through internships and attempt to apply ---
    print("\n--- Starting Stage 2: Autofill Application Process ---")
    applied_count = 0
    max_applications = 5
    
    jobs_to_apply = [job for job in initial_internships if job.get("url") and job["url"].startswith("http")]
    
    print(f"Found {len(jobs_to_apply)} jobs with valid application links. Attempting to apply to a max of {max_applications}.")

    for job in jobs_to_apply:
        if applied_count >= max_applications:
            print(f"Reached max applications limit of {max_applications}.")
            break
        
        url = job["url"]
        print(f"\n({applied_count + 1}/{max_applications}) Attempting to apply for: {job['company']} - {job['role']} at {url}")
        
        result = await apply_for_internship(url)
        
        print(f"  -> Application result: {result.get('status')} - {result.get('message')}")
        
        if result and result.get("status") == "success":
            applied_count += 1
        elif result and "No <form> tag found" in result.get("message", ""):
            print("  -> Skipping application as no form was found on the page.")
        else:
            print("  -> Application attempt failed or was aborted.")
        
        await asyncio.sleep(2)
        
    print(f"\n--- Autofill process finished. Attempted {applied_count} applications. ---")
    
    return initial_internships

# --- Stage 2: Autofill Agent ---

# Placeholder for user data. In a real application, this would be loaded from a secure config file.
USER_DATA = {
    "first_name": "John",
    "last_name": "Doe",
    "preferred_name": "John",
    "email": "johndoe@example.com",
    "phone": "555-123-4567",
    "linkedin_profile": "https://linkedin.com/in/johndoe",
    "github_profile": "https://github.com/johndoe",
    "website": "https://johndoe.dev",
    "street_address": "123 Main Street",
    "city": "Los Angeles",
    "state": "CA",
    "zip_code": "12345",
    "country": "United States",
    "university": "Alabama State University",
    "major": "Computer Science",
    "degree": "Bachelor's",
    "graduation_date_month": "May",
    "graduation_date_year": "2026",
    "start_date_month": "May",  
    "start_date_year": "2025",
    "end_date_month": "May",
    "end_date_year": "2026",
    "citizenship": "U.S. Citizen",
    "work_authorized": "Yes",
    "sponsorship_required": "No",
    "gender": "Prefer not to say",
    "race_ethnicity": "Prefer not to say",
    "resume_text": """
    John Doe
    (555) 123-4567 | johndoe@example.com | linkedin.com/in/johndoe | github.com/johndoe

    SUMMARY
    Aspiring Software Engineer with a strong foundation in Python, Java, and C++. Experience in developing web applications and a passion for problem-solving and algorithms. Eager to apply academic knowledge to real-world challenges in a fast-paced internship.

    EDUCATION
    State University, Los Angeles, CA
    Bachelor of Science in Computer Science, May 2026

    PROJECTS
    - AI Job Agent: Developed a Python-based agent using Playwright and Gemini to automate job applications.
    - E-commerce Website: Built a full-stack web application with a React frontend and Flask backend.
    """,
    "cover_letter": "Dear Hiring Manager, I am very interested in this internship opportunity...",
    "resume_path": "C:/Users/Samik/Downloads/exam2key.pdf" # IMPORTANT: Use an absolute path
}

async def get_answer_from_gemini(question: str, job_description: str, resume_text: str) -> str:
    """Uses Gemini to generate a response to a custom application question."""
    print(f"Agent (Question): Asking Gemini to answer the question: '{question[:50]}...'")
    model = GenerativeModel('gemini-2.0-flash')

    prompt = f"""
    You are a professional career coach. A candidate is applying for a job.
    Based on their resume and the job description, please provide a concise, professional, and well-written answer to the following application question.

    **Job Description:**
    ```
    {job_description}
    ```

    **Candidate's Resume:**
    ```
    {resume_text}
    ```

    **Application Question:**
    "{question}"

    **Instructions:**
    - Keep the answer to 2-4 sentences.
    - Be enthusiastic and professional.
    - Directly address the question.

    **Generated Answer:**
    """

    try:
        response = await model.generate_content_async(prompt)
        print("Agent (Question): Successfully generated an answer.")
        return response.text.strip()
    except Exception as e:
        print(f"Agent (Question): Gemini failed to generate an answer. Error: {e}")
        return "Could not generate an answer."

async def get_page_plan_from_gemini(html_content: str) -> dict:
    """Uses Gemini to create a full plan of actions for a given webpage."""
    print("Agent (Autofill): Asking Gemini to create a plan for the current page...")
    model = GenerativeModel('gemini-2.0-flash')
    
    prompt = f"""
    You are an expert web automation assistant. Your goal is to create a step-by-step plan to fill out a job application form based on the user's data.
    I will provide you with the current HTML of the web page. You must analyze it and return a complete plan of all the steps required to fill out the form on THIS PAGE.

    This is the user's data you need to use for filling the form:
    {json.dumps(USER_DATA, indent=2)}

    Please respond with a single, valid JSON object containing a "plan" which is a list of action objects.

    **Rules for Creating the Plan:**
    1.  **Initial Apply Button:** If the page seems to be a job description with an "Apply" or "Continue" button that would lead to the actual form, the plan should contain ONLY ONE action: `{{ "action": "CLICK", "selector": "<selector_for_apply_button>" }}`.
    2.  **Form Fields:** If the page contains a form, the plan should include a `FILL` or `UPLOAD` action for every relevant field found.
    3.  **Multi-Page Forms:** If the form has a "Next," "Continue," or similar button to get to the next page, the LAST action in the plan should be to `CLICK` that button.
    4.  **No More Actions:** If no form fields or actionable buttons are found, return an empty plan: `{{ "plan": [] }}`.

    **Action Formats:**
    - To fill a text input: `{{"action": "FILL", "selector": "<CSS selector>", "user_data_key": "<key from user data>"}}`
    - To upload a resume: `{{"action": "UPLOAD", "selector": "<CSS selector for the input type='file'>", "user_data_key": "resume_path"}}`
    - To select from a dropdown: `{{"action": "SELECT", "selector": "<CSS selector for the <select> element>", "value_to_select": "<The visible text or value of the option to select>"}}`
    - For custom dropdowns (that are not `<select>` tags, often using `role="combobox"`): `{{"action": "CUSTOM_SELECT", "selector": "<selector for the fillable <input> element inside the component>", "option_text": "<text of the option to select>"}}`. **Important**: The selector MUST point to the actual `<input>` tag to type into, not a surrounding `<div>`.
    - To answer a text-based question: `{{"action": "ANSWER_QUESTION", "selector": "<selector for the textarea>", "question_text": "<The text of the question label>"}}`
    - To click a button/link: `{{"action": "CLICK", "selector": "<CSS selector>"}}`

    HTML Content:
    ```html
    {html_content}
    ```
    """

    try:
        response = await model.generate_content_async(prompt)
        cleaned_response = response.text.strip().replace("`", "")
        if cleaned_response.startswith("json"):
            cleaned_response = cleaned_response[4:]

        plan_json = json.loads(cleaned_response)
        print(f"Agent (Autofill): Gemini created a plan with {len(plan_json.get('plan', []))} steps.")
        return plan_json
    except Exception as e:
        print(f"Agent (Autofill): Gemini failed to create a plan. Error: {e}")
        print(f"Gemini's raw response was: {getattr(response, 'text', 'N/A')}")
        return {"plan": []}


async def apply_for_internship(job_url: str):
    """
    (Stage 2 - Plan-Based Approach)
    Navigates a job application using a plan from an LLM. Handles multi-page
    applications by generating a new plan after each navigation.
    """
    print(f"\n--- Starting Plan-Based Autofill for Job at {job_url} ---")
    
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=False)
            page = await browser.new_page()
            print(f"Agent (Autofill): Navigating to {job_url}...")
            await page.goto(job_url, timeout=60000)

            max_pages_to_process = 10  # Safety break for navigation loops
            for i in range(max_pages_to_process):
                print(f"\n--- Analyzing Page {i + 1}/{max_pages_to_process} at {page.url} ---")
                await page.wait_for_load_state('domcontentloaded', timeout=15000)
                await asyncio.sleep(2)  # Wait for dynamic content

                html_content = await page.content()

                # Scrape job description for context-aware answers
                soup = BeautifulSoup(html_content, 'lxml')
                job_description_el = soup.find(id='content') or soup.find('main') or soup.body
                job_description = job_description_el.get_text(' ', strip=True)[:4000]

                page_plan_json = await get_page_plan_from_gemini(html_content)
                page_plan = page_plan_json.get("plan", [])

                if not page_plan:
                    print("  -> Gemini found no further actions for this page. Ending application attempt.")
                    break

                navigated = False
                for step_num, step in enumerate(page_plan):
                    action = step.get("action", "FAIL")
                    selector = step.get("selector")
                    print(f"  [Step {step_num + 1}/{len(page_plan)}] Action: {action}, Selector: '{selector}'")

                    if action == "FILL":
                        key = step.get("user_data_key")
                        value = USER_DATA.get(key)
                        try:
                            await page.locator(selector).first.fill(str(value))
                        except Exception as e:
                            print(f"     !! Failed to FILL. Error: {e}")
                    
                    elif action == "UPLOAD":
                        path = USER_DATA.get("resume_path")
                        try:
                            await page.locator(selector).first.set_input_files(path, timeout=10000)
                        except Exception as e:
                            print(f"     !! Failed to UPLOAD. This is critical. Aborting job. Error: {e}")
                            return {"status": "error", "message": f"Failed to upload resume to selector: {selector}"}

                    elif action == "SELECT":
                        value = step.get("value_to_select")
                        try:
                            await page.locator(selector).first.select_option(value)
                        except Exception as e:
                            print(f"     !! Failed to SELECT '{value}' for selector '{selector}'. Error: {e}")

                    elif action == "CUSTOM_SELECT":
                        option_text = step.get("option_text")
                        try:
                            # For combobox-style dropdowns, click to activate, type the value, then press Enter.
                            await page.locator(selector).first.click()
                            await asyncio.sleep(0.2) # Brief pause after click
                            await page.locator(selector).first.fill(option_text)
                            # Wait for the dropdown options to appear/filter
                            await asyncio.sleep(0.5)
                            # Press Enter to confirm the selection
                            await page.locator(selector).first.press("Enter")
                        except Exception as e:
                            print(f"     !! Failed to perform CUSTOM_SELECT for '{option_text}' on selector '{selector}'. Error: {e}")

                    elif action == "ANSWER_QUESTION":
                        question_text = step.get("question_text")
                        try:
                            answer = await get_answer_from_gemini(question_text, job_description, USER_DATA["resume_text"])
                            await page.locator(selector).first.fill(answer)
                        except Exception as e:
                            print(f"     !! Failed to ANSWER question '{question_text[:30]}...'. Error: {e}")

                    elif action == "CLICK":
                        try:
                            # Use expect_navigation for clicks that should change the page
                            async with page.expect_navigation(timeout=5000, wait_until='domcontentloaded'):
                                await page.locator(selector).first.click()
                            print(f"    -> Navigation detected to: {page.url}")
                            navigated = True
                            break  # Exit plan loop to re-analyze new page
                        except PlaywrightTimeoutError:
                            # This is okay, it means the click didn't navigate (e.g., a radio button)
                            print("    -> Click did not cause navigation. Continuing plan.")
                        except Exception as e:
                            print(f"     !! Failed to CLICK. Aborting job. Error: {e}")
                            return {"status": "error", "message": f"Failed to click selector: {selector}"}
                
                if not navigated:
                    # If we finished the whole plan and didn't navigate, we are done.
                    print("\n  -> Completed page plan without navigation. Assuming application is finished.")
                    break
            
            print("\nForm filling process complete or max pages reached. Pausing for review.")
            print("The browser will remain open. Please review the form, then manually close the browser to continue.")
            await page.wait_for_timeout(60000)

            await browser.close()
            return {"status": "success", "message": "Autofill process complete. Browser was open for review."}

        except Exception as e:
            print(f"An unexpected error occurred during the apply process: {e}")
            if 'browser' in locals() and browser.is_connected():
                await browser.close()
            return {"status": "error", "message": str(e)}


root_agent = Agent(
    name="internship_agent",
    model="gemini-2.0-flash", 
    description="An agent that finds internship listings from a GitHub repo, saves them to Google Sheets, and then attempts to autofill applications.",
    instruction=(
        "You are a helpful internship pipeline assistant."
        "Your main function is to find and apply for internships."
        "When the user asks you to start, use the `find_and_apply_for_internships` tool."
        "This single tool will perform the entire pipeline:"
        "1. Scrape the main GitHub list for new internships."
        "2. Save the findings to Google Sheets."
        "3. Attempt to autofill applications for up to 5 of the discovered jobs."
        "   - The URL is fixed. Always use: https://github.com/vanshb03/Summer2026-Internships?tab=readme-ov-file"
        "   - The tool will open a browser window for each application attempt. The user should monitor this."
        "After running, report on how many internships were found and how many application attempts were made."
    ),
    tools=[find_and_apply_for_internships],
    generate_content_config=genai_types.GenerationConfig(
        max_output_tokens=2048
    )
)
