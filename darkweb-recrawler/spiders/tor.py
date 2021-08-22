import base64
import hashlib
import os
import re
from datetime import datetime

from bs4 import BeautifulSoup
from scrapy_redis.spiders import RedisSpider

from ..items import TorspiderItem
from ..support import TorHelper

ONION_PAT = re.compile(r"(?:https?://)?(([^/.]*)\.)*(\w{56}|\w{16})\.onion")


class TorSpider(RedisSpider):
    name = "darkweb-recrawler"

    def __init__(self):
        RedisSpider.__init__(self)
        self.helper = TorHelper()
        self.site_info = {}
        self.seq_number = 0
        self.dirname = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.domain_count = dict()

    def make_requests_from_url(self, url):
        return TorHelper.build_splash_request(url, callback=self.parse)

    def parse(self, response):
        history = response.data['history']
        last_response = history[-1]["response"]
        redirect_status = response.data['redirect_status']

        requested_url = response.url.strip("/")
        url = last_response["url"].strip("/")
        scheme = self.helper.get_scheme(url)
        domain = self.helper.get_domain(url)

        http_redirect, other_redirect = self.helper \
            .build_redirect_paths(history, response.data["http_redirects"], requested_url, url)
        self.helper.persist_http_redirects(http_redirect)

        js_files = response.data["js"]
        css_files = response.data["css"]

        for rurl, meta in other_redirect.items():
            if meta["type"] == "meta":
                yield TorHelper\
                    .build_splash_request(rurl, callback=self.parse, wait=meta["wait"], to=meta["to"], type="meta")
            else:
                yield TorHelper.build_splash_request(rurl, callback=self.parse, to=meta["to"], type="js")

        rendered_page = response.data["rendered"]
        raw_page = str(base64.b64decode(last_response["content"]["text"]))

        headers = dict()
        for entry in last_response["headers"]:
            headers[entry["name"].lower()] = entry["value"]

        soup_rendered = BeautifulSoup(rendered_page, "lxml")
        urls = self.helper.extract_all_urls(url, domain, scheme, soup_rendered)

        if ONION_PAT.match(url):
            domain_key = domain.replace('.onion', '')
            self.server.sadd(domain_key, url)

            item = TorspiderItem()
            item["date"] = datetime.today()
            item["url"] = url
            item['domain'] = domain
            item["scheme"] = self.helper.get_scheme(url)
            item['title'] = soup_rendered.title.string.strip() \
                if soup_rendered.title and soup_rendered.title.string else ""
            item['scheme'] = scheme
            item["homepage"] = self.helper.is_home_page(requested_url)
            item['urls'] = urls
            item["version"] = 3 if len(domain.replace(".onion", "")) > 16 else 2
            item["response_header"] = headers
            item["btc"] = self.helper.get_btc(soup_rendered)
            item["rendered_page"] = rendered_page
            item["raw_page"] = raw_page
            item["raw_md5"] = hashlib.md5(raw_page.encode('utf-8')).hexdigest(),
            item["js"] = len(soup_rendered.find_all('script')) > 0
            item["css"] = len(soup_rendered.find_all('style')) > 0
            item["screenshot"] = base64.b64decode(response.data['jpeg'])
            item["js_files"] = js_files
            item["css_files"] = css_files

            if "redirect_type" in redirect_status and redirect_status["redirect_type"]:
                item["redirect"] = {
                    "url": redirect_status["redirect_to"],
                    "type": redirect_status["redirect_type"]
                }

            yield item

            for u in sorted(urls["internal"]["anchor"]):
                domain_count = self.server.scard(domain_key)
                if domain_count >= 30:
                    break
                if ONION_PAT.match(u) and u != url and self.helper.get_domain(u) == domain:
                    self.server.sadd(domain_key, u)
                    yield TorHelper.build_splash_request(u, callback=self.parse)

            external_domains_http = [self.helper.unify(self.helper.get_domain(u), "http") for u in
                                     urls["external"]["anchor"]]
            external_domains_https = [self.helper.unify(self.helper.get_domain(u), "https") for u in
                                      urls["external"]["anchor"]]
            external_domains = [*external_domains_http, *external_domains_https]
            if len(external_domains) > 0:
                self.server.lpush('sup-darkweb-crawler:start_urls', *external_domains)
