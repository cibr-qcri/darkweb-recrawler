import hashlib

from scrapy_redis.dupefilter import RFPDupeFilter


class CustomRFPDupeFilter(RFPDupeFilter):
    def request_fingerprint(self, request):
        url = request.url
        return hashlib.sha1(url.encode("utf-8")).hexdigest()
