### Dockerfile 

### Usage:
### docker build -t url-shortener .
### docker run -it --rm -v $(pwd):/data -v $(pwd)/htdocs:/var/www/html \
###   -p 8088:80  url-shortener ./one-writer-multiple-readers.sh

FROM ubuntu:18.04
ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update && apt-get dist-upgrade -y
RUN apt-get install -y python3 python3-pip nginx
RUN pip3 install --upgrade pip

RUN mkdir /project
WORKDIR /project

COPY requirements.txt .
RUN pip3 install -r requirements.txt

# Avoid copying python files into container to re-inforce that durable
# storage exists externally.  This also facilitates iterating on those
# files during development.

# Only for release, may these become candidates for inclusion here:
# COPY url-shortener.py .
# COPY base62ish.py .
# COPY nginx.conf .

# Location for mounting directory tree of URLs:
RUN mkdir /data
WORKDIR /data

# Configure and start HTTP service in background:
RUN rm -f /etc/nginx/sites-enabled/default
COPY nginx.conf /etc/nginx/sites-available/url-shortener
RUN ln -s /etc/nginx/sites-available/url-shortener /etc/nginx/sites-enabled/
RUN nginx -t

# COPY one-writer-multiple-readers.sh .
# ENTRYPOINT one-writer-multiple-readers.sh

# Only Nginx port needs to be exposed, as app uses internal communications:
expose 80
