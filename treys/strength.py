import itertools
from math import comb

from .card import Card
from .evaluator import Evaluator
from .lookup import LookupTable
from .preflop_table import PRE_FLOP_RANK_SUMS, PRE_FLOP_TOTAL_BOARDS


FULL_DECK = tuple(Card.new(rank + suit) for rank in Card.STR_RANKS for suit in Card.STR_SUITS)


def canonical_holdem_hand_key(hand: list[int]) -> str:
    if len(hand) != Evaluator.HAND_LENGTH:
        raise ValueError("Hold'em hands must contain exactly 2 cards")

    cards = sorted(hand, key=Card.get_rank_int, reverse=True)
    high_rank = Card.STR_RANKS[Card.get_rank_int(cards[0])]
    low_rank = Card.STR_RANKS[Card.get_rank_int(cards[1])]

    if high_rank == low_rank:
        return high_rank + low_rank

    suited = Card.get_suit_int(cards[0]) == Card.get_suit_int(cards[1])
    return high_rank + low_rank + ("s" if suited else "o")


def rank_percentage_from_rank_sum(rank_sum: int, completions: int) -> float:
    return 1.0 - (float(rank_sum) / float(completions * LookupTable.MAX_HIGH_CARD))


def preflop_rank_percentage(hand: list[int]) -> float:
    key = canonical_holdem_hand_key(hand)
    return rank_percentage_from_rank_sum(PRE_FLOP_RANK_SUMS[key], PRE_FLOP_TOTAL_BOARDS)


def exact_projected_rank_percentages(
    evaluator: Evaluator,
    board: list[int],
    hands: list[list[int]],
) -> tuple[list[float], int]:
    missing_board_cards = evaluator.BOARD_LENGTH - len(board)
    if missing_board_cards < 0:
        raise ValueError("Board cannot contain more than 5 cards")

    known_cards = set(board)
    for hand in hands:
        known_cards.update(hand)

    remaining = [card for card in FULL_DECK if card not in known_cards]
    completion_count = comb(len(remaining), missing_board_cards)
    rank_sums = [0] * len(hands)

    for completion in itertools.combinations(remaining, missing_board_cards):
        final_board = board + list(completion)
        for index, hand in enumerate(hands):
            rank_sums[index] += evaluator.evaluate(hand, final_board)

    return [
        rank_percentage_from_rank_sum(rank_sum, completion_count)
        for rank_sum in rank_sums
    ], completion_count
