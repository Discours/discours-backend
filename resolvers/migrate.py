
from base.orm import query
from resoolvers.auth import login_required
from migration.extract import extract_md


@login_required
@query.field("markdownBody")
def markdown_body(_, info, body):
    body = extract_md(body)
    return body
