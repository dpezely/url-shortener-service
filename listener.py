#! /usr/bin/env python3

import http.server
import os
import re
import sys
import urllib

import base62ish

MAX_URL_SIZE = 2000

# FIXME: upgrade to ThreadingHTTPServer, which requires Python 3.7
# but Debian/Ubuntu have `python3` set to 3.6 at time of writing.
# However, `apt-get install python3.7` is available. 2018-10-09
class Listener(http.server.BaseHTTPRequestHandler):
    
    well_formed_url = re.compile('^[A-Za-z]{2,}://')
    strict_valid_uri = re.compile('^/[' + base62ish.ALPHABET + ']+$')

    def configure(self, shortener):
        """Supply instance of UrlShortener"""
        self.shortener = shortener
        
    def do_POST(self):
        """Receive Full URL, and attempt creating Short URI"""
        #print("POST: {}".format(self.headers))
        length = int(self.headers['Content-Length'])
        content_type = self.headers['Content-Type']
        # FIXME: Attempt to extract charset from headers, defaulting to utf-8
        post_data = urllib.parse.parse_qs(self.rfile.read(length).decode('utf-8'))
        full_url = post_data.get('url', [''])[0]
        if self.well_formed_url.match(full_url) is None:
            full_url = 'http://' + full_url # FIXME: display error page instead
        served = False
        if full_url:
            status, _pathname, short_uri = self.shortener.shorten(full_url)
            if status == 'SHORTENED' or status == 'DUPLICATE':
                served = True
                self.send_response(302) # "Found" (moved temporarily)
                self.send_header('Location',
                                 '{}?short-url={}/{}&full-url={}'
                                 .format(self.shortener.success_landing,
                                         self.shortener.public_display_url,
                                         short_uri, full_url))
            elif status == 'PHISHING':
                served = True
                self.send_response(302) # "Found" (moved temporarily)
                # FIXME: add link to phishing report for specific item
                self.send_header('Location',
                                 '{}?full-url={}'
                                 .format(self.shortener.phishing_landing,
                                         full_url))

        if not served:
            self.send_response(302) # "Found" (moved temporarily)
            self.send_header('Location', self.shortener.home_landing)

        print("status={} short-uri={} full-url={}"
              .format(status, short_uri, full_url), file=sys.stderr)
        self.end_headers()

    def do_GET(self, suppress_content=False):
        """Resolve a Short URI to Full URL as HTTP 302 redirect"""
        #print("GET:\n{}\n{}".format(self.requestline, self.headers))
        _get, relative_uri, _protocol = self.requestline.split(' ')
        content = None
        if self.strict_valid_uri.match(relative_uri) is None:
            print("error=invalid uri={}".format(relative_uri), file=sys.stderr)
            self.send_response(404)
            content = "404 Not Found"
        else:
            filepath = (self.shortener.short_uri_directory +
                        relative_uri[1:] + '.txt')
            if not os.path.exists(filepath):
                print("error=not-found path={}".format(filepath), file=sys.stderr)
                self.send_response(404)
                content = "404 Not Found"
            else:
                with open(filepath, 'r') as file:
                    full_url = file.read(MAX_URL_SIZE)
                if full_url:
                    print("found path={} full-url={}".format(filepath, full_url),
                          file=sys.stderr)
                    self.send_response(302) # "Found" (moved temporarily)
                    self.send_header('Location', full_url)
                    content = "302 (Found) Redirect: {}".format(full_url)
                else:
                    print("reserved path={}".format(filepath), file=sys.stderr)
                    self.send_response(404)
                    content = "404 Not Found"

        self.send_header('Content-Type','text/plain;charset=utf-8')
        self.send_header('Length', str(len(content)))
        self.end_headers()
        if content and not suppress_content:
            self.wfile.write(bytes(content, 'utf-8'))

    def do_HEAD(self):
        self.do_GET(True)

def run(url_shortener, address='', port=8000,
        server_class=http.server.HTTPServer, handler_class=Listener):
    server_address = (address, port)
    httpd = server_class(server_address, handler_class)
    httpd.RequestHandlerClass.configure(httpd.RequestHandlerClass,
                                        url_shortener)
    # FIXME: create custom loop that calls httpd.handle() directly so
    # that we may either watch for updates to anti-phishing URL list
    # file and/or handle POSIX Signal such as SIG_HUP, SIG_USR1, etc.
    # to trigger processing it.
    # (Then once that feature has been added, remove warning comments
    # within url-shortener.py about pausing "other active writer".)
    httpd.serve_forever()
