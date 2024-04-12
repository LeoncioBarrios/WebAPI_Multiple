from fastapi import FastAPI, Depends, HTTPException, status, Request
from pydantic import BaseModel
from fastapi.security import OAuth2PasswordBearer, HTTPBasic, HTTPBasicCredentials
from jose import jwt, JWTError
from passlib.context import CryptContext
from datetime import datetime, timedelta
from dotenv import load_dotenv
import base64
import os
from conexion_db_c import Conexion, ConexionMutual

from urllib.parse import parse_qs

from modelo import User, Movimiento, DBCredentials

#-- Cargar las variables de entorno.
load_dotenv()

ALGORITHM = "HS256"
ACCESS_TOKEN_DURATION = 1
SECRET_KEY = os.environ.get('SECRET_KEY')

app = FastAPI()

oauth2 = OAuth2PasswordBearer(tokenUrl="/oauth2/token")
security = HTTPBasic()  # Esquema Auth Basic (client_id|client_secret)

crypt = CryptContext(schemes=["bcrypt"])


#-- Funciones ----------------------------------------------

def write_log(filelog, message):
	with open(filelog, "a", encoding="utf-8") as file:
		file.write(message)


def search_user(username: str):
	user_db = None
	try:
		with Conexion.get_connection() as conexion:
			with conexion.cursor() as cursor:
				sentenciaSQL = """
					SELECT u.username, u.full_name, u.email,  u.disabled, u.password, c.client_id, c.client_secret
						FROM UserAPI u
						JOIN ClientCredentials c
							ON u.credentials_id = c.id
						WHERE username = ? COLLATE Latin1_General_CS_AS
				"""
				cursor.execute(sentenciaSQL, username)
				user = cursor.fetchone()
				
				if user:
					user_db = User(
						username=user[0],
						full_name=user[1],
						email=user[2],
						disabled=user[3],
						password=user[4],
						client_id=user[5],
						client_secret=user[6]
					)
	except Exception as e:
		raise HTTPException(
			status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
			detail="No se pudo establecer la conexión con el servidor!"
		)
	
	return user_db


async def auth_user(token: str = Depends(oauth2)):
	exception = HTTPException(
		status_code=status.HTTP_401_UNAUTHORIZED,
		detail="Credenciales de autenticación inválidas",
		headers={"WWW-Authenticate": "Bearer"}
	)
	
	try:
		username = jwt.decode(token, SECRET_KEY, algorithms=[
							  ALGORITHM]).get('sub')
		if username is None:
			raise exception
	
	except JWTError:
		raise exception
	
	return search_user(username)


async def current_user(user: User = Depends(auth_user)):
	if user.disabled:
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail="Usuario inactivo"
		)
	
	return user


#-- EndPoints ---------------------------------------------

@app.post("/oauth2/token", status_code=200)
async def login(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
	
	#-- Obtener los header de la solicitud(Request).
	headers = request.headers
	
	#-- Obtener el header específico (Authorization).
	authorization_header = headers.get("Authorization")
	
	#-- Extraer solo el dato codificado base64.
	authorization_credentials = authorization_header.replace("Basic ", "")
	
	#-- Decodificar la cadena.
	decoded_credentials = base64.b64decode(
		authorization_credentials).decode("utf-8")
	
	#-- Pasar a variables los datos separados por los dos puntos (:).
	client_id, client_secret = decoded_credentials.split(":")
	
	#-- Obtener el contenido del body como bytes
	body_bytes = await request.body()
	
	#-- Decodificar el contenido del body como texto (JSON)
	body_text = body_bytes.decode("utf-8")
	
	#-- Obtener los parámetros del body como texto sin formato (DICT)
	params_dict = parse_qs(body_text)
	
	#-- Extraer los valores de los parámetros
	grant_type = params_dict.get("grant_type", [None])[0]
	username = params_dict.get("username", [None])[0]
	password = params_dict.get("password", [None])[0]
	#####################################################################
	user = search_user(username)
	
	#-- Validad si existe el usuario.
	if not user:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="El usuario no es correcto"
		)
	
	#-- Validar el password.
	if not crypt.verify(password, user.password):
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="El password no es correcto"
		)
	
	#-- Validar el client_id.
	if client_id != user.client_id:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="El client_id no es correcto",
			headers={"WWW-Authenticate": "Basic"}
		)
	
	#-- Validar el client_crecret.
	if client_secret != user.client_secret:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="El client_secret no es correcto",
			headers={"WWW-Authenticate": "Basic"}
		)
	
	#-- Generar el token.
	
	expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_DURATION)
	
	difference = expire - datetime.utcnow()
	expire_in_seconds = difference.total_seconds()
	
	access_token = {
		"sub": user.username,
		"exp": expire
	}
	
	return {
		"access_token": jwt.encode(access_token, SECRET_KEY, algorithm=ALGORITHM),
		"token_type": "bearer",
		"expires_in": expire_in_seconds
	}


