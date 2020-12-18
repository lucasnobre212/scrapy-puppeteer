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
        middleware.browser = await launch(logLevel=crawler.settings.get('LOG_LEVEL'), headless=False)
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
        if request.incognito:
            context = await self.browser.createIncognitoBrowserContext()
            page = await context.newPage()
        else:
            page = await self.browser.newPage()

        # Cookies
        if isinstance(request.cookies, dict):
            await page.setCookie(*[
                {'name': k, 'value': v}
                for k, v in request.cookies.items()
            ])
        else:
            for cookie in request.cookies:
                await page.setCookie(cookie)

        if request.replace_headers:
            headers = {k.decode(): ','.join(map(lambda v: v.decode(), v)) for k, v in request.headers.items()}
            await page.setExtraHTTPHeaders(headers)

        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36')
        response = await page.goto(
            request.url,
            {
                'waitUntil': request.wait_until,
                'timeout': 120000,
            },
        )

        if request.select_element:
            # {'element_selector': {'action': '', 'value': ''}
            for element_selector, instructions in request.select_element.items():
                await page.waitForSelector(element_selector)
                element_handle = await page.querySelector(element_selector)
                action = instructions.get('action')
                action_value = instructions.get('value')
                if action == 'click':
                    await element_handle.focus()
                    await element_handle.click()
                elif action == 'type':
                    await element_handle.focus()
                    await element_handle.type(action_value)
                else:
                    raise CloseSpider('Unkown action')
                await asyncio.sleep(1)

        if request.exec_pup:
            exec(request.exec_pup)
        if request.wait_for:
            await page.waitFor(request.wait_for,
                               timeout=120000)

        if request.screenshot:
            request.meta['screenshot'] = await page.screenshot()
           
        if request.screenshot_element:
            element_ss_selector = request.screenshot_element
            await page.waitForSelector(element_ss_selector)
            element_ss = await page.querySelector(element_ss_selector)
            request.meta['element_ss'] = await element_ss.screenshot()


        content = await page.content()
        pyp_cookies = await page.cookies()
        request.cookies = pyp_cookies
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

        if not isinstance(request, PuppeteerRequest):
            return None

        return as_deferred(self._process_request(request, spider))

    async def _spider_closed(self):
        await self.browser.close()

    def spider_closed(self):
        """Shutdown the browser when spider is closed"""

        return as_deferred(self._spider_closed())
