from fastapi.testclient import TestClient

# Import the app from the package
from app.main import app

client = TestClient(app)

try:
    resp = client.get('/essay')
    print('STATUS:', resp.status_code)
    print(resp.text[:1000])
except Exception as e:
    import traceback
    traceback.print_exc()
    print('EXCEPTION:', e)
