from pathlib import Path
import json
import pytest
from playwright.sync_api import expect
from test_critical_flow import fake_platform, json_response  # noqa: F401

pytestmark = pytest.mark.e2e
ARTIFACTS = Path("test-results/ui-premium")

def sign_in(page, admin=False):
    if admin:
        page.locator("#admin-login-form input[name=email]").fill("admin@example.test")
        page.locator("#admin-login-form input[name=password]").fill("admin-e2e")
        page.locator("#admin-login-form button[type=submit]").click()
    else:
        page.evaluate("""() => localStorage.setItem("lugano.customer.session", JSON.stringify({
          access_token:"customer-e2e-token", user:{id:"customer-e2e",email:"cliente@example.test"}
        }))""")

@pytest.mark.parametrize("width", [360,390,430,768,1440])
def test_layout_and_runtime(page, frontend_url, fake_platform, width):
    errors=[]
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.set_viewport_size({"width":width,"height":1000})
    ARTIFACTS.mkdir(parents=True,exist_ok=True)
    for module in ["orders","auth","customer","admin"]:
        page.goto(f"{frontend_url}/{module}/")
        page.wait_for_timeout(150)
        if module == "orders":
            expect(page.locator("[data-add-product]")).to_be_visible()
        if module == "admin":
            sign_in(page,admin=True)
            page.wait_for_timeout(300)
        assert not errors, errors
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (module, page.evaluate("Array.from(document.querySelectorAll('body *')).filter(e=>e.getBoundingClientRect().right>innerWidth+1 && e.getBoundingClientRect().width>0).slice(0,10).map(e=>[e.tagName,e.className,e.getBoundingClientRect().width])"))
        page.screenshot(path=str(ARTIFACTS/f"{module}-{width}.png"),full_page=True)
        vitals=page.evaluate("window.__luganoVitals")
        (ARTIFACTS/f"{module}-{width}-vitals.json").write_text(json.dumps(vitals),encoding="utf-8")

def test_search_detail_cart_and_recovery(page, frontend_url, fake_platform):
    page.set_viewport_size({"width":390,"height":844})
    page.goto(f"{frontend_url}/orders/")
    page.locator("#product-search").fill("inexistente")
    expect(page.get_by_text("Nenhum produto encontrado",exact=True)).to_be_visible()
    page.locator("#product-search").fill("chocolate")
    page.locator("[data-product-detail]").first.click()
    expect(page.locator("#product-dialog")).to_be_visible()
    page.locator("#product-quantity").fill("2")
    page.locator("#product-note").fill("Pouco açúcar")
    page.locator("#add-product-detail").click()
    page.locator("#mobile-cart").click()
    expect(page.locator("#cart-count")).to_have_text("2 itens")
    expect(page.locator("#cart-list")).to_contain_text("Pouco açúcar")
    page.locator("[data-cart-remove]").click()
    page.get_by_role("button",name="Desfazer",exact=True).click()
    expect(page.locator("#cart-count")).to_have_text("2 itens")
    page.reload()
    expect(page.locator("#mobile-cart")).to_contain_text("2 itens")
    page.locator("[data-product-detail]").first.click()
    page.keyboard.press("Escape")
    expect(page.locator("#product-dialog")).not_to_be_visible()

def test_catalog_failure_retry_and_empty(page,frontend_url,fake_platform):
    page.route("**/api/v1/catalog/products*",lambda route:json_response(route,{"detail":"internal secret"},503))
    page.goto(f"{frontend_url}/orders/")
    expect(page.get_by_text("Não conseguimos abrir o cardápio",exact=True)).to_be_visible()
    expect(page.locator("body")).not_to_contain_text("internal secret")
    page.route("**/api/v1/catalog/products*",lambda route:json_response(route,[]))
    page.locator('[data-retry="products"]').click()
    expect(page.get_by_text("Nenhum produto encontrado",exact=True)).to_be_visible()

def test_reorder_reconciles_prices_and_requires_confirmation(page,frontend_url,fake_platform):
    fake_platform["order"]["items"][0]["unit_price"]=10
    fake_platform["orders"]=[fake_platform["order"]]
    page.goto(f"{frontend_url}/customer/")
    sign_in(page)
    page.reload()
    page.locator("[data-reorder]").click()
    expect(page.locator("#customer-order-dialog")).to_contain_text("24,90")
    assert page.evaluate("localStorage.getItem('lugano.customer.cart')") is None
    page.locator("#confirm-reorder").click()
    page.wait_for_url("**/orders/")
    cart=page.evaluate("JSON.parse(localStorage.getItem('lugano.customer.cart'))")
    assert cart[0]["price"]==24.9

