#! /usr/bin/env python3

"""URL Shortener

This offers usage as web app and with a command-line interface,
because it's simpler to test without HTTP overhead.

"""

import argparse
import bz2
import cityhash
import datetime
import http.server
import os
import re
import string
import sys

import base62ish
import listener

# Globals should be treated as constant due to being external
# parameters that should persist across runs:

# Account for file systems limits on number of directory entry items:
# e.g., Legacy NetApp Filer FS previously had limit of just under 65k
# entries.  ZFS has limit around 255m entries.  Accommodate base62
# alphabet when computing these values:
FIRST_PREFIX_DEPTH = 2
SECOND_PREFIX_DEPTH = FIRST_PREFIX_DEPTH + 2

STATUS_UNKNOWN = 'UNKNOWN'
STATUS_REJECTED = 'REJECTED'
STATUS_SHORTENED = 'SHORTENED'
STATUS_DUPLICATE = 'DUPLICATE'
STATUS_PHISHING = 'PHISHING'
STATUS_FOUND = 'FOUND'

FILE_EXTENSION = '.txt'

class UrlShortener:
    
    __slots__ = ('public_display_url', 'public_static_url', 'recursive_url_re',
                 'success_landing', 'phishing_landing', 'home_landing',
                 'address', 'port', 'data_directory',
                 'anti_phishing_dir', 'anti_phishing_dir_updating',
                 'anti_phishing_file',
                 'full_url_directory', 'short_uri_directory',
                 'sequence_pathname', 'sequence_file', 'sequence_number',
                 'short_uri', 'full_url')

    def __init__(self):
        # See also .configure() when changing these values:
        self.public_display_url = 'example.com/' # Omit http:// for aesthetics
        self.public_static_url = 'http://localhost:8088' # omit trailing '/'
        self.recursive_url_re = re.compile('^http[s]?://(www\.)*' +
                                           self.public_display_url,
                                           re.IGNORECASE)
        self.home_landing = self.public_static_url + '/'
        self.success_landing = self.public_static_url + '/_v1/results'
        self.phishing_landing = self.public_static_url + '/_v1/phishing'
        self.address = ''       # Leave blank for wildcard address
        self.port = 8000
        self.data_directory = ''
        self.anti_phishing_dir = 'anti-phish'
        self.anti_phishing_dir_updating = '_UPDATING_anti-phish'
        self.full_url_directory = 'full/'
        self.short_uri_directory = 'short/'
        self.sequence_file = 'sequence.dat'
        self.sequence_pathname = self.sequence_file
        self.anti_phishing_file = None

        # Begin with multiple character sequence for aesthetic reasons:
        self.sequence_number = base62ish.LENGTH

        self.short_uri = None   # to be resolved and redirected
        self.full_url = None    # to be shortened

    def main(self):
        if len(sys.argv) > 1:
            self.configure()

        if self.data_directory:
            os.makedirs(self.data_directory, exist_ok=True)

        if self.anti_phishing_file:
            # FIXME: migrate to watching for file change or POSIX Signal
            self.start_anti_phishing_update()
            self.update_anti_phishing_catalogue()
            self.finish_anti_phishing_update()
        else:
            if os.path.exists(self.sequence_pathname):
                with open(self.sequence_pathname, encoding='utf-8') as file:
                    value = file.readline().rstrip()
                    if value != '':
                        self.sequence_number = int(value)

            if self.short_uri:
                relative_uri = self.short_uri.lstrip('/')
                status, pathname, full_url = self.resolve(relative_uri)
                print("Resolve: status={}, pathname={}, full_url={}"
                      .format(status, pathname, full_url))
            elif self.full_url:
                status, pathname, shortened = self.shorten(self.full_url)
                print("Shorten: status={}, pathname={}, shortened={}"
                      .format(status, pathname, shortened))
            else:
                self.serve_http_requests_forever()
            
    def configure(self):
        args = self.parse_args()
        # See also .__init__() when changing these values:
        # FIXME: confirm integrity of individual values
        self.public_display_url = args.public_display_url.rstrip('/')
        self.public_static_url = args.public_static_url.rstrip('/')
        self.home_landing = args.home_landing
        self.success_landing = args.success_landing
        self.phishing_landing = args.phishing_landing
        self.address = args.address
        if args.port:
            self.port = int(args.port)

        if args.data_directory:
            self.data_directory = args.data_directory
            if self.data_directory[-1] != '/':
                self.data_directory += '/'

        self.anti_phishing_dir = args.data_directory + 'anti-phish'
        self.anti_phishing_dir_updating = args.data_directory + '_UPDATING_anti-phish'
        self.full_url_directory = args.data_directory + 'full/'
        self.short_uri_directory = args.data_directory + 'short/'
        self.sequence_pathname = args.data_directory + self.sequence_file
        self.anti_phishing_file = args.anti_phishing_file
        if args.url_or_uri:
            # RegExp to discover protocol scheme indicating full URL or not:
            if re.match('^[A-Za-z]{2,}://', args.url_or_uri[0]) is None:
                self.short_uri = args.url_or_uri[0]
            else:
                self.full_url = args.url_or_uri[0]

        if self.public_display_url.find('http') == 0:
            self.recursive_url_re = re.compile(self.public_display_url,
                                               re.IGNORECASE)
        else:
            self.recursive_url_re = re.compile('^http[s]?://(www\.)*' +
                                               self.public_display_url,
                                               re.IGNORECASE)
            
    def parse_args(self):
        parser = argparse.ArgumentParser(
            description="URL Shortener HTTP app and command-line interface",
            epilog='Without any arguments, listens using defaults.')
        parser.add_argument('-a', dest='address',
                            default=self.address,
                            help='Listen on IP interface bound to host address;'
                            ' Leave blank for wildcard address')
        parser.add_argument('--display', dest='public_display_url',
                            default=self.public_display_url,
                            help='Base URL to display on success page;'
                            ' e.g., Example.com (omit "https://" for aesthetics)')
        parser.add_argument('-d', dest='data_directory',
                            default=self.data_directory,
                            help='Directory for storing URLs')
        parser.add_argument('--home', dest='home_landing',
                            default=self.home_landing,
                            help='Filename of home page with Form')
        parser.add_argument('-p', dest='port',
                            default=self.port,
                            help='Listen on this IP port number')
        parser.add_argument('--phishing', dest='phishing_landing',
                            default=self.phishing_landing,
                            help='Filename of landing page when phishing discovered')
        parser.add_argument('--success', dest='success_landing',
                            default=self.success_landing,
                            help='Filename of landing page for successful shortening')
        parser.add_argument('--static', dest='public_static_url',
                            default=self.public_static_url,
                            help='Address of static HTTP service; i.e., nginx;'
                            ' e.g., https://www.example.com')
        parser.add_argument('--anti-phishing', dest='anti_phishing_file',
                            help='Supply file of known phishing URLs'
                            ' and process it')
        parser.add_argument('url_or_uri', nargs=argparse.REMAINDER,
                            help='A full URL to be shortened'
                            ' or short relative URI to be resolved')
        args = parser.parse_args()
        return args

    def resolve(self, short_uri):
        """Look-up URI within public namespace as read-only operation.
        Returns: tuple containing state, pathname, full URL
        """
        status = STATUS_UNKNOWN
        full_url = None
        _dir_path, file_path = self.make_pathname(short_uri)
        pathname = self.short_uri_directory + file_path
        if os.path.exists(pathname):
            with open(pathname, encoding='utf-8') as file:
                full_url = file.readline().rstrip() or None

        if full_url:
            status = STATUS_FOUND

        return (status, file_path, full_url)
        
    def shorten(self, full_url):
        """Create short relative URI from full URL.
        Thou shall have only one node as writer; see README.
        SIDE-EFFECTS: causes state to be written to durable storage.
        Returns: tuple containing state, pathname, shortened URI
        """
        status = STATUS_UNKNOWN
        file_path = None
        shortened = ''
        if self.recursive_url_re.match(full_url):
            status = STATUS_REJECTED
        while status is STATUS_UNKNOWN:
            # Using same custom encoding here for compressing path name:
            #print("shorten: full-url={}".format(full_url))
            hashed = base62ish.encode(cityhash.CityHash128(full_url))
            dir_path, file_path = self.make_pathname(hashed)
            full_url_pathname = self.full_url_directory + '/' + file_path
            phishing_pathname = self.anti_phishing_dir + '/' + file_path
            if self.match_phishing_url(phishing_pathname, full_url):
                status = STATUS_PHISHING
                break
            elif os.path.exists(full_url_pathname):
                shortened = self.match_full_url(full_url_pathname, full_url)
                if shortened != '':
                    status = STATUS_DUPLICATE
                    break
                # Else, we found hash collision but is a new Full URL

            # Handle new Full URL:
            shortened = self.make_short_uri(file_path)
            self.persist(full_url, shortened, dir_path, file_path)
            status = STATUS_SHORTENED

        return (status, file_path, shortened)

    def match_phishing_url(self, pathname, full_url):
        """Inspect file contents for whether Full URL exists or not"""
        if os.path.exists(pathname):
            with open(pathname, encoding='utf-8') as file:
                while True:
                    url = file.readline()
                    if url == '':
                        break
                    if full_url == url[:-1]:
                        return True
        return False

    def match_full_url(self, pathname, full_url):
        """For a given Full URL, return its associated Short URI"""
        shortened = ''
        with open(pathname, encoding='utf-8') as file:
            while '' != file.readline().rstrip() != full_url:
                # Consume hash collisions, if any
                pass
            shortened = file.readline().rstrip()

        return shortened

    def remove_entry(self, pathname, full_url):
        """Subtract pair of Full URL and its correspoonding Short URI
        without modifying original file.
        Returns: tuple containing Short URI corresponding to Full URL
        and list of any remaining file contents.
        """
        paired_short_uri = None
        others = []
        with open(pathname, encoding='utf-8') as file:
            while True:
                url = file.readline()
                if url == '':
                    break
                elif full_url == url[:-1]: # omit Newline
                    paired_short_uri = file.readline().strip()
                else:
                    others.append(url)
                    others.append(file.readline())

        return (paired_short_uri, others)

    def make_short_uri(self, pathname):
        """Generate a short, relative URI based upon sequence number
        and increment sequence number in preparation for next call.
        Be sure to call .persist() next for durably recording state.
        Loops in case recorded sequence number mismatches actual value
        on durable storage.
        Returns: short URI as string
        """
        shortened = None
        while True:
            shortened = base62ish.encode(self.sequence_number)
            self.sequence_number += 1
            _dir_path, file_path = self.make_pathname(shortened)
            if os.path.exists(self.short_uri_directory + file_path):
                continue
            # FIXME: accommodate dictonary of strings/patterns to skip,
            # but see README #Implementation.
            return shortened

    def persist(self, full_url, shortened, dir_path, file_path):
        """Durably record state.
        SIDE-EFFECTS: directly writes state to durable storage/disk.
        """
        print("persist full_url={} shortened={} dir_path={} file_path={}"
              .format(full_url, shortened, dir_path, file_path), file=sys.stderr)
        with open(self.sequence_pathname, 'w', encoding='utf-8') as file:
            file.write("{}\n".format(self.sequence_number))

        os.makedirs(self.full_url_directory + dir_path, exist_ok=True)
        with open(self.full_url_directory + file_path, 'a', encoding='utf-8') as file:
            # Accommodate hash collisions; alternate lines as key/value pairs:
            file.write(full_url + "\n")
            file.write(shortened + "\n")

        d_path, f_path = self.make_pathname(shortened)
        os.makedirs(self.short_uri_directory + d_path, exist_ok=True)
        with open(self.short_uri_directory + f_path, 'w', encoding='utf-8') as file:
            file.write(full_url + "\n")

    def make_pathname(self, text):
        """Generate hierarchical pathname from TEXT.
        Returns: tuple of directory path, file path
        """
        dir_path = ''
        file_path = ''
        length = len(text)
        # Highest traffic work-flow is for City Hash (128 bit integer)
        if length > SECOND_PREFIX_DEPTH:
            first_prefix = text[:FIRST_PREFIX_DEPTH]
            second_prefix = text[FIRST_PREFIX_DEPTH:SECOND_PREFIX_DEPTH]
            remainder = text[SECOND_PREFIX_DEPTH:] + FILE_EXTENSION
            dir_path = first_prefix + '/' + second_prefix
            file_path = dir_path + '/' + remainder
        elif length > FIRST_PREFIX_DEPTH:
            first_prefix = text[:FIRST_PREFIX_DEPTH]
            remainder = text[FIRST_PREFIX_DEPTH:] + FILE_EXTENSION
            dir_path = first_prefix
            file_path = first_prefix + '/' + remainder
        else:
            file_path = text + FILE_EXTENSION

        return (dir_path, file_path)

    def serve_http_requests_forever(self):
        """Start HTTP service.
        SIDE-EFFECTS: never returns but handles KeyboardInterrupt
        """
        print('Listening on {}:{} ...'.format(self.address or '*', self.port))
        try:
            listener.run(self, address=self.address, port=self.port)
        except KeyboardInterrupt:
            print("\nCaught keyboard interrupt.  Exiting.")
            sys.exit(0)

    def start_anti_phishing_update(self):
        """In lieu of file locking, new content goes under temp location"""
        os.makedirs(self.anti_phishing_dir_updating)

    # WARNING: pause any other active writer.  See README #Maintenance.
    # There is a theoretical vulnerability of a perfectly timed
    # attack here-- time elapsed between 2 renaming calls; see README
    def finish_anti_phishing_update(self):
        """Preserve former location via renaming as lightweight versioning.
        This accommodates any number of readers still in progress.
        """
        if os.path.exists(self.anti_phishing_dir):
            os.rename(self.anti_phishing_dir, self.anti_phishing_dir + '.' +
                      datetime.datetime.now().isoformat())
        os.rename(self.anti_phishing_dir_updating, self.anti_phishing_dir)

    # WARNING: pause any other active writer.  See README #Maintenance.
    # Because we accommodate hash collisions, there is a theoretical
    # data race between appending to a file with full URL by the
    # principal writer versus replacing that file with a modified
    # version, such that the appended data becomes lost.
    def update_anti_phishing_catalogue(self):
        """Update and repair artifacts related to known phishing URLs.
        SIDE-EFFECTS: destructively modifies Full URL files, removes
        Short URI files corresponding to URLs in known phishing list.
        Also, populates subdirectory with known phishing URL in list.
        """
        if os.path.exists(self.anti_phishing_file):
            with open(self.anti_phishing_file, encoding='utf-8') as file:
                while True:
                    phishing_url = file.readline()[1:-2] # "foo"\n => foo
                    if phishing_url == '':
                        break
                    hashed = base62ish.encode(cityhash.CityHash128(phishing_url))
                    dir_path, file_path = self.make_pathname(hashed)
                    full_url_pathname = self.full_url_directory + file_path
                    if os.path.exists(full_url_pathname):
                        # Remove pair of Full URL and Short URI from file
                        short_uri, others = self.remove_entry(full_url_pathname,
                                                              phishing_url)
                        if short_uri: # Else was hash collision but new URL
                            _d_path, f_path = self.make_pathname(short_uri)
                            pathname = self.short_uri_directory + f_path
                            if os.path.exists(pathname):
                                print("removing short-uri={}".format(short_uri),
                                      file=sys.stderr)
                                os.remove(pathname)

                        if len(others) == 0:
                            os.remove(full_url_pathname)
                        else:
                            temp_pathname = full_url_pathname + '.TEMP'
                            with open(temp_pathname, 'w',
                                      encoding='utf-8') as temp_file:
                                temp_file.write(''.join(others))
                            os.rename(temp_pathname, full_url_pathname)

                    pathname = self.anti_phishing_dir_updating + '/' + file_path
                    if (not os.path.exists(pathname) or
                        not self.match_phishing_url(pathname, phishing_url)):
                        os.makedirs(self.anti_phishing_dir_updating + '/' + dir_path,
                                    exist_ok=True)
                        with open(pathname, 'a', encoding='utf-8') as phishy_file:
                            phishy_file.write(phishing_url)
                            phishy_file.write("\n")

if __name__ == '__main__':
    url_shortener = UrlShortener()
    url_shortener.main()
