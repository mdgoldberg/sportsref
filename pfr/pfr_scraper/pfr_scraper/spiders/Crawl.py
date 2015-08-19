# -*- coding: utf-8 -*-
import scrapy
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule

from pfr_scraper.items import PfrScraperItem


class CrawlSpider(CrawlSpider):
    name = 'Crawl'
    allowed_domains = ['http://www.pro-football-reference.com']
    start_urls = ['http://www.http://www.pro-football-reference.com/']

    rules = (
        Rule(LinkExtractor(allow=r'Items/'), callback='parse_item', follow=True),
    )

    def parse_item(self, response):
        i = PfrScraperItem()
        #i['domain_id'] = response.xpath('//input[@id="sid"]/@value').extract()
        #i['name'] = response.xpath('//div[@id="name"]').extract()
        #i['description'] = response.xpath('//div[@id="description"]').extract()
        return i
