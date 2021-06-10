import os
import re
from hashlib import sha256
from urllib.parse import urlparse

import redis


request_count = dict()


class TorHelper:
    @staticmethod
    def get_redis_connection():
        conn = redis.Redis(host=os.getenv("REDIS_MASTER_SERVICE_HOST"),
                           port=os.getenv("REDIS_MASTER_SERVICE_PORT"), db=0, decode_responses=True)
        return conn

    def __init__(self):
        self.requests = dict()
        pass

    def outlinks(self, domain):
        client = self.get_redis_connection()
        return client.scard(domain)

    def append_outlink(self, from_domain, to_domain):
        if from_domain != to_domain:
            client = self.get_redis_connection()
            client.sadd(from_domain, to_domain)

    def increment_domain_count(self, domain):
        client = self.get_redis_connection()
        client.sadd(domain + '_c', 1)

    def domain_count(self, domain):
        client = self.get_redis_connection()
        return client.scard(domain + '_c')

    @staticmethod
    def unify(url):
        if not url:
            return ""
        if url.startswith("http://") or url.startswith("https://"):
            pass
        else:
            url = "http://" + url
        return url.strip("/")

    @staticmethod
    def get_domain(url):
        net_loc = urlparse(url).netloc
        domain_levels = re.split("[.:]", net_loc)
        for idx, oni in enumerate(domain_levels):
            if idx == 0:
                continue
            if oni == "onion" and len(domain_levels[idx - 1]) in (16, 56):
                return domain_levels[idx - 1] + "." + oni

        return net_loc

    @staticmethod
    def decode_base58(bc, length):
        digits58 = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
        n = 0
        for char in bc:
            n = n * 58 + digits58.index(char)
        return n.to_bytes(length, 'big')

    def check_bc(self, bc):
        try:
            bcbytes = self.decode_base58(bc, 25)
            return bcbytes[-4:] == sha256(sha256(
                bcbytes[:-4]).digest()).digest()[:4]
        except:
            return False
