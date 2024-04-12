import http.client
import json

conn = http.client.HTTPConnection("127.0.0.1", 8000)

headersList = {
 "Accept": "application/json",
 "Content-Type": "application/json; charset=UTF-8",
 "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJsZW9uY2lvIiwiZXhwIjoxNjg3NDY5MTUwfQ.8yDqkfWpKG04aQAi6E301DfbLoEp3WgrihdQ7psYjYA" 
}

payload = json.dumps({
	"CuitMutual": 2060202020,
	"NumeroCuenta": 202002,
	"CodigoMovimiento": "MOVIMIENTO ZZZ",
	"TipoMovimiento": "C",
	"NumeroMovimiento": 20020,
	"FechaMovimiento": "2023-06-22T14:33:16",
	"Importe": 9999.00
})

conn.request("POST", "/Movimientos/GuardarMovimiento", payload, headersList)
response = conn.getresponse()
result = response.read()

print(result.decode("utf-8"))