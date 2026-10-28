## What is this?

VK-Check is a small applied AI system which can be used to evaluate a set of symptoms and lab results, as supplied from four main formats: standard U.S. EHR (Electronic Health Record) template notes, shorthand notes, copy-forward progress notes (follow-ups), and labs + visit record created as a SOAP format (Subjective-Objective-Assessment-Plan) record from an ambient AI scribe transcribing clinic visit audio.  Velorin-Kessler Syndrome is an invented disease which can be diagnosed with a high degree of accuracy given proper lab values and symptom notes.

## Why this project?

Broadly, VK-Check is a project undertaken to explore and demonstrate creating a small chat agent for use in medical diagnosis.  I wanted to think through a use case, how synthetic data could be generated and validated in the absence of a real condition and real human clinicians who know something about it. I wanted the synthetic data to represent a reasonable set of formats that a clinician might have for their patient notes, and compare result quality between a custom-trained small model and one or more frontier models.  Finally, I wanted to build out a comprehensive set of evals for the trained small model, the frontier model(s) and the orchestrating agent which responds to prompts through a web UI.

## Why a fictional disease?

Real patient data was never a real option. A made-up syndrome for which we can create a hidden scoring rule means we can check every claim for accuracy: for every synthetic patient the true probability of the disease is known, so we could compare a score with the truth and not only with a label.

## How the training and test data were generated

Separate LLM-based data generation and validation systems were created.  The patients, labs, and hidden scoring rules come from a seeded generator, so the same seed always gives the same patient data.  An LLM (Haiku 5.5) is used to generate clinician notes corresponding to the seed data, based on publicly available sample text styles for the record style (AI scribe, copy forward, EHR template, shorthand).  I passed a common cross-style prompt and an additional style-specific prompt to the LLM and tasked it to generate roughly 5,700 records (notes+labs), evenly split among note types. Splits for development, test, train, and adversarial (difficult to diagnose, missing or incorrect data, prompt injection) were created.

**One look at the test and adversarial splits.** All choices made during development (prompts, model settings, targets) were made while running on the separate development split. The test and adversarial splits were each run once per system, after that system was frozen, and the run was recorded in a ledger.

**Checking that the notes look real.** A web-based user interface (Next.js, local dev only) was set up to simulate what would be given to expert human reviewers to determine whether the training and test data sets were realistic representations of clinician notes for possible V-K diagnosis.  It was a test record plausibility check only.  It provided 80 distinct clinical notes + lab results and an indication of which type of note (AI Scribe, shorthand, etc.) the test data represented.  A second LLM, Sonnet 5.5, independent of the Haiku model that wrote the notes, was prompted to operate the user interface with Playwright and mark each note as plausible or not.

It took six rounds to get a good result. Each round the reviewer's comments pointed at something that a human clinician should find implausible; for example, wrong or missing units on the lab results, the same opening phrase in many notes, AI scribe drafts with content a scribe would not include. Some of the improvements were to prompt that it was actually normal for AI scribe style notes to sound wooden and mechanical.  Each round, the issue was fixed in the writer's prompts or rules, then a new sample was written, and it was rated again.  As a developer, I reviewed the screen recordings of the Playwright review sessions to find issues.  


## Eval-driven development

I started with the evals, before any model work. Targets were derived on the development split from simple reference systems (an oracle that knows the answer, a floor, and a labs-only model) and then fixed. Most scorers are code, not an LLM judge. Every target number allows for a 95% interval and returns a plain verdict: clearly met, clearly missed, or not distinguishable from the target at this sample size. After each final run I read a sample of the failing transcripts to check whether the system or the grader was at fault.

Headline results on the test split (931 synthetic patients, one look each):

* The classifier, and the agent built on it, reach an AUC of 0.796, just under the 0.80 target. That target was fixed on the development split before the runs: reach the labs-only baseline, then close half of the remaining gap to the oracle. The interval around 0.796 includes the target, so the miss cannot be told apart from a hit.
* A prompted Haiku 5.5, given the same written briefing about the disease, reaches an AUC of 0.735, clearly under the target. Its scores were compressed toward the middle.
* Among the targets missed were the frontier model's "uncertain" flag, which it set from doubts about the record rather than from the probability, and a very small rate of invalid reports (about 1 in 1,900 calls, which were due to a hallucinated extra field).

## Baseline frontier model testing

