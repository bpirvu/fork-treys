import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from .card import Card
from .deck import Deck
from .evaluator import Evaluator, PLOEvaluator


GAME_HAND_SIZES = {
    "holdem": Evaluator.HAND_LENGTH,
    "plo": PLOEvaluator.HAND_LENGTH,
}


class ValidationError(Exception):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="treys", description="Treys poker hand evaluation CLI")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--input",
        default=None,
        help="Path to a JSON payload file. Use - or omit to read JSON from stdin.",
    )
    common.add_argument(
        "--pretty",
        action="store_true",
        help="Print human-readable output instead of JSON.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "eval",
        parents=[common],
        help="Evaluate one or more hands against a board.",
    )
    subparsers.add_parser(
        "summary",
        parents=[common],
        help="Summarize hand strength across flop, turn, and river.",
    )
    subparsers.add_parser(
        "deal",
        parents=[common],
        help="Deal random board and player hands.",
    )
    subparsers.add_parser(
        "bench",
        parents=[common],
        help="Benchmark evaluation throughput.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        payload = load_payload(args.input)
        if args.command == "eval":
            result = run_eval(payload)
        elif args.command == "summary":
            result = run_summary(payload)
        elif args.command == "deal":
            result = run_deal(payload)
        elif args.command == "bench":
            result = run_bench(payload)
        else:
            raise ValidationError(f"Unsupported command: {args.command}")

        write_output(args.command, result, pretty=args.pretty)
        return 0
    except ValidationError as exc:
        write_error("validation_error", str(exc), pretty=args.pretty)
        return 2
    except Exception as exc:
        write_error("runtime_error", str(exc), pretty=args.pretty)
        return 1


def load_payload(source: str | None) -> dict[str, Any]:
    if source in (None, "-"):
        raw = sys.stdin.read()
    else:
        try:
            raw = Path(source).read_text(encoding="utf-8")
        except OSError as exc:
            raise ValidationError(f"Unable to read input file: {exc}") from exc

    if not raw.strip():
        raise ValidationError("No JSON input received")

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            f"Invalid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}"
        ) from exc

    if not isinstance(payload, dict):
        raise ValidationError("Input payload must be a JSON object")

    return payload


def run_eval(payload: dict[str, Any]) -> dict[str, Any]:
    request = parse_game_state_payload(payload, require_full_board=False)
    evaluator = create_evaluator(request["game"])
    board_ints = Card.hand_to_binary(request["board"])

    results = []
    best_rank: int | None = None
    winner_indexes: list[int] = []

    for player in request["players"]:
        hand_ints = Card.hand_to_binary(player["hand"])
        rank = evaluator.evaluate(hand_ints, board_ints)
        class_id = evaluator.get_rank_class(rank)
        player_result = {
            "index": player["index"],
            "name": player["name"],
            "hand": player["hand"],
            "rank": rank,
            "class_id": class_id,
            "class_name": evaluator.class_to_string(class_id),
            "percentage": 1.0 - evaluator.get_five_card_rank_percentage(rank),
        }
        results.append(player_result)

        if best_rank is None or rank < best_rank:
            best_rank = rank
            winner_indexes = [player["index"]]
        elif rank == best_rank:
            winner_indexes.append(player["index"])

    winners = [
        {"index": player["index"], "name": player["name"]}
        for player in request["players"]
        if player["index"] in winner_indexes
    ]

    return {
        "command": "eval",
        "game": request["game"],
        "board": request["board"],
        "players": results,
        "winners": winners,
    }


def run_summary(payload: dict[str, Any]) -> dict[str, Any]:
    request = parse_game_state_payload(payload, require_full_board=True)
    evaluator = create_evaluator(request["game"])
    board_ints = Card.hand_to_binary(request["board"])
    hands_ints = [Card.hand_to_binary(player["hand"]) for player in request["players"]]
    summary = evaluator.hand_summary_data(board_ints, hands_ints)
    players_by_index = {player["index"]: player for player in request["players"]}

    stages = []
    for stage in summary["stages"]:
        stage_players = []
        for player_result in stage["players"]:
            player = players_by_index[player_result["player"]]
            stage_players.append({
                "index": player["index"],
                "name": player["name"],
                "rank": player_result["rank"],
                "class_id": player_result["class_id"],
                "class_name": player_result["class_name"],
                "percentage": player_result["percentage"],
            })

        stages.append({
            "stage": stage["stage"],
            "board": [Card.int_to_str(card_int) for card_int in stage["board"]],
            "players": stage_players,
            "leaders": [
                {
                    "index": player_index,
                    "name": players_by_index[player_index]["name"],
                }
                for player_index in stage["leaders"]
            ],
        })

    return {
        "command": "summary",
        "game": request["game"],
        "board": request["board"],
        "players": [
            {
                "index": player["index"],
                "name": player["name"],
                "hand": player["hand"],
            }
            for player in request["players"]
        ],
        "stages": stages,
        "result": {
            "winners": [
                {
                    "index": player_index,
                    "name": players_by_index[player_index]["name"],
                }
                for player_index in summary["result"]["winners"]
            ],
            "rank": summary["result"]["rank"],
            "class_id": summary["result"]["class_id"],
            "class_name": summary["result"]["class_name"],
        },
    }


