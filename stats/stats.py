#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Aggregate & display stats for an HTTP REST API."""

__author__ = 'zain'

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from os import path
from threading import Lock
from validate import Validator

import requests
from configobj import ConfigObj
from retry import retry

from .stream_summary import StreamSummary

SCRIPT_DIR = path.dirname(path.realpath(__file__))
CONFIG_FILE = path.normpath(path.join(SCRIPT_DIR, '../config/config.ini'))
CONFIG_SPEC_FILE = path.normpath(path.join(SCRIPT_DIR, '../config/configspec.ini'))
MAIN_THREAD_SLEEP_INTERVAL = 50.0 / 1000.0
TOP_FOODS_TITLE = 'Top {} Foods\n' \
                  '============'
TOP_FOOD_CATEGORIES_TITLE = 'Top {} Food Categories\n' \
                            '======================'
quit_now = False  # pylint: disable=invalid-name


# pylint: disable=too-many-locals
def run(top_foods_no, top_food_categories_no):
    """Runner where the main logic of this programme starts."""
    config = ConfigObj(CONFIG_FILE, configspec=CONFIG_SPEC_FILE)
    config.validate(Validator())
    # using 100 times the required top items as length of stream summaries, in order to accumulate better estimates
    top_foods = StreamSummary(top_foods_no * 100)
    top_food_categories = StreamSummary(top_food_categories_no * 100)
    max_threads = config['Multi-threading']['max_threads']
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        try:
            endpoint = config['API']['endpoint']
            global_min_offset = config['API']['min_offset']
            global_max_offset = config['API']['max_offset']
            # using maximum limit of the endpoint
            # since, theoretically, large I/O per unit of work plays well with multi-threading
            # although, the API seems to be serving requests with different limits in almost the same time
            limit = config['API']['max_limit']
            # distributing the data points equally among the threads
            batch_size = int((global_max_offset - global_min_offset + 1) / max_threads)
            if not batch_size:
                batch_size = 1
            lock = Lock()
            global_offset_upper_bound = global_max_offset + 1
            futures = []
            for min_offset in range(global_min_offset, global_offset_upper_bound, batch_size):
                offset_upper_bound = min_offset + batch_size
                if offset_upper_bound > global_offset_upper_bound:
                    offset_upper_bound = global_offset_upper_bound
                futures.append(executor.submit(aggregate_stats, top_foods, top_food_categories, endpoint, min_offset,
                                               offset_upper_bound, limit, lock))
            # the thread pool executor handles keyboard interrupt gracefully
            # as in, it blocks until all active workers finish their tasks
            # in our case, we would rather exit immediately and display the stats aggregated up to that point
            # so, we poll for completion of worker tasks with interleaved sleep to intercept keyboard interrupt
            while any(not future.done() for future in futures):
                time.sleep(MAIN_THREAD_SLEEP_INTERVAL)
        except KeyboardInterrupt:
            # we use a global variable to signal the workers to stop further processing
            global quit_now  # pylint: disable=invalid-name, global-statement
            quit_now = True
    display_stats(top_foods, TOP_FOODS_TITLE, top_foods_no)
    display_stats(top_food_categories, TOP_FOOD_CATEGORIES_TITLE, top_food_categories_no)
# pylint: enable=too-many-locals


# pylint: disable=too-many-arguments
def aggregate_stats(top_foods, top_food_categories, endpoint, min_offset, offset_upper_bound, limit, lock):
    """Invoke requests to the REST API and add the responses to the stream summaries."""
    # we're making an optimistic assumption that the data for all IDs is present on the server
    # so, requesting data with an incremental offset equal to the endpoint limit will not introduce duplication
    for offset in range(min_offset, offset_upper_bound, limit):
        if quit_now:
            break
        if offset + limit > offset_upper_bound:
            limit = offset_upper_bound - offset
        try:
            foods = furnish_request(endpoint, offset, limit)
            with lock:
                for food in foods:
                    top_foods.add(food['food_id'])
                    top_food_categories.add(food['food_category_id'])
        except RequestError:
            # this exception will only occur here if the retry logic gave up,
            # in which case we skip the request deeming it impossible to succeed
            pass
# pylint: enable=too-many-arguments


class RequestError(Exception):
    """Represents an unsuccessful request."""
    pass


@retry(RequestError, tries=5, delay=1, backoff=2)
def furnish_request(endpoint, offset, limit):
    """Furnish requests to the REST API and return the response.
    This function will be retried a set number of times with an exponential backoff, in case of failed requests."""
    res = requests.get(endpoint, params={'offset': offset, 'limit': limit})
    foods = []
    if res.status_code == 200:
        try:
            res_body = res.json()
            if res_body['response']:
                foods = res_body['response']
        except (ValueError, TypeError):
            # these exceptions are expected in case of non-JSON response
            # as the request itself was successful, we will skip the response
            pass
    else:
        # we raise an exception if the request is not successful, in order to retry it
        raise RequestError('Unsuccessful request to: {} with offset: {} and limit: {}'.format(endpoint, offset, limit))
    return foods


def display_stats(stream_summary, display_title, no_of_topk):
    """Display the stats for top items."""
    print(display_title.format(no_of_topk))
    frequencies = list(stream_summary.bucket_map.keys())
    frequencies.reverse()
    topk_iter = iter(range(1, no_of_topk + 1))
    for frequency, serial_no in zip(frequencies, topk_iter):
        items_iter = iter(stream_summary.bucket_map[frequency].items)
        item = next(items_iter)
        while True:
            print('{}) Item(s) {} occur(s) {} times.'.format(serial_no, item, frequency))
            try:
                item = next(items_iter)
                serial_no = next(topk_iter)
            # break iteration on either of the following:
            # a) items with the same frequency exhausted, we move on to items with other frequencies
            # b) the requested number of top items displayed, we skip stats for any further items
            except StopIteration:
                break


def main(argv):
    """Parse the argv, verify the args, and call the runner."""
    args = arg_parse(argv)
    return run(args.top_foods, args.top_food_categories)


def arg_parse(argv):
    """Parse arguments and return an args object."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--top_foods', help='Number of top foods to aggregate stats for.', type=int, default=100)
    parser.add_argument('--top_food_categories', help='Number of top food categories to aggregate stats for.', type=int,
                        default=5)

    return parser.parse_args(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
