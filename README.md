# AliExpress Product Scraper

A powerful command-line tool for scraping product data from AliExpress using their unofficial API.

![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)

## Features

- 🖥️ **Command-Line Interface**: Simple and efficient CLI for batch processing and automation
- 🚀 **API-Based Scraping**: Fast and efficient data collection using AliExpress's unofficial API
- 🔒 **Smart Session Management**: Uses browser automation only for initial cookie collection
- ⚡ **Multi-Query Parallel Scraping**: Process multiple search queries simultaneously across all CPU cores
- 🛡️ **Anti-Block Protection**:
  - Configurable delay between requests (0.2-10 seconds)
  - Sequential request processing to avoid overwhelming the server
  - Session caching to minimize browser automation
- 🌎 **Optional Proxy Support**: Oxylabs proxy integration for enhanced reliability
- 🧠 **Intelligent Store Retry**: Automatic retry mechanism for missing store information
- 🏪 **Enhanced Store Data**: Advanced store information extraction with fallback strategies
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
   - **Store Information**: Seller/store fields are set to null by default for faster processing (focuses on product listing data only)

## Project Structure

The AliExpress scraper is organized into a modular architecture with clear separation of concerns:

```text
aliexpress_scraper/
├── core/                    # Core scraping functionality
│   ├── scraper.py          # Basic API-based scraper implementation
│   └── captcha_solver.py   # Captcha detection and solving utilities
├── scrapers/               # Enhanced scraping implementations
│   └── enhanced_scraper.py # Advanced scraper with retry logic
├── store/                  # Store information extraction modules
│   ├── scraper_interface.py      # Abstract base classes and interfaces
│   ├── store_integration.py      # Main store scraper integration layer
│   ├── mcp_store_scraper.py      # MCP Playwright-based store scraper
│   └── traditional_store_scraper.py # Standard Playwright store scraper
├── utils/                  # Utility modules and helpers
│   ├── standalone_store_retry.py # Store retry logic and batch processing
│   └── transform_to_listing.py   # Data transformation utilities
└── cli.py                  # Command-line interface router
main.py                     # Main entry point
```

### Core Modules (`core/`)

#### `scraper.py`

The foundational scraping module that provides the basic functionality:

- **API Integration**: Direct communication with AliExpress's unofficial API
- **Session Management**: Handles browser automation for initial cookie collection
- **Request Processing**: Sequential API calls with configurable delays
- **Data Extraction**: Parses product information from API responses
- **Pagination Handling**: Manages multi-page scraping operations
- **Caching System**: 30-minute session cache to minimize browser usage

**Key Functions:**

- `scrape_aliexpress_data()`: Main scraping orchestrator
- `initialize_session_data()`: Browser-based cookie collection
- `extract_product_details()`: API response parsing
- `extract_store_information()`: Basic store data extraction

#### `captcha_solver.py`

Specialized captcha detection and solving capabilities:

- **Browser Automation**: Playwright-based captcha detection
- **Interactive Solving**: Support for manual captcha resolution
- **Session Integration**: Seamless integration with main scraper
- **Proxy Support**: Works with proxy providers for enhanced reliability
- **Stealth Mode**: Anti-detection measures and browser fingerprinting evasion

**Key Classes:**

- `AliExpressCaptchaSolver`: Main captcha solving implementation
- `CaptchaSolverIntegration`: High-level integration interface

### Enhanced Scrapers (`scrapers/`)

#### `enhanced_scraper.py`

Advanced scraper with comprehensive retry and error handling:

- **Intelligent Retry**: Automatic retry for failed store information extraction
- **Batch Processing**: Configurable batch sizes for efficient processing
- **Error Recovery**: Graceful handling of network errors and timeouts
- **Store Integration**: Deep integration with store scraping modules
- **Progress Tracking**: Real-time logging and status updates
- **Result Validation**: Data completeness checking and verification

