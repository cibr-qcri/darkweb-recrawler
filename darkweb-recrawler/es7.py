from elasticsearch import Elasticsearch
from scrapy.utils.project import get_project_settings

from .singleton import Singleton


class ES7(metaclass=Singleton):

    def __init__(self):
        self.settings = get_project_settings()
        server = self.settings['ELASTICSEARCH_CLIENT_SERVICE_HOST']
        port = int(self.settings['ELASTICSEARCH_CLIENT_SERVICE_PORT'])
        self.index = self.settings['ELASTICSEARCH_INDEX']
        self.es = Elasticsearch([server], scheme="http", port=port, timeout=50, max_retries=10, retry_on_timeout=True)

    def persist_report(self, report, es_id):
        self.es.index(index=self.index, id=es_id, body=report)
