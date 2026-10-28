# VK-Check

## What is this?

VK-Check is a small applied AI system that reads a patient's symptoms and lab results and estimates their risk of Velorin-Kessler Syndrome, an invented disease that can be diagnosed with a high degree of accuracy given proper lab values and symptom notes.  The input can be any of four note styles: a standard U.S. EHR (Electronic Health Record) template, shorthand, a copy-forward follow-up, or a SOAP (Subjective-Objective-Assessment-Plan) draft from an ambient AI scribe.

## Why this project?

I wanted to explore building a small chat agent for medical diagnosis: how to generate and validate synthetic data when there is no real condition and no clinicians who know about it, how a small trained model compares with frontier models, and how to build a thorough set of evals for all of it.

A fictional disease made that possible. Real patient data was never an option, and with a made-up syndrome and a hidden scoring rule I know the true probability for every synthetic patient, so a score can be checked against the truth and not only against a label.

## How the data was made

A seeded generator produces the patients, labs and hidden scoring rule, so the same seed always gives the same data.  Haiku 5.5 then wrote a clinician's note for each patient in one of the four styles, from a common prompt plus a style-specific one and publicly available sample text.  That made roughly 5,700 records, split into development, train, test and adversarial (hard to diagnose, missing or wrong data, prompt injection) sets.  Every choice I made, such as prompts, settings and targets, was made on the development set.  The test and adversarial sets got one look per system, after it was frozen, and each run went into a ledger.

To check the notes looked real, I built a rating interface of the kind expert human reviewers would use: 80 notes with their labs, each marked plausible or not.  A second LLM, Sonnet 5.5, independent of the Haiku model that wrote the notes, was prompted to operate the user interface with Playwright and do the rating.  It took six rounds to pass.  Each round the reviewer found something a clinician would find implausible, like wrong or missing units, the same opening phrase in many notes, or scribe drafts with content a scribe would not include.  I watched the recordings, fixed the writer's prompts, and had a fresh sample rated again.  One fix was telling the writer that AI scribe notes really are wooden and mechanical.

<!-- video: /review-round4.webm | Round 4 of the review: Sonnet 5.5 operating the rating app with Playwright (11 MB, loads when played) -->

## How it was evaluated

I started with the evals, before any model.  Targets were set on the development set from simple reference systems (an oracle that knows the answer, a floor, and a labs-only model) and then fixed.  Most scorers are code, not an LLM judge.  Every result has a 95% interval and a plain verdict: clearly met, clearly missed, or not distinguishable from the target at this sample size.  After each final run I read a sample of the failing transcripts to see whether the system or the grader was at fault.

The baseline was a prompted frontier model, briefed in words on the disease.  I developed the prompt on Haiku 5.5, capped at five versions, and the AUC went from 0.65 to 0.75.  Sonnet 5.5 was no better on the development set, so I stuck with Haiku.  On the test set (931 patients, one look) the trained classifier reaches an AUC of 0.796, just under its 0.80 target but within the noise of it, and prompted Haiku reaches 0.735, clearly under.  The Model card tab has the classifier's full results.

## How it works

A visitor's chart becomes one message.  A small note reader and risk classifier score it on a CPU, and an agent built on Claude Haiku 5.5 decides whether to score or decline and writes a short reply.  Code, not the model, supplies the numbers and the disclaimer.

```text
chart or note --> web app --> agent (secret, size, rate and spend checks)
                                 |--> score tool --> note reader + classifier --> report
                                 |--> decline tool (closed list of reasons)
                  reply check <--+  the model's short summary of the report
```

The classifier is a simple logistic model: training set a weight for each lab and symptom, and the note reader turns free text into those same features.  It is about 200 kB and answers in under a millisecond.  The agent's scoring tool takes no arguments, so the model cannot change what is scored.  Declines use a closed set of reasons, and a check replaces any reply that quotes a wrong number or names a drug.  Limits per visitor and a daily dollar cap bound the spend.  On the Try the agent tab, the example with an instruction hidden in the note shows the injection being ignored.

## What went wrong and what I learned

* **My first prompts were weak.** The first version scored an AUC of 0.65 (0.5 is a coin flip, 1.0 is perfect), and it took five rewrites to reach 0.75.
* **No system can score perfectly here, by design.** Each label was drawn at random from the patient's true probability, so a patient at 30% still gets a "has the disease" label three times in ten.  About one patient in five ended up on the wrong side of 50%, and in the failures I read, many were exactly that.
* **The agent sometimes tried to call a tool twice.** In about 1 request in 180 it asked to score a note twice, or to score and decline in the same turn, usually on short follow-up notes with most labs missing.  The service runs the first call and ignores the second, so the visitor still gets the right answer, but my checks count it as a miss.  I left the prompt alone afterwards, because the test set had been looked at and changing it then would be tuning on the test.
* **The realism check was an LLM, not a clinician.** It can catch what looks odd, not whether a real doctor would write these notes, so the data cannot claim more than plausibility.

## What would change with real data

Generated data would still be useful, since agent setup, early model work and evaluation could start before any sensitive data was available.  But I would train on real clinician notes, labs and confirmed diagnoses, validate realism with expert human reviewers, and make the evals tell Velorin-Kessler apart from conditions with overlapping labs and symptoms.

A real system would probably sit inside an EHR and need much more care with PHI/PII.  Here there is no real data, the text a visitor types is not written to the logs (only sizes, timings and outcomes), and keys stay on the server.  A real deployment would need all of that reviewed, an agreement with the model provider, access controls and an audit trail.  This is not a medical device and was never validated on real patients, so it would also need clinical validation and regulatory review.

## Stack, code and contact

* Agent UI: Next.js on Vercel
* Model and inference API: FastAPI on Vercel, Claude Haiku 5.5 as orchestrator agent
* Evals: Inspect AI, with trials recorded with MLflow

[Public code repository](https://github.com/bryanlandia/synthetic-medical-risk-agent). Contact: bryanlandia@gmail.com
