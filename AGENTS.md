# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Treys is a pure Python poker hand evaluation library (Python 3.12+). Cards are 32-bit integers with bit fields for prime, rank, suit, and bitrank. No external dependencies — changes must not add any (termcolor is optional, for colored printing).

## Testing

No test suite. Verify changes by running the example/benchmark scripts:
- `python go.py` — Texas Hold'em demo
- `python plo_go.py` — PLO/Omaha demo
- `python perf.py` — Hold'em evaluation benchmark
- `python plo_perf.py` — PLO evaluation benchmark

## Key Architecture

- **Card representation**: 32-bit int with prime number, rank, suit flags, and bitrank fields. Bit manipulation is central — understand the encoding before modifying card.py or lookup.py.
- **Hand evaluation**: Uses Cactus Kev's algorithm via prime-product lookup tables. 5-card hands evaluated directly; 6/7-card hands use brute-force C(n,5) combinations.
- **LookupTable**: Regenerated on every `Evaluator()` instantiation (not cached). Hand strength scale: 1 (Royal Flush) to 7462 (worst hand).
- **PLOEvaluator** extends Evaluator — changes to Evaluator may affect PLO evaluation.
- **No input validation** by design ("that's cycles!") — functions assume valid input.

## Code Style

- Use modern type hints (`list[int]`, `dict[str, int]` — no `typing.List`/`typing.Dict`).
- Card class is all `@staticmethod` — no instances.
