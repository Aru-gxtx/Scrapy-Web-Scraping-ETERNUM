import scrapy


class LibertySpider(scrapy.Spider):
    name = "liberty"
    allowed_domains = ["www.liberty-ua.com"]
    start_urls = [
        "https://www.liberty-ua.com/ua/products/all?search_block_form=ETERNUM"
        "&op=%D0%9F%D0%BE%D1%88%D1%83%D0%BA%20%D0%BF%D0%BE%20%D1%81%D0%B0%D0%B9%D1%82%D1%83&page=0"
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
            "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8,en;q=0.7",
            "Referer": "https://www.liberty-ua.com/ua/",
        },
    }

    def parse(self, response):
        products = response.css("div.view-content div.views-row")
        seen_urls = set()

        for product in products:
            title = product.css("div.views-field-title-field a::text").get()
            product_url = product.css("div.views-field-title-field a::attr(href)").get()
            listing_image_url = product.css("div.views-field-field-product-photo img::attr(src)").get()
            availability = product.css("div.views-field-sclad .field-content::text").get()
            price_value = product.css("div.views-field-field-product-price div.price::text").get()
            currency = product.css("div.views-field-field-product-price div.price div::text").get()
            product_id = product.css("span.basket_addto_basket_inner::attr(data-nid)").get()

            absolute_url = response.urljoin(product_url) if product_url else None
            if absolute_url in seen_urls:
                continue
            if absolute_url:
                seen_urls.add(absolute_url)

            item = {
                "product_id": self._clean_text(product_id),
                "sku": self._clean_text(product_id),
                "title": self._clean_text(title),
                "brand": "Eternum",
                "price": self._join_price(price_value, currency),
                "availability": self._clean_text(availability),
                "listing_image_url": response.urljoin(listing_image_url)
                if listing_image_url
                else None,
                "url": absolute_url,
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

        next_page = response.css("li.pager-next a::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def parse_product(self, response):
        item = response.meta["item"]

        title = (
            response.css("meta[property='og:title']::attr(content)").get()
            or response.css("meta[name='description']::attr(content)").get()
            or response.css(".product_title h1::text, h1.node-title::text").get()
            or response.css("h1::text").get()
        )
        price_value = response.css("div.product_tright_section div.prices div.price::text").get()
        currency = response.css("div.product_tright_section div.prices div.price span::text").get()
        availability = response.css("div.product_tright_section .check_for_manager span::text").get()
        product_id = response.css("span.basket_addto_basket_inner::attr(data-nid)").get()

        description = " ".join(
            text.strip()
            for text in response.css("div.product_desc_wrap *::text, div.full_info_wrap *::text").getall()
            if text.strip()
        )
        if not description:
            description = self._clean_text(response.css("meta[name='description']::attr(content)").get())

        detail_images = response.css(
            "div.product_tmiddle_section div.product_photo_slider div.big_img img::attr(src), "
            "div.product_tmiddle_section div.product_nav_slider img::attr(src)"
        ).getall()

        unique_images = []
        for image_url in detail_images:
            absolute_url = response.urljoin(image_url)
            if absolute_url and absolute_url not in unique_images:
                unique_images.append(absolute_url)

        item.update(
            {
                "product_id": self._clean_text(product_id) or item.get("product_id"),
                "sku": self._clean_text(product_id) or item.get("sku"),
                "title": self._safe_title(self._clean_text(title), item.get("title")),
                "price": self._join_price(price_value, currency) or item.get("price"),
                "availability": self._clean_text(availability) or item.get("availability"),
                "description": description or None,
                "image_url": unique_images[0] if unique_images else item.get("listing_image_url"),
                "detail_image_url": unique_images[0] if unique_images else item.get("listing_image_url"),
                "image_urls": unique_images,
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

    @staticmethod
    def _join_price(value, currency):
        value_clean = " ".join(value.split()) if value else ""
        currency_clean = " ".join(currency.split()) if currency else ""

        if value_clean and currency_clean:
            return f"{value_clean} {currency_clean}"
        if value_clean:
            return value_clean
        return None

    @staticmethod
    def _safe_title(detail_title, fallback_title):
        if not detail_title:
            return fallback_title

        normalized = detail_title.lower()
        if "каталог" in normalized or normalized == "catalog":
            return fallback_title

        return detail_title
