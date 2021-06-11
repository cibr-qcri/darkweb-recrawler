import os
import re
from urllib.parse import urljoin

import scrapy
from bs4 import BeautifulSoup
from scrapy.spidermiddlewares.httperror import HttpError
from scrapy_redis.spiders import RedisSpider
from twisted.internet.error import DNSLookupError

from ..es7 import ES7
from ..items import TorspiderItem
from ..support import TorHelper

ONION_PAT = re.compile(r"(?:https?://)?(([^/.]*)\.)*(\w{56}|\w{16})\.onion")


class TorSpider(RedisSpider):
    name = "darkweb-recrawler"
    start_source = {}
    log_timeval = 3600
    tor_ref_timeval = 600
    seq_number = 0

    def __init__(self):
        RedisSpider.__init__(self)
        self.helper = TorHelper()
        self.site_info = {}
        self.seq_number = 0
        self.dirname = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.domain_count = dict()
        # self.es = ES7()

    '''
    def start_requests(self):
        self.start_urls = self.get_start_urls()
        for url in self.start_urls:
            yield scrapy.Request(url, dont_filter=False, callback=self.parse, errback=self.handle_error)
    '''

    def parse(self, response):
        url = self.helper.unify(response.url)
        domain = self.helper.get_domain(url)

        soup = BeautifulSoup(response.text, "lxml")
        url_links = set(self.helper.unify(urljoin(url, a.get("href"))) for a in soup.find_all("a"))

        if ONION_PAT.match(response.url):
            domain_key = domain.replace('.onion', '')
            domain_first = self.server.sadd('domains', domain_key)
            self.server.sadd(domain_key, url)

            external_links_tor = list()
            external_links_web = list()
            item = TorspiderItem()
            item["url"] = url
            item['page'] = response.text
            item['url'] = url
            item['domain'] = domain
            item['title'] = soup.title.string.strip() if soup.title else ""
            item["is_landing_page"] = domain_first > 0
            for u in url_links:
                if self.helper.get_domain(u) != domain:
                    if ONION_PAT.match(u):
                        external_links_tor.append(u)
                    else:
                        external_links_web.append(u)
            item['external_links_tor'] = external_links_tor
            item['external_links_web'] = external_links_web

            yield item

            if ONION_PAT.match(response.url):
                for u in sorted(url_links):
                    domain_count = self.server.scard(domain_key)
                    if domain_count >= 50:
                        break
                    if ONION_PAT.match(u) and u != url:
                        if self.helper.get_domain(u) == domain:
                            u = u.replace("onion.link", "onion")
                            self.server.sadd(domain_key, u)
                            yield scrapy.Request(u, dont_filter=False, callback=self.parse, errback=self.handle_error)
                        else:
                            pass  # Push into Redis

    def handle_error(self, failure):
        self.logger.debug(repr(failure))
        if failure.check(HttpError):
            response = failure.value.response
            self.logger.error('HttpError on %s', response.url)
        elif failure.check(DNSLookupError):
            request = failure.request
            self.logger.error('DNSLookupError on %s', request.url)
        elif failure.check(TimeoutError):
            request = failure.request
            self.logger.error('TimeoutError on %s', request.url)

    '''
    def get_start_urls(self):
        domains = self.es.get_domains()
        return [self.helper.unify(domain) for domain in domains]
    '''
