def test_paper_order_flow(client):
    empty = client.get("/v1/paper/portfolio")
    assert empty.status_code == 200
    assert empty.json()["cash"] == 100000
    assert empty.json()["mode"] == "paper"

    assert (
        client.post(
            "/v1/paper/orders", json={"symbol": "DEMOA", "side": "buy", "quantity": 1}
        ).status_code
        == 400
    )
    assert client.post("/v1/ingestions/demo").status_code == 200

    bought = client.post("/v1/paper/orders", json={"symbol": "DEMOA", "side": "buy", "quantity": 2})
    assert bought.status_code == 200
    body = bought.json()
    assert body["mode"] == "paper"
    assert body["price_date"] == "2024-03-30"
    assert body["source"] == "demo"
    portfolio = client.get("/v1/paper/portfolio").json()
    assert portfolio["positions"][0]["quantity"] == 2
    assert portfolio["cash"] < 100000

    assert (
        client.post(
            "/v1/paper/orders", json={"symbol": "DEMOA", "side": "sell", "quantity": 3}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/v1/paper/orders", json={"symbol": "DEMOA", "side": "buy", "quantity": 1000000}
        ).status_code
        == 400
    )
    sold = client.post("/v1/paper/orders", json={"symbol": "DEMOA", "side": "sell", "quantity": 2})
    assert sold.status_code == 200
    final = client.get("/v1/paper/portfolio").json()
    assert final["cash"] == 100000
    assert final["positions"] == []
    assert len(final["orders"]) == 2
