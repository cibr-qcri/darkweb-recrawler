# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/items.html

import scrapy


class TorspiderItem(scrapy.Item):
    page = scrapy.Field()
    url = scrapy.Field()
    domain = scrapy.Field()
    title = scrapy.Field()
    is_landing_page = scrapy.Field()
    external_links_web = scrapy.Field()
    external_links_tor = scrapy.Field()