def test_admin_payment_guard_and_responsive_detail(page,frontend_url,fake_platform):
    fake_platform["order"]["status"]="confirmed"
    fake_platform["orders"]=[fake_platform["order"]]
    page.set_viewport_size({"width":390,"height":844})
    page.goto(f"{frontend_url}/admin/")
    sign_in(page,admin=True)
    expect(page.locator("#admin-app")).to_be_visible()
    page.locator("[data-order-select]").click()
    expect(page.locator("#order-detail")).to_be_visible()
    expect(page.locator("#order-detail .quick-actions button")).to_be_disabled()
    page.locator("#back-to-queue").click()
    expect(page.locator(".orders-queue-panel")).to_be_visible()


def open_checkout(page, frontend_url, platform):
    platform["addresses"] = [platform["order"]["address"]]
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(f"{frontend_url}/orders/")
    sign_in(page)
    page.reload()
    page.locator("[data-add-product]").click()
    page.locator("#mobile-cart").click()
    page.locator('#step-cart [data-go-step]').click()
    page.locator('#step-delivery [data-go-step="step-payment"]').click()
    page.locator("#order-notes").fill("Tocar a campainha")
    page.locator("#checkout-button").click()


def test_uncertain_submission_blocks_repeat_after_reload(page, frontend_url, fake_platform):
    requests = []

    def fail_order(route):
        requests.append(route.request.post_data_json)
        json_response(route, {"detail": "private internal message"}, 503)

    open_checkout(page, frontend_url, fake_platform)
    page.route("**/api/v1/orders/", fail_order)
    page.locator("#confirm-order").click()
    expect(page.locator("#notice")).to_contain_text("Confira Meus pedidos")
    assert len(requests) == 1
    assert page.evaluate("JSON.parse(localStorage.getItem('lugano.order.uncertain')).user") == "customer-e2e"
    page.reload()
    expect(page.locator("#order-notes")).to_have_value("Tocar a campainha")
    page.locator("#checkout-button").click()
    expect(page.locator("#notice")).to_contain_text("envio anterior")
    assert len(requests) == 1


def test_validation_failure_visible_inside_dialog_and_retry(page, frontend_url, fake_platform):
    open_checkout(page, frontend_url, fake_platform)
    page.route("**/api/v1/orders/", lambda route: json_response(route, {}, 422))
    page.locator("#confirm-order").click()
    expect(page.locator("#confirm-dialog .dialog-notice")).to_contain_text("Confira os campos")
    expect(page.locator("#order-notes")).to_have_value("Tocar a campainha")
    assert page.evaluate("localStorage.getItem('lugano.order.uncertain')") is None
    page.route("**/api/v1/orders/", lambda route: json_response(route, fake_platform["order"], 201))
    page.locator("#confirm-order").click()
    expect(page.locator("#last-order-title")).to_contain_text("order-e2")


def test_confirmation_survives_failed_query_then_payment_update(page, frontend_url, fake_platform):
    open_checkout(page, frontend_url, fake_platform)
    page.locator("#confirm-order").click()
    expect(page.locator("#last-order-panel")).to_be_visible()
    page.route("**/api/v1/orders/order-e2e-0001", lambda route: json_response(route, {}, 503))
    page.reload()
    expect(page.locator("#last-order-summary")).to_contain_text("Não envie novamente")
    expect(page.locator("#last-order-title")).to_contain_text("order-e2")
    fake_platform["order"].update(payment_status="paid", status="preparing")
    page.route("**/api/v1/orders/order-e2e-0001", lambda route: json_response(route, fake_platform["order"]))
    page.locator("#refresh-order").click()
    expect(page.locator("#last-order-summary")).to_contain_text("Pago")
    expect(page.locator("#last-order-status")).to_have_text("Em preparo")
    assert len(fake_platform["orders"]) == 1


def test_expired_session_preserves_cart_and_offers_login(page, frontend_url, fake_platform):
    open_checkout(page, frontend_url, fake_platform)
    page.locator("#cancel-confirmation").click()
    page.route("**/api/v1/me/addresses", lambda route: json_response(route, {}, 401))
    page.reload()
    expect(page.locator("#step-account")).to_be_visible()
    expect(page.get_by_role("link", name="Entrar para continuar")).to_be_visible()
    assert page.evaluate("JSON.parse(localStorage.getItem('lugano.customer.cart')).length") == 1


