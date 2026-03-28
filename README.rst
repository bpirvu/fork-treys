Treys
=====

A pure Python poker hand evaluation library

::

   [ 3 ❤ ] , [ 3 ♠ ]

Installation
------------

::

   $ pip install treys

Implementation notes
--------------------

Treys is a Python 3 port of
`Deuces <https://github.com/worldveil/deuces>`__ based on the initial work in
`msaindon’s <https://github.com/msaindon/deuces>`__ fork. Deuces was written 
by `Will Drevo <http://willdrevo.com/>`__ for the MIT Pokerbots Competition. 

Treys is lightweight and fast. All lookups are done with bit arithmetic and
dictionary lookups. That said, Treys won’t beat a C implemenation (~250k
eval/s) but it is useful for situations where Python is required or
where bots are allocated reasonable thinking time (human time scale).

Treys handles 5, 6, and 7 card hand lookups. The 6 and 7 card lookups
are done by combinatorially evaluating the 5 card choices.

Usage
-----

Treys is easy to set up and use.

.. code:: python

   >>> from treys import Card
   >>> card = Card.new('Qh')

Card objects are represented as integers to keep Treys performant and
lightweight.

Now let’s create the board and an example Texas Hold’em hand:

.. code:: python

   >>> board = [
   >>>     Card.new('Ah'),
   >>>     Card.new('Kd'),
   >>>     Card.new('Jc')
   >>> ]
   >>> hand = [
   >>>    Card.new('Qs'),
   >>>    Card.new('Th')
   >>> ]

Pretty print card integers to the terminal:

::

   >>> Card.print_pretty_cards(board + hand)
     [ A ❤ ] , [ K ♦ ] , [ J ♣ ] , [ Q ♠ ] , [ T ❤ ] 

If you have `termcolor <http://pypi.python.org/pypi/termcolor>`__
installed, they will be colored as well.

Otherwise move straight to evaluating your hand strength:

.. code:: python

   >>> from treys import Evaluator
   >>> evaluator = Evaluator()
   >>> print(evaluator.evaluate(board, hand))
   1600

Hand strength is valued on a scale of 1 to 7462, where 1 is a Royal
Flush and 7462 is unsuited 7-5-4-3-2, as there are only 7642 distinctly
ranked hands in poker.

If you want to deal out cards randomly from a deck, you can also do that
with Treys:

.. code:: python

   >>> from treys import Deck
   >>> deck = Deck()
   >>> board = deck.draw(5)
   >>> player1_hand = deck.draw(2)
   >>> player2_hand = deck.draw(2)

and print them:

::

   >>> Card.print_pretty_cards(board)
     [ 4 ♣ ] , [ A ♠ ] , [ 5 ♦ ] , [ K ♣ ] , [ 2 ♠ ]
   >>> Card.print_pretty_cards(player1_hand)
     [ 6 ♣ ] , [ 7 ❤ ] 
   >>> Card.print_pretty_cards(player2_hand)
     [ A ♣ ] , [ 3 ❤ ] 

Let’s evaluate both hands strength, and then bin them into classes, one
for each hand type (High Card, Pair, etc)

.. code:: python

   >>> p1_score = evaluator.evaluate(board, player1_hand)
   >>> p2_score = evaluator.evaluate(board, player2_hand)
   >>> p1_class = evaluator.get_rank_class(p1_score)
   >>> p2_class = evaluator.get_rank_class(p2_score)

or get a human-friendly string to describe the score,

::

   >>> print("Player 1 hand rank = %d (%s)\n" % (p1_score, evaluator.class_to_string(p1_class)))
   Player 1 hand rank = 6330 (High Card)

   >>> print("Player 2 hand rank = %d (%s)\n" % (p2_score, evaluator.class_to_string(p2_class)))
   Player 2 hand rank = 1609 (Straight)

or, coolest of all, get a blow-by-blow analysis of the stages of the
game with relation to hand strength:

