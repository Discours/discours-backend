from orm.reaction import ReactionKind

PROPOSAL_REACTIONS = [
    ReactionKind.ACCEPT.value,
    ReactionKind.REJECT.value,
    ReactionKind.AGREE.value,
    ReactionKind.DISAGREE.value,
    ReactionKind.ASK.value,
    ReactionKind.PROPOSE.value,
]

PROOF_REACTIONS = [ReactionKind.PROOF.value, ReactionKind.DISPROOF.value]
RATING_REACTIONS = [ReactionKind.LIKE.value, ReactionKind.DISLIKE.value]
POSITIVE_REACTIONS = [ReactionKind.ACCEPT.value, ReactionKind.LIKE.value, ReactionKind.PROOF.value]
NEGATIVE_REACTIONS = [ReactionKind.REJECT.value, ReactionKind.DISLIKE.value, ReactionKind.DISPROOF.value]


def is_negative(x: ReactionKind) -> bool:
    return x.value in NEGATIVE_REACTIONS


def is_positive(x: ReactionKind) -> bool:
    return x.value in POSITIVE_REACTIONS
