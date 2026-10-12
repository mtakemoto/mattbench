# Coding benchmark plan: even or odd

**Planned — 2026-10-11:** This is a proposed first coding case, not a scored model run. It defines the behavior before the fixture and grader are built. The intended audience is the owner and anyone implementing the Inspect case.

## Why this case

The public [Codewars “Even or Odd” kata](https://www.codewars.com/kata/53da3dbb4a5168369a0000fe) asks for an integer-to-label function; the [HackerRank C++ loop exercise](https://www.hackerrank.com/challenges/c-tutorial-for-loop/problem) also uses exact lower-case `even` and `odd` output for values above its word-name range. Those exercises establish the familiar core. **Our proposed contract is deliberately broader:** it includes text input, invalid values, and numbers beyond fixed-width integer ranges. This is an adaptation, not a claim that either source has these requirements.

Python is the proposed first language because the existing Inspect coding pilot already runs Python in a disposable, networkless sandbox. Its `int` has unlimited precision, but CPython can limit decimal-string conversion length; using a bounded input contract avoids conflating that interpreter safeguard with parity. [Python numeric types](https://docs.python.org/3/library/stdtypes.html#numeric-types-int-float-complex); [Python `int()` input rules and conversion limit](https://docs.python.org/3/library/functions.html#int).

## Candidate-visible contract

Implement `classify_integer(text: str) -> str` in `parity.py` and a `python parity.py` command-line entry point. Keep the supplied interface. Do not use a floating-point conversion.

- A valid token has one optional ASCII `+` or `-`, followed by 1–256 ASCII digits `0`–`9`. Leading zeros are valid. Surrounding ASCII spaces and tabs are allowed; embedded whitespace and all other characters are invalid. The digit limit excludes the sign and surrounding whitespace.
- Return exactly `EVEN` or `ODD` from the function. Zero, including signed zero, is even. A negative integer has the same parity as its magnitude.
- For invalid string input, raise `ValueError`. For a non-string argument, raise `TypeError`; in particular, do not treat Python `True` as integer one. Python documents that `bool` is a subtype of `int`, so a generic `isinstance(x, int)` check would miss this distinction. [Python numeric types](https://docs.python.org/3/library/stdtypes.html#numeric-types-int-float-complex).
- The CLI accepts exactly one input line, with an optional final line ending. For valid input, print the classification and one newline to stdout, print nothing to stderr, and exit 0. For invalid input or extra lines, print `INVALID` and one newline to stderr, print nothing to stdout, and exit 2. No traceback, prompt, numeric echo, or tutorial explanation belongs in either output stream.

The CLI and function are intentionally separate checks. “Non-number output” is interpreted here as both a nonnumeric input path and a strict output format; the owner can narrow that interpretation before the case is implemented.

## Pinned test examples and expected outcomes

The table is a public specification. The eventual hidden tests should use different values from the same classes, plus a few metamorphic checks. `ValueError` and `TypeError` below refer to direct function calls; all invalid CLI inputs use the stderr/exit-2 behavior above.

| Class | Function input | Expected | What it catches |
|---|---|---|---|
| Basic even | `"2"` | `EVEN` | Core behavior |
| Basic odd | `"7"` | `ODD` | Core behavior |
| Zero | `"0"` | `EVEN` | Treating zero as neither or as odd |
| Signed zero | `"-0"`, `"+000"` | `EVEN` | Sign and leading zeros |
| Negative even | `"-42"` | `EVEN` | Negative path |
| Negative odd | `"-43"` | `ODD` | Sign-sensitive remainder mistakes |
| Surrounding ASCII whitespace | `" \t+0017\t "` | `ODD` | Accepted formatting |
| 32-bit boundary | `"2147483647"`, `"2147483648"` | `ODD`, `EVEN` | Fixed-width assumption |
| 64-bit boundary | `"9223372036854775807"`, `"9223372036854775808"` | `ODD`, `EVEN` | Larger fixed-width assumption |
| Beyond exact binary-float integer range | `"9007199254740993"` | `ODD` | Accidental float conversion |
| Long valid token | `"1" + "0" * 255` | `EVEN` | 256-digit bound and large input |
| Long valid odd token | `"1" + "0" * 254 + "1"` | `ODD` | Parity after many digits |
| Too many digits | `"1" * 257` | `ValueError` | Input bound |
| Empty or blank | `""`, `" \t "` | `ValueError` | No digits |
| Bare sign | `"+"`, `"-"` | `ValueError` | No digits after sign |
| Partial parse | `"12cats"`, `"8 4"` | `ValueError` | Accepting a valid prefix |
| Decimal or exponent | `"2.0"`, `"1e3"` | `ValueError` | Coercion or float parsing |
| Special words | `"NaN"`, `"Infinity"` | `ValueError` | Float special values |
| Other bases or separators | `"0x10"`, `"1_000"`, `"1,000"` | `ValueError` | Unspecified numeric syntax |
| Non-ASCII digit or space | `"１２"`, `"\u00a02"` | `ValueError` | Unicode normalization or broad `isdigit`/`strip` |
| Wrong Python type | `True`, `2`, `None` | `TypeError` | Coercion and `bool` subtype |

CLI-specific examples: stdin `b"8\n"` gives stdout `b"EVEN\n"`, empty stderr, exit 0; stdin `b"cat\n"` gives empty stdout, stderr `b"INVALID\n"`, exit 2; stdin `b"2\n3\n"` is invalid rather than silently using the first line. A valid result containing extra text, such as `"The answer is EVEN"`, fails the exact output check.

## Grading and run design

1. Stage a small `parity.py` skeleton in the existing networkless Inspect coding sandbox. Expose the public contract and a few example tests. Keep hidden tests and the scorer outside the candidate-writable directory.
2. Run direct function checks for every equivalence class, then subprocess checks for stdout, stderr, and exit status. Add deterministic property checks: toggling the last decimal digit between an even and odd digit flips parity; adding a sign or leading zeros does not. Bound input size and subprocess time.
3. Report separate results for ordinary integers, boundary/large values, invalid values, and CLI protocol. Full pass requires all four and no unrelated file changes. Show the failing class, not a single opaque score.
4. Compare the same fixture under base and careful prompts with fixed model ID, runtime, inference settings, tool access, call/time limits, and grader version. Record code diff, calls, tokens, latency, and cost. Do not run a paid variant until its cap and stop condition are set.

**Implementation decision still open:** whether the first runnable version should include the CLI or only the function. This document proposes both because output discipline and invalid input are part of the owner's interview signal. Freeze that scope before a scored run; do not revise the rubric after seeing model output.
