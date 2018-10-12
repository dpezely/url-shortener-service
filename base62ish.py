#! /usr/bin/env python3

"""Convert an integer to an encoded string, and decode it.

Shortened URLs may need to be manually typed, so avoid visually
similar characters: "Il1" and "O0".  Otherwise, this would be base62.
"""
# FIXME: alternatively, include digits 1 and 0 within alphabet, and
# map letters I, l to 1 and O to 0, which would increase namespace
# while resolving typos but would be less ergonomic for some people.

ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
LENGTH = len(ALPHABET)
INVERTED = {char: index for (index, char) in enumerate(ALPHABET)}

def encode(integer):
    """Returns INTEGER encoded as Base62ish string"""
    assert integer >= 0, 'Number must be non-negative'
    if integer < LENGTH:
        return ALPHABET[integer]
    results = ''
    while integer != 0:
        integer, remainder = divmod(integer, LENGTH)
        results = ALPHABET[remainder] + results

    return results

def decode(encoded_string):
    """Returns ENCODED_STRING in Base62ish format as an integer.
    May raise KeyError"""
    integer = 0
    for i, char in enumerate(encoded_string[::-1]):
        integer += INVERTED[char] * (LENGTH ** i)

    return integer
