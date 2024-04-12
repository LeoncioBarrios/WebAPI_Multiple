from pydantic import BaseModel
from datetime import datetime


class User(BaseModel):
	username: str
	full_name: str
	email: str
	disabled: bool
	password: str
	client_id: str
	client_secret: str


class Movimiento(BaseModel):
	CuitMutual: int
	NumeroCuenta: int
	CodigoMovimiento: str
	TipoMovimiento: str
	NumeroMovimiento: int
	FechaMovimiento: datetime
	Importe: float


class DBCredentials:
	CUIT = None
	DATA_BASE = None
	USER_DB = None
	PASS_DB = None
	