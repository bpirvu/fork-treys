import itertools
from typing import Sequence

from .card import Card
from .lookup import LookupTable


class Evaluator:
    """
    Evaluates hand strengths using a variant of Cactus Kev's algorithm:
    http://suffe.cool/poker/evaluator.html

    I make considerable optimizations in terms of speed and memory usage, 
    in fact the lookup table generation can be done in under a second and 
    consequent evaluations are very fast. Won't beat C, but very fast as 
    all calculations are done with bit arithmetic and table lookups. 
    """

    HAND_LENGTH = 2
    BOARD_LENGTH = 5

    def __init__(self) -> None:

        self.table = LookupTable()
        
        self.hand_size_map = {
            5: self._five,
            6: self._six,
            7: self._seven
        }

    def evaluate(self, hand: list[int], board: list[int]) -> int:
        """
        This is the function that the user calls to get a hand rank. 

        No input validation because that's cycles!
        """
        all_cards = hand + board
        return self.hand_size_map[len(all_cards)](all_cards)

    def _five(self, cards: Sequence[int]) -> int:
        """
        Performs an evalution given cards in integer form, mapping them to
        a rank in the range [1, 7462], with lower ranks being more powerful.

        Variant of Cactus Kev's 5 card evaluator, though I saved a lot of memory
        space using a hash table and condensing some of the calculations. 
        """
        # if flush
        if cards[0] & cards[1] & cards[2] & cards[3] & cards[4] & 0xF000:
            handOR = (cards[0] | cards[1] | cards[2] | cards[3] | cards[4]) >> 16
            prime = Card.prime_product_from_rankbits(handOR)
            return self.table.flush_lookup[prime]

        # otherwise
        else:
            prime = Card.prime_product_from_hand(cards)
            return self.table.unsuited_lookup[prime]

    def _six(self, cards: Sequence[int]) -> int:
        """
        Performs five_card_eval() on all (6 choose 5) = 6 subsets
        of 5 cards in the set of 6 to determine the best ranking, 
        and returns this ranking.
        """
        minimum = LookupTable.MAX_HIGH_CARD

        for combo in itertools.combinations(cards, 5):

            score = self._five(combo)
            if score < minimum:
                minimum = score

        return minimum

    def _seven(self, cards: Sequence[int]) -> int:
        """
        Performs five_card_eval() on all (7 choose 5) = 21 subsets
        of 5 cards in the set of 7 to determine the best ranking, 
        and returns this ranking.
        """
        minimum = LookupTable.MAX_HIGH_CARD

        for combo in itertools.combinations(cards, 5):
            
            score = self._five(combo)
            if score < minimum:
                minimum = score

        return minimum

    def get_rank_class(self, hr: int) -> int:
        """
        Returns the class of hand given the hand hand_rank
        returned from evaluate. 
        """
        if hr >= 0 and hr <= LookupTable.MAX_ROYAL_FLUSH:
            return LookupTable.MAX_TO_RANK_CLASS[LookupTable.MAX_ROYAL_FLUSH]
        elif hr <= LookupTable.MAX_STRAIGHT_FLUSH:
            return LookupTable.MAX_TO_RANK_CLASS[LookupTable.MAX_STRAIGHT_FLUSH]
        elif hr <= LookupTable.MAX_FOUR_OF_A_KIND:
            return LookupTable.MAX_TO_RANK_CLASS[LookupTable.MAX_FOUR_OF_A_KIND]
        elif hr <= LookupTable.MAX_FULL_HOUSE:
            return LookupTable.MAX_TO_RANK_CLASS[LookupTable.MAX_FULL_HOUSE]
        elif hr <= LookupTable.MAX_FLUSH:
            return LookupTable.MAX_TO_RANK_CLASS[LookupTable.MAX_FLUSH]
        elif hr <= LookupTable.MAX_STRAIGHT:
            return LookupTable.MAX_TO_RANK_CLASS[LookupTable.MAX_STRAIGHT]
        elif hr <= LookupTable.MAX_THREE_OF_A_KIND:
            return LookupTable.MAX_TO_RANK_CLASS[LookupTable.MAX_THREE_OF_A_KIND]
        elif hr <= LookupTable.MAX_TWO_PAIR:
            return LookupTable.MAX_TO_RANK_CLASS[LookupTable.MAX_TWO_PAIR]
        elif hr <= LookupTable.MAX_PAIR:
            return LookupTable.MAX_TO_RANK_CLASS[LookupTable.MAX_PAIR]
        elif hr <= LookupTable.MAX_HIGH_CARD:
            return LookupTable.MAX_TO_RANK_CLASS[LookupTable.MAX_HIGH_CARD]
        else:
            raise Exception("Inavlid hand rank, cannot return rank class")

    def class_to_string(self, class_int: int) -> str:
        """
        Converts the integer class hand score into a human-readable string.
        """
        return LookupTable.RANK_CLASS_TO_STRING[class_int]

    def get_five_card_rank_percentage(self, hand_rank: int) -> float:
        """
        Scales the hand rank score to the [0.0, 1.0] range.
        """
        return float(hand_rank) / float(LookupTable.MAX_HIGH_CARD)

    def get_rank_percentage(self, hand_rank: int) -> float:
        """
        Returns a higher-is-better strength value in the [0.0, 1.0] range.
        """
        return 1.0 - self.get_five_card_rank_percentage(hand_rank)

    def hand_summary_data(self, board: list[int], hands: list[list[int]]) -> dict[str, object]:
        """
        Returns a structured summary of the hand as the board develops.

        Requires that the board is in chronological order for the
        analysis to make sense.
        """

        assert len(board) == self.BOARD_LENGTH, "Invalid board length"
        for hand in hands:
            assert len(hand) == self.HAND_LENGTH, "Invalid hand length"

        stages: list[dict[str, object]] = []

        for stage_index, stage_name in enumerate(["FLOP", "TURN", "RIVER"]):
            current_board = board[:(stage_index + 3)]
            best_rank = LookupTable.MAX_HIGH_CARD + 1
            leaders: list[int] = []
            player_summaries: list[dict[str, object]] = []

            for player_index, hand in enumerate(hands, start=1):
                rank = self.evaluate(hand, current_board)
                rank_class = self.get_rank_class(rank)
                player_summaries.append({
                    "player": player_index,
                    "rank": rank,
                    "class_id": rank_class,
                    "class_name": self.class_to_string(rank_class),
                    "rank_percentage": self.get_rank_percentage(rank),
                    "percentage": self.get_rank_percentage(rank),
                })

                if rank == best_rank:
                    leaders.append(player_index)
                elif rank < best_rank:
                    leaders = [player_index]
                    best_rank = rank

            stages.append({
                "stage": stage_name,
                "board": list(current_board),
                "players": player_summaries,
                "leaders": leaders,
            })

        final_rank = self.evaluate(hands[stages[-1]["leaders"][0] - 1], board)
        final_class_id = self.get_rank_class(final_rank)

        result = {
            "winners": list(stages[-1]["leaders"]),
            "rank": final_rank,
            "class_id": final_class_id,
            "class_name": self.class_to_string(final_class_id),
        }

        return {
            "stages": stages,
            "result": result,
        }

    def hand_summary(self, board: list[int], hands: list[list[int]]) -> None:
        """
        Gives a sumamry of the hand with ranks as time proceeds. 

        Requires that the board is in chronological order for the 
        analysis to make sense.
        """

        line_length = 10
        summary = self.hand_summary_data(board, hands)

        for stage in summary["stages"]:
            line = "=" * line_length
            print("{} {} {}".format(line, stage["stage"], line))

            for player in stage["players"]:
                print(
                    "Player {} hand = {}, percentage rank among all hands = {}".format(
                        player["player"],
                        player["class_name"],
                        player["rank_percentage"],
                    )
                )

            if stage["stage"] != "RIVER":
                if len(stage["leaders"]) == 1:
                    print("Player {} hand is currently winning.\n".format(stage["leaders"][0]))
                else:
                    print("Players {} are tied for the lead.\n".format(stage["leaders"]))
            else:
                print()
                print("{} HAND OVER {}".format(line, line))
                if len(summary["result"]["winners"]) == 1:
                    print(
                        "Player {} is the winner with a {}\n".format(
                            summary["result"]["winners"][0],
                            summary["result"]["class_name"],
                        )
                    )
                else:
                    print(
                        "Players {} tied for the win with a {}\n".format(
                            summary["result"]["winners"],
                            summary["result"]["class_name"],
                        )
                    )


class PLOEvaluator(Evaluator):

    HAND_LENGTH = 4

    def evaluate(self, hand: list[int], board: list[int]) -> int:
        minimum = LookupTable.MAX_HIGH_CARD

        for hand_combo in itertools.combinations(hand, 2):
            for board_combo in itertools.combinations(board, 3):
                score = Evaluator._five(self, list(board_combo) + list(hand_combo))
                if score < minimum:
                    minimum = score

        return minimum
