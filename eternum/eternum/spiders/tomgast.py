import scrapy


class TomgastSpider(scrapy.Spider):
    name = "tomgast"
    allowed_domains = ["tomgast.pl"]
    start_urls = [
        "https://tomgast.pl/en/catalogsearch/result/index/?p=1&product_list_limit=96&q=eternum"
    ]
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,pl;q=0.8",
            "Referer": "https://tomgast.pl/en/",
        },
    }

    def parse(self, response):
        products = response.css("li.product.product-item")

        for product in products:
            product_url = product.css("a.product-item-link::attr(href)").get()
            title = product.css("a.product-item-link::text").get()
            sku = product.css("div.sku_nr::text").get()
            brand = product.css("div.product-manufacturer img.logo::attr(alt)").get()
            listing_image_url = product.css("img.product-image-photo::attr(src)").get()

            price_excl = product.css(
                "span.price-excluding-tax span.price::text"
            ).get()
            price_incl = product.css(
                "span.price-including-tax span.price::text"
            ).get()

            product_id = product.css("form[data-role='tocart-form'] input[name='product']::attr(value)").get()

            item = {
                "product_id": product_id,
                "sku": sku.strip() if sku else None,
                "title": title.strip() if title else None,
                "brand": brand.strip() if brand else None,
                "price_excl_tax": price_excl.strip() if price_excl else None,
                "price_incl_tax": price_incl.strip() if price_incl else None,
                "listing_image_url": response.urljoin(listing_image_url)
                if listing_image_url
                else None,
                "url": response.urljoin(product_url) if product_url else None,
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

        next_page = (
            response.css("a.action.next::attr(href)").get()
            or response.css("li.pages-item-next a::attr(href)").get()
            or response.css("a.next::attr(href)").get()
        )
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def parse_product(self, response):
        item = response.meta["item"]

        title = response.css("h1.page-title span.base::text").get()
        sku = response.css("div.product.attribute.sku .value::text").get()

        detail_price_excl = response.css(
            "span.price-excluding-tax span.price::text"
        ).get()
        detail_price_incl = response.css(
            "span.price-including-tax span.price::text"
        ).get()

        description = " ".join(
            text.strip()
            for text in response.css("div.description-product *::text").getall()
            if text.strip()
        )

        image_urls = response.css("div.fotorama__stage__frame::attr(href)").getall()
        if not image_urls:
            image_urls = response.css("div.fotorama__stage img::attr(src)").getall()

        unique_image_urls = []
        for image_url in image_urls:
            absolute_url = response.urljoin(image_url)
            if absolute_url not in unique_image_urls:
                unique_image_urls.append(absolute_url)

        item.update(
            {
                "title": title.strip() if title else item.get("title"),
                "sku": sku.strip() if sku else item.get("sku"),
                "price_excl_tax": detail_price_excl.strip()
                if detail_price_excl
                else item.get("price_excl_tax"),
                "price_incl_tax": detail_price_incl.strip()
                if detail_price_incl
                else item.get("price_incl_tax"),
                "description": description or None,
                "image_url": unique_image_urls[0]
                if unique_image_urls
                else item.get("listing_image_url"),
                "image_urls": unique_image_urls,
                "product_page": response.url,
            }
        )

        yield item

    def parse_product_error(self, failure):
        item = failure.request.meta["item"]
        item["product_page"] = item.get("url")
        item["image_url"] = item.get("listing_image_url")
        item["image_urls"] = [item["listing_image_url"]] if item.get("listing_image_url") else []
        item["detail_error"] = str(failure.value)
        yield item
