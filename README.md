# AliExpress Product Scraper

A powerful command-line tool for scraping product data from AliExpress using their unofficial API.

![MIT License](https://img.shields.io/badge/License-MIT-green.svg)
![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)

## Features

- 🖥️ **Command-Line Interface**: Simple and efficient CLI for batch processing and automation
- 🚀 **API-Based Scraping**: Fast and efficient data collection using AliExpress's unofficial API
- 🔒 **Smart Session Management**: Uses browser automation only for initial cookie collection
- 🛡️ **Anti-Block Protection**:
  - Configurable delay between requests (0.2-10 seconds)
  - Sequential request processing to avoid overwhelming the server
  - Session caching to minimize browser automation
- 🌐 **Optional Proxy Support**: Oxylabs proxy integration for enhanced reliability
- � **Intelligent Store Retry**: Automatic retry mechanism for missing store information
- 🏪 **Enhanced Store Data**: Advanced store information extraction with fallback strategies
- �📊 **Flexible Data Export**:
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

### Enhanced Scraper with Auto-Retry

The project includes an enhanced scraper (`enhanced_scraper.py`) with intelligent retry capabilities for missing store information:

```bash
# Enhanced scraper with automatic store retry
python enhanced_scraper.py --keyword "gaming mouse" --brand "Logitech" --enable-store-retry

# Configure retry settings
python enhanced_scraper.py --keyword "bluetooth headphones" --brand "Sony" --enable-store-retry --store-retry-batch-size 10 --store-retry-delay 2.0

# Use proxy with enhanced scraper for best results
python enhanced_scraper.py --keyword "mechanical keyboard" --brand "Razer" --proxy-provider oxylabs --enable-store-retry
```

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

#### Standard Scraper (`scraper.py`)

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

#### Enhanced Scraper (`enhanced_scraper.py`)

```text
All standard scraper options plus:

Store Retry Options:
  --enable-store-retry        Enable automatic retry for missing store information
  --store-retry-batch-size    Batch size for store retry processing (default: 5)
  --store-retry-delay         Delay between retry batches in seconds (default: 1.0)

Captcha Handling:
  --enable-captcha-solver     Enable automatic captcha solving (experimental)
  --captcha-service          Captcha solving service to use (default: 2captcha)
```

### Examples

```bash
# Basic scraping
python scraper.py --keyword "lego batman" --brand "LEGO" --pages 3

# Enhanced scraper with store retry
python enhanced_scraper.py --keyword "gaming mouse" --brand "Razer" --pages 5 --enable-store-retry --proxy-provider oxylabs

# Configure retry behavior
python enhanced_scraper.py --keyword "bluetooth headphones" --brand "Sony" --enable-store-retry --store-retry-batch-size 8 --store-retry-delay 1.5

# With proxy and filters
python scraper.py --keyword "gaming mouse" --brand "Razer" --pages 5 --discount --free-shipping --proxy-provider oxylabs

# Price range filtering
python scraper.py --keyword "bluetooth headphones" --brand "Sony" --pages 2 --min-price 20 --max-price 100
```

Results will be saved in the `results` folder as:

- `aliexpress_[keyword]_extracted.json`
- `aliexpress_[keyword]_extracted.csv`

## Store Information Extraction

The scraper includes advanced store information extraction capabilities:

### Store Scraper Architecture

- **Dependency Injection Framework**: Flexible architecture supporting multiple scraper implementations
- **MCP Playwright Integration**: VS Code optimized scraper using MCP browser functions
- **Traditional Playwright Support**: Universal scraper for any Python environment
- **Automatic Fallback**: Intelligent fallback between scraping methods
- **Batch Processing**: Efficient concurrent processing with configurable limits

### Store Retry System

When `--enable-store-retry` is used, the enhanced scraper will:

1. **Analyze Results**: Identify products with missing store information
2. **Batch Retry**: Process failed URLs in configurable batches
3. **Silent Operation**: Retry happens in background without interrupting main scraping
4. **Update Results**: Seamlessly merge retry results back into the dataset
5. **Metadata Tracking**: Add retry information for debugging and monitoring

### Store Data Fields

When proxy is configured and store extraction succeeds:

- **Store Name**: Official store name on AliExpress
- **Store ID**: Unique store identifier
- **Store URL**: Direct link to the store page
- **Extraction Method**: Which scraper method was used
- **Retry Information**: Metadata about retry attempts (when applicable)

## Data Transformation

The project includes a transformation utility to convert scraped AliExpress data into a standardized Listing table schema format.

### Transform to Listing Format

Use `transform_to_listing.py` to convert scraper results to a structured format suitable for database import or further processing:

```bash
# Transform JSON results
python transform_to_listing.py results/aliexpress_gaming_mouse_extracted.json

# Transform CSV results
python transform_to_listing.py results/aliexpress_gaming_mouse_extracted.csv

# Specify output format and filename
python transform_to_listing.py results/aliexpress_gaming_mouse_extracted.json -o transformed_data.csv -f csv
python transform_to_listing.py results/aliexpress_gaming_mouse_extracted.json -o transformed_data.json -f json
```

### Transformation Features

- **UUID Generation**: Creates unique identifiers for each listing
- **Price Parsing**: Converts price strings to numeric values
- **Price History**: Generates price history JSON from current prices
- **Image URL Arrays**: Converts single image URLs to JSON arrays
- **Schema Mapping**: Maps AliExpress fields to standardized Listing schema
- **Data Validation**: Filters out incomplete records

### Schema Mapping

The transformation maps AliExpress data to the following Listing table schema:

| Listing Field | AliExpress Source | Notes |
|---------------|-------------------|-------|
| `listing_uuid` | Generated | Unique UUID for each listing |
| `product_title` | Title | Product name |
| `item_number` | Product ID | AliExpress product identifier |
| `price` | Sale Price | Parsed to numeric value |
| `price_history` | Sale Price + Original Price | JSON array with current pricing |
| `units_sold` | Orders Count | Number of orders |
| `currency` | Currency | Price currency |
| `listing_url` | Product URL | Direct link to product |
| `brand_name` | Brand | User-specified brand |
| `product_image_urls` | Image URL | JSON array format |
| `listing_status` | - | Set to "New" |
| `listing_state` | - | Set to "Active" |
| `date_first_detected` | - | Current timestamp |
| `last_checked` | - | Current timestamp |

Other fields are set to appropriate defaults or null values where AliExpress data is not available.

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

1. **Choosing the Right Scraper**:
   - Use `scraper.py` for basic, fast scraping
   - Use `enhanced_scraper.py` for maximum store data completeness
   - Enable `--enable-store-retry` when store information is critical

2. **Store Information Extraction**:
   - Always use proxy provider for best store data results
   - Configure appropriate retry batch sizes (5-10) for balance of speed and reliability
   - Set retry delays (1-2 seconds) to avoid overwhelming servers

3. **Request Delay**:
4. **Request Delay**:
   - Default: 1 second between requests
   - Lower values (0.2-0.5s) may work but risk temporary IP blocks
   - Adjust based on your needs and risk tolerance

5. **Page Count**:
   - Maximum: 60 pages per search
   - Recommended: Start with fewer pages to test
   - Use filters to get more relevant results

6. **Proxy Usage**:
   - Optional but recommended for store information extraction
   - Required credentials in `.env` file when using `--proxy-provider`
   - Helps avoid rate limiting and IP blocks

7. **Session Management**:
   - Session data is cached for 30 minutes
   - Clear browser cookies if you encounter issues
   - Let the automated browser handle cookie collection

8. **Field Selection**:
   - Use `--fields` to extract only needed data for faster processing
   - Omit `--fields` to get all available fields
   - Store fields require proxy provider to be populated

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for educational purposes only. Use responsibly and in accordance with AliExpress's terms of service.
