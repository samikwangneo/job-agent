import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import os
from bs4 import BeautifulSoup # Added for BeautifulSoup

# Requires beautifulsoup4 and lxml to be installed (pip install beautifulsoup4 lxml)

MAX_PAGES_TO_SCRAPE = 10 # Configure how many pages to attempt (user changed)

def parse_html_with_beautifulsoup(html_content, page_number):
    """
    Parses the HTML content of a Simply Hired search results page to extract job postings.
    """
    soup = BeautifulSoup(html_content, 'lxml') # Changed from html.parser to lxml for robustness
    jobs = []
    # Find all job cards. Each job card is a div with data-testid="searchSerpJob"
    job_cards = soup.find_all('div', attrs={'data-testid': 'searchSerpJob'})

    print(f"Page {page_number}: Found {len(job_cards)} job cards using new selectors.")

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

        if title != "N/A": # Only add if a title was found
            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "url": url,
                "page": page_number
            })
    return jobs

async def main():
    role_to_search = input("Enter the job role you are looking for: ")
    default_location = "United States"

    all_extracted_jobs = []
    browser = None

    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=True) # user changed
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )
            page = await context.new_page()

            for page_num in range(1, MAX_PAGES_TO_SCRAPE + 1):
                print(f"\n--- Processing Page {page_num} ---")
                html_content = None
                current_url = ""

                if page_num == 1:
                    search_role_query = role_to_search.replace(" ", "+")
                    search_location_query = default_location.replace(" ", "+")
                    target_url = f"https://www.simplyhired.com/search?q={search_role_query}&l={search_location_query}"
                    print(f"Navigating to initial URL: {target_url}")
                    await page.goto(target_url, timeout=60000)
                    current_url = target_url
                else:
                    next_page_selector = f"[data-testid='paginationBlock{page_num}']"
                    print(f"Attempting to find and click link for page {page_num} using selector: {next_page_selector}")
                    next_page_link = page.locator(next_page_selector)
                    
                    if await next_page_link.count() > 0:
                        await next_page_link.click()
                        print(f"Clicked link for page {page_num}.")
                        await page.wait_for_load_state('domcontentloaded', timeout=30000)
                        await asyncio.sleep(3) 
                        current_url = page.url
                        print(f"Navigated to page {page_num}. Current URL: {current_url}")
                    else:
                        print(f"Could not find link for page {page_num}. Stopping pagination.")
                        break 
                
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
                html_content = await page.content()
                print(f"Successfully retrieved HTML content from {current_url} (length: {len(html_content)} characters).")

                if html_content:
                    # Re-adding HTML saving
                    downloads_dir = "downloads"
                    os.makedirs(downloads_dir, exist_ok=True)
                    output_filename = os.path.join(downloads_dir, f"downloaded_page_{page_num}.html")
                    try:
                        with open(output_filename, "w", encoding="utf-8") as f:
                            f.write(html_content)
                        print(f"HTML content for page {page_num} saved to: {output_filename}")
                    except Exception as e:
                        print(f"  Error saving HTML for page {page_num} to file: {e}")
                    
                    # Existing BeautifulSoup parsing call
                    try:
                        jobs_from_page = parse_html_with_beautifulsoup(html_content, page_num)
                        if jobs_from_page:
                            all_extracted_jobs.extend(jobs_from_page)
                    except Exception as e:
                        print(f"Error processing with BeautifulSoup for page {page_num}: {e}")
                else:
                    print(f"No HTML content was downloaded for page {page_num}, skipping parsing.")
            
        except PlaywrightTimeoutError as pte:
            print(f"A Playwright timeout occurred: {pte}")
        except Exception as e:
            print(f"An unexpected error occurred in the main loop: {e}")
        finally:
            if browser:
                print("\nClosing browser...")
                await browser.close()

    print("\n🍲 Consolidated Extracted Job Postings by BeautifulSoup (All Pages):")
    print("============================================================")
    if all_extracted_jobs:
        for i, job in enumerate(all_extracted_jobs):
            print(f"  Job #{i+1}:")
            print(f"    Title: {job.get('title', 'N/A')}")
            print(f"    Company: {job.get('company', 'N/A')}")
            print(f"    Location: {job.get('location', 'N/A')}")
            print(f"    URL: {job.get('url', 'N/A')}")
            print(f"    Source: {job.get('source', 'N/A')}")
            print("    ---")
    else:
        print("  BeautifulSoup did not find any job postings, or an error occurred during processing.")

if __name__ == "__main__":
    asyncio.run(main()) 