I wanted to establish a baseline performance using a prompted frontier model with a set of instructions on how to determine probability.  The idea was to develop the prompts and test first against a less expensive model, Haiku 5.5 and then do a full set of tests using Sonnet 5.5.  As it turned out, Sonnet 5.5 was no better than Haiku on the development split (an AUC of 0.74 against 0.75, well within the noise).  I stuck with Haiku for the full frontier model benchmark.

Prompt development was capped at five versions, each scored on the development split, and then frozen. The AUC of the Haiku baseline went from 0.65 with the first prompt to 0.75 with the fifth, mostly by describing in words which labs matter most and how to treat missing values.

## How it fits together

A visitor's chart becomes one message. A small note reader and risk classifier score it on a CPU. An agent built on Claude Haiku 5.5 decides whether to score or decline and writes a short reply. Code, not the model, supplies the numbers and the disclaimer.

```text
chart or note --> web app --> agent (secret, size, rate and spend checks)
                                 |--> score tool --> note reader + classifier --> report
                                 |--> decline tool (closed list of reasons)
                  reply check <--+  the model's short summary of the report
```

## The classifier

The alternative to the frontier model was a simple logistic model predicting the probability of Velorin-Kessler syndrome risk from the inputs.  The training established the weights for each feature (lab results, reported symptoms), and a small note reader turns the free text of a note into those same features. It is fitted on the training split only, with its settings chosen on the development split. The whole model is about 200 kB and answers in under a millisecond on a CPU.

On the same 931 test patients it scores better than the prompted Haiku baseline (an AUC of 0.796 against 0.735). The agent scores exactly the same as the classifier, because the agent's number comes from it. The Model card tab has the metrics, the data and the limits.

## The agent and its guards

The scoring tool takes no arguments, so the model cannot change what is scored. Declines use a closed set of reasons. A check replaces any reply that quotes a wrong number or names a drug. Limits per visitor and a daily dollar cap bound the spend. On the Try the agent tab, the example with an instruction hidden in the note shows the injection being ignored: the number still comes from the note, not from the instruction.

## What went wrong and what I learned

* **My first prompts for the frontier model were weak.** The first version barely ranked patients better than chance would suggest (an AUC of 0.65, where 0.5 is a coin flip and 1.0 is perfect). It took five rewrites, mostly spelling out in words which labs matter most and what to do when one is missing, to reach 0.75.
* **No system can score perfectly here, by design.** Each synthetic patient has a true probability of having the disease, and their label was then drawn at random from it. A patient with a 30% true probability still gets a "has the disease" label three times in ten. So even a perfect model is wrong on some patients, and in the failures I read, many were exactly that. About one patient in five ended up on the wrong side of 50%.
* **The agent sometimes tried to call a tool twice.** In about 1 request in 180 during testing, the model asked to score the note twice, or to score it and decline it in the same turn, usually on very short follow-up notes with most labs missing. The service runs the first call and ignores the second, so the visitor still gets the right answer, but my checks count it as a miss. I did not change the prompt afterwards, because the test set had already been looked at and changing it then would be tuning on the test.
* **The realism check was an LLM, not a clinician.** It can catch things that look odd, but it cannot tell me whether a real doctor would write these notes, so the data cannot claim more than plausibility.

## Future work

* Improve model training using 'real' patient clinician notes, lab results, and confirmed diagnoses.
* Improve the models and evals to reliably disambiguate Velorin-Kessler from other conditions with overlapping lab value/symptom sets.

## What would change with real data

The generated test data would still be useful in a real-world use-case.  Working from a generated set of test data would allow work on agent setup, initial model development, and evaluation to proceed before touching sensitive patient data, or before such data was made available.  Refinement of and validation of the realism of the test data would be done with a rating UI as in this example, but with expert human reviewers.

A real-world system might be directly integrated into an EHR system to provide generative AI chat and analysis.  Additional care would need to be taken with PHI/PII. In this demo there is no real data, the text a visitor types is not written to the logs (only sizes, timings and outcomes), and keys stay on the server. A real deployment would need all of that reviewed, with an agreement in place with the model provider, access controls and an audit trail.

This is not a medical device and was never validated on real patients. A real deployment would live inside an existing record system, use verified context, and need clinical validation and regulatory review.

## Stack, code and contact

* Agent UI: Next.js on Vercel
* Model and inference API: FastAPI on Vercel, Claude Haiku 5.5 as orchestrator agent
* Evals: Inspect AI, with trials recorded with MLflow

[Public code repository](https://github.com/bryanlandia/synthetic-medical-risk-agent). Contact: bryanlandia@gmail.com