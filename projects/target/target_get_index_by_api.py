import httpx
from fake_useragent import UserAgent

base_url = "https://redsky.target.com/redsky_aggregations/v1/web/plp_search_v2"
category = ""
useragent = UserAgent.random
base_params = dict(
    category=category,
    default_purchasability_filter=True,
    page=f"/c/{category}",
    platform="desktop",
    channel="WEB",
)


async def main():
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(url="")


if __name__ == "__main__":
    pass
