def test_dashboard_and_static_assets_are_served(client):
    home = client.get("/")
    assert home.status_code == 200
    assert "Explore a stock, understand the numbers" in home.text

    script = client.get("/static/app.js")
    assert script.status_code == 200
    assert "/v1/ingestions/market" in script.text

    styles = client.get("/static/styles.css")
    assert styles.status_code == 200
    assert ".workspace" in styles.text
