from ariadne import MutationType, QueryType, ScalarType

datetime_scalar = ScalarType("DateTime")


@datetime_scalar.serializer
def serialize_datetime(value):
    return value.isoformat()


query = QueryType()
mutation = MutationType()
resolvers = [query, mutation, datetime_scalar]
