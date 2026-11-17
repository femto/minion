import pytest

from minion.providers.cost import CostManager
from minion.utils.model_price import get_model_price


def test_gpt_4o_list_price():
    # the bundled JSON had $5/$15, the 2024-05 price
    price = get_model_price("gpt-4o")
    assert price["prompt"] == pytest.approx(2.5e-06)
    assert price["completion"] == pytest.approx(1e-05)


def test_reseller_ids_keep_bundled_rows():
    assert get_model_price("azure/gpt-4o-2024-08-06") == {"prompt": 2.75e-06, "completion": 1.1e-05}


@pytest.mark.parametrize(
    "model, input_per_m, output_per_m",
    [("claude-opus-4-6", 5.0, 25.0), ("claude-sonnet-4-5", 3.0, 15.0), ("gpt-5.2", 1.75, 14.0)],
)
def test_models_newer_than_bundled_json(model, input_per_m, output_per_m):
    price = get_model_price(model)
    assert price["prompt"] == pytest.approx(input_per_m / 1e6)
    assert price["completion"] == pytest.approx(output_per_m / 1e6)


def test_cost_manager_counts_new_model():
    cm = CostManager()
    cm.update_cost(1_000_000, 1_000_000, "claude-opus-4-6")
    assert cm.total_cost == pytest.approx(30.0)


def test_unknown_model_has_no_price():
    assert get_model_price("my-local-model") is None