@app.post("/Movimientos/GuardarMovimiento", status_code=200)
async def GuardarMovimiento(mov: Movimiento, token: str = Depends(current_user)):
	status = False
	mensaje = ""
	
	#-- Hacer validaciones básicas. --------------------------------
	if not mov:
		message = "No se ha recibido ningún movimiento para guardar."
		write_log("logs/logAPI_fail.txt", message)
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=message
		)
	
	if not mov.NumeroCuenta:
		message = "No hay número de cuenta."
		write_log("logs/logAPI_fail.txt", message)
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=message
		)
	
	if not mov.CuitMutual:
		message = "No hay CUIT Mutual."
		write_log("logs/logAPI_fail.txt", message)
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=message
		)
	
	#----------------------------------------------------------------
	
	try:
		with Conexion.get_connection() as conexion:
			with conexion.cursor() as cursor:
				cursor.execute(
					"SELECT * FROM Mutuales WHERE CUIT = ?", mov.CuitMutual)
				mutual = cursor.fetchone()
	
	except Exception as e:
		#-- Se registra la excepción en el log.
		message = f"{datetime.today()} => Hubo una Excepción! No se pudo registrar el movimiento: \
			Exceptción: {e}, CUIT: {mov.CuitMutual}, NumeroCuenta: {mov.NumeroCuenta}, CodigoMovimiento: \
			{mov.CodigoMovimiento}, TipoMovimiento: {mov.TipoMovimiento}, NumeroMovimiento: {mov.NumeroMovimiento}, \
			FechaMovimiento{mov.FechaMovimiento}, Importe: {mov.Importe}\n"
		write_log("logs/logAPI_exceptions.txt", message)
		
		raise HTTPException(
			status_code=status.HTTP_400_BAD_REQUEST,
			detail=message
		)
	
	if mutual:
		#-- Si validación=OK, invocar SP con sus parámetros. ------------
		
		DBCredentials.CUIT = mutual[1]
		DBCredentials.DATA_BASE = mutual[3]
		DBCredentials.USER_DB = mutual[4]
		DBCredentials.PASS_DB = mutual[5]
		
		with ConexionMutual.get_connection() as conexion:
			
			conexion.autocommit = False
			with conexion.cursor() as cursor:
				
				comandoSQL = "exec GuardarMovimiento @cuit=?, @Cuenta=?, @CodMov=?, @TipoMov=?, @Numero=?, @Fecha=?, @Importe=?"
				param = (mov.CuitMutual, mov.NumeroCuenta, mov.CodigoMovimiento, mov.TipoMovimiento, mov.NumeroMovimiento,
						 mov.FechaMovimiento, mov.Importe)
				
				try:
					cursor.execute(comandoSQL, param)
				
				except Exception as e:
					status = False
					mensaje = "Hubo una Excepción! No se pudo registrar el movimiento: " + str(e)
					
					#-- Se registra la excepción en el log.
					message = f"{datetime.today()} => Hubo una Excepción! No se pudo registrar el movimiento: \
						Exceptción: {e}, CUIT: {mov.CuitMutual}, NumeroCuenta: {mov.NumeroCuenta}, CodigoMovimiento: \
						{mov.CodigoMovimiento}, TipoMovimiento: {mov.TipoMovimiento}, NumeroMovimiento: {mov.NumeroMovimiento}, \
						FechaMovimiento{mov.FechaMovimiento}, Importe: {mov.Importe}\n"
					write_log("logs/logAPI_exceptions.txt", message)
					
					conexion.rollback()
					
				else:
					conexion.commit()
					
					#-- Comprobar si el registro fue realizado efectivamente.
					comandoSQL = "SELECT COUNT(*) FROM AMVMovimientos \
						WHERE cuit=? and NumeroCuenta=? and CodigoMovimiento=? \
							and TipoMovimiento=? and NumeroMovimiento=? and \
							FechaMovimiento=CONVERT(DATETIME, ?, 120) and \
							Importe=?"
					
					cursor.execute(comandoSQL, param)
					
					if cursor.fetchone():
						#-- Se registró con éxito.
						message = f"{datetime.today()} => El movimiento se registró correctamente: \
							CUIT: {mov.CuitMutual}, NumeroCuenta: {mov.NumeroCuenta}, CodigoMovimiento: \
							{mov.CodigoMovimiento}, TipoMovimiento: {mov.TipoMovimiento}, NumeroMovimiento: \
							{mov.NumeroMovimiento}, FechaMovimiento{mov.FechaMovimiento}, Importe: {mov.Importe}\n"
						write_log("logs/logAPI_success.txt", message)
					
					else:
						#-- No se registró.
						message = f"{datetime.today()} => El movimiento NO se registró: CUIT: {mov.CuitMutual}, \
							NumeroCuenta: {mov.NumeroCuenta}, CodigoMovimiento: {mov.CodigoMovimiento}, TipoMovimiento: \
							{mov.TipoMovimiento}, NumeroMovimiento: {mov.NumeroMovimiento}, FechaMovimiento{mov.FechaMovimiento}, \
							Importe: {mov.Importe}\n"
						write_log("logs/logAPI_fail.txt", message)
					
					status = True
					mensaje = "OK"
		
	else:
		status = False
		mensaje = f"No se pudo registrar el movimiento, no se encontró una mutual con CUIT {mov.CuitMutual}"
		
		#-- Se registra en el log.
		message = f"{datetime.today()} => El movimiento NO se registró: CUIT: {mov.CuitMutual}, NumeroCuenta: {mov.NumeroCuenta}, CodigoMovimiento: {mov.CodigoMovimiento}, TipoMovimiento: {mov.TipoMovimiento}, NumeroMovimiento: {mov.NumeroMovimiento}, FechaMovimiento{mov.FechaMovimiento}, Importe: {mov.Importe}\n"
		write_log("logs/logAPI_fail.txt", message)
		
	resp = {
		"Status": status,
		"Mensaje": mensaje
	}
	return resp



"""
Para ejecutar la aplicación en FastAPI:

uvicorn main:app --reload

"""
