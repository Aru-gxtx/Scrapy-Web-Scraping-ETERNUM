import scrapy


class HorecaserviseSpider(scrapy.Spider):
    name = "horecaservise"
    allowed_domains = ["horecaservise.com.ua"]
    base_url = "https://horecaservise.com.ua/ru/posud/stolove-priladdya/eternum?page={}"
    max_pages = 28
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru,en-US;q=0.9,en;q=0.8",
            "Referer": "https://horecaservise.com.ua/",
        },
    }

    async def start(self):
        max_pages = int(self.max_pages)
        for page in range(1, max_pages + 1):
            yield scrapy.Request(self.base_url.format(page), callback=self.parse)

    def start_requests(self):
        max_pages = int(self.max_pages)
        for page in range(1, max_pages + 1):
            yield scrapy.Request(self.base_url.format(page), callback=self.parse)

    def parse(self, response):
        products = response.css("div.product-layout")

        for product in products:
            title = product.css("div.caption h4 a::text").get()
            url = product.css("div.caption h4 a::attr(href)").get()
            price = product.css("p.price::text").get()
            image_url = product.css("div.image a img::attr(src)").get()
            product_id = product.css("div.button-group button::attr(onclick)").re_first(r"cart\.add\('([^']+)'")

            item = {
                "title": title.strip() if title else None,
                "url": response.urljoin(url) if url else None,
                "price": " ".join(price.split()) if price else None,
                "image_url": image_url,
                "product_id": product_id,
                "source_page": response.url,
            }

            if item["url"]:
                yield scrapy.Request(
                    item["url"],
                    callback=self.parse_product,
                    errback=self.parse_product_error,
                    meta={"item": item},
                )
            else:
                yield item

    def parse_product(self, response):
        item = response.meta["item"]
        detail_image_url = response.css("li a.thumbnail::attr(href)").get()
        detail_image_urls = response.css("li a.thumbnail::attr(href)").getall()

        item["detail_image_url"] = response.urljoin(detail_image_url) if detail_image_url else None
        item["detail_image_urls"] = [response.urljoin(url) for url in detail_image_urls]
        item["product_page"] = response.url

        yield item

    def parse_product_error(self, failure):
        item = failure.request.meta["item"]
        item["detail_image_url"] = None
        item["detail_image_urls"] = []
        item["product_page"] = item.get("url")
        item["detail_error"] = str(failure.value)
        yield item
