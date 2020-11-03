from scrapy.cmdline import execute

asyncioreactor.install(asyncio.get_event_loop())

if __name__ == '__main__':
    execute()
