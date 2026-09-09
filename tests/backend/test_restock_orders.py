"""
Tests for restocking order API endpoints.
"""
from datetime import date, timedelta

import pytest


# Forecast prices and lead times these lines rely on (server/data/demand_forecasts.json):
# WDG-001 is $12.50 with a 7-day lead time, MTR-304 is $385.00 with a 14-day lead time.
WDG_LINE = {"item_sku": "WDG-001", "quantity": 450}
MTR_LINE = {"item_sku": "MTR-304", "quantity": 35}


def place_order(client, lines):
    """Submit a restocking order and return the response."""
    return client.post("/api/restock-orders", json={"lines": lines})


class TestDemandForecastPricing:
    """Test suite for the pricing fields restocking relies on."""

    def test_demand_forecasts_have_cost_and_lead_time(self, client):
        """Test that every forecast carries a unit cost and a lead time."""
        response = client.get("/api/demand")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0

        for forecast in data:
            assert isinstance(forecast["unit_cost"], (int, float))
            assert forecast["unit_cost"] > 0
            assert isinstance(forecast["lead_time_days"], int)
            assert 1 <= forecast["lead_time_days"] <= 30


class TestRestockOrderEndpoints:
    """Test suite for restocking order endpoints."""

    def test_get_restock_orders_empty(self, client):
        """Test that no restocking orders exist before any are placed."""
        response = client.get("/api/restock-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_restock_order(self, client):
        """Test submitting a restocking order."""
        response = place_order(client, [WDG_LINE, MTR_LINE])
        assert response.status_code == 201

        order = response.json()
        assert order["id"] == "1"
        assert order["order_number"].startswith("RST-")
        assert order["status"] == "Submitted"
        assert len(order["lines"]) == 2

        for line in order["lines"]:
            for field in ["item_sku", "item_name", "quantity", "unit_cost", "line_total", "lead_time_days"]:
                assert field in line

    def test_restock_order_total_calculation(self, client):
        """Test that line totals and the order total are computed correctly."""
        order = place_order(client, [WDG_LINE, MTR_LINE]).json()

        for line in order["lines"]:
            assert abs(line["line_total"] - line["quantity"] * line["unit_cost"]) < 0.01

        # 450 x $12.50 + 35 x $385.00
        assert abs(order["total_cost"] - 19100.00) < 0.01

    def test_restock_order_priced_by_server(self, client):
        """Test that a client-supplied price is ignored in favor of forecast data."""
        response = place_order(client, [{"item_sku": "WDG-001", "quantity": 10, "unit_cost": 0.01}])
        assert response.status_code == 201

        line = response.json()["lines"][0]
        assert line["unit_cost"] == 12.5
        assert abs(line["line_total"] - 125.00) < 0.01

    def test_restock_order_lead_time_is_longest_line(self, client):
        """Test that an order's lead time is its slowest line's lead time."""
        order = place_order(client, [WDG_LINE, MTR_LINE]).json()

        assert order["lead_time_days"] == 14
        assert order["lead_time_days"] == max(line["lead_time_days"] for line in order["lines"])

    def test_restock_order_expected_delivery_calculation(self, client):
        """Test that expected delivery is the submit date plus the lead time."""
        order = place_order(client, [WDG_LINE, MTR_LINE]).json()

        created = date.fromisoformat(order["created_date"])
        expected = date.fromisoformat(order["expected_delivery"])
        assert expected - created == timedelta(days=order["lead_time_days"])

    def test_get_restock_orders_newest_first(self, client):
        """Test that submitted orders are listed newest first."""
        place_order(client, [WDG_LINE])
        place_order(client, [MTR_LINE])

        response = client.get("/api/restock-orders")
        assert response.status_code == 200

        data = response.json()
        assert [order["id"] for order in data] == ["2", "1"]
        assert data[0]["lines"][0]["item_sku"] == "MTR-304"

    def test_create_restock_order_unknown_sku(self, client):
        """Test that an unknown SKU is rejected."""
        response = place_order(client, [{"item_sku": "NOPE-999", "quantity": 5}])
        assert response.status_code == 400
        assert "unknown sku" in response.json()["detail"].lower()

    def test_create_restock_order_duplicate_sku(self, client):
        """Test that the same SKU cannot appear on two lines."""
        response = place_order(client, [WDG_LINE, WDG_LINE])
        assert response.status_code == 400
        assert "duplicate" in response.json()["detail"].lower()

    @pytest.mark.parametrize("quantity", [0, -5])
    def test_create_restock_order_invalid_quantity(self, client, quantity):
        """Test that zero and negative quantities fail validation."""
        response = place_order(client, [{"item_sku": "WDG-001", "quantity": quantity}])
        assert response.status_code == 422

    def test_create_restock_order_no_lines(self, client):
        """Test that an order needs at least one line."""
        response = place_order(client, [])
        assert response.status_code == 422

    @pytest.mark.parametrize("quantity", [100_001, 10**400])
    def test_create_restock_order_quantity_too_large(self, client, quantity):
        """Test that oversized quantities fail validation instead of overflowing the price math."""
        response = place_order(client, [{"item_sku": "WDG-001", "quantity": quantity}])
        assert response.status_code == 422

    def test_create_restock_order_normalizes_sku(self, client):
        """Test that SKU case and surrounding whitespace are ignored."""
        response = place_order(client, [{"item_sku": " wdg-001 ", "quantity": 1}])
        assert response.status_code == 201
        assert response.json()["lines"][0]["item_sku"] == "WDG-001"

    def test_create_restock_order_duplicate_sku_different_case(self, client):
        """Test that case variants of one SKU count as duplicates."""
        response = place_order(client, [WDG_LINE, {"item_sku": "wdg-001", "quantity": 1}])
        assert response.status_code == 400
        assert "duplicate" in response.json()["detail"].lower()

    def test_rejected_order_is_not_stored(self, client):
        """Test that a failed submission leaves no order behind."""
        place_order(client, [WDG_LINE, {"item_sku": "NOPE-999", "quantity": 5}])

        response = client.get("/api/restock-orders")
        assert response.json() == []

    def test_restock_orders_do_not_affect_other_endpoints(self, client):
        """Test that restocking orders stay separate from customer orders and the backlog."""
        orders_before = len(client.get("/api/orders").json())
        backlog_before = client.get("/api/backlog").json()

        assert place_order(client, [WDG_LINE]).status_code == 201

        orders_response = client.get("/api/orders")
        backlog_response = client.get("/api/backlog")
        assert orders_response.status_code == 200
        assert backlog_response.status_code == 200
        assert len(orders_response.json()) == orders_before
        assert backlog_response.json() == backlog_before
