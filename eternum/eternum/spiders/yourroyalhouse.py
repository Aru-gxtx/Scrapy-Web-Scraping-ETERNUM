import scrapy


class YourroyalhouseSpider(scrapy.Spider):
    name = "yourroyalhouse"
    allowed_domains = ["yourroyalhouse.ge"]
    start_urls = ["https://yourroyalhouse.ge/en/product-category/eternum/page/1/"]
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-GB,en;q=0.9",
            "Referer": "https://yourroyalhouse.ge/",
        },
    }

    def parse(self, response):
        for product in response.css("li.type-product"):
            url = product.css("h3.product_title a::attr(href)").get()
            title = product.css("h3.product_title a::text").get()
            price = product.css("span.woocommerce-Price-amount bdi::text").get()
            image_url = product.css("figure.post-image img::attr(src)").get()
            sku = product.css("a.button::attr(data-product_sku)").get()

            item = {
                "sku": sku.strip() if sku else None,
                "title": title.strip() if title else None,
                "price": price.strip() if price else None,
                "image_url": image_url,
                "url": url,
                "source_page": response.url,
            }

            if url:
                yield scrapy.Request(
                    url,
                    callback=self.parse_product,
                    errback=self.parse_product_error,
                    meta={"item": item},
                )
            else:
                yield item

        # Follow "next page" pagination link
        next_page = response.css("a.next.page-numbers::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def parse_product(self, response):
        item = response.meta["item"]

        # Full-resolution image from the product gallery anchor
        full_image = response.css(
            "div.woocommerce-product-gallery__image a::attr(href)"
        ).get()
        if full_image:
            item["image_url"] = full_image

        # Short description (e.g. "Length: 182mm Thickness:2.5mm 18/10 stainless steel")
        description = " ".join(
            response.css(
                "div.woocommerce-product-details__short-description *::text"
            ).getall()
        ).strip()
        if not description:
            description = response.css(
                "meta[name='description']::attr(content)"
            ).get("").strip()
        item["description"] = description or None

        # SKU from product page span (more reliable than listing button attribute)
        sku = response.css("span.sku::text, [itemprop='sku']::text").get()
        if sku:
            item["sku"] = sku.strip()

        item["product_page"] = response.url
        yield item

    def parse_product_error(self, failure):
        item = failure.request.meta["item"]
        item["product_page"] = item.get("url")
        item["description"] = None
        item["detail_error"] = str(failure.value)
        yield item
