from ariadne import MutationType, QueryType, SubscriptionType, ScalarType

query = QueryType()
mutation = MutationType()
subscription = SubscriptionType()


datetime_scalar = ScalarType("DateTime")

@datetime_scalar.serializer
def serialize_datetime(value):
	return value.isoformat()


resolvers = [query, mutation, subscription, datetime_scalar]