def run_deal(payload: dict[str, Any]) -> dict[str, Any]:
    game = parse_game(payload)
    player_count = require_int(payload.get("players"), "players", minimum=1)
    board_cards = require_int(payload.get("board_cards"), "board_cards", minimum=0, maximum=5)
    seed = payload.get("seed")

    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise ValidationError("seed must be an integer when provided")

    hand_size = GAME_HAND_SIZES[game]
    total_cards = (player_count * hand_size) + board_cards
    if total_cards > 52:
        raise ValidationError("Requested deal exceeds a standard 52-card deck")

    deck = Deck(seed=seed)
    board = [Card.int_to_str(card_int) for card_int in deck.draw(board_cards)]
    players = []
    for player_index in range(1, player_count + 1):
        hand = [Card.int_to_str(card_int) for card_int in deck.draw(hand_size)]
        players.append({
            "index": player_index,
            "name": f"player_{player_index}",
            "hand": hand,
        })

    return {
        "command": "deal",
        "game": game,
        "board": board,
        "players": players,
        "seed": seed,
    }


def run_bench(payload: dict[str, Any]) -> dict[str, Any]:
    game = parse_game(payload)
    iterations = require_int(payload.get("iterations"), "iterations", minimum=1)
    board_cards = require_int(payload.get("board_cards"), "board_cards", minimum=3, maximum=5)
    hand_size = GAME_HAND_SIZES[game]

    deck = Deck()
    boards: list[list[int]] = []
    hands: list[list[int]] = []

    for _ in range(iterations):
        boards.append(deck.draw(board_cards))
        hands.append(deck.draw(hand_size))
        deck.shuffle()

    evaluator = create_evaluator(game)
    started_at = time.perf_counter()
    for index in range(iterations):
        evaluator.evaluate(hands[index], boards[index])
    elapsed = time.perf_counter() - started_at
    average = elapsed / float(iterations)

    return {
        "command": "bench",
        "game": game,
        "iterations": iterations,
        "board_cards": board_cards,
        "average_seconds": average,
        "evaluations_per_second": 1.0 / average,
    }


def parse_game_state_payload(payload: dict[str, Any], require_full_board: bool) -> dict[str, Any]:
    game = parse_game(payload)
    hand_size = GAME_HAND_SIZES[game]
    board = parse_cards(
        payload.get("board"),
        "board",
        minimum_length=3,
        maximum_length=5,
    )

    if require_full_board and len(board) != 5:
        raise ValidationError("summary requires exactly 5 board cards")

    raw_players = payload.get("players")
    if not isinstance(raw_players, list) or not raw_players:
        raise ValidationError("players must be a non-empty list")

    players = []
    all_cards = list(board)

    for position, raw_player in enumerate(raw_players):
        if not isinstance(raw_player, dict):
            raise ValidationError(f"players[{position}] must be an object")

        raw_name = raw_player.get("name")
        if raw_name is None:
            name = f"player_{position + 1}"
        elif not isinstance(raw_name, str) or not raw_name.strip():
            raise ValidationError(f"players[{position}].name must be a non-empty string when provided")
        else:
            name = raw_name.strip()

        hand = parse_cards(
            raw_player.get("hand"),
            f"players[{position}].hand",
            expected_length=hand_size,
        )
        players.append({
            "index": position + 1,
            "name": name,
            "hand": hand,
        })
        all_cards.extend(hand)

    ensure_unique_cards(all_cards)

    return {
        "game": game,
        "board": board,
        "players": players,
    }


def parse_game(payload: dict[str, Any]) -> str:
    game = payload.get("game")
    if not isinstance(game, str):
        raise ValidationError("game must be a string")

    normalized = game.strip().lower()
    if normalized not in GAME_HAND_SIZES:
        allowed = ", ".join(sorted(GAME_HAND_SIZES))
        raise ValidationError(f"game must be one of: {allowed}")
    return normalized


def parse_cards(
    value: Any,
    field_name: str,
    expected_length: int | None = None,
    minimum_length: int | None = None,
    maximum_length: int | None = None,
) -> list[str]:
    if not isinstance(value, list):
        raise ValidationError(f"{field_name} must be an array of card strings")

    if expected_length is not None and len(value) != expected_length:
        raise ValidationError(f"{field_name} must contain exactly {expected_length} cards")

    if minimum_length is not None and len(value) < minimum_length:
        raise ValidationError(f"{field_name} must contain at least {minimum_length} cards")

    if maximum_length is not None and len(value) > maximum_length:
        raise ValidationError(f"{field_name} must contain at most {maximum_length} cards")

    cards = []
    for position, raw_card in enumerate(value):
        cards.append(normalize_card(raw_card, f"{field_name}[{position}]"))
    return cards


