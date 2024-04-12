import http.client
import json
import base64

conn = http.client.HTTPConnection("127.0.0.1", 8000)

grant_type = "password"
username = "leoncio"
password = "123456"
client_id = "1234567890"
client_secret = "0987654321"

credentials = f"{client_id}:{client_secret}"
base64_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')

headersList = {
    "Accept": "application/json",
    "Content-Type": "text/plain",
    "Authorization": f"Basic {base64_credentials}"
}

payload = f"grant_type={grant_type}&username={username}&password={password}"

conn.request("POST", "/oauth2/token", payload, headersList)

response = conn.getresponse()
result = response.read()

print(result.decode("utf-8"))
