URL Shortener Service
=====================

## Criteria

The exercise was to "build a url shortener" capable of handling
approximately 50 requests per second initially and increasing.

URL Shortener services are fairly well understood as of 2018.

One key requirement was enforcing an anti-phishing policy that includes
checking against known offending URLs, such as one supplied by
[PhishTank](https://phishtank.com/developer_info.php).

This implementation was intended as a complete, deployable *service*.
Having worked in other programming languages such as Rust recently, the
added bits here were mainly for getting my sealegs again with Python 3.

There were templates intended to be provided that were unavailable (due to
GitHub repo permission issues beyond my control), so everything for offering
an end-to-end service was freshly created.

## Design

### URI Namespaces

The public namespace for short URI is an encoded sequence number and
available directly from "/" path.

This led to introducing an overlay namespace of "/_v1/" for serving static
HTML pages and other resources, including path to our app: `/_v1/shorten`.

The underscore character is excluded from the alphabet of valid symbols used
for shortened URIs.  Therefore, "/QxGj6" and "/v1" Short URIs would be
unambiguously distinguished from the first level of "/_v1/style.css" when
handling HTTP requests.

### Base62-ish For Short URIs

The shortened URI namespace builds upon base62 alphabet: A-Z, a-z, 0-9
characters.  However, some characters appear ambiguous for some people due
to eye-sight, based upon certain fonts, etc.

Therefore, the most obvious offenders have been completely eliminated: I, l,
1, O and 0.  While the numerals could be kept and those letters mapped to
the numerals when expanding from a short URI, that's a business case
decision punted for our purposes here.

The base62-ish namespace gets used exclusively for short URIs.

### Use of CityHash

Separate from the public shortened URI namespace, a second internal hash
table is maintained for tracking duplicates among full URLs and for caching
known phishing URLs.

Choice of CityHash was made based upon balance of performance, the fact that
this is **not** a cryptographic service, fixed key size, and low frequency
of known collisions.

(Without being a specialist on hash functions, selecting a "better" one
should be made based upon load & capacity test results.)

### Flat Files

For efficient run-time delivery of results as trade-off of overall namespace
capacity and cold-start initialization, flat files are used for durable
storage.

In another context, such an exercise might have called for a pair of Python
dictionaries used as in-memory databases: one for tracking uniqueness of
input Full URLs versus one for serving Short URIs from the public namespace.

Today, established use of SSD in production and ZFS, Btrfs, NetApp, VMware,
etc. file systems have proven capable of holding extremely large volumes of
small files.

Therefore, *let the file system be the database.*

This has measured to be very performant in other applications and expected
here as well.

This gives nice balance for minimal cold-start times and scaling to a large
number of read-only servers.  Having a single hot server responsible for
writes is reasonable for this application and may be tuned with very long
TCP listen queue for added assurances.  (See Deployment section for more
details.)

### Concurrency

Python has a concurrency model using a co-routines architecture on top of OS
heavyweight threads.  However, the Global Interpreter Lock (GIL) creates a
bottleneck of resource contention.  For really high concurrency with Python,
multiple heavyweight OS processes on multi-core hardware generally
out-performs the other approach.  (For very high concurrency, consider Rust,
Erlang, etc.)

### Accommodating Deployment As Distributed System

This implementation uses Nginx to partition work between a single writer and
multiple readers.  Due to the data being stored on SSD or disk, this model
could scale to multiple machines or server instances by sharing a common
file server.

Regular updates-- even via `rsync` launched from `cron` jobs-- would
accommodate geographically distributed read-only nodes.

## Implementation

### Done
- Inbound HTTP traffic handled by Nginx
  + Accommodates one app doing everything; **OR**
  + One writer, multiple reader app instances with round-robin balancing
- Python 3 implementation for web app
- Take any URL protocol scheme; e.g., http, ftp, mailto, news/nntp, etc.
- Check for duplicate URLs
- Check against known phishing URLs
  + Retroactively sanitize published short URIs upon applying updated list
  + Account for previously reported phishing URLs to be removed
- Iterate sequence number which tracks Short URIs
  + Loops in case of reconciling in-memory value with what's been persisted
  + Therefore, vanity/offensive words may be reserved simply by populating
    empty files in relevant subdirectory as manual procedure
- Encode sequence number to base62
  + Use alphabet subset suitable for reducing typos
- Dockerfile for running without polluting existing python environment
  + Not quite ready as deployment-grade container
  + Goes beyond merely an alternative to Py 2-vs-3 environment
- Minimal tests
- Minimal docs (i.e., this README)
- Separation of public URI namespaces:
  + Short URIs
  + Local HTML pages; e.g., success/error landing pages

### To Do
- Integrate updating known phishing URLs
  + Migrate from being a separate maintenance task
  + Monitor changes to file or handle `SIG_HUP`, `SIG_USR1`, etc.
- More robust handling of hash collisions when storing full URL
  + Collisions have yet to be robustly tested
  + Proper tests probably require refactoring of .shorten()
- Supply dictionary of encoded values to be omitted:
  + Definitely reject offensive words in all natural languages
  + Maybe restrict common words from various natural languages, and consider
    their use as a revenue-generating feature; e.g., vanity URLs
- Optionally, conform to PEP8 style
- Create doc-strings suitable for your doc gen system of choice
- More thorough automated tests
- Measure test code coverage
- Refactor code for shorter functions
  + For me, this usually occurs while writing more tests
- More documentation
- More robust Dockerfile per your deployment environment(s)
  + Chaining Docker build: base for build/dev and extension for release/production
- Generate file: Dockerfile, Makefile, Bash scripts and nginx.conf
  + Generate via Chef, Puppet or similar tool
  + Configuration should be defined only once ("one source of truth", etc.)
- Web design make-over:
  + HTML and CSS were intentionally *minimal* placeholders
  + Improve upon "404 Not Found", etc.

## Coding Style

I adapt to full PEP8 or other existing coding style at each company.

This implementation, however, uses a more minimal coding style, providing
insight to my quick & dirty code.

Also, my preferred style aligns with functional programming-- or at least
being relatively free from side-effects.  At minimum, this makes testing
easier.  Therefore, you may see values supplied to methods that could be
extracted from self.  This distinction helps identify base configuration
from actual parameters used for computing/generating results.  (For those
arguing about performance here, consider another language such as Rust, and
I can help you get [there](https://play.org/links/rust).)

Since this exercise was indicated to be just a "few hours", shortcuts made
include abbreviated doc-strings, fewer tests, etc.

(See Implementation section, above.)

## Dependencies

Run `make apt` and `make deps` for installation on your laptop/workstation,
or use `make docker-image` for keeping everything contained.

This requires Python 3 and its conventional package manager, pip.  In
addition, Nginx and `jq` are used:

	sudo apt-get install python3 python3-pip nginx jq
    pip3 install --upgrade pip
	pip install -r requirements.txt
    
Or use the optional Dockerfile:
(Your [Docker setup](https://docs.docker.com/install/linux/docker-ce/ubuntu/)
may require using `sudo`)

	docker build -t url-shortener .
	docker run -it --rm -v $(pwd):/data  -v $(pwd)/htdocs:/var/www/html \
	  -p 8088:80  url-shortener ./one-writer-multiple-readers.sh

When running from within Docker or other containers, be aware subdirectories
and files will be created in your current directory.  These files will be
owned by `root`.

## Running As Command-line Utility

Run `make` to display basic help:

	make
    
You may want to run the following commands inside of a Docker container to
ensure a pristine environment:

	make docker-image
    make docker-dev

Once dependencies have been resolved (see above), specific usage is as follows.

Display command-line options:

    ./url-shortener.py --help

Supply a full URL to be shortened:

    ./url-shortener.py https://example.com/foo
    Output:
	Shorten: status=SHORTENED, pathname=WW/2H/mtz7yDFs9jjrVMaoyz.txt, shortened=BG

The actual encoded value that you see may be different here.

Try again, and see that it would be a duplicate:

    ./url-shortener.py https://example.com/foo
    Output:
	Shorten: status=DUPLICATE, pathname=WW/2H/mtz7yDFs9jjrVMaoyz.txt, shortened=BG

Try another URL:

	./url-shortener.py https://example.com/bar
    Output:
    Shorten: status=SHORTENED, pathname=vi/8u/eiKMYWtAkUMQWrDFCe.txt, shortened=BH

Resolve short, relative URI using encoded value from right side of
`shortened=` from results of a previous successful command:

	./url-shortener.py /BH
    Output:
	Resolve: status=FOUND, pathname=BH.txt, full_url=https://example.com/bar

Accommodates URIs with or without leading slash:

	./url-shortener.py BH
    Output:
	Resolve: status=FOUND, pathname=BH.txt, full_url=https://example.com/bar

## Running As HTTP Service

Run without specifying any URL or relative URI, and this becomes the
back-end of an HTTP web app:

	./url-shortener.py -a localhost -p 8088
    
Or simply run without any arguments for default configuration:

	./url-shortener.py

See `one-writer-multiple-readers.sh` script for running within the Docker
container:

	./one-writer-multiple-readers.sh
    
However, there is no companion script for gracefully *stopping* the
multiple reader processes other than exiting the container.

## Maintenance

(This procedure is an interim measure; see #Implementation To Do list above.)

Create a cron job or similar for fetching list of known phishing URLs:

	wget -N http://data.phishtank.com/data/online-valid.json.bz2

	bunzip2 < online-valid.json.bz2 | \
      jq '.[] | {url} | .url' > known-phishing-urls.txt

The writer's HTTP handler must be paused-- not necessarily stopped-- to
avoid contention over files containing anti-phishing and full URLs.
(Again, see To Do items above.)

Ensure that the listening socket's wait queue is large enough on Nginx for
your anticipated traffic, and the few seconds for updating on production
server instance will be indistinguishable from network latency for most
visitors.

Read-only app workers may continue running.

With those caveats addressed-- to actually update the known phishing URLs,
run:

    ./url-shortener.py --anti-phishing known-phishing-urls.txt

**Note:** any previously published short URIs that resolve to a phishing URL
will be purged retroactively when using the `--anti-phishing` flag.

However, this purge only occurs *while* processing the file.

## Deployment

**Thou shall have only one node as writer.**

Ensure a maximum of one instance for writing; i.e., if using a network
load-balancer, ensure that the following URI always goes to the same node
in the pool:

	URI="/_v1/shorten"

That ensures sanity with sequence numbers.

Resolving already shortened URIs may use as many nodes in a network
load-balancer pool as deemed necessary, as these function as read-only
workers.

This implementation uses Nginx for several purposes: 1) normalizing HTTP
requests from public abuse; 2) load-balancing across read-only app
instances; 3) serving static HTML pages, style.css and similar files.

Nginx runs on port 80 *within* Docker container for serving static web
content.  Static files live under the conventional [htdocs/](./htdocs/)
subdirectory here, which inside the Docker Container gets mapped to its
conventional location for Debian/Ubuntu servers: `/var/www/html/`.

The htdocs subdirectory contains:

- [home.html](htdocs/_v1/home.html) with HTML Form for input
- [phishing.html](htdocs/_v1/phishing.html) error page (requires JS)
- [results.html](htdocs/_v1/results.html) success page (requires JS)
- [shortener.js](htdocs/_v1/shortener.js) for presentation niceties
- [style.css](htdocs/_v1/style.css)

Nginx forwards requests via its `upstream` directive to the Python app.
This feature of Nginx easily accommodates multiple readers and a single
writer.  This in turn lets the OS scheduler handle concurrency, thereby
avoiding Python's GIL limitations, as explained above.

There is a single script
[one-writer-multiple-readers.sh](./one-writer-multiple-readers.sh) that
launches Nginx, single writer and multiple reader app processes within
Docker.

Changing the port on which Nginx listens involves updating:

- [nginx.conf](./nginx.conf)
- [Dockerfile](./Dockerfile)

Edit both `nginx.conf` and `one-writer-multiple-readers.sh` in tandem when
adjusting number of read-only app instances.  (See To Do items, as these
should be generated via Chef, Puppet, etc. for complying with *one source of
truth*.)

## Automated Testing

Minimal test coverage exists.

Run from subdirectory containing Python modules: (should be same as
containing this README file)

	python -m unittest tests/*.py
    
Alternatively, run:

	make docker-test
    
## Manual Testing

The following sequence confirms:

- Building Docker container
- Adding a URL from the known phishing list
- Adding same URL, but system gracefully and ergonomically handles the duplicate
- Apply list of known phishing URLs
- Note the offending URL and its short URI have both been purged
- Add a new URL, observe that the encoded sequence number has increased.
- When manually updating the sequence number between runs, the system uses
  this newer value.
- Manually creating a reserved Short URI causes sequence number to skip this
  value when adding a new Full URL via HTML Form

### Applying Anti-Phishing Maintenance Purges Offending Short URIs

First, clear all data.  This will invoke `sudo` because some files may
have been owned by `root` from within the Docker container:

    make dist-clean

Build the container from scratch:

    make docker-image

Different than instructions from `make all`, run **without** applying
anti-phishing URLs to demonstrate retroactive purge of offending URLs that have already been shortened:

    make docker-run

Connect web browser to [http://localhost:8088/](http://localhost:8088/), and enter the following (not a clickable link, because it's phishy, so **DON'T** follow it-- you've been warned) address:

	http://sonicboommusic.com.au/administrator/templates/khepri/dhl2/dhl.htm

While there, go back to [http://localhost:8088/](http://localhost:8088/),
and attempt adding it again.  Confirm message from Docker stdout that this
was marked **status=DUPLICATE**.

Leave that browser window/tab open (because we'll have you confirm that the
link no longer forwards-- **but do not click it yet**-- in a moment).

Stop the running Docker process-- press **Ctrl C** to exit.

Run the maintenance procedure: (note: this manual step is an interim
measure; see #Implementation To Do items)

    make docker-maint

Messages from Docker stdout should indicate *removing* the Short URI.

Finally, return to nominal operations:

    make docker-run
    
Now, attempt clicking on the short URL that should still be visible in your
browser, and confirm that you were **not forwarded** to the offending URL.

### Manually Changing State (between runs)

Next, add a URL of your choosing and observe that the encoded sequence
number has changed.  Add several more and some attempted duplicates.

(Should you have forgotten to prefix a protocol scheme, the default of
`http://` is silently added for ergonomics-- possibly a mis-feature in need
of further consideration.)

Stop the server with **Ctrl C** again.

Replace contents of `sequence.dat` file with a triple digit integer or
larger plus Newline.

	echo 99999999 | sudo tee sequence.dat 

Start nominal server operations again:

    make docker-run

Add another URL and notice the sequence number has jumped.

### Manually Creating A Reserved/Vanity URI

Stop the server with **Ctrl C** again.

Clear all data, but this will invoke `sudo` because some files may have been
owned by `root` from within the Docker container:

	make clean-data
    
Create the subdirectory and file, `short/BA.txt`, containing a valid safe
full URL of our choosing.  (Due to clearing the data in previous step, there
should be no permission issues.)

	mkdir short
    echo 'https://play.org/articles/' > short/BA.txt

Start nominal server operations again:

    make docker-run

Click the following link:
[http://localhost:8088/BA](http://localhost:8088/BA)

(If that link *doesn't* work, did you manually change the contents of
sequence.dat` or `self.sequence_number` within url-shortener.py?)

Note that your web browser has been forwarded appropriately.

Next, add a different URL (we didn't create the corresponding CityHash-based
file that would check for duplicates, so this next one needs to be a new
URL) than before.

Observe that the encoded sequence number has skipped the manually created
entry's value.  (This is a feature accommodating reserved words such as
skipping offensive words in various natural languages as well as offering
vanity URIs as a premium product to generate revenue potentially paying for
the whole thing.)

## License

MIT License

Essentially, do as you wish and without warranty from authors or maintainers.
