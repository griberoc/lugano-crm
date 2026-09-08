from pathlib import Path

import pytest

from scripts.replace_menu import classify, read_menu


def test_source_menu_is_complete_and_deterministic():
    path = Path('data/menu-sao-luis-2026.csv')
    rows = read_menu(path)
    assert len(rows) == 121
    assert len({r['category'] for r in rows}) == 16
    assert rows == read_menu(path)
    assert len({r['id'] for r in rows}) == len(rows)
    assert next(r for r in rows if r['name'] == 'Chocolate quente médio')['price'] == '17.00'
    assert next(r for r in rows if r['name'] == 'Taça de sorvete')['price'] == '28.90'


def test_history_is_preserved_and_new_ids_excluded():
    sold, unsold = classify([{'id': 'sold'}, {'id': 'unsold'}, {'id': 'new'}], {'sold'}, {'new'})
    assert sold == [{'id': 'sold'}]
    assert unsold == [{'id': 'unsold'}]


@pytest.mark.parametrize('price', ['-1', '0', 'NaN', '1.234'])
def test_reject_invalid_prices(tmp_path, price):
    path = tmp_path / 'menu.csv'
    path.write_text('slide,category,name,price,description\n3,Cafe,Teste,' + price + ',\n', encoding='utf-8')
    with pytest.raises(ValueError):
        read_menu(path)
