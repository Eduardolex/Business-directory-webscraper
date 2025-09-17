#!/usr/bin/env python3
"""
Lead Scraper - Extract business directory data to JSON

Requirements:
- pip install playwright bs4 pytz phonenumbers
- python -m playwright install

Usage:
python scrape_leads.py \
  --urls "https://business.loudounchamber.org/list/searchalpha/a" \
         "https://example.com/directory?page=1" \
  --list-name "Ashburn Push" \
  --out leads.json \
  --max-pages 4

Robots/TOS Note: This tool respects rate limiting with delays.
Always check robots.txt and terms of service before scraping.
"""

import argparse
import json
import re
import random
import time
import sys
from datetime import datetime
from typing import List, Dict, Callable, Optional
from urllib.parse import urljoin, urlparse

try:
    import pytz
except ImportError:
    print("Error: pytz not installed. Run: pip install pytz", file=sys.stderr)
    sys.exit(1)

try:
    import phonenumbers
except ImportError:
    print("Error: phonenumbers not installed. Run: pip install phonenumbers", file=sys.stderr)
    sys.exit(1)

try:
    from playwright.sync_api import sync_playwright, Page
except ImportError:
    print("Error: playwright not installed. Run: pip install playwright && python -m playwright install", file=sys.stderr)
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 not installed. Run: pip install beautifulsoup4", file=sys.stderr)
    sys.exit(1)


def now_str_la() -> str:
    """Return current time in America/Los_Angeles timezone as YYYY-MM-DD HH:MM"""
    la_tz = pytz.timezone('America/Los_Angeles')
    now = datetime.now(la_tz)
    return now.strftime('%Y-%m-%d %H:%M')


def norm_phone(raw: str) -> str:
    """Normalize phone number using phonenumbers library, fallback to digits-only"""
    if not raw:
        return ""

    try:
        # Try parsing as US number
        parsed = phonenumbers.parse(raw, "US")
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)[1:]  # Remove +
    except:
        pass

    # Fallback: extract digits only
    digits = re.sub(r'\D', '', raw)
    return digits if len(digits) >= 10 else ""


def schema_row(business: str, name: str = "", number: str = "", email: str = "",
               location: str = "", industry: str = "", call_notes: str = "",
               list_name: str = "Default") -> Dict[str, str]:
    """Create a row matching the exact JSON schema"""
    return {
        "Business": business,
        "Name": name,
        "Number": norm_phone(number),
        "Email": email,
        "Location": location,
        "Industry": industry,
        "Call Notes": call_notes,
        "Date Added": now_str_la(),
        "List": list_name
    }


