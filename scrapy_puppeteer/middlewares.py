"""This module contains the ``SeleniumMiddleware`` scrapy middleware"""

import asyncio

from pyppeteer import launch
from scrapy import signals
from scrapy.http import HtmlResponse
from twisted.internet.defer import Deferred

from .http import PuppeteerRequest


def as_deferred(f):
    """Transform a Twisted Deffered to an Asyncio Future"""

    return Deferred.fromFuture(asyncio.ensure_future(f))


class PuppeteerMiddleware:
    """Downloader middleware handling the requests with Puppeteer"""

    @classmethod
    async def _from_crawler(cls, crawler):
        """Start the browser"""

        middleware = cls()
        middleware.browser = await launch(logLevel=crawler.settings.get('LOG_LEVEL'))
        crawler.signals.connect(middleware.spider_closed, signals.spider_closed)

        return middleware

    @classmethod
    def from_crawler(cls, crawler):
        """Initialize the middleware"""

        loop = asyncio.get_event_loop()
        middleware = loop.run_until_complete(
            asyncio.ensure_future(cls._from_crawler(crawler))
        )

        return middleware

    async def _process_request(self, request, spider):
        """Handle the request using Puppeteer"""

        # Create new incognito browser
        context = await self.browser.createIncognitoBrowserContext()
        page = await context.newPage()

        # Cookies
        if isinstance(request.cookies, dict):
            await page.setCookie(*[
                {'name': k, 'value': v}
                for k, v in request.cookies.items()
            ])
        else:
            for cookie in request.cookies:
                await page.setCookie(cookie)

        # The headers must be set using request interception
        if request.replace_headers:
            headers = {k.decode(): ','.join(map(lambda v: v.decode(), v)) for k, v in request.headers.items()}
            await page.setExtraHTTPHeaders(headers)
            # page.on('request', onMediaInfoIntercept)
            #
            # @page.on('request')
            # async def _handle_headers(pu_request):
            #     overrides = {
            #         'headers': {
            #             k.decode(): ','.join(map(lambda v: v.decode(), v))
            #             for k, v in request.headers.items()
            #         }
            #     }
            #     await pu_request.continue_(overrides=overrides)
        response = await page.goto(
            request.url,
            {
                'waitUntil': request.wait_until
            },
        )
        if request.select_element:
            for element in request.select_element:
                element_selector = element
                print(element)
                await page.waitForSelector(element_selector)
                element_handle = await page.querySelector(element_selector)
                print(element_handle)
                if request.action:
                    for action in request.action:
                        if action == 'click':
                            await element_handle.focus()
                            await element_handle.click({'delay': 1000})
                        if action == 'type':
                            await element_handle.focus()
                            await element_handle.type(request.send_value)

        if request.exec_pup:
            exec(request.exec_pup)
        if request.wait_for:
            await page.waitFor(request.wait_for)

        if request.screenshot:
            request.meta['screenshot'] = await page.screenshot()


        content = await page.content()
        body = str.encode(content)
        await page.close()

        # Necessary to bypass the compression middleware (?)
        response.headers.pop('content-encoding', None)
        response.headers.pop('Content-Encoding', None)

        return HtmlResponse(
            page.url,
            status=response.status,
            headers=response.headers,
            body=body,
            encoding='utf-8',
            request=request
        )

    def process_request(self, request, spider):
        """Check if the Request should be handled by Puppeteer"""
        
        if not isinstance(request, PuppeteerRequest) and 'pyppeteer' not in request.meta:
            return None

        return as_deferred(self._process_request(request, spider))

    async def _spider_closed(self):
        await self.browser.close()

    def spider_closed(self):
        """Shutdown the browser when spider is closed"""

        return as_deferred(self._spider_closed())