def test_keyboard_tabs_dialog_focus_and_offline(page, frontend_url, fake_platform):
    page.goto(f"{frontend_url}/auth/")
    page.locator("#show-login").focus()
    page.keyboard.press("ArrowRight")
    expect(page.locator("#show-signup")).to_be_focused()
    expect(page.locator("#signup-form")).to_be_visible()
    page.keyboard.press("ArrowLeft")
    expect(page.locator("#login-form")).to_be_visible()
    page.goto(f"{frontend_url}/orders/")
    trigger = page.locator(".product-name")
    trigger.focus()
    page.keyboard.press("Enter")
    expect(page.locator("#close-product")).to_be_focused()
    page.keyboard.press("Escape")
    expect(trigger).to_be_focused()
    page.context.set_offline(True)
    expect(page.locator("#ux-toast")).to_contain_text("Sem conexão")
    page.context.set_offline(False)
    expect(page.locator("#ux-toast")).to_contain_text("Conexão restabelecida")


@pytest.mark.parametrize("legacy,target", [("client/#/delivery","orders"),("app/#/pedidos","orders"),("app/#/cliente","customer")])
def test_legacy_route_navigation_and_back(page, frontend_url, fake_platform, legacy, target):
    page.goto(f"{frontend_url}/{legacy}")
    page.wait_for_url(f"**/{target}/")
    assert page.locator("iframe").count() == 0
    page.locator('.shop-header a[href="../orders/"]').first.click()
    page.locator('.shop-header a[href="../customer/"]').click()
    page.go_back()
    expect(page.locator("#product-search")).to_be_visible()


def test_corrupt_saved_cart_does_not_break_menu(page, frontend_url, fake_platform):
    page.goto(f"{frontend_url}/orders/")
    page.evaluate("localStorage.setItem('lugano.customer.cart','{}')")
    page.reload()
    expect(page.locator("[data-add-product]")).to_be_visible()
    expect(page.locator("#cart-count")).to_have_text("0 itens")


def test_customer_partial_failure_does_not_imply_no_active_order(page, frontend_url, fake_platform):
    page.goto(f"{frontend_url}/customer/")
    sign_in(page)
    page.route("**/api/v1/orders/", lambda route: json_response(route, {}, 503))
    page.reload()
    expect(page.locator("#active-order")).to_contain_text("Não repita um pedido")
    expect(page.locator("#orders-list [data-retry-dashboard]")).to_be_visible()
    expect(page.locator("#loyalty-available")).to_have_text("30")


def populate_admin(page, platform):
    product = platform["order"]["items"][0]["product"]
    customer = dict(platform["order"]["customer"], id="customer-e2e", created_at="2026-08-22")
    promotion = {"id":"promotion-e2e","code":"PAUSA10","description":"Uma pausa especial","type":"percentage","value":10,"active":True}
    page.route("**/api/v1/admin/products*", lambda route: json_response(route, [product]))
    page.route("**/api/v1/admin/customers*", lambda route: json_response(route, [customer]))
    page.route("**/api/v1/admin/promotions*", lambda route: json_response(route, [promotion]))
    platform["orders"] = [platform["order"]]


@pytest.mark.parametrize("width", [390,360,430,768,1440])
def test_admin_all_views_and_customer_account(page,frontend_url,fake_platform,width):
    errors=[]
    page.on("pageerror",lambda error:errors.append(str(error)))
    page.set_viewport_size({"width":width,"height":900})
    populate_admin(page,fake_platform)
    page.goto(f"{frontend_url}/admin/")
    sign_in(page,admin=True)
    expect(page.locator("#admin-app")).to_be_visible()
    for view in ["overview","orders","products","customers","promotions","reports","audit","team","settings"]:
        page.locator(f'.nav-tab[data-view="{view}"]').click()
        expect(page.locator(f"#view-{view}")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (width,view)
        page.screenshot(path=str(ARTIFACTS/f"admin-{view}-{width}.png"),full_page=True)
    page.goto(f"{frontend_url}/customer/")
    sign_in(page)
    page.reload()
    expect(page.locator("#loyalty-available")).to_have_text("30")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(ARTIFACTS/f"account-signed-in-{width}.png"),full_page=True)
    assert not errors, errors


def test_admin_edit_failure_preserves_fields_and_search(page,frontend_url,fake_platform):
    populate_admin(page,fake_platform)
    page.set_viewport_size({"width":390,"height":844})
    page.goto(f"{frontend_url}/admin/")
    sign_in(page,admin=True)
    page.locator('.nav-tab[data-view="products"]').click()
    page.locator("#products-search").fill("chocolate")
    page.locator("[data-edit-product]").click()
    expect(page.locator("#product-form input[name=price]")).to_have_value("24.9")
    page.locator("#product-form input[name=name]").fill("Chocolate especial")
    page.route("**/api/v1/admin/products/product-e2e",lambda route:json_response(route,{},422))
    page.locator("#product-form button[type=submit]").click()
    expect(page.locator("dialog[open] .dialog-notice")).to_contain_text("Confira os campos")
    expect(page.locator("#product-form input[name=name]")).to_have_value("Chocolate especial")
    page.keyboard.press("Escape")
    page.reload()
    expect(page.locator("#products-search")).to_have_value("chocolate")
    expect(page.locator("[data-edit-product]")).to_be_visible()


