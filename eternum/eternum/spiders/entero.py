import scrapy


class EnteroSpider(scrapy.Spider):
    name = "entero"
    allowed_domains = ["entero.by"]
    start_urls = ["https://entero.by/search.php?text=eternum&page=1"]
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://entero.by/",
        },
    }

    def parse(self, response):
        products = response.css("div.product-wrapper[data-index]")

        for product in products:
            product_id = product.css("::attr(data-index)").get()
            title = product.css("div.product-title a::text").get()
            product_url = product.css("div.product-title a::attr(href)").get()
            listing_image_url = product.css("a.product-image img::attr(src)").get()
            availability = product.css("div.product-status-badge::text").get()
            price = product.css("div.product-current-price::text").get()
            old_price = product.css("div.product-old-price::text").get()

            item = {
                "product_id": product_id.strip() if product_id else None,
                "sku": None,
                "title": title.strip() if title else None,
                "brand": "Eternum",
                "price": self._clean_text(price),
                "old_price": self._clean_text(old_price),
                "availability": self._clean_text(availability),
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
            response.css("a[rel='next']::attr(href)").get()
            or response.css("a.next_page::attr(href)").get()
            or response.css("a.next::attr(href)").get()
            or response.xpath(
                "//a[contains(@href, '/search.php') and (contains(., 'Следующая') or contains(., 'Next'))]/@href"
            ).get()
        )
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def parse_product(self, response):
        item = response.meta["item"]

        title = response.css("h1[itemprop='name']::text").get()
        sku = response.css("b[itemprop='sku']::text").get()
        image_url = response.css("img[itemprop='image']::attr(src)").get()
        availability = response.css("span[itemprop='availability']::text").get()
        if not availability:
            availability = response.css("div.product_attributes span[style*='font-weight:bold']::text").get()

        price = response.css("div.price .price span::text").get()
        old_price = response.css("div.price .price span[style*='line-through']::text").get()

        description = " ".join(
            text.strip()
            for text in response.css("div.htmlcontent[itemprop='description'] *::text").getall()
            if text.strip()
        )

        brand_text = response.xpath(
            "normalize-space(//div[contains(@style,'Торговая марка')]/following-sibling::div[contains(@class,'htmlvendorcontent')][1])"
        ).get()

        item.update(
            {
                "title": self._clean_text(title) or item.get("title"),
                "sku": self._clean_text(sku) or item.get("product_id") or item.get("sku"),
                "brand": item.get("brand") if item.get("brand") else ("Eternum" if "eternum" in (brand_text or "").lower() else None),
                "price": self._clean_text(price) or item.get("price"),
                "old_price": self._clean_text(old_price) or item.get("old_price"),
                "availability": self._clean_text(availability) or item.get("availability"),
                "description": description or None,
                "image_url": response.urljoin(image_url) if image_url else item.get("listing_image_url"),
                "detail_image_url": response.urljoin(image_url) if image_url else item.get("listing_image_url"),
                "image_urls": [response.urljoin(image_url)] if image_url else ([item["listing_image_url"]] if item.get("listing_image_url") else []),
                "product_page": response.url,
            }
        )

        yield item

    def parse_product_error(self, failure):
        item = failure.request.meta["item"]
        item["product_page"] = item.get("url")
        item["image_url"] = item.get("listing_image_url")
        item["detail_image_url"] = item.get("listing_image_url")
        item["image_urls"] = [item["listing_image_url"]] if item.get("listing_image_url") else []
        item["detail_error"] = str(failure.value)
        yield item

    @staticmethod
    def _clean_text(value):
        if not value:
            return None
        return " ".join(value.split())
