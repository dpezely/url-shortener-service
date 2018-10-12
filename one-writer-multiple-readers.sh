#! /bin/sh

# For one writer & potentially multiple readers-- let OS scheduler
# facilitate multiprocessing (without Python GIL limitations).

nginx &

# Multiple read-only apps:
# (When changing, be sure to also uncomment equivalent `upstream`
# ports within nginx.conf)
for p in $(seq 8010 8014)
do
    ./url-shortener.py -p $p &
done

echo "Connect web broswer to http://localhost:8088/"
echo "Use keyboard interrupt (^C) to exit server within Docker container"

# One writer app:
./url-shortener.py -p 8000 --display Localhost:8088
