from sqlalchemy import and_

from orm.rating import is_negative, is_positive
from orm.reaction import Reaction, ReactionKind
from orm.shout import Shout
from services.db import local_session
from utils.diff import apply_diff, get_diff


def handle_proposing(kind: ReactionKind, reply_to: int, shout_id: int) -> None:
    with local_session() as session:
        if is_positive(kind):
            replied_reaction = (
                session.query(Reaction).filter(Reaction.id == reply_to, Reaction.shout == shout_id).first()
            )

            if replied_reaction and replied_reaction.kind is ReactionKind.PROPOSE.value and replied_reaction.quote:
                # patch all the proposals' quotes
                proposals = (
                    session.query(Reaction)
                    .filter(
                        and_(
                            Reaction.shout == shout_id,
                            Reaction.kind == ReactionKind.PROPOSE.value,
                        )
                    )
                    .all()
                )

                # patch shout's body
                shout = session.query(Shout).filter(Shout.id == shout_id).first()
                if shout:
                    body = replied_reaction.quote
                    # Use setattr instead of Shout.update for Column assignment
                    shout.body = body
                    session.add(shout)
                    session.commit()

                    # реакция содержит цитату -> обновляются все предложения
                    # (proposals) для соответствующего Shout.
                    for proposal in proposals:
                        if proposal.quote:
                            # Convert Column to string for get_diff
                            shout_body = str(shout.body) if shout.body else ""
                            proposal_dict = proposal.dict() if hasattr(proposal, "dict") else {"quote": proposal.quote}
                            proposal_diff = get_diff(shout_body, proposal_dict["quote"])
                            replied_reaction_dict = (
                                replied_reaction.dict()
                                if hasattr(replied_reaction, "dict")
                                else {"quote": replied_reaction.quote}
                            )
                            proposal_dict["quote"] = apply_diff(replied_reaction_dict["quote"], proposal_diff)

                            # Update proposal quote
                            proposal.quote = proposal_dict["quote"]  # type: ignore[assignment]
                            session.add(proposal)

        if is_negative(kind):
            # TODO: rejection logic
            pass
