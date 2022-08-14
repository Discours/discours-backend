from ariadne import MutationType, QueryType, SubscriptionType, ScalarType


datetime_scalar = ScalarType("DateTime")

@datetime_scalar.serializer
def serialize_datetime(value):
	return value.isoformat()

query = QueryType()
mutation = MutationType()
subscription = SubscriptionType()
resolvers = [query, mutation, subscription, datetime_scalar]