def normalize_card(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string")

    token = value.strip()
    if len(token) != 2:
        raise ValidationError(f"{field_name} must use two-character card notation like As or Td")

    normalized = token[0].upper() + token[1].lower()

    if normalized[0] not in Card.CHAR_RANK_TO_INT_RANK:
        raise ValidationError(f"{field_name} has an invalid rank: {value}")

    if normalized[1] not in Card.STR_SUITS:
        raise ValidationError(f"{field_name} has an invalid suit: {value}")

    return normalized


def ensure_unique_cards(cards: list[str]) -> None:
    seen = set()
    duplicates = []
    for card in cards:
        if card in seen and card not in duplicates:
            duplicates.append(card)
        seen.add(card)

    if duplicates:
        raise ValidationError("Duplicate cards are not allowed: {}".format(", ".join(duplicates)))


def require_int(value: Any, field_name: str, minimum: int | None = None, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{field_name} must be an integer")

    if minimum is not None and value < minimum:
        raise ValidationError(f"{field_name} must be at least {minimum}")

    if maximum is not None and value > maximum:
        raise ValidationError(f"{field_name} must be at most {maximum}")

    return value


def create_evaluator(game: str) -> Evaluator:
    if game == "holdem":
        return Evaluator()
    if game == "plo":
        return PLOEvaluator()
    raise ValidationError(f"Unsupported game: {game}")


def write_output(command: str, result: dict[str, Any], pretty: bool) -> None:
    if pretty:
        if command == "eval":
            sys.stdout.write(format_eval(result))
        elif command == "summary":
            sys.stdout.write(format_summary(result))
        elif command == "deal":
            sys.stdout.write(format_deal(result))
        elif command == "bench":
            sys.stdout.write(format_bench(result))
        else:
            sys.stdout.write(json.dumps(result, indent=2))
        if not result or not str(result).endswith("\n"):
            sys.stdout.write("\n")
        return

    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")


def write_error(error_type: str, message: str, pretty: bool) -> None:
    if pretty:
        sys.stderr.write(f"{error_type}: {message}\n")
        return

    json.dump({"error": {"type": error_type, "message": message}}, sys.stderr, indent=2)
    sys.stderr.write("\n")


def format_eval(result: dict[str, Any]) -> str:
    lines = [
        "Command: eval",
        f"Game: {result['game']}",
        "Board: {}".format(" ".join(result["board"])),
    ]

    for player in result["players"]:
        lines.append(
            "Player {index} ({name}): {hand} -> rank {rank}, {class_name}, percentage {percentage:.6f}".format(
                index=player["index"],
                name=player["name"],
                hand=" ".join(player["hand"]),
                rank=player["rank"],
                class_name=player["class_name"],
                percentage=player["percentage"],
            )
        )

    winner_names = ", ".join(winner["name"] for winner in result["winners"])
    lines.append(f"Winners: {winner_names}")
    return "\n".join(lines)


def format_summary(result: dict[str, Any]) -> str:
    lines = [
        "Command: summary",
        f"Game: {result['game']}",
        "Board: {}".format(" ".join(result["board"])),
    ]

    for stage in result["stages"]:
        lines.append("")
        lines.append(stage["stage"])
        lines.append("Board: {}".format(" ".join(stage["board"])))
        for player in stage["players"]:
            lines.append(
                "Player {index} ({name}): rank {rank}, {class_name}, percentage {percentage:.6f}".format(
                    index=player["index"],
                    name=player["name"],
                    rank=player["rank"],
                    class_name=player["class_name"],
                    percentage=player["percentage"],
                )
            )
        leader_names = ", ".join(leader["name"] for leader in stage["leaders"])
        lines.append(f"Leaders: {leader_names}")

    winner_names = ", ".join(winner["name"] for winner in result["result"]["winners"])
    lines.extend(
        [
            "",
            "Result",
            f"Winners: {winner_names}",
            f"Winning hand: {result['result']['class_name']} (rank {result['result']['rank']})",
        ]
    )
    return "\n".join(lines)


def format_deal(result: dict[str, Any]) -> str:
    lines = [
        "Command: deal",
        f"Game: {result['game']}",
        "Board: {}".format(" ".join(result["board"]) if result["board"] else "(empty)"),
    ]
    for player in result["players"]:
        lines.append("Player {index} ({name}): {hand}".format(
            index=player["index"],
            name=player["name"],
            hand=" ".join(player["hand"]),
        ))
    return "\n".join(lines)


def format_bench(result: dict[str, Any]) -> str:
    return "\n".join([
        "Command: bench",
        f"Game: {result['game']}",
        f"Iterations: {result['iterations']}",
        f"Board cards: {result['board_cards']}",
        f"Average seconds: {result['average_seconds']:.10f}",
        f"Evaluations per second: {result['evaluations_per_second']:.2f}",
    ])


if __name__ == "__main__":
    raise SystemExit(main())
