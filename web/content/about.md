## What is this?

VK-Check is a small applied AI system which evaluates a set of symptoms and lab results, supplied in one of four formats: standard U.S. EHR (Electronic Health Record) template notes, shorthand notes, copy-forward progress notes (follow-ups), and SOAP (Subjective-Objective-Assessment-Plan) records from an ambient AI scribe transcribing a clinic visit.  Velorin-Kessler Syndrome is an invented disease which can be diagnosed with a high degree of accuracy given proper lab values and symptom notes.

## Why this project?

I wanted to explore creating a small chat agent for medical diagnosis: how synthetic data could be generated and validated when there is no real condition and no clinicians who know about it, how a custom-trained small model compares with frontier models, and how to build a comprehensive set of evals for the small model, the frontier model(s) and the agent that answers through a web UI.

## Why a fictional disease?

Real patient data wasn't an option. With a made-up syndrome and a hidden scoring rule, the true probability of the disease is known for every synthetic patient, so a score can be compared with the truth and not only with a label.

## How the training and test data were generated

The patients, labs and hidden scoring rule come from a seeded generator, so the same seed always gives the same patient data.  An LLM (Haiku 5.5) then wrote clinician notes for those patients, based on publicly available sample text for each style (AI scribe, copy forward, EHR template, shorthand), using a common prompt plus a style-specific one.  That gave roughly 5,700 records (notes+labs), evenly split among note types, divided into development, train, test, and adversarial (difficult to diagnose, missing or incorrect data, prompt injection) splits.

**One look at test and adversarial.** Every choice (prompts, model settings, targets) was made on the development split. The test and adversarial splits were each run once per system, after it was frozen, and the run was recorded in a ledger.

**Checking that the notes look real.** A web interface (Next.js, local dev only) simulated what would be given to expert human reviewers to judge whether the notes were realistic clinician notes for possible V-K diagnosis.  It was a plausibility check only.  It showed 80 notes + lab results and which type of note each was.  A second LLM, Sonnet 5.5, independent of the Haiku model that wrote the notes, was prompted to operate the user interface with Playwright and mark each note as plausible or not.

It took six rounds to get a good result. Each round the reviewer pointed at something a clinician would find implausible: wrong or missing units, the same opening phrase in many notes, AI scribe drafts with content a scribe would not include. I fixed each in the writer's prompts or rules, wrote a new sample and had it rated again, watching the screen recordings of the review sessions to find issues. One fix was telling the writer that AI scribe notes are normally wooden and mechanical.

## Eval-driven development

I started with the evals, before any model work. Targets were derived on the development split from simple reference systems (an oracle that knows the answer, a floor, and a labs-only model) and then fixed. Most scorers are code, not an LLM judge. Every result has a 95% interval and a plain verdict: clearly met, clearly missed, or not distinguishable from the target at this sample size. After each final run I read a sample of the failing transcripts to check whether the system or the grader was at fault.

Top line on the test split (931 synthetic patients, one look each): the classifier reaches an AUC of 0.796, just under the 0.80 target but within the noise of it, and a prompted Haiku 5.5 reaches 0.735, clearly under. The Model card tab has the classifier's full results, and the repository has the rest.

## Baseline frontier model testing

I wanted a baseline from a prompted frontier model given instructions on how to determine probability.  The plan was to develop the prompts on a less expensive model, Haiku 5.5, then run the full tests on Sonnet 5.5.  Sonnet was no better than Haiku on the development split (an AUC of 0.74 against 0.75, well within the noise), so I stuck with Haiku for the full benchmark.

Prompt development was capped at five versions, each scored on the development split, then frozen. The AUC went from 0.65 with the first prompt to 0.75 with the fifth, mostly by describing in words which labs matter most and how to treat missing values.

## How it fits together

A visitor's chart becomes one message. A small note reader and risk classifier score it on a CPU. An agent built on Claude Haiku 5.5 decides whether to score or decline and writes a short reply. Code, not the model, supplies the numbers and the disclaimer.

```text
chart or note --> web app --> agent (secret, size, rate and spend checks)
                                 |--> score tool --> note reader + classifier --> report
                                 |--> decline tool (closed list of reasons)
                  reply check <--+  the model's short summary of the report
```

## The classifier

The alternative to the frontier model is a simple logistic model of Velorin-Kessler risk.  Training set the weight for each feature (lab results, reported symptoms), and a small note reader turns the free text of a note into those same features. It was fitted on the training split, with settings chosen on the development split. The whole model is about 200 kB and answers in under a millisecond on a CPU.

On the same 931 test patients it beats the prompted Haiku baseline (0.796 against 0.735 AUC). The agent scores exactly the same, because its number comes from the classifier. The Model card tab has the metrics, data and limits.

## The agent and its guards

The scoring tool takes no arguments, so the model cannot change what is scored. Declines use a closed set of reasons. A check replaces any reply that quotes a wrong number or names a drug. Limits per visitor and a daily dollar cap bound the spend. On the Try the agent tab, the example with an instruction hidden in the note shows the injection being ignored: the number still comes from the note, not from the instruction.

## What went wrong and what I learned

* **My first prompts for the frontier model were weak.** The first version scored an AUC of 0.65 (0.5 is a coin flip, 1.0 is perfect). It took five rewrites to reach 0.75.
* **No system can score perfectly here, by design.** Each synthetic patient has a true probability of the disease, and their label was drawn at random from it. A patient with a 30% probability still gets a "has the disease" label three times in ten, so even a perfect model is wrong on some patients. About one patient in five ended up on the wrong side of 50%, and in the failures I read, many were exactly that.
* **The agent sometimes tried to call a tool twice.** In about 1 request in 180 during testing, the model asked to score a note twice, or to score and decline it in the same turn, usually on very short follow-up notes with most labs missing. The service runs the first call and ignores the second, so the visitor still gets the right answer, but my checks count it as a miss. I left the prompt alone afterwards, because the test set had already been looked at and changing it then would be tuning on the test.
* **The realism check was an LLM, not a clinician.** It can catch things that look odd, but not whether a real doctor would write these notes, so the data cannot claim more than plausibility.

## Possible future work

* Improve model training using 'real' patient clinician notes, lab results, and confirmed diagnoses.
* Improve the models and evals to reliably disambiguate Velorin-Kessler from other conditions with overlapping lab value/symptom sets.

## What would change with real data

Generated test data would still be useful in a real-world use-case.  It would let work on agent setup, initial model development, and evaluation proceed before touching sensitive patient data, or before such data was available.  The realism of the data would be validated with a rating UI like this one, but with expert human reviewers.

A real system might be integrated directly into an EHR to provide generative AI chat and analysis, and would need much more care with PHI/PII. Here there is no real data, the text a visitor types is not written to the logs (only sizes, timings and outcomes), and keys stay on the server. A real deployment would need all of that reviewed, with an agreement with the model provider, access controls and an audit trail. This is not a medical device and was never validated on real patients; it would also need clinical validation and regulatory review.

## Stack, code and contact

* Agent UI: Next.js on Vercel
* Model and inference API: FastAPI on Vercel, Claude Haiku 5.5 as orchestrator agent
* Evals: Inspect AI, with trials recorded with MLflow

[Public code repository](https://github.com/bryanlandia/synthetic-medical-risk-agent). Contact: bryanlandia@gmail.com
