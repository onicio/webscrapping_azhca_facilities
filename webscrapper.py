from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import re
import time
import csv

def extract_emails(text):
    """Extract email addresses from text using regex"""
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return list(set(re.findall(email_pattern, text)))

def extract_phones(text):
    """Extract phone numbers from text"""
    phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
    return list(set(re.findall(phone_pattern, text)))

def setup_driver():
    """Setup Chrome driver with options"""
    options = Options()
    options.add_argument('--headless')  # Run in background
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    try:
        driver = webdriver.Chrome(options=options)
        return driver
    except Exception as e:
        print(f"Error setting up Chrome driver: {e}")
        print("\nPlease install ChromeDriver:")
        print("  brew install chromedriver")
        print("\nOr download from: https://chromedriver.chromium.org/")
        return None

def get_city_links(driver, base_url):
    """Get all city links from the main page"""
    try:
        print("Loading main page...")
        driver.get(base_url)
        
        # Wait for page to load
        time.sleep(3)
        
        # Find all city links
        city_elements = driver.find_elements(By.XPATH, "//a[contains(@href, 'directory_search=1') and contains(@href, 'ill_directory_city=')]")
        
        cities = []
        for element in city_elements:
            try:
                city_name = element.text.strip()
                city_url = element.get_attribute('href')
                if city_name and city_url and city_url not in [c['url'] for c in cities]:
                    cities.append({
                        'name': city_name,
                        'url': city_url
                    })
            except:
                continue
        
        return cities
    except Exception as e:
        print(f"Error getting cities: {e}")
        return []

def scrape_city_page(driver, city_name, city_url):
    """Scrape email addresses from a city's results page"""
    try:
        print(f"  Loading {city_name} results page...")
        driver.get(city_url)
        
        # Wait for content to load
        time.sleep(3)
        
        # Get all page text
        page_text = driver.find_element(By.TAG_NAME, 'body').text
        
        # Extract emails
        emails = extract_emails(page_text)
        phones = extract_phones(page_text)
        
        # Try to find facility names and associate with emails
        results = []
        
        # Look for facility entries
        try:
            facility_elements = driver.find_elements(By.XPATH, "//a[contains(@href, '/facility-finder/') and not(contains(@href, '?'))]")
            
            facility_names = []
            for element in facility_elements:
                try:
                    name = element.text.strip()
                    if name and len(name) > 3:  # Avoid empty or very short text
                        facility_names.append(name)
                except:
                    continue
            
            # If we have emails and facilities, try to match them
            if emails:
                if facility_names:
                    # Create entries for each email found
                    for email in emails:
                        results.append({
                            'city': city_name,
                            'email': email,
                            'facilities': ', '.join(facility_names[:3]) if len(facility_names) > 3 else ', '.join(facility_names),
                            'url': city_url
                        })
                else:
                    # No facility names found, just save the emails
                    for email in emails:
                        results.append({
                            'city': city_name,
                            'email': email,
                            'facilities': 'See city results',
                            'url': city_url
                        })
        except:
            # If anything fails, just save the emails we found
            for email in emails:
                results.append({
                    'city': city_name,
                    'email': email,
                    'facilities': 'See city results',
                    'url': city_url
                })
        
        print(f"    Found {len(emails)} email(s), {len(phones)} phone(s)")
        return results, emails, phones
        
    except Exception as e:
        print(f"  Error scraping {city_name}: {e}")
        return [], [], []

def main():
    base_url = "https://www.azhca.org/facility-finder/"
    
    print("AZHCA Facility Email Scraper (Selenium)")
    print("=" * 50)
    
    # Setup driver
    driver = setup_driver()
    if not driver:
        return
    
    try:
        # Get all city links
        print(f"\nFetching city list from {base_url}")
        cities = get_city_links(driver, base_url)
        
        if not cities:
            print("\nNo cities found. The page structure may have changed.")
            print("Saving page source for debugging...")
            with open('debug_page_source.html', 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            print("Saved to debug_page_source.html")
            return
        
        print(f"Found {len(cities)} cities\n")
        
        # Store all results
        all_results = []
        all_emails_set = set()
        all_phones_set = set()
        
        # Process each city
        for i, city in enumerate(cities, 1):
            print(f"[{i}/{len(cities)}] Processing: {city['name']}")
            results, emails, phones = scrape_city_page(driver, city['name'], city['url'])
            
            all_results.extend(results)
            all_emails_set.update(emails)
            all_phones_set.update(phones)
            
            # Be polite - wait between requests
            time.sleep(2)
        
        # Save to CSV
        if all_results:
            with open('facility_emails.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['City', 'Email', 'Facilities', 'URL'])
                
                for result in all_results:
                    writer.writerow([
                        result['city'],
                        result['email'],
                        result['facilities'],
                        result['url']
                    ])
            
            print("\n" + "=" * 50)
            print("✓ Scraping complete!")
            print(f"✓ Total unique emails: {len(all_emails_set)}")
            print(f"✓ Total unique phones: {len(all_phones_set)}")
            print(f"✓ Processed {len(cities)} cities")
            print(f"✓ Results saved to 'facility_emails.csv'")
            
            # Summary by city
            print("\n--- Summary by City ---")
            city_counts = {}
            for result in all_results:
                city_counts[result['city']] = city_counts.get(result['city'], 0) + 1
            
            for city, count in sorted(city_counts.items()):
                print(f"{city}: {count} email(s)")
            
            # Show sample emails
            print("\n--- Sample Emails Found ---")
            for email in list(all_emails_set)[:10]:
                print(f"  • {email}")
            
        else:
            print("\nNo emails found on any pages")
    
    finally:
        driver.quit()
        print("\nBrowser closed")

if __name__ == "__main__":
    main()