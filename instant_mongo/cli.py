import argparse
import logging
from time import sleep

from .instant_mongodb import InstantMongoDB


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dbpath', default='instant-mongo-data')
    p.add_argument('--port', type=int, default=27017)
    p.add_argument('--bind_ip', '--bind-ip', default='127.0.0.1')
    p.add_argument('--verbose', '-v', action='store_true')
    args = p.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)5s: %(message)s')
    im = InstantMongoDB(data_dir=args.dbpath, port=args.port, bind_ip=args.bind_ip,
        wired_tiger=True, wired_tiger_zlib=True)
    with im:
        while True:
            sleep(5)
