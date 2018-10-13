# Makefile for URL Shortener

all:
	@echo "Usage:"
	@echo ""
	@echo "For creating and using Docker container, use:"
	@echo "  make docker-image docker-maint docker-run"
	@echo ""
	@echo "For shell access within Docker container, run:"
	@echo "  make docker-image docker-dev"
	@echo ""
	@echo "When running locally on Linux (Debian/Ubuntu), use:"
	@echo "  make apt deps anti-phishing run"
	@echo ""
	@echo "For each of those, connect web browser to http://localhost:8088/"

# IP Port number accessible from outside the Docker container:
PORT=8088

.PHONY: apt
apt:
	@echo Invoking sudo for `apt-get install`
	sudo apt-get install python3 python3-pip nginx jq

.PHONY: deps
deps: dependencies

.PHONY: dependencies
dependencies:
	pip3 install -r requirements.txt

.PHONY: test
test:
	python3 -m unittest tests/*.py

.PHONY: run
run:
	./one-writer-multiple-readers.sh

online-valid.json.bz2:
	wget -N http://data.phishtank.com/data/online-valid.json.bz2

known-phishing-urls.txt: online-valid.json.bz2
	bunzip2 < online-valid.json.bz2 | \
	  jq '.[] | {url} | .url' > known-phishing-urls.txt

anti-phishing: known-phishing-urls.txt
	./url-shortener.py --anti-phishing known-phishing-urls.txt

.PHONY: docker-image
docker-image:
	docker build -t url-shortener .

.PHONY: docker-run
docker-run:
	docker run -it --rm \
	  -v $(shell pwd):/data -v $(shell pwd)/htdocs:/var/www/html \
	  -p ${PORT}:80 \
	  url-shortener ./one-writer-multiple-readers.sh

# This one gives you a Bash prompt:
.PHONY: docker-dev
docker-dev:
	docker run -it --rm \
	  -v $(shell pwd):/data -v $(shell pwd)/htdocs:/var/www/html \
	  -p ${PORT}:80 \
	  url-shortener

.PHONY: docker-test
docker-test:
	docker run -it --rm \
	  -v $(shell pwd):/data -v $(shell pwd)/htdocs:/var/www/html \
	  -p ${PORT}:80 \
	  url-shortener python3 -m unittest tests/*.py

# For off-line maintenance of updating anti-phishing protection:
# (note omission of other volumes and no IP port binding)
.PHONY: docker-maint
docker-maint: docker-maintenance
.PHONY: docker-maintenance
docker-maintenance: known-phishing-urls.txt
	docker run -it --rm \
	  -v $(shell pwd):/data \
	  url-shortener ./url-shortener.py \
	      --anti-phishing known-phishing-urls.txt

.PHONY: clean
clean:
	@echo 'invoking `sudo` to remove files created within Docker container'
	sudo rm -rf '__pycache__'
	sudo find . -name '*.pyc' -delete
	find . -name '*~' -delete

.PHONY: clean-data
clean-data:
	@echo 'invoking `sudo` to remove files created within Docker container'
	sudo rm -rf sequence.dat full short \
	  anti-phish anti-phish.????-??-??T*

.PHONY: dist-clean
dist-clean: clean-data clean
	rm -f known-phishing-urls.txt online-valid.json.bz2
	docker rmi url-shortener || true