def scrape_generic_chamber(html: str) -> List[Dict[str, str]]:
    """Scrape generic chamber/directory sites with card-based layouts"""
    soup = BeautifulSoup(html, 'html.parser')
    results = []

    # Card/container selectors - expanded list
    card_selectors = [
        # Common chamber/directory patterns
        'div.mn-listing',
        'div.mn-listing-container',
        'div.gz-member',
        'div.member-item',
        'div.member',
        'div.listing-item',
        'div.business-listing',
        'div.directory-item',
        'li.member',
        'li.listing',
        '.member-card',
        '.business-card',
        '.directory-entry',
        'article',
        'div.listing',
        'div.directory-listing',
        'li.directory-item',
        # Generic containers that might contain business info
        'div[class*="member"]',
        'div[class*="listing"]',
        'div[class*="business"]',
        'div[class*="directory"]',
        'li[class*="member"]',
        'li[class*="listing"]',
        # Fallback to any div with business-like content
        'div:has(a[href*="tel:"]), div:has(.phone), div:has(.email)'
    ]

    cards = []
    used_selector = ""
    for selector in card_selectors:
        try:
            cards = soup.select(selector)
            if cards and len(cards) > 1:  # Need multiple cards for it to be a listing
                used_selector = selector
                print(f"Found {len(cards)} cards using selector: {selector}", file=sys.stderr)
                break
        except Exception as e:
            continue

    if not cards:
        print(f"No cards found with any selector. Trying fallback approach.", file=sys.stderr)
        # Fallback: look for any containers with phone numbers
        phone_containers = soup.select('div:has(a[href^="tel:"]), li:has(a[href^="tel:"])')
        if phone_containers:
            cards = phone_containers
            used_selector = "phone fallback"
            print(f"Using phone fallback: found {len(cards)} containers", file=sys.stderr)
        else:
            # Last resort: look for divs with phone patterns in text
            all_divs = soup.find_all(['div', 'li'])
            phone_pattern = re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
            for div in all_divs:
                if phone_pattern.search(div.get_text()):
                    cards.append(div)
            if cards:
                used_selector = "text phone pattern"
                print(f"Using text pattern fallback: found {len(cards)} containers", file=sys.stderr)

    if not cards:
        print(f"No business listings found on page", file=sys.stderr)
        return results

    for card in cards:
        try:
            # Extract business name - improved selectors
            business = ""
            title_selectors = [
                '.mn-title a',  # Common chamber pattern
                '.mn-title',
                '.gz-title a',
                '.gz-title',
                '.member-name a',
                '.member-name',
                '.business-name a',
                '.business-name',
                '.company-name a',
                '.company-name',
                '.listing-title a',
                '.listing-title',
                '.directory-title a',
                '.directory-title',
                'h1 a', 'h2 a', 'h3 a', 'h4 a',
                'h1', 'h2', 'h3', 'h4',
                'a[href*="/business/"]',
                'a[href*="/member/"]',
                'a[href*="/listing/"]',
                '.title a',
                '.title',
                'strong a',
                'strong',
                'a'  # Last resort
            ]
            for sel in title_selectors:
                title_elem = card.select_one(sel)
                if title_elem:
                    business = title_elem.get_text(strip=True)
                    # Skip generic/header text and clean up
                    if business and len(business) > 3:
                        # Skip navigation/header elements
                        skip_terms = ['Home', 'Search', 'Directory', 'Business Directory Search', 'Find a Business', 'Member Directory']
                        if business not in skip_terms:
                            # Clean up business names with addresses mixed in
                            if len(business) > 50:  # Likely has address mixed in
                                # Try to extract just the business name (usually first line or before address)
                                lines = business.split('\n')
                                if lines:
                                    business = lines[0].strip()
                                # If still too long, try to find business name before address patterns
                                if len(business) > 50:
                                    # Split on common address patterns
                                    parts = re.split(r'\d+\s+[A-Za-z].*?(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Circle|Cir|Lane|Ln)', business)
                                    if parts and len(parts[0].strip()) > 3:
                                        business = parts[0].strip()
                            break
                    business = ""

            # Extract phone
            phone = ""
            phone_selectors = ['a[href^="tel:"]', '.phone', '.listing-phone', '.directory-phone', '.telephone']
            for sel in phone_selectors:
                phone_elem = card.select_one(sel)
                if phone_elem:
                    if phone_elem.get('href', '').startswith('tel:'):
                        phone = phone_elem['href'][4:]
                    else:
                        phone = phone_elem.get_text(strip=True)
                    break

            # Fallback phone regex
            if not phone:
                card_text = card.get_text()
                phone_match = re.search(r'(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', card_text)
                if phone_match:
                    phone = phone_match.group(1)

            # Extract email
            email = ""
            email_selectors = ['a[href^="mailto:"]', '.email', '.listing-email', '.directory-email']
            for sel in email_selectors:
                email_elem = card.select_one(sel)
                if email_elem:
                    if email_elem.get('href', '').startswith('mailto:'):
                        email = email_elem['href'][7:]
                    else:
                        email = email_elem.get_text(strip=True)
                    break

            # Extract address/location
            location = ""
            addr_selectors = ['.address', '.listing-address', '.directory-address', 'address', '.location']
            for sel in addr_selectors:
                addr_elem = card.select_one(sel)
                if addr_elem:
                    location = addr_elem.get_text(strip=True)
                    break

            # Extract category/industry
            industry = ""
            cat_selectors = ['.category', '.categories', '.tags', '.industry', '.business-type']
            for sel in cat_selectors:
                cat_elem = card.select_one(sel)
                if cat_elem:
                    industry = cat_elem.get_text(strip=True)
                    break

            if business:  # Only add if we found a business name
                results.append({
                    'business': business,
                    'phone': phone,
                    'email': email,
                    'location': location,
                    'industry': industry
                })

        except Exception as e:
            print(f"Error processing card: {e}", file=sys.stderr)
            continue

    return results


