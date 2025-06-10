import platform
import asyncio

# Initial attempt to set policy at module load
if platform.system() == "Windows":
    try:
        # Attempt to set the policy at module load
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        print("ADK Agent (Module Load): WindowsSelectorEventLoopPolicy set.")
    except Exception as e:
        # This might fail if a loop is already set or running, which can happen
        # depending on how ADK initializes.
        print(f"ADK Agent (Module Load): Info/Error setting event loop policy: {e}. May already be set or unchangeable.")

import os
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup
from google.adk.agents import Agent
from google.generativeai import types as genai_types

from dotenv import load_dotenv
load_dotenv() # Load environment variables from .env file

from .google_sheets_utils import save_jobs_to_google_sheet

# Requires beautifulsoup4, lxml, playwright to be installed in the environment
# Run `playwright install` after installing the playwright python package

def parse_html_with_beautifulsoup(html_content: str, page_number: int) -> list[dict]:
    """
    Parses the HTML content of a Simply Hired search results page to extract job postings.
    """
    soup = BeautifulSoup(html_content, 'lxml')
    jobs = []
    job_cards = soup.find_all('div', attrs={'data-testid': 'searchSerpJob'})

    print(f"ADK Agent - Page {page_number}: Found {len(job_cards)} job cards.")

    for job_card in job_cards:
        title_element = job_card.find('h2', attrs={'data-testid': 'searchSerpJobTitle'})
        title_link = title_element.find('a') if title_element else None
        title = title_link.text.strip() if title_link else "N/A"
        
        url = title_link['href'] if title_link and title_link.has_attr('href') else "N/A"
        if url != "N/A" and not url.startswith('http'):
            url = f"https://www.simplyhired.com{url}"

        company_element = job_card.find('span', attrs={'data-testid': 'companyName'})
        company = company_element.text.strip() if company_element else "N/A"

        location_element = job_card.find('span', attrs={'data-testid': 'searchSerpJobLocation'})
        location = location_element.text.strip() if location_element else "N/A"

        if title != "N/A":
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "page_scraped": page_number
            })
    return jobs

