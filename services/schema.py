from ariadne import MutationType, QueryType, ScalarType


datetime_scalar = ScalarType("DateTime")


@datetime_scalar.serializer
def serialize_datetime(value):
    return value.isoformat()


query = QueryType()

@query.field("_service")
def resolve_service(*_):
    # Load the full SDL from your SDL file
    with open("schemas/core.graphql", "r") as file:
        full_sdl = file.read()
    
    return {"sdl": full_sdl}
    
mutation = MutationType()
resolvers = [query, mutation, datetime_scalar]
