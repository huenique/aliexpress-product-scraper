from flask import Flask, render_template, request, Response, stream_with_context
import os
import json

ALL_POSSIBLE_FIELDS = [
    'Product ID', 'Title', 'Sale Price', 'Original Price', 'Discount (%)',
    'Currency', 'Rating', 'Orders Count', 'Store Name', 'Store ID',
    'Store URL', 'Product URL', 'Image URL'
]

try:
    from scraper import run_scrape_job
except ImportError:
    print("Error: Could not import functions from scraper.py.")
    print("Make sure scraper.py is in the same directory as app.py.")
    exit()

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# Route for streaming the scraping process
@app.route('/stream-scrape')
def stream_scrape():
    keyword = request.args.get('keyword', '')
    pages = request.args.get('pages', 1, type=int)
    min_price = request.args.get('min_price', type=float, default=None)
    max_price = request.args.get('max_price', type=float, default=None)
    apply_discount = request.args.get('apply_discount', 'false') == 'true'
    free_shipping = request.args.get('free_shipping', 'false') == 'true'
    selected_fields = request.args.getlist('fields')
    delay = request.args.get('delay', 1.0, type=float)  # Default 1 second

    if not keyword:
        def error_stream():
            yield "data: ERROR: Search product is required.\n\n"
            yield "data: PROCESS_COMPLETE\n\n"
        return Response(stream_with_context(error_stream()), mimetype='text/event-stream')

    if not selected_fields:
        def error_stream():
            yield "data: ERROR: Please select at least one output field.\n\n"
            yield "data: PROCESS_COMPLETE\n\n"
        return Response(stream_with_context(error_stream()), mimetype='text/event-stream')

    stream = run_scrape_job(
        keyword=keyword,
        pages=pages,
        apply_discount=apply_discount,
        free_shipping=free_shipping,
        min_price=min_price,
        max_price=max_price,
        selected_fields=selected_fields,
        delay=delay  # Add delay parameter
    )

    return Response(stream_with_context(stream), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True, threaded=True)