async def find_jobs_on_simplyhired(job_role: str, location: str = "United States", max_pages: int = 1) -> list[dict]:
    """
    Scrapes job postings from Simply Hired for a given job role and location using Playwright and BeautifulSoup.
    It can scrape multiple pages as specified by max_pages.
    Also saves the found jobs to a configured Google Sheet.
    Args:
        job_role (str): The job role to search for (e.g., "Software Engineer").
        location (str): The location to search in (e.g., "New York, NY"). Defaults to "United States".
        max_pages (int): The maximum number of search result pages to scrape. Defaults to 1.
    Returns:
        list[dict]: A list of dictionaries, where each dictionary contains details of a job posting
                    (title, company, location, url, page_scraped). Returns an empty list if no jobs are found
                    or an error occurs.
    """
    print(f"ADK Agent - Starting Simply Hired scrape for role: '{job_role}', location: '{location}', max_pages: {max_pages}")
    all_extracted_jobs = []
    browser = None
    context = None

    # Ensure downloads directory exists (within adk-backend for this agent)
    downloads_dir = os.path.join(os.path.dirname(__file__), "downloads")
    os.makedirs(downloads_dir, exist_ok=True)

    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            page = await context.new_page()

            for page_num in range(1, max_pages + 1):
                print(f"ADK Agent - --- Processing Page {page_num} ---")
                html_content = None
                current_url = ""

                if page_num == 1:
                    search_role_query = job_role.replace(" ", "+")
                    search_location_query = location.replace(" ", "+")
                    target_url = f"https://www.simplyhired.com/search?q={search_role_query}&l={search_location_query}"
                    print(f"ADK Agent - Navigating to initial URL: {target_url}")
                    await page.goto(target_url, timeout=60000, wait_until='domcontentloaded')
                    current_url = target_url
                else:
                    next_page_selector = f"[data-testid='paginationBlock{page_num}']" # Example, may need adjustment
                    print(f"ADK Agent - Attempting to find and click link for page {page_num} using selector: {next_page_selector}")
                    
                    try:
                        next_page_link = page.locator(next_page_selector)
                        if await next_page_link.count() > 0:
                            await next_page_link.first.click(timeout=10000) # Added timeout
                            await page.wait_for_load_state('domcontentloaded', timeout=30000)
                            await asyncio.sleep(3) # Give time for dynamic content
                            current_url = page.url
                            print(f"ADK Agent - Navigated to page {page_num}. Current URL: {current_url}")
                        else:
                            print(f"ADK Agent - Could not find link for page {page_num}. Stopping pagination.")
                            break
                    except PlaywrightTimeoutError:
                        print(f"ADK Agent - Timeout clicking next page link for page {page_num}. Stopping pagination.")
                        break
                    except Exception as e:
                        print(f"ADK Agent - Error clicking next page link for page {page_num}: {e}. Stopping pagination.")
                        break
                
                html_content = await page.content()
                print(f"ADK Agent - Retrieved HTML from {current_url} (length: {len(html_content)} chars).")

                if html_content:
                    output_filename = os.path.join(downloads_dir, f"downloaded_page_{page_num}.html")
                    try:
                        with open(output_filename, "w", encoding="utf-8") as f:
                            f.write(html_content)
                        print(f"ADK Agent - HTML for page {page_num} saved to: {output_filename}")
                    except Exception as e:
                        print(f"ADK Agent - Error saving HTML for page {page_num}: {e}")
                    
                    try:
                        jobs_from_page = parse_html_with_beautifulsoup(html_content, page_num)
                        if jobs_from_page:
                            all_extracted_jobs.extend(jobs_from_page)
                            print(f"ADK Agent - Successfully parsed {len(jobs_from_page)} jobs from page {page_num}.")
                    except Exception as e:
                        print(f"ADK Agent - Error parsing with BeautifulSoup for page {page_num}: {e}")
                else:
                    print(f"ADK Agent - No HTML content for page {page_num}, skipping parsing.")
            
        except PlaywrightTimeoutError as pte:
            print(f"ADK Agent - A Playwright timeout occurred: {pte}")
            # Optionally, save whatever was collected before the timeout if all_extracted_jobs is not empty
            if all_extracted_jobs:
                print(f"ADK Agent - Saving {len(all_extracted_jobs)} jobs collected before timeout to Google Sheets.")
                try:
                    await asyncio.to_thread(save_jobs_to_google_sheet, all_extracted_jobs)
                except Exception as sheet_error:
                    print(f"ADK Agent - Error saving to Google Sheets after Playwright timeout: {sheet_error}")
            return [{"error": "Playwright timeout", "details": str(pte), "jobs_collected_before_timeout": len(all_extracted_jobs)}]
        except Exception as e:
            print(f"ADK Agent - An unexpected error occurred in find_jobs_on_simplyhired: {e}")
            # Optionally, save whatever was collected before the error
            if all_extracted_jobs:
                print(f"ADK Agent - Saving {len(all_extracted_jobs)} jobs collected before error to Google Sheets.")
                try:
                    await asyncio.to_thread(save_jobs_to_google_sheet, all_extracted_jobs)
                except Exception as sheet_error:
                    print(f"ADK Agent - Error saving to Google Sheets after unexpected error: {sheet_error}")
            return [{"error": "Unexpected error during scraping", "details": str(e), "jobs_collected_before_error": len(all_extracted_jobs)}]
        finally:
            if context:
                await context.close()
            if browser:
                print("ADK Agent - Closing browser...")
                await browser.close()
        
        print(f"ADK Agent - Finished scraping. Total jobs found: {len(all_extracted_jobs)}")
        
        if all_extracted_jobs:
            print(f"ADK Agent - Attempting to save {len(all_extracted_jobs)} jobs to Google Sheets...")
            try:
                # Run the synchronous save_jobs_to_google_sheet in a separate thread
                await asyncio.to_thread(save_jobs_to_google_sheet, all_extracted_jobs)
                print("ADK Agent - Job saving to Google Sheets initiated.")
            except Exception as e:
                # Log error but don't let it prevent returning jobs to the user
                print(f"ADK Agent - Error initiating job saving to Google Sheets: {e}")
                # The save_jobs_to_google_sheet function itself has more detailed error logging.

        return all_extracted_jobs

