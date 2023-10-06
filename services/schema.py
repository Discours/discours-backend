from ariadne import MutationType, QueryType, ScalarType


datetime_scalar = ScalarType("DateTime")


@datetime_scalar.serializer
def serialize_datetime(value):
    return value.isoformat()


query = QueryType()

@query.field("_service")
def resolve_service(*_):
    print("Inside the _service resolver")
    # For now, return a placeholder SDL.
    sdl = "type Query { _service: _Service } type _Service { sdl: String }"
    return {"sdl": sdl}
    
mutation = MutationType()
resolvers = [query, mutation, datetime_scalar]
