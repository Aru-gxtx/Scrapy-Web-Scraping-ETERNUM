import scrapy
import json
from urllib.parse import urlparse, parse_qs


class ZakazSpider(scrapy.Spider):
    name = "zakaz"
    allowed_domains = ["ultramarket.zakaz.ua", "stores-api.zakaz.ua"]
    search_query = "eternum"
    per_page = 30
    store_id = "48277601"
    search_api_url = (
        "https://stores-api.zakaz.ua/stores/{store_id}/products/search/"
        "?q={query}&page=1&per_page={per_page}"
    )
    custom_settings = {
        "ROBOTSTXT_OBEY": False,
        "USER_AGENT": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "DEFAULT_REQUEST_HEADERS": {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://ultramarket.zakaz.ua/",
        },
    }

    async def start(self):
        url = self.search_api_url.format(
            store_id=self.store_id,
            query=self.search_query,
            per_page=self.per_page,
        )
        yield scrapy.Request(url, callback=self.parse_search)

    def parse_search(self, response):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError:
            self.logger.error("Could not decode search API JSON: %s", response.url)
            return

        results = data.get("results") or []
        count = data.get("count") or 0

        seen_urls = set()

        for product in results:
            product_url = product.get("web_url")
            if not product_url or product_url in seen_urls:
                continue

            seen_urls.add(product_url)

            image_map = product.get("img") or {}
            listing_image_url = (
                image_map.get("s150x150")
                or image_map.get("s200x200")
                or image_map.get("s350x350")
            )
            detail_image_url = (
                image_map.get("s350x350")
                or image_map.get("s200x200")
                or image_map.get("s150x150")
                or listing_image_url
            )

            title = product.get("title")
            price_minor = product.get("price")
            currency = (product.get("currency") or "").upper()

            product_key = product.get("ean") or product.get("sku")

            item = {
                "product_key": product_key,
                "title": title.strip() if title else None,
                "price": self._format_price(price_minor, currency),
                "listing_image_url": listing_image_url,
                "image_url": detail_image_url,
                "url": product_url,
                "product_page": product_url,
                "source_page": response.url,
            }

            yield item

        query = parse_qs(urlparse(response.url).query)
        current_page = int((query.get("page") or [1])[0])

        if current_page * self.per_page < count and results:
            next_page = current_page + 1
            next_url = (
                "https://stores-api.zakaz.ua/stores/"
                f"{self.store_id}/products/search/?q={self.search_query}"
                f"&page={next_page}&per_page={self.per_page}"
            )
            yield scrapy.Request(next_url, callback=self.parse_search)

    def parse_product(self, response):
        item = response.meta["item"]

        if response.status >= 400:
            item["product_page"] = response.url
            item["detail_error"] = f"HTTP {response.status}"
            item["image_url"] = item.get("listing_image_url")
            yield item
            return

        detail_title = response.css("h1[data-marker='Big Product Cart Title']::text").get()
        detail_price_value = response.css("h6 span.Price__value_title::text").get()
        detail_price_currency = response.css("h6 span.Price__currency_title::text").get()
        in_stock_text = response.css("[data-testid='stock-balance-label']::text").get()
        detail_image_url = response.css("[data-marker='Main_product_image'] img::attr(src)").get()
        product_key = response.css("#BigProductCard::attr(data-productkey)").get()

        next_data_raw = response.css("script#__NEXT_DATA__::text").get()
        next_data_image = self._extract_next_data_image(next_data_raw)

        item.update(
            {
                "product_key": product_key or item.get("product_key"),
                "title": (detail_title or item.get("title") or "").strip() or None,
                "price": self._join_price(detail_price_value, detail_price_currency) or item.get("price"),
                "image_url": detail_image_url or next_data_image or item.get("listing_image_url"),
                "in_stock": in_stock_text.strip() if in_stock_text else None,
                "product_page": response.url,
            }
        )

        yield item

    def parse_product_error(self, failure):
        item = failure.request.meta["item"]
        item["product_page"] = item.get("url")
        item["detail_error"] = str(failure.value)
        yield item

    @staticmethod
    def _join_price(value, currency):
        value_clean = value.strip() if value else ""
        currency_clean = currency.strip() if currency else ""

        if value_clean and currency_clean:
            return f"{value_clean} {currency_clean}"
        if value_clean:
            return value_clean
        if currency_clean:
            return currency_clean
        return None

    @staticmethod
    def _format_price(price_minor, currency):
        if price_minor is None:
            return None

        try:
            value = float(price_minor) / 100
        except (TypeError, ValueError):
            return None

        symbol = "₴" if currency == "UAH" else currency
        return f"{value:.2f} {symbol}".strip()

    @staticmethod
    def _extract_next_data_image(next_data_raw):
        if not next_data_raw:
            return None

        try:
            data = json.loads(next_data_raw)
        except json.JSONDecodeError:
            return None

        product = (
            data.get("props", {})
            .get("pageProps", {})
            .get("initialState", {})
            .get("product", {})
            .get("productData", {})
            .get("product", {})
        )

        return (
            product.get("img", {}).get("s350x350")
            or product.get("img", {}).get("s200x200")
            or product.get("img", {}).get("s150x150")
        )
