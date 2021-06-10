import os
import re
from datetime import datetime
from hashlib import sha256

from scrapy_redis.pipelines import RedisPipeline

from .support import TorHelper
from .es7 import ES7


class TorspiderPipeline(RedisPipeline):

    def __init__(self, server):
        super().__init__(server)
        self.dirname = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.helper = TorHelper()
        self.date = datetime.today()
        self.es = ES7()

    def process_item(self, item, spider):
        url = item["url"]
        domain = item['domain']
        page = item['page']

        btc_addr_pat = re.compile(
            r"\b(1[a-km-zA-HJ-NP-Z1-9]{25,34})\b|\b(3[a-km-zA-HJ-NP-Z1-9]{25,34})\b|\b(bc1[a-zA-HJ-NP-Z0-9]{25,39})\b"
        )
        addr_list = set()
        for res in btc_addr_pat.findall(page):
            addr_list.update(set(res))

        addr_list = set(filter(self.helper.check_bc, addr_list))
        es_id = url + datetime.today().strftime("%d-%m-%y")
        es_id = sha256(es_id.encode("utf-8")).hexdigest()

        tag = {
            "timestamp": datetime.now().timestamp() * 1000,
            "type": "recrawl",
            "source": "tor",
            "method": "html",
            "info": {
                "domain": domain,
                "url": url,
                "title": item['title'],
                "external_urls": {
                    "href_urls": {
                        "web": item["external_links_web"],
                        "tor": item["external_links_tor"]
                    }
                },
                "tags": {
                    "cryptocurrency": {
                        "address": {
                            "btc": list(addr_list)
                        }
                    },
                    "hidden_service": {
                        "landing_page": item["is_landing_page"]
                    }
                }
            },
            "raw_data": page
        }


        '''try:
            self.write_to_file(page, domain, url)
        except :
            pass'''
        self.write_to_file(page, domain, url)

        self.es.persist_report(tag, es_id)

        return item

    def write_to_file(self, page, domain, url):
        current_date = datetime.today()
        if self.date != current_date:
            self.date = current_date
        path = "/mnt/data/{date}/{domain}".format(date=self.date.strftime("%d-%m-%y"), domain=domain)
        try:
            os.makedirs(path)
        except OSError:
            pass

        with open("{path}/{file}".format(path=path, file=url), "w+") as f:
            f.write(page)
