from flask import Flask, render_template, request, Response, stream_with_context
import os
import json

# Define the full ordered list of possible fields (matches scraper.py extraction)
ALL_POSSIBLE_FIELDS = [
    'Product ID', 'Title', 'Sale Price', 'Original Price', 'Discount (%)',
    'Currency', 'Rating', 'Orders Count', 'Store Name', 'Store ID',
    'Store URL', 'Product URL', 'Image URL'
]

# Define essential fields that should always be included
ESSENTIAL_FIELDS = ['Product ID', 'Title', 'Product URL']

# Import your scraper functions
try:
    from scraper import run_scrape_job
except ImportError:
    print("Error: Could not import functions from scraper.py.")
    print("Make sure scraper.py is in the same directory as app.py.")
    exit()

# Initialize the Flask application
app = Flask(__name__)

# Route for the homepage
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# Route for streaming the scraping process
@app.route('/stream-scrape')
def stream_scrape():
    # Get parameters from query string
    keyword = request.args.get('keyword', '')
    pages = request.args.get('pages', 1, type=int)
    min_price = request.args.get('min_price', type=float, default=None)
    max_price = request.args.get('max_price', type=float, default=None)
    apply_discount = request.args.get('apply_discount', 'false') == 'true'
    free_shipping = request.args.get('free_shipping', 'false') == 'true'
    selected_fields = request.args.getlist('fields')

    # Basic validation
    if not keyword:
        def error_stream():
            yield "data: ERROR: Keyword is required.\n\n"
            yield "data: PROCESS_COMPLETE\n\n"
        return Response(stream_with_context(error_stream()), mimetype='text/event-stream')

    # If user selected no fields via checkbox, use an empty list (scraper handles defaults if needed)
    # Or, alternatively, return an error if you require at least one field to be selected.
    if not selected_fields:
        def error_stream():
            yield "data: ERROR: Please select at least one output field.\n\n"
            yield "data: PROCESS_COMPLETE\n\n"
        return Response(stream_with_context(error_stream()), mimetype='text/event-stream')
        # selected_fields = [] # Or set to empty list if scraper can handle it

    # Call the generator function from scraper.py with the user's direct selection
    stream = run_scrape_job(
        keyword=keyword,
        pages=pages,
        apply_discount=apply_discount,
        free_shipping=free_shipping,
        min_price=min_price,
        max_price=max_price,
        selected_fields=selected_fields
    )

    # Return a streaming response
    return Response(stream_with_context(stream), mimetype='text/event-stream')

if __name__ == '__main__':
    # Use threaded=True for handling multiple requests
    app.run(debug=True, threaded=True)