## What this is

*Suggested content:* A portfolio demonstration of a decision-support panel for a fictional disease, Velorin-Kessler syndrome. Say who it is for, what a visitor can do on each tab, and that the evaluations, not the chart, are the main work.

## Why a fictional disease

*Suggested content:* Real patient data was never an option. A made-up syndrome with a hidden scoring rule the project owns means the true answer is known, so every claim about accuracy can be checked, and nobody can mistake the output for medical advice.

## How it fits together

*Suggested content:* A visitor's chart becomes one message; a small note reader and risk classifier score it on a CPU; an agent built on Claude Haiku 5.5 decides whether to score or decline and writes a short reply; code, not the model, supplies the numbers and the disclaimer. A small diagram would help.

## The data

*Suggested content:* A seeded generator makes labs and notes; the notes are written by a language model in four documentation styles (AI scribe, EHR template, shorthand, copy-forward) and were reviewed for plausibility by a language-model reviewer, not a clinician. Mention the dev, test and adversarial splits and why the last two are looked at once each.

## The classifier

*Suggested content:* A logistic risk model with a note reader, about 200 kB, answering in under a millisecond on a CPU. Say how it compares with simply prompting a frontier model (the repository has a paired comparison) and point to the Model card tab.

## The agent and its guards

*Suggested content:* The scoring tool takes no arguments, so the model cannot change what is scored; declines use a closed set of reasons; a check replaces any reply that quotes a wrong number or names a drug; limits and a daily dollar cap bound the spend. Point at the injected-instruction example on the Try the agent tab.

## How it is measured

*Suggested content:* Code-graded evals built with Inspect AI, targets set before the runs, 95% intervals with a plain-language verdict, protected splits looked at once, failing transcripts read by a person. Give the headline results and say which targets were missed.

## What went wrong and what I learned

*Suggested content:* Honest notes: early prompts did poorly; label noise caps any system's score; a small share of requests make a second, refused tool call; the guards had to be built on a platform that keeps no state between requests.

## What would change with real data

*Suggested content:* This is not a medical device and was never validated on real patients. A real deployment would live inside an existing record system, use verified context, and need clinical validation and regulatory review.

## Stack, code and contact

*Suggested content:* Next.js and a Python function on Vercel, FastAPI and Strands, Inspect AI, MLflow, an Upstash store for the limits, specs kept with OpenSpec. Link [the repository](https://github.com/bryanlandia/synthetic-medical-risk-agent) and give a way to reach the author.
