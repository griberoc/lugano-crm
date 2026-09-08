import pytest
from playwright.sync_api import expect
from test_critical_flow import fake_platform  # noqa: F401

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize('width', [390, 1440])
def test_product_titles_and_categories_use_brand_color(page, frontend_url, fake_platform, width):
    page.set_viewport_size({'width': width, 'height': 844})
    page.goto(frontend_url + '/orders/')
    title = page.locator('.product-name').first
    expect(title).to_be_visible()
    # Simulate a browser's blue default for buttons at lower specificity.
    page.add_style_tag(content=':where(button) { color: rgb(0, 122, 255); }')
    brand = page.locator('.product-buy .primary-button').first.evaluate(
        '(element) => getComputedStyle(element).backgroundColor')
    assert title.evaluate('(element) => getComputedStyle(element).color') == brand
    category = page.locator('.category-tabs button[aria-pressed="false"]').first
    assert category.evaluate('(element) => getComputedStyle(element).color') == brand
    category.click()
    selected = page.locator('.category-tabs button[aria-pressed="true"]')
    assert selected.evaluate('(element) => getComputedStyle(element).color') == 'rgb(255, 255, 255)'
    assert page.locator('.category-tabs button[aria-pressed="false"]').first.evaluate(
        '(element) => getComputedStyle(element).color') == brand
