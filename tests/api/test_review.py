from fastapi.testclient import TestClient


def test_review_analysis(client: TestClient):
    response = client.post('/api/product/review_analysis', json={
        "product_id": "728681",
        "source": "gap",
        "date_start": "2024-07-09",
        "date_end": "2024-07-10",
        "lang": "en",
        "from_api": False,
        "llm": "ark",
    })
    data = response.json()
    assert response.status_code == 200
