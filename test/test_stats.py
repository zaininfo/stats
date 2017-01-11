#!/usr/bin/env python3
# -*- coding: utf8 -*-

"""Tests for Stats."""

__author__ = 'zain'

from io import StringIO
import unittest
from threading import Lock
from unittest.mock import patch

from httmock import all_requests, response, urlmatch, HTTMock

from stats import stats
from stats.stream_summary import Bucket, StreamSummary


class TestStats(unittest.TestCase):
    """Test Stats functions."""

    def test_aggregate_stats(self):
        """Test aggregate_stats function."""
        # successful requests should result in items being added to the stream summaries
        def mock_furnish_request(endpoint, offset, limit):  # pylint: disable=missing-docstring, unused-argument
            return [
                {
                    'food_id': 1,
                    'food_category_id': 10,
                },
                {
                    'food_id': 2,
                    'food_category_id': 10,
                },
                {
                    'food_id': 2,
                    'food_category_id': 20,
                }
            ]
        top_foods = StreamSummary(10)
        top_food_categories = StreamSummary(10)
        endpoint = ''
        min_offset = 100
        offset_upper_bound = 250
        limit = 100
        lock = Lock()
        with patch('stats.stats.furnish_request', new=mock_furnish_request):
            stats.aggregate_stats(top_foods, top_food_categories, endpoint, min_offset, offset_upper_bound, limit, lock)
            self.assertEqual(tuple(top_foods.bucket_map.keys()), (2, 4))
            self.assertEqual(top_foods.bucket_map[2].items, [1])
            self.assertEqual(top_foods.bucket_map[4].items, [2])
            self.assertEqual(tuple(top_food_categories.bucket_map.keys()), (2, 4))
            self.assertEqual(top_food_categories.bucket_map[2].items, [20])
            self.assertEqual(top_food_categories.bucket_map[4].items, [10])

        # failed requests should result in no items being added to the stream summaries
        def mock_failed_furnish_request(endpoint, offset, limit):  # pylint: disable=missing-docstring, unused-argument
            raise stats.RequestError
        top_foods = StreamSummary(10)
        top_food_categories = StreamSummary(10)
        endpoint = ''
        min_offset = 123
        offset_upper_bound = 456
        limit = 100
        lock = Lock()
        with patch('stats.stats.furnish_request', side_effect=mock_failed_furnish_request):
            stats.aggregate_stats(top_foods, top_food_categories, endpoint, min_offset, offset_upper_bound, limit, lock)
            self.assertEqual(tuple(top_foods.bucket_map.keys()), ())
            self.assertEqual(tuple(top_food_categories.bucket_map.keys()), ())

        print('\n✓ aggregate_stats() works as expected')

    def test_furnish_request(self):
        """Test furnish_request function."""
        # 200 response with JSON content should result in 'response' array being returned
        @all_requests
        def json_response(url, request):  # pylint: disable=missing-docstring, unused-argument
            content = {'response': ['abc', 123]}
            headers = {'content-type': 'application/json'}
            return response(200, content, headers)
        with HTTMock(json_response):
            self.assertEqual(stats.furnish_request('http://lucky', 10, 10), ['abc', 123])

        # 200 response with non-JSON content should result in empty array being returned
        @urlmatch(netloc=r'(.*\.)?string')
        def string_response(url, request):  # pylint: disable=missing-docstring, unused-argument
            return {
                'status_code': 200,
                'content': 'abc'
            }

        @urlmatch(netloc=r'(.*\.)?integer')
        def integer_response(url, request):  # pylint: disable=missing-docstring, unused-argument
            return {
                'status_code': 200,
                'content': 123
            }
        with HTTMock(string_response, integer_response):
            self.assertEqual(stats.furnish_request('http://string', 10, 10), [])
            self.assertEqual(stats.furnish_request('http://integer', 10, 10), [])

        # persistent non-200 responses should result in RequestError being thrown
        @all_requests
        def non_200_response(url, request):  # pylint: disable=missing-docstring, unused-argument
            return {'status_code': 503}
        with self.assertRaises(stats.RequestError):
            with HTTMock(non_200_response):
                stats.furnish_request('http://bluh', 10, 10)

        print('\n✓ furnish_request() works as expected')

    def test_display_stats(self):
        """Test display_stats function."""
        # stream summary should be displayed with buckets arranged in descending order,
        # and items (including same frequency ones) displayed up to the topk limit
        stream_summary = StreamSummary(10)
        stream_summary.bucket_map = {
            1: Bucket(1),
            2: Bucket(2),
            3: Bucket(3),
            4: Bucket(4),
            5: Bucket(5),
        }
        stream_summary.bucket_map[1].items = [1, 2]
        stream_summary.bucket_map[2].items = [3]
        stream_summary.bucket_map[3].items = [4, 5, 6]
        stream_summary.bucket_map[4].items = [7]
        stream_summary.bucket_map[5].items = [8, 9]
        expected_output = 'Top 5 items\n' \
                          '1) Item(s) 8 occur(s) 5 times.\n' \
                          '2) Item(s) 9 occur(s) 5 times.\n' \
                          '3) Item(s) 7 occur(s) 4 times.\n' \
                          '4) Item(s) 4 occur(s) 3 times.\n' \
                          '5) Item(s) 5 occur(s) 3 times.'
        with patch('sys.stdout', new=StringIO()) as mock_stdout:
            stats.display_stats(stream_summary, 'Top {} items', 5)
            self.assertEqual(mock_stdout.getvalue().strip(), expected_output)
        print('\n✓ display_stats() works as expected')

    def setUpClass(self=None):
        print('\n==============================================' +
              '\n|              Stats Unit Tests              |' +
              '\n==============================================')


if __name__ == '__main__':
    unittest.main()