::

   >>> hands = [player1_hand, player2_hand]
   >>> evaluator.hand_summary(board, hands)

   ========== FLOP ==========
   Player 1 hand = High Card, percentage rank among all hands = 0.893192
   Player 2 hand = Pair, percentage rank among all hands = 0.474672
   Player 2 hand is currently winning.

   ========== TURN ==========
   Player 1 hand = High Card, percentage rank among all hands = 0.848298
   Player 2 hand = Pair, percentage rank among all hands = 0.452292
   Player 2 hand is currently winning.

   ========== RIVER ==========
   Player 1 hand = High Card, percentage rank among all hands = 0.848298
   Player 2 hand = Straight, percentage rank among all hands = 0.215626

   ========== HAND OVER ==========
   Player 2 is the winner with a Straight

CLI
---

Treys also includes a JSON-first CLI with subcommands for:

- current hand evaluation (``eval``)
- street-by-street summaries on a full 5-card board (``summary``)
- current or projected Hold'em hand strength on partial boards (``strength``)
- random dealing (``deal``)
- benchmark runs (``bench``)

Local development shell helper
------------------------------

If you are working from a checkout of this repository, add this shell
function to your ``~/.zshrc`` so you can call the CLI from anywhere:

.. code:: bash

   treys-dev() {
     (
       cd /Users/bpirvu/devel/test/fork-treys || return 1
       UV_CACHE_DIR="$TMPDIR/uv-cache" uv run python -m treys.cli "$@"
     )
   }

Reload your shell after adding it:

.. code:: bash

   source ~/.zshrc

Then use ``treys-dev ...`` in the examples below.

How the CLI works
-----------------

- Input is JSON.
- Pass JSON on stdin or with ``--input <file>``.
- Output is JSON by default.
- Add ``--pretty`` for human-readable output.

Examples:

.. code:: bash

   $ treys eval --input payload.json
   $ treys strength --pretty <<'EOF'
   {"game":"holdem","board":[],"players":[{"name":"p1","hand":["As","Ah"]}]}
   EOF

Command summary
---------------

``eval``
   Scores the current made hand.
   Hold'em and PLO are supported.
   Requires 3-5 board cards.

``summary``
   Shows flop/turn/river strength progression.
   Hold'em and PLO are supported.
   Requires exactly 5 board cards.

``strength``
   Returns the hand-strength metric used by the README examples.
   Hold'em only.
   Accepts 0-5 board cards.
   For 0-2 board cards it returns projected strength, not win probability.

``deal``
   Deals random cards using Treys' ``Deck``.

``bench``
   Runs evaluation throughput benchmarks.

Evaluate a Hold'em board from stdin:

.. code:: bash

   $ treys eval <<'EOF'
   {"game":"holdem","board":["Ah","Kd","Jc"],"players":[{"name":"p1","hand":["Qs","Th"]}]}
   EOF

Request human-readable output instead of JSON:

.. code:: bash

   $ treys eval --pretty <<'EOF'
   {"game":"holdem","board":["Ah","Kd","Jc"],"players":[{"name":"p1","hand":["Qs","Th"]}]}
   EOF

Current or projected Hold'em rank strength:

.. code:: bash

   $ treys strength <<'EOF'
   {"game":"holdem","board":[],"players":[{"name":"p1","hand":["As","Ah"]}]}
   EOF

Projected Hold'em rank strength from a partial board:

.. code:: bash

   $ treys strength <<'EOF'
   {"game":"holdem","board":["Ah","Kd"],"players":[{"name":"p1","hand":["Qs","Th"]}]}
   EOF

What the main output fields mean:

- ``rank_percentage``: a float from ``0.0`` to ``1.0`` where higher is better
- ``rank_zero_to_hundred``: the same metric rounded to an integer from ``0`` to ``100``
- ``percentage``: compatibility alias for ``rank_percentage``
- ``mode``:
  ``current`` means the board already has enough cards to score the made hand directly
  ``projected`` means the CLI averaged over all legal future board completions
- ``method``:
  ``precomputed_table`` for fast preflop Hold'em strength
  ``exact_rollout`` for 1-2 board cards
  ``direct`` for 3-5 board cards
- ``completions_evaluated``: how many future boards were considered

Important:

- ``rank_percentage`` and ``rank_zero_to_hundred`` are hand-strength metrics.
- They are not pot-winning probability.
- A higher number is better.
- There is no threshold that guarantees a win, because these metrics do not model opponents.
