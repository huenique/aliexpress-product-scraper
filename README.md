# AliExpress Product Scraper

A powerful command-line tool for scraping product data from AliExpress using their unofficial API.

![MIT License](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)

## Features

- 🖥️ **Command-Line Interface**: Simple and efficient CLI for batch processing and automation
- 🚀 **API-Based Scraping**: Fast and efficient data collection using AliExpress's unofficial API
- 🔒 **Smart Session Management**: Uses browser automation only for initial cookie collection
- 🛡️ **Anti-Block Protection**:
  - Configurable delay between requests (0.2-10 seconds)
  - Sequential request processing to avoid overwhelming the server
  - Session caching to minimize browser automation
- 🌐 **Optional Proxy Support**: Oxylabs proxy integration for enhanced reliability
- 📊 **Flexible Data Export**:
  - JSON format for full data preservation
  - CSV format for easy spreadsheet import
- 🎯 **Customizable Fields**: Select exactly which product details to extract
- 🔍 **Advanced Filtering**:
  - Price range filtering
  - Discount deals filter
  - Free shipping filter
  - Brand specification
- 📝 **Real-time Progress**: Live logging of the scraping process

## How It Works

1. **Smart Session Handling**:
   - First visit uses a headless browser to collect necessary cookies
   - Subsequent requests use cached session data (30-minute validity)
   - Minimizes the need for browser automation

2. **Efficient API Scraping**:
   - Uses AliExpress's internal API for data collection
   - Faster and more reliable than HTML scraping
   - Reduces the chance of being blocked

3. **Data Processing**:
   - Extracts clean, structured data
   - Handles currency formatting
   - Processes URLs and image links
   - Manages pagination automatically

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/huenique/aliexpress-scraper.git
   cd aliexpress-scraper
   ```

2. Install required packages:

   ```bash
   pip install -r requirements.txt
   ```

   Or if using `uv`:

   ```bash
   uv sync
   ```

## Configuration

### Environment Variables Setup

1. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file and add your Oxylabs proxy credentials:

   ```bash
   # Oxylabs U.S. Residential Proxy Configuration
   OXYLABS_USERNAME=your_oxylabs_username_here
   OXYLABS_PASSWORD=your_oxylabs_password_here
   OXYLABS_ENDPOINT=pr.oxylabs.io:7777
   ```

**Note**: The proxy provider is optional. The scraper can run without proxy, but using Oxylabs proxy enhances reliability and enables store information extraction.

## Usage

### Basic Usage

```bash
python scraper.py --keyword "gaming mouse" --brand "Logitech"
```

### Advanced Usage

```bash
# Scrape multiple pages with filters
python scraper.py --keyword "bluetooth headphones" --brand "Sony" --pages 5 --discount --free-shipping

# Use proxy for enhanced reliability
python scraper.py --keyword "mechanical keyboard" --brand "Razer" --pages 3 --proxy-provider oxylabs

# Extract specific fields only
python scraper.py --keyword "laptop stand" --brand "Generic" --fields "Product ID" "Title" "Sale Price" "Brand"

# Apply price filters
python scraper.py --keyword "phone case" --brand "Spigen" --min-price 10 --max-price 50
```

### Command-Line Options

```text
Required arguments:
  --keyword, -k         Product keyword to search for on AliExpress
  --brand, -b          Brand name to associate with the scraped products

Optional arguments:
  --pages, -p          Number of pages to scrape (default: 1, max: 60)
  --discount, -d       Apply 'Big Sale' discount filter
  --free-shipping, -f  Apply 'Free Shipping' filter
  --min-price         Minimum price filter
  --max-price         Maximum price filter
  --delay             Delay between requests in seconds (default: 1.0)
  --fields            Specific fields to extract (default: all fields)
  --proxy-provider    Proxy provider to use: oxylabs, massive (default: None)
```

### Examples

```bash
# Basic scraping
python scraper.py --keyword "lego batman" --brand "LEGO" --pages 3

# With proxy and filters
python scraper.py --keyword "gaming mouse" --brand "Razer" --pages 5 --discount --free-shipping --proxy-provider oxylabs

# Price range filtering
python scraper.py --keyword "bluetooth headphones" --brand "Sony" --pages 2 --min-price 20 --max-price 100
```

Results will be saved in the `results` folder as:

- `aliexpress_[keyword]_extracted.json`
- `aliexpress_[keyword]_extracted.csv`

## Available Fields

The scraper can extract the following product information:

- Product ID
- Title
- Sale Price
- Original Price
- Discount (%)
- Currency
- Rating
- Orders Count
- Store Name (requires proxy)
- Store ID (requires proxy)
- Store URL (requires proxy)
- Product URL
- Image URL
- Brand (user-specified)

## Best Practices

1. **Request Delay**:
   - Default: 1 second between requests
   - Lower values (0.2-0.5s) may work but risk temporary IP blocks
   - Adjust based on your needs and risk tolerance

2. **Page Count**:
   - Maximum: 60 pages per search
   - Recommended: Start with fewer pages to test
   - Use filters to get more relevant results

3. **Proxy Usage**:
   - Optional but recommended for store information extraction
   - Required credentials in `.env` file when using `--proxy-provider`
   - Helps avoid rate limiting and IP blocks

4. **Session Management**:
   - Session data is cached for 30 minutes
   - Clear browser cookies if you encounter issues
   - Let the automated browser handle cookie collection

5. **Field Selection**:
   - Use `--fields` to extract only needed data for faster processing
   - Omit `--fields` to get all available fields
   - Store fields require proxy provider to be populated

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for educational purposes only. Use responsibly and in accordance with AliExpress's terms of service.
