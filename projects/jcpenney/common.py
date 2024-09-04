import re


async def cancel_requests(page):
    """
    取消无效的请求
    """

    async def cancel_request(route, request):
        # print(request.url)
        await route.abort()

    await page.route(
        re.compile(
            r"(\.png)|(\.jpg)|(\.jpeg)|(\.jpeg)|(\.avif)|(\.webp)|(\.gif)|(\.svg)|(\.woff)|(\.woff2)"
        ),
        cancel_request,
    )

    await page.route("**image/**", cancel_request)
    await page.route("**images/**", cancel_request)
    await page.route("*image/jcpenney/*", cancel_request)
    await page.route("*image/JCPenney/*", cancel_request)
    await page.route("*image/jcpenneyimages/*", cancel_request)
    await page.route("*image/JCPenneyimages/*", cancel_request)
    await page.route("**jcpenney.scene7.com/**", cancel_request)
    await page.route("*.bing.com/*", cancel_request)
    await page.route("*.googletagmanager.com/*", cancel_request)
    await page.route("*.google-analytics.com/*", cancel_request)
    await page.route("*.paypal.com/*", cancel_request)
    await page.route("*.doubleclick.net/*", cancel_request)
    await page.route("*.googleadservices.com/*", cancel_request)
    await page.route("*.snapchat.com/*", cancel_request)
    await page.route("*.pinterest.com/*", cancel_request)
    await page.route("*.tiktok.com/*", cancel_request)
    await page.route("*.quantummetric.com/*", cancel_request)
    await page.route("*.googlesyndication.com/*", cancel_request)
    await page.route("*.sharethrough.com/*", cancel_request)
    await page.route("*.media.net/*", cancel_request)
    await page.route("*.ad.gt/*", cancel_request)
    await page.route("*.vergic.com/*", cancel_request)
    await page.route("*.ccgateway.net/*", cancel_request)
    await page.route("*.floors.dev.net/*", cancel_request)
    await page.route("*.amazon-adsystem.com/*", cancel_request)
    await page.route("*.criteo.com/*", cancel_request)
    await page.route("*.bidswitch.net/*", cancel_request)
    await page.route("*.adform.net/*", cancel_request)
    await page.route("*.kampyle.com/*", cancel_request)
    await page.route("*.truefitcorp.com/*", cancel_request)
