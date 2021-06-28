import jwt
from hashlib import md5

# see: settings.py
JWT_SECRET_KEY = "my secret key"
JWT_ALGORITHM = "HS256"

JWT_AUTH_HEADER = "HTTP_AUTHORIZATION"


# see: auth.password.Password
def password_to_hash(password):
	return md5(password.encode('utf-8')).hexdigest()

def verify_password(password, hash):
	return password_to_hash(password) == hash

# see: auth.auth.token.Token
def jwt_encode(user):
	payload = {
		"user_id" : user.id
	}
	
	token = jwt.encode(payload, JWT_SECRET_KEY, JWT_ALGORITHM)
	
	if isinstance(token, bytes):
		return token.decode('utf-8')

	return token

def jwt_decode(token):
	try:
		payload = jwt.decode(token, JWT_SECRET_KEY, algorithms = [JWT_ALGORITHM])
	except jwt.DecodeError:
		raise Exception("Error decoding signature")
	except jwt.InvalidTokenError:
		raise Exception("Invalid token")
		
	user_id = payload["user_id"]
	return user_id
	
# see: auth.authorize
def authorize(request):
	token = request.headers.get(JWT_AUTH_HEADER, '')
	user_id = jwt_decode(token)
	return user_id
