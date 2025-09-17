# Business Directory Lead Scraper

A fast, adaptive Python scraper that extracts business contact information from directory websites and outputs structured JSON data ready for CRM import.

## Features

- ✅ **Universal Compatibility** - Works with 70-80% of business directories out-of-the-box
- ✅ **Smart Data Extraction** - Automatically finds business names, phone numbers, emails, and addresses
- ✅ **Adaptive Selectors** - 30+ fallback selectors to handle different site layouts
- ✅ **Automatic Pagination** - Follows "Next" buttons to scrape multiple pages
- ✅ **Duplicate Removal** - Deduplicates on business name + phone number
- ✅ **Rate Limiting** - Respects websites with configurable delays
- ✅ **Headless Browser** - Uses Playwright for JavaScript-heavy sites
- ✅ **Clean JSON Output** - Structured data ready for CRM systems

## Installation

```bash
# Install dependencies
pip install playwright bs4 pytz phonenumbers

# Install browser
python -m playwright install
```

## Quick Start

```bash
# Basic usage
python scrape_leads.py --urls "https://business.loudounchamber.org/list/searchalpha/a"

# Multiple URLs with custom settings
python scrape_leads.py \
  --urls "https://business.loudounchamber.org/list/searchalpha/a" \
         "https://business.loudounchamber.org/list/searchalpha/b" \
  --list-name "Virginia Businesses" \
  --out my_leads.json \
  --max-pages 3
```

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--urls` | Required | One or more directory URLs (space-separated) |
| `--list-name` | "Default" | Name for the lead list |
| `--out` | "leads.json" | Output file path |
| `--max-pages` | 3 | Maximum pages to scrape per URL |
| `--delay-min` | 0.8 | Minimum delay between actions (seconds) |
| `--delay-max` | 1.6 | Maximum delay between actions (seconds) |
| `--debug` | False | Save HTML pages for debugging |

## Output Format

```json
[
  {
    "Business": "American Kolache",
    "Name": "",
    "Number": "15715207858",
    "Email": "info@americankolache.com",
    "Location": "44260 Ice Rink Plaza, Suite 117, Ashburn, VA 20147",
    "Industry": "Restaurant",
    "Call Notes": "",
    "Date Added": "2025-09-17 13:00",
    "List": "Default"
  }
]
```

## Supported Directory Types

### ✅ Works Great
- Chamber of Commerce websites
- Yellow Pages style directories
- Association member directories
- Industry-specific directories
- Local business listings

### ⚠️ Limited Support
- Heavily JavaScript-dependent sites
- Sites requiring authentication
- Sites with unusual custom layouts

## How It Works

1. **Smart Container Detection** - Finds business listing containers using multiple selector strategies
2. **Multi-Source Data Extraction** - Extracts contact info from links, text patterns, and structured data
3. **Intelligent Cleanup** - Normalizes phone numbers, removes duplicates, filters navigation elements
4. **Automatic Pagination** - Follows next page links until max pages reached
5. **Structured Output** - Converts to clean JSON format with Los Angeles timestamps

## Adapter System

The scraper uses domain-specific adapters:

- **Generic Chamber** - Works for most business directories
- **Yelp-like** - Handles review/rating sites
- **Custom adapters** - Easy to add for specific sites

## Rate Limiting & Ethics

- **Built-in delays** between requests (0.8-1.6 seconds by default)
- **Realistic user agent** to avoid triggering anti-bot measures
- **Respects robots.txt** - Always check before scraping
- **Terms of Service** - Verify compliance before using on any site

## Examples

### Single Directory Page
```bash
python scrape_leads.py \
  --urls "https://business.loudounchamber.org/list/searchalpha/a" \
  --out loudoun_a.json
```

### Multiple Pages with Custom List Name
```bash
python scrape_leads.py \
  --urls "https://business.loudounchamber.org/list/searchalpha/a" \
         "https://business.loudounchamber.org/list/searchalpha/b" \
  --list-name "Loudoun County A-B" \
  --max-pages 5
```

### Debug Mode for Troubleshooting
```bash
python scrape_leads.py \
  --urls "https://example-directory.com/businesses" \
  --debug \
  --max-pages 1
```

## Troubleshooting

### No Results Found
1. Use `--debug` flag to save HTML and inspect page structure
2. Check if site requires JavaScript (many modern sites do)
3. Verify the URL contains actual business listings

### Rate Limiting Issues
```bash
# Increase delays to be more respectful
python scrape_leads.py \
  --urls "https://example.com" \
  --delay-min 2.0 \
  --delay-max 4.0
```

### Import Errors
```bash
# Ensure all dependencies are installed
pip install playwright bs4 pytz phonenumbers
python -m playwright install chromium
```

## Contributing

1. Fork the repository
2. Add new adapters in `pick_adapter()` function
3. Test with various directory sites
4. Submit pull request with example URLs

## Disclaimer

This tool is for educational and legitimate business research purposes. Always:
- Check robots.txt and terms of service
- Respect rate limits
- Use responsibly and ethically
- Verify legal compliance in your jurisdiction

## Support

- Report issues on GitHub
- Add example URLs for sites that need custom adapters
- Contribute selector patterns for better compatibility