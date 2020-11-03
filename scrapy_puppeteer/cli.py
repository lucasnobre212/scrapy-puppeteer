import asyncio
import sys
from twisted.internet import asyncioreactor

# Need to install the asyncio reactor before importing Scrapy (?)
# Maybe there is a cleaner way to to it?
asyncioreactor.install(asyncio.get_event_loop())

from scrapy.cmdline import execute


def scrapyp_execute():
    execute(argv=sys.argv)

if __name__ == '__main__':
    scrapyp_execute()