**Key Features:**

- Product URL retry mechanism for missing store data
- Configurable retry batch sizes and delays
- Automatic fallback between scraping methods
- Comprehensive logging and error reporting
- Results merging and deduplication

### Store Information System (`store/`)

#### `scraper_interface.py`

Abstract base classes and interfaces that define the store scraping architecture:

- **Interface Definitions**: Abstract base classes for store scrapers
- **Data Models**: `StoreInfo` class for standardized store data
- **Method Registry**: Enumeration of available scraping methods
- **Factory Pattern**: `StoreScraperFactory` for scraper instantiation
- **Fallback Chain**: `FallbackStoreScraperManager` for method chaining

**Key Components:**

- `StoreScraperInterface`: Base interface for all store scrapers
- `StoreInfo`: Data class for store information
- `StoreScrapingMethod`: Enumeration of scraping strategies
- `StoreScraperFactory`: Factory for creating scraper instances

#### `store_integration.py`

Main integration layer that orchestrates store information extraction:

- **Unified Interface**: Single entry point for all store scraping operations
- **Method Coordination**: Manages multiple scraping strategies
- **Proxy Management**: Handles proxy configuration and rotation
- **Performance Optimization**: Concurrent processing with rate limiting
- **Legacy Compatibility**: Maintains compatibility with existing data formats

**Integration Features:**

- Automatic scraper selection based on environment
- Seamless fallback between MCP and traditional scrapers
- Batch processing with configurable concurrency limits
- Results formatting and standardization

#### `mcp_store_scraper.py`

VS Code MCP (Model Context Protocol) optimized store scraper:

- **MCP Integration**: Uses VS Code's MCP browser functions
- **Optimized Performance**: Leverages existing browser instances
- **Memory Efficiency**: Shared resources with VS Code environment
- **Enhanced Reliability**: Benefits from VS Code's stability
- **Developer Experience**: Integrated debugging and monitoring

**MCP Features:**

- Direct integration with VS Code's browser automation
- Shared browser context for reduced overhead
- Enhanced error reporting and debugging
- Seamless development workflow integration

#### `traditional_store_scraper.py`

Universal Playwright-based store scraper for any Python environment:

- **Environment Agnostic**: Works in any Python environment
- **Full Playwright Features**: Complete access to Playwright capabilities
- **Independent Operation**: No external dependencies beyond Playwright
- **Comprehensive Coverage**: Handles all types of store pages
- **Error Resilience**: Robust error handling and recovery

**Traditional Features:**

- Standalone Playwright browser management
- Complete DOM manipulation capabilities
- Screenshot and debugging support
- Custom browser configuration options

### Utilities (`utils/`)

#### `standalone_store_retry.py`

Comprehensive retry system for store information extraction:

- **Batch Processing**: Intelligent batching of retry operations
- **Progress Analytics**: Detailed statistics on retry success rates
- **Method Testing**: Individual scraper method testing and validation
- **Performance Monitoring**: Bandwidth and timing statistics
- **Interactive Mode**: Manual intervention support for complex cases

**Retry Features:**

- Configurable retry strategies and delays
- Comprehensive failure analysis and reporting
- Support for different scraping method combinations
- Real-time progress tracking and statistics

#### `transform_to_listing.py`

Data transformation utilities for standardizing scraper output:

- **Schema Mapping**: Converts AliExpress data to standard Listing format
- **Data Validation**: Ensures data completeness and format correctness
- **Format Support**: Handles both JSON and CSV input/output formats
- **UUID Generation**: Creates unique identifiers for each listing
- **Price Processing**: Standardizes pricing information and currency handling

**Transformation Features:**

- Flexible input format detection
- Comprehensive data cleaning and validation
- Price history generation from current pricing data
- Image URL array formatting
- Timestamp generation for tracking

### Command-Line Interface (`cli.py`)

Unified command-line router that provides access to all scraping functionality:

- **Subcommand Architecture**: Organized command structure with intuitive navigation
- **Parameter Validation**: Comprehensive argument validation and error handling
- **Help System**: Detailed help documentation for all commands and options
- **Configuration Management**: Environment variable and config file support
- **Integration Layer**: Seamless integration with all scraper modules

**CLI Structure:**

- `scrape basic`: Access to core scraper functionality
- `scrape enhanced`: Enhanced scraper with retry capabilities  
- `transform`: Data transformation operations
- `store-retry`: Standalone store information retry operations

### Main Entry Point (`main.py`)

Simple entry point that routes all operations through the CLI system:

- **Single Interface**: Unified access point for all functionality
- **Error Handling**: Top-level error catching and user-friendly messages
- **Documentation**: Built-in help and usage examples
- **Environment Setup**: Automatic environment detection and configuration

This modular architecture provides:

- **Separation of Concerns**: Each module has a clear, focused responsibility
- **Extensibility**: Easy to add new scrapers or data sources
- **Maintainability**: Clean interfaces make testing and debugging straightforward
- **Flexibility**: Mix and match components based on specific needs
- **Scalability**: Architecture supports both simple and complex use cases

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

### Unified CLI Interface

The project provides a unified command-line interface through `main.py` that gives access to all scraping functionality:

```bash
# View all available commands
python main.py --help

# Basic scraping
python main.py scrape basic --keyword "gaming mouse" --brand "Logitech" --pages 3

# Enhanced scraping with captcha solving and store retry
python main.py scrape enhanced --keyword "mechanical keyboard" --brand "Razer" --enable-store-retry

# Transform scraper results to listing format
python main.py transform results/aliexpress_gaming_mouse_20250808_1754597039.json

# Retry missing store information
python main.py store-retry results/aliexpress_data.json --batch-size 10
```

### Enhanced Scraper with Auto-Retry

The enhanced scraper provides intelligent retry capabilities for missing store information:

```bash
# Enhanced scraper with automatic store retry
python main.py scrape enhanced --keyword "gaming mouse" --brand "Logitech" --enable-store-retry
```

```bash
# Configure retry settings
python main.py scrape enhanced --keyword "bluetooth headphones" --brand "Sony" --enable-store-retry --store-retry-batch-size 10 --store-retry-delay 2.0
```

```bash
# Use proxy with enhanced scraper for best results
python main.py scrape enhanced --keyword "mechanical keyboard" --brand "Razer" --proxy-provider oxylabs --enable-store-retry
```

### Basic Scraping Usage

```bash
python main.py scrape basic --keyword "gaming mouse" --brand "Logitech"
```

### Advanced Scraping Options

```bash
# Scrape multiple pages with filters
python main.py scrape basic --keyword "bluetooth headphones" --brand "Sony" --pages 5 --discount --free-shipping

# Use proxy for enhanced reliability
python main.py scrape basic --keyword "mechanical keyboard" --brand "Razer" --pages 3 --proxy-provider oxylabs

# Extract specific fields only
python main.py scrape basic --keyword "laptop stand" --brand "Generic" --fields "Product ID" "Title" "Sale Price" "Brand"

# Apply price filters
python main.py scrape basic --keyword "phone case" --brand "Spigen" --min-price 10 --max-price 50
```

### Multi-Query Parallel Scraping ⚡

The multi-query feature allows you to process multiple search queries simultaneously, utilizing all available CPU cores for maximum efficiency.

#### Setup Query File

Create a text file with one search query per line:

```bash
# Create queries/instyler.txt
cat > queries/instyler.txt << EOF
instyler
instyler rotating iron
instyler hair dryer
instyler styling iron
instyler styling brush
instyler dryer
instyler accessories
instyler 7x
EOF
```

#### Run Multi-Query Scraping