def scrape_yelp_like(html: str) -> List[Dict[str, str]]:
    """Minimal extraction for Yelp-like sites"""
    soup = BeautifulSoup(html, 'html.parser')
    results = []

    # Yelp-specific selectors
    cards = soup.select('[data-testid="serp-ia-card"], .businessName, .search-result, .biz-listing')

    for card in cards:
        try:
            # Business name
            business = ""
            name_selectors = ['h3 a', 'h4 a', '.business-name a', 'a[href*="/biz/"]']
            for sel in name_selectors:
                name_elem = card.select_one(sel)
                if name_elem:
                    business = name_elem.get_text(strip=True)
                    break

            # Phone (often hidden behind click-to-reveal)
            phone = ""
            phone_elem = card.select_one('[data-testid="phone-number"], .phone-number')
            if phone_elem:
                phone = phone_elem.get_text(strip=True)

            # Location (usually just city/neighborhood)
            location = ""
            loc_elem = card.select_one('.address, [data-testid="address"]')
            if loc_elem:
                location = loc_elem.get_text(strip=True)

            # Category
            industry = ""
            cat_elem = card.select_one('.category, .categories a')
            if cat_elem:
                industry = cat_elem.get_text(strip=True)

            if business:
                results.append({
                    'business': business,
                    'phone': phone,
                    'email': "",  # Rarely available on Yelp
                    'location': location,
                    'industry': industry
                })

        except Exception as e:
            print(f"Error processing Yelp card: {e}", file=sys.stderr)
            continue

    return results


def pick_adapter(url: str) -> Callable[[str], List[Dict[str, str]]]:
    """Select appropriate adapter based on URL domain"""
    domain = urlparse(url).netloc.lower()

    if 'yelp.com' in domain or 'foursquare.com' in domain:
        return scrape_yelp_like
    else:
        # Default to generic chamber for most business directories
        return scrape_generic_chamber


def paginate_and_scrape(page: Page, adapter: Callable, max_pages: int,
                       delay_min: float, delay_max: float, debug: bool = False) -> List[Dict[str, str]]:
    """Navigate through pages and scrape with the given adapter"""
    all_results = []
    pages_scraped = 0

    # Next button selectors in priority order
    next_selectors = [
        'a[rel="next"]',
        'a.next',
        'a.pagination-next',
        'button[aria-label="Next"]',
        'a:has-text("Next")',
        'a:has-text(">")',
        '.pagination .next',
        '.pager .next'
    ]

    while pages_scraped < max_pages:
        try:
            # Wait for page to load
            page.wait_for_load_state('networkidle', timeout=10000)

            # Add random delay
            delay = random.uniform(delay_min, delay_max)
            time.sleep(delay)

            # Get page content and scrape
            html = page.content()

            # Debug: save HTML for inspection
            if debug:
                debug_file = f"debug_page_{pages_scraped + 1}.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(html)
                print(f"Debug: saved HTML to {debug_file}", file=sys.stderr)

            page_results = adapter(html)
            all_results.extend(page_results)

            pages_scraped += 1
            print(f"Scraped page {pages_scraped}: {len(page_results)} items found", file=sys.stderr)

            if pages_scraped >= max_pages:
                break

            # Try to find and click next button
            next_clicked = False
            for selector in next_selectors:
                try:
                    next_btn = page.query_selector(selector)
                    if next_btn and next_btn.is_visible():
                        # Check if it's actually clickable (not disabled)
                        if not next_btn.get_attribute('disabled') and 'disabled' not in (next_btn.get_attribute('class') or ''):
                            next_btn.click()
                            next_clicked = True
                            print(f"Clicked next using selector: {selector}", file=sys.stderr)
                            break
                except Exception as e:
                    continue

            if not next_clicked:
                print(f"No more pages found after {pages_scraped} pages", file=sys.stderr)
                break

        except Exception as e:
            print(f"Error on page {pages_scraped + 1}: {e}", file=sys.stderr)
            break

    return all_results


