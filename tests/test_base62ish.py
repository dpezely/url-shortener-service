#! /usr/bin/env python3

import unittest

import base62ish

class TestBase62ish(unittest.TestCase):

    def test_bounds(self):
        self.assertEqual(base62ish.encode(0), base62ish.ALPHABET[0])

        self.assertEqual(base62ish.decode(base62ish.encode(0)), 0)

    def test_thresholds(self):
        for power in range(1, 5):
            for value in range((base62ish.LENGTH**power) - 2,
                               (base62ish.LENGTH**power) + 2):
                self.assertEqual(base62ish.decode(base62ish.encode(value)),
                                 value)

    def test_heuristics(self):
        self.assertEqual(len(base62ish.ALPHABET), base62ish.LENGTH)

        # This is used for seeding default sequence number to ensure
        # more than one encoded character appears in public URI
        # namespace:
        self.assertEqual(len(base62ish.encode(base62ish.LENGTH)), 2)

if __name__ == '__main__':
    unittest.main()
