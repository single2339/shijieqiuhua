# Football Analysis Branch

This branch adds a football-specific analysis vertical inspired by
`a872034547-cpu/Football-2026`.

## What We Learned

Football-2026 is a Chrome MV3 extension focused on Titan007 match pages. Its
useful product pattern is:

- collect fixture, team form, 1x2 odds, Asian handicap, over/under, corners, and
  same-handicap history;
- normalize market odds into implied probabilities;
- run a deterministic local model before asking an LLM;
- attach web intelligence such as injuries, weather, team news, and lineup
  signals;
- report value, uncertainty, and risk instead of only a direction.

The extension also includes browser DOM extraction and public-sync code. Those
parts are not copied into OSINT Network. The OSINT branch keeps the football
logic server-side and source-agnostic so collectors can be added later.

## First Scope

`backend.football` provides a deterministic match analyzer:

- de-margin 1x2 market probabilities;
- estimate home/away scoring rates from recent goals for/against;
- run a Poisson score matrix for win/draw/loss, top scores, and over 2.5;
- compare model probability with market odds for positive expected value;
- cap Kelly stake suggestions at a small research limit;
- flag large odds movement, external risk signals, and thin intelligence.

API entrypoint:

```http
POST /api/football/analyze
```

This is research and risk analysis only. It does not provide guaranteed picks or
betting advice.

## Later Collectors

Good next additions are:

- football news and injury collectors;
- fixture and odds adapters behind provider-neutral schemas;
- a football dashboard tab for match watchlists and risk-ranked value edges;
- provenance tracking for each odds/intelligence signal.
