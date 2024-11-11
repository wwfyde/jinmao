import pytest
from unittest.mock import patch, AsyncMock

from projects.next.get_products_by_keyword import run, parse_url

@pytest.mark.asyncio
async def test_run_happy_path():
    with patch("projects.next.get_products_by_keyword.async_playwright") as mock_playwright:
        mock_playwright.return_value.__aenter__.return_value.chromium.launch_persistent_context = AsyncMock()
        mock_playwright.return_value.__aenter__.return_value.chromium.launch = AsyncMock()
        mock_context = mock_playwright.return_value.__aenter__.return_value.chromium.launch_persistent_context.return_value
        mock_context.new_page = AsyncMock()
        mock_page = mock_context.new_page.return_value
        mock_page.locator = AsyncMock()
        mock_page.locator.return_value.count = AsyncMock(return_value=10)
        mock_page.locator.return_value.nth = AsyncMock()
        mock_page.locator.return_value.nth.return_value.locator = AsyncMock()
        mock_page.locator.return_value.nth.return_value.locator.return_value.get_attribute = AsyncMock(return_value="https://example.com/product/123")

        await run(mock_playwright.return_value)

        assert mock_page.goto.called
        assert mock_page.locator.return_value.count.called
        assert mock_page.locator.return_value.nth.return_value.locator.return_value.get_attribute.called

def test_parse_url_happy_path():
    url = "https://example.com/product/123/456"
    product_id, sku_id = parse_url(url)
    assert product_id == "123"
    assert sku_id == "456"

def test_parse_url_edge_case():
    url = "https://example.com/product/"
    product_id, sku_id = parse_url(url)
    assert product_id == ""
    assert sku_id == ""