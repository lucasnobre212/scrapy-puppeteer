from scrapy.cmdline import execute
from twisted.internet import asyncioreactor
import asyncio


asyncioreactor.install(asyncio.get_event_loop())

if __name__ == '__main__':
    execute()
