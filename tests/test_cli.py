import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(command: str, payload: dict, *extra_args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "treys.cli", command, *extra_args],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=ROOT,
    )


def run_cli_json(command: str, payload: dict, *extra_args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
    completed = run_cli(command, payload, *extra_args)
    if completed.stdout:
        return completed, json.loads(completed.stdout)
    return completed, {}


class TreysCLITests(unittest.TestCase):
    def test_holdem_eval_accepts_three_four_and_five_board_cards(self) -> None:
        board_variants = [
            ["Ah", "Kd", "Jc"],
            ["Ah", "Kd", "Jc", "2s"],
            ["Ah", "Kd", "Jc", "2s", "3d"],
        ]

        for board in board_variants:
            with self.subTest(board=board):
                completed, output = run_cli_json(
                    "eval",
                    {
                        "game": "holdem",
                        "board": board,
                        "players": [
                            {"name": "p1", "hand": ["Qs", "Th"]},
                            {"name": "p2", "hand": ["Ac", "Ad"]},
                        ],
                    },
                )

                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(output["game"], "holdem")
                self.assertEqual(output["winners"], [{"index": 1, "name": "p1"}])
                self.assertEqual(output["players"][0]["class_name"], "Straight")
                self.assertGreater(output["players"][0]["rank_percentage"], output["players"][1]["rank_percentage"])
                self.assertEqual(output["players"][0]["rank_percentage"], output["players"][0]["percentage"])
                self.assertEqual(
                    output["players"][0]["rank_zero_to_hundred"],
                    round(output["players"][0]["rank_percentage"] * 100),
                )

    def test_plo_eval_accepts_three_four_and_five_board_cards(self) -> None:
        board_variants = [
            ["Ah", "Kd", "Jc"],
            ["Ah", "Kd", "Jc", "2s"],
            ["Ah", "Kd", "Jc", "2s", "3d"],
        ]

        for board in board_variants:
            with self.subTest(board=board):
                completed, output = run_cli_json(
                    "eval",
                    {
                        "game": "plo",
                        "board": board,
                        "players": [
                            {"name": "p1", "hand": ["Qs", "Th", "9c", "8s"]},
                            {"name": "p2", "hand": ["Ac", "Ad", "4s", "5d"]},
                        ],
                    },
                )

                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(output["winners"], [{"index": 1, "name": "p1"}])
                self.assertEqual(output["players"][0]["class_name"], "Straight")

    def test_plo_eval_respects_exactly_two_cards_from_hand(self) -> None:
        completed, output = run_cli_json(
            "eval",
            {
                "game": "plo",
                "board": ["Ah", "Kh", "Qh", "2c", "3d"],
                "players": [
                    {"name": "one_heart", "hand": ["9h", "4s", "5s", "6s"]},
                    {"name": "two_hearts", "hand": ["Jh", "Th", "4c", "5d"]},
                ],
            },
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertNotEqual(output["players"][0]["class_name"], "Flush")
        self.assertEqual(output["players"][1]["class_name"], "Royal Flush")
        self.assertEqual(output["winners"], [{"index": 2, "name": "two_hearts"}])

    def test_holdem_summary_reports_stage_leaders(self) -> None:
        completed, output = run_cli_json(
            "summary",
            {
                "game": "holdem",
                "board": ["8h", "6s", "2c", "Ah", "5s"],
                "players": [
                    {"name": "p1", "hand": ["Qs", "9h"]},
                    {"name": "p2", "hand": ["6d", "Ad"]},
                ],
            },
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual([stage["stage"] for stage in output["stages"]], ["FLOP", "TURN", "RIVER"])
        self.assertEqual(output["stages"][0]["leaders"], [{"index": 2, "name": "p2"}])
        self.assertEqual(output["result"]["winners"], [{"index": 2, "name": "p2"}])
        self.assertEqual(output["result"]["class_name"], "Two Pair")
        self.assertEqual(
            output["stages"][0]["players"][0]["rank_percentage"],
            output["stages"][0]["players"][0]["percentage"],
        )
        self.assertEqual(
            output["stages"][0]["players"][0]["rank_zero_to_hundred"],
            round(output["stages"][0]["players"][0]["rank_percentage"] * 100),
        )

    def test_plo_summary_reports_lead_changes(self) -> None:
        completed, output = run_cli_json(
            "summary",
            {
                "game": "plo",
                "board": ["6d", "5d", "Qc", "Kd", "5c"],
                "players": [
                    {"name": "p1", "hand": ["9s", "Kh", "Ks", "Td"]},
                    {"name": "p2", "hand": ["6s", "Kc", "Qs", "4c"]},
                ],
            },
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(output["stages"][0]["leaders"], [{"index": 2, "name": "p2"}])
        self.assertEqual(output["stages"][1]["leaders"], [{"index": 1, "name": "p1"}])
        self.assertEqual(output["result"]["winners"], [{"index": 1, "name": "p1"}])
        self.assertEqual(output["result"]["class_name"], "Full House")

    def test_deal_is_deterministic_with_seed_for_both_games(self) -> None:
        for game, hand_size in [("holdem", 2), ("plo", 4)]:
            with self.subTest(game=game):
                payload = {"game": game, "players": 3, "board_cards": 5, "seed": 123}
                completed_one, output_one = run_cli_json("deal", payload)
                completed_two, output_two = run_cli_json("deal", payload)

                self.assertEqual(completed_one.returncode, 0, completed_one.stderr)
                self.assertEqual(completed_two.returncode, 0, completed_two.stderr)
                self.assertEqual(output_one, output_two)
                self.assertEqual(len(output_one["board"]), 5)

                all_cards = list(output_one["board"])
                for player in output_one["players"]:
                    self.assertEqual(len(player["hand"]), hand_size)
                    all_cards.extend(player["hand"])

                self.assertEqual(len(all_cards), len(set(all_cards)))

    def test_bench_smoke_test_for_holdem_and_plo(self) -> None:
        for game in ["holdem", "plo"]:
            with self.subTest(game=game):
                completed, output = run_cli_json(
                    "bench",
                    {"game": game, "iterations": 5, "board_cards": 5},
                )

                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(output["game"], game)
                self.assertEqual(output["iterations"], 5)
                self.assertGreater(output["average_seconds"], 0.0)
                self.assertGreater(output["evaluations_per_second"], 0.0)

    def test_validation_errors_return_exit_code_two(self) -> None:
        invalid_payloads = [
            {
                "game": "holdem",
                "board": ["Ah", "Kd", "1c"],
                "players": [{"hand": ["Qs", "Th"]}],
            },
            {
                "game": "holdem",
                "board": ["Ah", "Kd", "Jc"],
                "players": [{"hand": ["Ah", "Th"]}],
            },
            {
                "game": "holdem",
                "board": ["Ah", "Kd", "Jc"],
                "players": [{"hand": ["Qs"]}],
            },
            {
                "game": "holdem",
                "board": ["Ah", "Kd", "Jc"],
                "players": [],
            },
        ]

        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                completed = run_cli("eval", payload)
                self.assertEqual(completed.returncode, 2)
                error = json.loads(completed.stderr)
                self.assertEqual(error["error"]["type"], "validation_error")

    def test_eval_short_board_error_points_to_strength(self) -> None:
        completed = run_cli(
            "eval",
            {
                "game": "holdem",
                "board": ["Ah"],
                "players": [{"name": "p1", "hand": ["Qs", "Th"]}],
            },
        )

        self.assertEqual(completed.returncode, 2)
        error = json.loads(completed.stderr)
        self.assertIn("treys strength", error["error"]["message"])

    def test_strength_preflop_uses_fast_table_and_is_canonical(self) -> None:
        hands = [
            ("pair", ["As", "Ah"]),
            ("suited", ["As", "Ks"]),
            ("offsuit", ["As", "Kh"]),
        ]

        results = {}
        for label, hand in hands:
            completed, output = run_cli_json(
                "strength",
                {
                    "game": "holdem",
                    "board": [],
                    "players": [{"name": label, "hand": hand}],
                },
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(output["method"], "precomputed_table")
            self.assertEqual(output["mode"], "projected")
            self.assertEqual(output["completions_evaluated"], 2118760)
            results[label] = output["players"][0]["rank_percentage"]
            self.assertEqual(
                output["players"][0]["rank_zero_to_hundred"],
                round(output["players"][0]["rank_percentage"] * 100),
            )

        self.assertGreater(results["pair"], results["suited"])
        self.assertGreater(results["suited"], results["offsuit"])

        completed, output = run_cli_json(
            "strength",
            {
                "game": "holdem",
                "board": [],
                "players": [{"name": "suited_alt", "hand": ["Ah", "Kh"]}],
            },
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(results["suited"], output["players"][0]["rank_percentage"])

        completed, output = run_cli_json(
            "strength",
            {
                "game": "holdem",
                "board": [],
                "players": [
                    {"name": "p1", "hand": ["As", "Ah"]},
                    {"name": "p2", "hand": ["Ks", "Qh"]},
                ],
            },
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(output["method"], "precomputed_table")
        self.assertEqual(len(output["players"]), 2)

    def test_strength_rollout_supports_one_and_two_board_cards(self) -> None:
        expected_completions = {
            1: 211876,
            2: 17296,
        }

        for board in [["Ah"], ["Ah", "Kd"]]:
            with self.subTest(board=board):
                completed, output = run_cli_json(
                    "strength",
                    {
                        "game": "holdem",
                        "board": board,
                        "players": [{"name": "p1", "hand": ["Qs", "Th"]}],
                    },
                )

                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(output["method"], "exact_rollout")
                self.assertEqual(output["mode"], "projected")
                self.assertEqual(output["completions_evaluated"], expected_completions[len(board)])
                self.assertIn("rank_percentage", output["players"][0])
                self.assertIn("rank_zero_to_hundred", output["players"][0])
                self.assertNotIn("rank", output["players"][0])

    def test_strength_current_mode_matches_eval_rank_percentage(self) -> None:
        payload = {
            "game": "holdem",
            "board": ["Ah", "Kd", "Jc"],
            "players": [
                {"name": "p1", "hand": ["Qs", "Th"]},
                {"name": "p2", "hand": ["Ac", "Ad"]},
            ],
        }

        eval_completed, eval_output = run_cli_json("eval", payload)
        strength_completed, strength_output = run_cli_json("strength", payload)

        self.assertEqual(eval_completed.returncode, 0, eval_completed.stderr)
        self.assertEqual(strength_completed.returncode, 0, strength_completed.stderr)
        self.assertEqual(strength_output["method"], "direct")
        self.assertEqual(strength_output["mode"], "current")

        for eval_player, strength_player in zip(eval_output["players"], strength_output["players"]):
            self.assertEqual(eval_player["rank"], strength_player["rank"])
            self.assertEqual(eval_player["class_name"], strength_player["class_name"])
            self.assertEqual(eval_player["rank_percentage"], strength_player["rank_percentage"])
            self.assertEqual(eval_player["rank_zero_to_hundred"], strength_player["rank_zero_to_hundred"])

    def test_strength_rejects_plo(self) -> None:
        completed = run_cli(
            "strength",
            {
                "game": "plo",
                "board": [],
                "players": [{"name": "p1", "hand": ["As", "Ah", "Ks", "Kh"]}],
            },
        )

        self.assertEqual(completed.returncode, 2)
        error = json.loads(completed.stderr)
        self.assertIn("holdem only", error["error"]["message"])

    def test_strength_pretty_output_is_human_readable(self) -> None:
        completed = run_cli(
            "strength",
            {
                "game": "holdem",
                "board": [],
                "players": [{"name": "p1", "hand": ["As", "Ah"]}],
            },
            "--pretty",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Command: strength", completed.stdout)
        self.assertIn("Method: precomputed_table", completed.stdout)
        self.assertIn("/100", completed.stdout)

    def test_eval_supports_file_input(self) -> None:
        payload = {
            "game": "holdem",
            "board": ["Ah", "Kd", "Jc"],
            "players": [{"name": "p1", "hand": ["Qs", "Th"]}],
        }

        temp_path = None
        try:
            with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
                json.dump(payload, handle)
                temp_path = Path(handle.name)

            completed = subprocess.run(
                [sys.executable, "-m", "treys.cli", "eval", "--input", str(temp_path)],
                text=True,
                capture_output=True,
                cwd=ROOT,
            )
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()

        self.assertEqual(completed.returncode, 0, completed.stderr)
        output = json.loads(completed.stdout)
        self.assertEqual(output["players"][0]["class_name"], "Straight")

    def test_pretty_output_is_human_readable(self) -> None:
        completed = run_cli(
            "eval",
            {
                "game": "holdem",
                "board": ["Ah", "Kd", "Jc"],
                "players": [
                    {"name": "p1", "hand": ["Qs", "Th"]},
                    {"name": "p2", "hand": ["Ac", "Ad"]},
                ],
            },
            "--pretty",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("Command: eval", completed.stdout)
        self.assertIn("Winners: p1", completed.stdout)


if __name__ == "__main__":
    unittest.main()
