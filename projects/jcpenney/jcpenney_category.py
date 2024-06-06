__doc__ = """
# 按类别搜索
DOM
API示例:
https://search-api.jcpenney.com/v1/search-service/g/women/skirts?productGridView=medium&id=cat100250097&responseType=organic
"""


async def parse_category_from_api(data: dict) -> dict:
    """
    通过API解析类别数据
    """
    pass
    parsed_products = []
    product_info = data.get("organicZoneInfo") if data.get("organicZoneInfo", None) else None
    products = product_info.get("products", []) if product_info else []
    for product in products:
        parsed_product = dict(
            product_id=product.get("ppId", None),
            product_name=product.get("name", None),
            brand=product.get("brand", None),
            price=product.get("currentMin", None),
            rating=product.get("averageRating", None),
            review_count=product.get("reviewCount", None),
            sku_id=product.get("skuId", None),
            url=product.get("pdpUrl", None),
            currency=product.get("currencyCode", None),
        )
        parsed_products.append(parsed_product)

    return data
