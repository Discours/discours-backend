from ariadne import MutationType, QueryType, SubscriptionType, ScalarType, InterfaceType, UnionType


query = QueryType()
mutation = MutationType()
subscription = SubscriptionType()


datetime_scalar = ScalarType("DateTime")

@datetime_scalar.serializer
def serialize_datetime(value):
	return value.isoformat()


class ApiError:
	def __init__(self, message):
		self.message = message

error_interface = InterfaceType("ErrorInterface")

@error_interface.type_resolver
def resolve_search_result_type(obj, *_):
	if isinstance(obj, ApiError):
		return "ApiError"


sign_in_result = UnionType("SignInResult")
register_user_result = UnionType("RegisterUserResult")

results = [sign_in_result, register_user_result]

resolvers = [query, mutation, subscription, datetime_scalar, error_interface]
resolvers.extend(results)
