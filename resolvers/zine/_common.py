from sqlalchemy import func, case
from sqlalchemy.orm import aliased
from orm.reaction import Reaction, ReactionKind


def add_common_stat_columns(q):
    aliased_reaction = aliased(Reaction)

    q = q.outerjoin(aliased_reaction).add_columns(
        func.sum(
            aliased_reaction.id
        ).label('reacted_stat'),
        func.sum(
            case(
                (aliased_reaction.body.is_not(None), 1),
                else_=0
            )
        ).label('commented_stat'),
        func.sum(case(
            (aliased_reaction.kind == ReactionKind.AGREE, 1),
            (aliased_reaction.kind == ReactionKind.DISAGREE, -1),
            (aliased_reaction.kind == ReactionKind.PROOF, 1),
            (aliased_reaction.kind == ReactionKind.DISPROOF, -1),
            (aliased_reaction.kind == ReactionKind.ACCEPT, 1),
            (aliased_reaction.kind == ReactionKind.REJECT, -1),
            (aliased_reaction.kind == ReactionKind.LIKE, 1),
            (aliased_reaction.kind == ReactionKind.DISLIKE, -1),
            else_=0)
        ).label('rating_stat'))

    return q
