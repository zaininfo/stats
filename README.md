# Stats
Aggregate &amp; display stats for an HTTP REST API (which exposes a collection of items categorized into groups e.g. an endpoint `/api/foods?offset=&limit=` with response `{'response': [{'food_id': 1, food_category_id': 1}, ...]}`).

## Design
Following design decisions influenced the implementation of this script.
* Stream Summary<sup>[1]</sup> (a probabilistic data structure well-suited for top-k problems) is used to aggregate the most popular items. This enables aggregation of million of items without exhausting resources and/or requiring a DB, with acceptable accuracy.
* The requests to the REST API are parallelized using multi-threading. Since, the requests are mostly I/O bound, GIL is not a huge factor.
* Basic concurrency locks are used around insertion operations to prevent race conditions.
* The requests to the REST API are retried with an exponential backoff, but limited to ensure progress.
* Keyboard interrupt (`Ctrl+C`) is intercepted to signal all worker threads to immediately stop processing. This enables displaying stats up to the point of interrupt and gracefully exit after that.

## Requirements
* Python 3.4.x
* virtualenv >= 12.0.7

## Setup
Run the following command:

    make bootstrap

## Usage
Run the following command:

    source venv/bin/activate
Run Stats:

    python3 -m stats.stats

## Acknowledgements
This product includes software developed by Bryant Moscon (http://www.bryantmoscon.org/).

## References
[1] https://www.cs.ucsb.edu/research/tech-reports/2005-23
