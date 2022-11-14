from gql import gql, Client
from gql.transport.aiohttp import AIOHTTPTransport

# Provide a GraphQL query
query_ackee_views = gql(
    """
    query getDomainsFacts {
        domains {
            statistics {
                views {
                    id
                    count
                }
                pages {
                    id
                    count
                    created
                }
            }
            facts {
                activeVisitors
                # averageViews
                # averageDuration
                viewsToday
                viewsMonth
                viewsYear
            }
        }
    }
    """
)


class GraphQLClient:
    # Select your transport with a defined url endpoint
    transport = AIOHTTPTransport(url="https://ackee.discours.io/")

    # Create a GraphQL client using the defined transport
    client = Client(transport=transport, fetch_schema_from_transport=True)

    @staticmethod
    def get_views_by_slug(slug):
        # Execute the query on the transport
        domains = GraphQLClient.client.execute(query_ackee_views)
        print(domains)