```bash
# Basic multi-query scraping
python main.py scrape multi \
  --queries-dir queries/instyler.txt \
  --brand "InStyler" \
  --scraper-type basic \
  --pages 2

# Enhanced multi-query scraping (recommended for better success rate)
python main.py scrape multi \
  --queries-dir queries/instyler.txt \
  --brand "InStyler" \
  --scraper-type enhanced \
  --max-pages 3 \
  --enable-store-retry

# With custom worker count and output prefix
python main.py scrape multi \
  --queries-dir queries/gaming_products.txt \
  --brand "Gaming" \
  --scraper-type enhanced \
  --max-workers 4 \
  --output-prefix "gaming_products" \
  --max-pages 2
```

#### Multi-Query Features

- **Parallel Processing**: Uses all CPU cores by default (configurable with `--max-workers`)
- **Individual Output Files**: Each query generates its own JSON file:
  - Format: `{output_prefix}_{clean_query}_{timestamp}.json`
  - Example: `aliexpress_instyler_rotating_iron_20250808_175459123.json`
- **Automatic Result Merging**: Combines all individual JSON results into a single CSV file
- **Progress Tracking**: Real-time progress updates for each query
- **Error Resilience**: Continues processing even if individual queries fail
- **Comprehensive Summary**: Shows success/failure statistics and total execution time

#### Example Multi-Query Results

```bash
📋 Found 8 queries to process
🔧 Scraper type: enhanced  
⚙️ Using 8 parallel workers

✅ Completed scraping for query: 'instyler' -> aliexpress_instyler_20250808_175459123.json
✅ Completed scraping for query: 'instyler rotating iron' -> aliexpress_instyler_rotating_iron_20250808_175501456.json
✅ Completed scraping for query: 'instyler hair dryer' -> aliexpress_instyler_hair_dryer_20250808_175503789.json

📈 Scraping Summary:
   ✅ Successful: 8
   ❌ Failed: 0  
   ⏱️ Total time: 245.67 seconds

🔄 Merging 8 result files...
📄 Merged results saved to: results/aliexpress_merged_20250808_175505012.csv
📊 Total records: 1,247
🎉 Final merged results: results/aliexpress_merged_20250808_175505012.csv
```

### Legacy Direct Module Usage

For backward compatibility, you can still run the modules directly:

```bash
# Enhanced scraper with store retry
python enhanced_scraper.py --keyword "bluetooth headphones" --brand "Sony" --enable-store-retry --store-retry-batch-size 10 --store-retry-delay 2.0

# Basic scraper
python scraper.py --keyword "gaming mouse" --brand "Logitech"

# Transform data
python transform_to_listing.py results/aliexpress_gaming_mouse_20250808_1754597039.json

# Store retry utility
python standalone_store_retry.py results/aliexpress_data.json --batch-size 10
```

### Command-Line Options

#### Unified CLI (`main.py`)

The main CLI provides organized access to all functionality:

```text
Available operations:
  scrape              Scraping operations (basic/enhanced)
  transform           Transform scraper results to Listing format  
  store-retry         Retry missing store information

Basic scraping options:
  --keyword, -k       Product keyword to search for
  --brand, -b         Brand name to associate with products
  --pages, -p         Number of pages to scrape (default: 1, max: 60)
  --discount, -d      Apply 'Big Sale' discount filter
  --free-shipping, -f Apply 'Free Shipping' filter
  --min-price         Minimum price filter
  --max-price         Maximum price filter
  --proxy-provider    Proxy provider: oxylabs, massive (default: None)

Enhanced scraping options:
  --enable-store-retry           Enable automatic store retry
  --store-retry-batch-size       Batch size for retry operations (default: 5)
  --store-retry-delay           Delay between retry batches (default: 2.0)
  --disable-captcha-solver      Disable automatic captcha solving
  --captcha-solver-visible      Run captcha solver in visible mode
```

#### Legacy Direct Module Options

For backward compatibility when running modules directly, the original module-specific options are still available. See the individual module help for details:

```bash
python enhanced_scraper.py --help
python scraper.py --help
python transform_to_listing.py --help
```

### Examples

#### Unified CLI Examples

```bash
# Basic scraping
python main.py scrape basic --keyword "lego batman" --brand "LEGO" --pages 3

# Enhanced scraper with store retry
python main.py scrape enhanced --keyword "gaming mouse" --brand "Razer" --pages 5 --enable-store-retry --proxy-provider oxylabs

# Configure retry behavior
python main.py scrape enhanced --keyword "bluetooth headphones" --brand "Sony" --enable-store-retry --store-retry-batch-size 8 --store-retry-delay 1.5

# Data transformation
python main.py transform results/aliexpress_gaming_mouse_20250808_1754597039.json --category "Electronics" --output-format csv

# Store retry for existing data
python main.py store-retry results/aliexpress_data.json --batch-size 10 --proxy-provider oxylabs
```

#### Legacy Module Examples

```bash
# Enhanced scraper with proxy and filters
python enhanced_scraper.py --keyword "gaming mouse" --brand "Razer" --pages 5 --discount --free-shipping --proxy-provider oxylabs

# Price range filtering with basic scraper
python scraper.py --keyword "bluetooth headphones" --brand "Sony" --pages 2 --min-price 20 --max-price 100

# Transform existing data
python transform_to_listing.py results/aliexpress_gaming_mouse_20250808_1754597039.json -o listings.csv -f csv
```

### Output Files

Results will be saved in the `results` folder with the following naming format (no Unix timestamp):

- `aliexpress_<brand>_<date>.json`
- `aliexpress_<brand>_<date>.csv`

For example:

- `aliexpress_logitech_20250808.json`
- `aliexpress_logitech_20250808.csv`

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
python transform_to_listing.py results/aliexpress_gaming_mouse_20250808_1754597039.json

# Transform CSV results
python transform_to_listing.py results/aliexpress_gaming_mouse_20250808_1754597039.csv

# Specify output format and filename
python transform_to_listing.py results/aliexpress_gaming_mouse_20250808_1754597039.json -o transformed_data.csv -f csv
python transform_to_listing.py results/aliexpress_gaming_mouse_20250808_1754597039.json -o transformed_data.json -f json
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
- Store Name (**set to null** - store extraction disabled for faster processing)
- Store ID (**set to null** - store extraction disabled for faster processing)
- Store URL (**set to null** - store extraction disabled for faster processing)
- Product URL
- Image URL
- Brand (user-specified)

## Best Practices

1. **Choosing the Right Scraper**:
   - Use `scraper.py` for basic, fast scraping focused on product information
   - Use `enhanced_scraper.py` for advanced features and error handling
   - Both scrapers now focus on listing data only (store fields set to null)

2. **Performance Optimization**:
   - Store information extraction is disabled for faster processing
   - Scraper focuses on product listing data only
   - No individual product page visits required for store information

3. **Request Delay**:
   - Default: 1 second between requests
   - Lower values (0.2-0.5s) may work but risk temporary IP blocks
   - Adjust based on your needs and risk tolerance

4. **Page Count**:
   - Maximum: 60 pages per search
   - Recommended: Start with fewer pages to test
   - Use filters to get more relevant results

5. **Proxy Usage**:
   - Optional for basic listing scraping
   - Required credentials in `.env` file when using `--proxy-provider`
   - Helps avoid rate limiting and IP blocks

6. **Session Management**:
   - Session data is cached for 30 minutes
   - Clear browser cookies if you encounter issues
   - Let the automated browser handle cookie collection

7. **Field Selection**:
   - Use `--fields` to extract only needed data for faster processing
   - Omit `--fields` to get all available fields
   - Store fields require proxy provider to be populated

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This tool is for educational purposes only. Use responsibly and in accordance with AliExpress's terms of service.
