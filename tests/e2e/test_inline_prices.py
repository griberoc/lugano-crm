from pathlib import Path

import pytest
from playwright.sync_api import expect
from test_critical_flow import fake_platform, json_response  # noqa: F401
from test_premium_ui import sign_in

pytestmark = pytest.mark.e2e


@pytest.mark.parametrize('width', [390, 1440])
def test_inline_price_validation_save_failure_retry(page, frontend_url, fake_platform, width):
    product = dict(id='price-test', name='Café de teste', price=19.9,
                   category='Cafés', available=True, image_url=None)
    patches = []
    failure = [False]
    def handler(route):
        if route.request.method == 'PATCH':
            patches.append(route.request.post_data_json)
            if failure[0]:
                return json_response(route, {'detail': 'Unavailable'}, 503)
            product.update(route.request.post_data_json)
            return json_response(route, product)
        return json_response(route, [product])
    page.route('**/api/v1/admin/products**', handler)
    page.set_viewport_size({'width': width, 'height': 1000})
    page.goto(frontend_url + '/admin/')
    sign_in(page, admin=True)
    page.locator('[data-view="products"]').click()
    form = page.locator('[data-price-product]')
    field = form.locator('input')
    save = form.get_by_role('button', name='Salvar', exact=True)
    for invalid in ['0', '-1', '19,999', 'abc', '']:
        field.fill(invalid)
        save.click()
        expect(field).to_have_attribute('aria-invalid', 'true')
    assert patches == []
    field.fill('21,90')
    save.click()
    expect(form.get_by_role('status')).to_have_text('Preço atualizado com sucesso.')
    assert patches == [{'price': '21.90'}]
    expect(page.locator('[data-product-price-display]')).to_contain_text('21,90')
    save.click()
    assert len(patches) == 1
    failure[0] = True
    field.fill('22.50')
    save.click()
    expect(form.get_by_role('status')).to_contain_text('Não foi possível confirmar')
    expect(field).to_have_value('22.50')
    expect(save).to_be_enabled()
    failure[0] = False
    save.click()
    expect(form.get_by_role('status')).to_have_text('Preço atualizado com sucesso.')
    expect(field).to_have_value('22,50')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    Path('test-results/menu').mkdir(parents=True, exist_ok=True)
    page.screenshot(path=f'test-results/menu/inline-price-{width}.png', full_page=True)
