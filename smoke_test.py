import json

from app import app, init_db


def assert_ok(resp, code=200):
    if resp.status_code != code:
        raise AssertionError(f"Expected {code}, got {resp.status_code}: {resp.data.decode('utf-8', errors='ignore')}")


def main():
    init_db()
    client = app.test_client()

    r = client.get("/api/health")
    assert_ok(r, 200)

    products = client.get("/api/products")
    assert_ok(products, 200)
    p_data = products.get_json()
    if not p_data:
        raise AssertionError("No products found in database")

    customers = client.get("/api/customers")
    assert_ok(customers, 200)
    c_data = customers.get_json()
    if not c_data:
        created = client.post(
            "/api/customers",
            data=json.dumps({"name": "Smoke Test User", "phone": "0900000000", "zalo": "0900000000"}),
            content_type="application/json",
        )
        assert created.status_code in (200, 201)
        c_data = [created.get_json()]

    payload = {
        "customer_id": c_data[0]["id"],
        "product_id": p_data[0]["id"],
        "amount": p_data[0]["price"],
        "status": "pending",
        "quantity": 1,
    }
    create_order = client.post("/api/orders", data=json.dumps(payload), content_type="application/json")
    assert create_order.status_code in (200, 201)
    order = create_order.get_json()

    update = client.put(
        f"/api/orders/{order['id']}",
        data=json.dumps({"status": "success", "amount": order["amount"]}),
        content_type="application/json",
    )
    assert_ok(update, 200)

    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()