### Dockerfile 

### Usage:
### docker build -t url-shortener .
### docker run -it --rm -v $(pwd):/data -v $(pwd)/htdocs:/var/www/html \
###   -p 8088:80  url-shortener ./one-writer-multiple-readers.sh

FROM alpine
RUN apk update
RUN apk add --update python3 python3-dev g++
RUN pip3 install --upgrade pip
RUN apk add nginx

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
# COPY one-writer-multiple-readers.sh .
# ENTRYPOINT /project/one-writer-multiple-readers.sh

# Location for mounting directory tree of URLs:
RUN mkdir /data
WORKDIR /data

# Configure and start HTTP service in background:
RUN rm -f /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/url-shortener.conf

# Work-around bug from PID file location not being created:
RUN mkdir -p /run/nginx/

RUN nginx -t

# Only Nginx port needs to be exposed, as app uses internal communications:
expose 80