def run(urls: List[str], list_name: str, out_path: str, delay_min: float,
        delay_max: float, max_pages: int, debug: bool = False) -> None:
    """Main scraping orchestrator"""
    all_leads = []
    seen_leads = set()  # For deduplication on (business.lower(), phone)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )

        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        page = context.new_page()

        for url in urls:
            try:
                print(f"Processing URL: {url}", file=sys.stderr)
                adapter = pick_adapter(url)

                # Navigate to URL
                page.goto(url, timeout=30000)

                # Scrape with pagination
                results = paginate_and_scrape(page, adapter, max_pages, delay_min, delay_max, debug)

                # Convert to schema and deduplicate
                for result in results:
                    business = result.get('business', '').strip()
                    phone = norm_phone(result.get('phone', ''))

                    if not business:
                        continue

                    # Deduplication key
                    dedup_key = (business.lower(), phone)
                    if dedup_key in seen_leads:
                        continue
                    seen_leads.add(dedup_key)

                    lead = schema_row(
                        business=business,
                        name="",  # Usually not available in directory listings
                        number=phone,
                        email=result.get('email', ''),
                        location=result.get('location', ''),
                        industry=result.get('industry', ''),
                        list_name=list_name
                    )
                    all_leads.append(lead)

                print(f"Completed {url}: {len(results)} raw items, {len(all_leads)} total unique leads", file=sys.stderr)

            except Exception as e:
                print(f"Error processing {url}: {e}", file=sys.stderr)
                continue

        browser.close()

    # Write results to JSON
    try:
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(all_leads, f, indent=2, ensure_ascii=False)
        print(f"Successfully wrote {len(all_leads)} leads to {out_path}", file=sys.stderr)
    except Exception as e:
        print(f"Error writing to {out_path}: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """CLI entry point with argument parsing"""
    parser = argparse.ArgumentParser(
        description='Scrape business directories and output leads to JSON',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scrape_leads.py --urls "https://business.loudounchamber.org/list/searchalpha/a"

  python scrape_leads.py \\
    --urls "https://business.loudounchamber.org/list/searchalpha/a" \\
           "https://example.com/directory?page=1" \\
    --list-name "Ashburn Push" \\
    --out leads.json \\
    --max-pages 4

Setup:
  pip install playwright bs4 pytz phonenumbers
  python -m playwright install
        """
    )

    parser.add_argument(
        '--urls',
        nargs='+',
        required=True,
        help='One or more directory URLs to scrape (space-separated)'
    )

    parser.add_argument(
        '--list-name',
        default='Default',
        help='List name for the leads (default: Default)'
    )

    parser.add_argument(
        '--out',
        default='leads.json',
        help='Output file path (default: leads.json)'
    )

    parser.add_argument(
        '--max-pages',
        type=int,
        default=3,
        help='Maximum pages to scrape per URL (default: 3)'
    )

    parser.add_argument(
        '--delay-min',
        type=float,
        default=0.8,
        help='Minimum delay between page actions in seconds (default: 0.8)'
    )

    parser.add_argument(
        '--delay-max',
        type=float,
        default=1.6,
        help='Maximum delay between page actions in seconds (default: 1.6)'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Save HTML pages for debugging (saves to debug_page_N.html)'
    )

    args = parser.parse_args()

    # Validate delays
    if args.delay_min < 0 or args.delay_max < args.delay_min:
        print("Error: Invalid delay values. delay-max must be >= delay-min >= 0", file=sys.stderr)
        sys.exit(1)

    # Run the scraper
    run(
        urls=args.urls,
        list_name=args.list_name,
        out_path=args.out,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
        max_pages=args.max_pages,
        debug=args.debug
    )


if __name__ == '__main__':
    main()