def test_staff_cannot_see_management_actions(page,frontend_url,fake_platform):
    populate_admin(page,fake_platform)
    page.route("**/api/v1/admin/login",lambda route:json_response(route,{
        "access_token":"staff-test-token","user":{"id":"staff-e2e"},
        "admin":{"profile_id":"staff-e2e","role":"staff","active":True,"auth_method":"supabase"}
    }))
    page.goto(f"{frontend_url}/admin/")
    sign_in(page,admin=True)
    expect(page.locator('.nav-tab[data-view="promotions"]')).not_to_be_visible()
    expect(page.locator('.nav-tab[data-view="team"]')).not_to_be_visible()
    page.locator('.nav-tab[data-view="products"]').click()
    expect(page.get_by_role("button",name="Novo produto",exact=True)).not_to_be_visible()
    assert page.locator("[data-edit-product]").count()==0


def test_zoom_200_percent_and_reduced_motion(page,frontend_url,fake_platform):
    page.set_viewport_size({"width":1440,"height":1000})
    page.emulate_media(reduced_motion="reduce")
    for module in ["orders","auth","customer","admin"]:
        page.goto(f"{frontend_url}/{module}/")
        page.evaluate("document.documentElement.style.zoom='2'")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"),module
        assert page.evaluate("getComputedStyle(document.querySelector('button')).transitionDuration") == "0s"


def test_primary_targets_and_token_contrast(page,frontend_url,fake_platform):
    page.set_viewport_size({"width":390,"height":844})
    page.goto(f"{frontend_url}/orders/")
    expect(page.locator("[data-add-product]")).to_be_visible()
    for selector in ["[data-add-product]",".product-name","#refresh-products","#product-search"]:
        box=page.locator(selector).first.bounding_box()
        assert box["height"] >= 44 and box["width"] >= 44, selector

    def luminance(color):
        values=[int(color[index:index+2],16)/255 for index in (1,3,5)]
        linear=[v/12.92 if v<=0.04045 else ((v+0.055)/1.055)**2.4 for v in values]
        return sum(a*b for a,b in zip(linear,[0.2126,0.7152,0.0722]))

    pairs={"body":("#30231e","#faf8f4"),"muted":("#6f655e","#ffffff"),
           "primary":("#ffffff","#38271f"),"error":("#8a2720","#fff3f1"),
           "success":("#20533d","#f0f8f3"),"accent_text":("#87602f","#faf8f4")}
    ratios={}
    for name,colors in pairs.items():
        light,dark=sorted(map(luminance,colors),reverse=True)
        ratios[name]=round((light+0.05)/(dark+0.05),2)
        assert ratios[name] >= 4.5, (name,ratios[name])
    (ARTIFACTS/"token-contrast.json").write_text(json.dumps(ratios),encoding="utf-8")


@pytest.mark.parametrize("status", ["paid","failed","refunded","expired"])
def test_payment_states_never_offer_invalid_pix(page,frontend_url,fake_platform,status):
    order=fake_platform["order"]
    if status=="expired":
        order["payment_instructions"]["expires_at"]="2020-01-01T00:00:00Z"
    else:
        order["payment_status"]=status
    page.goto(f"{frontend_url}/orders/")
    sign_in(page)
    page.evaluate("localStorage.setItem('lugano.lastOrder',JSON.stringify({id:'order-e2e-0001',user:'customer-e2e'}))")
    page.goto(f"{frontend_url}/orders/?acompanhar=1")
    expect(page.locator("#last-order-panel")).to_be_visible()
    expect(page.locator("#copy-pix")).not_to_be_visible()
    expect(page.locator("#payment-url")).not_to_be_visible()
    if status=="expired":
        expect(page.locator("#payment-live-status")).to_contain_text("expirou")


def test_read_only_preview_blocks_business_writes(page,frontend_url,fake_platform):
    open_checkout(page,frontend_url,fake_platform)
    page.evaluate("window.LUGANO_CONFIG.previewReadOnly=true")
    page.locator("#confirm-order").click()
    expect(page.locator("#confirm-dialog .dialog-notice")).to_contain_text("alterações reais estão desativadas")
    assert fake_platform["orders"] == []
    assert page.evaluate("localStorage.getItem('lugano.order.uncertain')") is None