root_agent = Agent(
    name="job_search_agent",
    model="gemini-2.0-flash", 
    description="Agent that searches for job postings on Simply Hired and saves them to a Google Sheet.",
    instruction=(
        "You are a helpful job search assistant. Your main task is to find job postings based on user queries."
        "1. When a user asks you to find jobs, first ask for the 'job role' they are interested in, unless it's already provided in their query."
        "2. Optionally, ask for a 'location'. If not provided, default to 'United States'. If provided, use it."
        "3. Optionally, ask for the 'maximum number of pages' to scrape. If not provided, default to 1. If provided, use it."
        "4. Use the `find_jobs_on_simplyhired` tool with the collected or provided job role, location, and max_pages."
        "5. After the tool runs, if jobs are found, clearly state the total number of jobs found. Jobs found are also automatically saved to a configured Google Sheet."
        "6. IMPORTANT: Present ALL found jobs. For EACH job, provide its title, company, location, and URL. Do not summarize or truncate the list of jobs. Ensure every job retrieved by the tool is shown to the user."
        "7. If the tool returns an error or no jobs are found, inform the user clearly and specifically about the outcome (e.g., if a Playwright timeout occurred, mention it)."
        "Example of presentation for a single job (repeat for ALL jobs found):\n"
        "  Title: Software Engineer\n"
        "  Company: Tech Solutions Inc.\n"
        "  Location: San Francisco, CA\n"
        "  URL: https://example.com/job/123"
    ),
    tools=[find_jobs_on_simplyhired],
    generate_content_config=genai_types.GenerationConfig(
        # Temperature, top_p, top_k can be adjusted if needed
        # Attempt to increase max output tokens if truncation is an issue.
        # Common values are 2048, 4096, 8192. Check model specifics if this causes errors.
        max_output_tokens=8192 
    )
)

# Example of how to test the tool function directly (for development)
async def _test_tool():
    print("Testing find_jobs_on_simplyhired tool directly...")
    # Test case 1: Software Engineer in US, 1 page
    # jobs = await find_jobs_on_simplyhired(job_role="Software Engineer", location="United States", max_pages=1)
    # Test case 2: Data Analyst in Remote, 2 pages
    jobs = await find_jobs_on_simplyhired(job_role="Data Analyst", location="Remote", max_pages=2)
    if jobs and (not isinstance(jobs, list) or not jobs[0].get("error")):
        print(f"\nFound {len(jobs)} jobs:")
        for i, job in enumerate(jobs):
            print(f"  Job #{i+1}:")
            print(f"    Title: {job.get('title', 'N/A')}")
            print(f"    Company: {job.get('company', 'N/A')}")
            print(f"    Location: {job.get('location', 'N/A')}")
            print(f"    URL: {job.get('url', 'N/A')}")
            print(f"    Page Scraped: {job.get('page_scraped', 'N/A')}")
            print("    ---")
    elif jobs and isinstance(jobs, list) and jobs[0].get("error"):
        print(f"\nError during scraping: {jobs[0]['error']} - {jobs[0].get('details', '')}")
    else:
        print("\nNo jobs found or an issue occurred.")

if __name__ == '__main__':
    # To run the test: python -m adk-backend.agent 
    # Make sure your .env is in the adk-backend folder or your GOOGLE_API_KEY is globally available
    # Also ensure Playwright browsers are installed: playwright install
    # print("Running test from if __name__ == '__main__'")
    # asyncio.run(_test_tool())
    pass