# VK-Check

## What is this?

VK-Check is a small applied AI system that reads a patient's symptoms and lab results and estimates their risk of Velorin-Kessler Syndrome, an invented disease that can be readily diagnosed given proper lab values and symptom notes.  The input can be any of four note styles: a standard U.S. EHR (Electronic Health Record) template, shorthand, a copy-forward follow-up, or a SOAP (Subjective-Objective-Assessment-Plan) draft from an ambient AI scribe.

To date, it's a limited single-prompt chat UI in front of a small tool-calling agent, with no conversation memory.  The agent evaluates whether to score or decline to score, and calls the appropriate tool.  Its first turn picks and calls the tool, and its second writes a reply.

## Why this project?

I wanted to explore building a small assistant for medical diagnosis: how to generate and validate synthetic data when there is no real condition and no clinicians who know about it, how a small trained model compares with frontier models, and how to build a thorough set of evals for all of it.

## How the data was made

The data consists of:

* synthetic patient records with lab results and symptoms
* a scoring rule for how the labs and symptoms combine to give a probability a patient has V-K syndrome
* 1 clinician note for each patient


A code generator, given a seed, deterministically produces a set of patients, labs, and a scoring rule.  An oracle reference system is given the true probability that a patient has V-K syndrome.  Patients are labeled as positive and negative for having the actual syndrome. The max AUC for the oracle system is still below 1.0 since it only knows the probability and not which way the patient was actually labeled for really having the syndrome based on random determination from probability. 

I then used Claude Haiku 5.5 to write a clinician's note for each patient in one of the four styles, from a common prompt plus a style-specific one based on publicly available sample notes in those styles.  That made roughly 5,700 records, which were split into development, train, test and adversarial (hard to diagnose, missing or wrong data, prompt injection) sets.  Every choice I made, such as prompts, settings and targets, was made on the development set.  Once the config and prompts were frozen, the test and adversarial sets got one run each, and each run's results went into a local ledger.

To check the notes looked real, I built a rating interface of the kind expert human reviewers might use: 80 notes with their labs, each marked plausible or not.  A second LLM, Sonnet 5.5, independent of the Haiku model that wrote the notes, was prompted to operate the user interface with Playwright and do the rating.  It took six rounds to pass.  Each round the reviewer found something a clinician would find implausible, like wrong or missing units, the same opening phrase in many notes, or scribe drafts with content a scribe would not include.  I watched the recordings, fixed the Haiku writer's prompts, and had a fresh sample rated again.  As an example, one fix was telling the writer that AI scribe notes really are wooden and mechanical.

<!-- video: /review-round4.webm | Round 4 of the review: Sonnet 5.5 operating the rating app with Playwright (11 MB) -->

## How it was trained and evaluated

I started with the evals, before creating any model.  Target AUC, Brier, and log loss scores were set on the development set from simple reference systems (the oracle mentioned above, a floor, and a labs-only model) and then fixed.  Evals used code graders.  Every result outputted a verdict: clearly met, clearly missed, or not distinguishable from the target at this sample size and allowed 95% interval.  After each final run I read a sample of the failing transcripts to see whether the system or the grader was at fault.

The baseline model-to-beat was a prompted frontier model, briefed in words on the disease.  I developed the prompt on Haiku 5.5, stopped at five versions, over which the AUC improved from 0.65 to 0.75.  A test against Sonnet 5.5 on the development set was no better, so I stuck with Haiku.  

The alternative was two simple models in sequence, both simple logistic classifiers built with scikit-learn.  The first is trained on clinical note text to determine symptoms.  The second is trained on the note reader's symptom predictions plus lab values.  On the test set (931 patients) it reached an AUC of 0.796, just under its 0.80 target but within noise, and better than the prompted frontier models I tested. The weights get saved in two JSON files.

Inference, once scoring is allowed and requested, just needs numpy.  Scoring just finds labs and symptoms in the note, multiplies them by the stored weights, adds them up, and turns the totals into the disease probability.

I logged training runs (params, seed, config hash, chosen train ids hash, model files) locally using MLflow, and then saved the final chosen model details as a model card following the HuggingFace format.  Tests will fail if the hash captured on the model card and actual model don't match.


## Results, lessons learned

* **This is of course not a full agent demo**, just a simple one.  It can't ask for clarifying questions yet, or respond to follow-ups about the report it generates, doesn't advise on collecting more labs, help with differential diagnosis from other 'look-alike' conditions.
* **My first prompts were weak.** The first version scored an AUC of 0.65 (0.5 is a coin flip, 1.0 is perfect), and it took five rewrites to reach 0.75.
* **No system can score perfectly here, by design.** Each label was drawn at random from the patient's true probability, so a patient at 30% still gets a "has the disease" label three times in ten.  About one patient in five ended up on the wrong side of 50%.  Many of the test failures I read were for that reason.
* **The assistant sometimes tried to call a tool twice.** In about 1 request in 180 it asked to score a note twice, or to score and decline in the same turn, usually on short follow-up notes with most labs missing.  The service runs the first call and ignores the second, so the visitor still gets the right answer, but my checks count it as a miss.  I left the prompt alone afterwards, because the test set had been looked at and changing it then would be tuning on the test.

## What would change with real data

Generated data would still be useful, since assistant setup, early model work and evaluation could start before any sensitive data was available.  But once available, I would train on real clinician notes, labs and confirmed diagnoses, validate realism with expert human reviewers, and make the evals tell Velorin-Kessler apart from conditions with overlapping labs and symptoms.

A real agent would probably sit inside an EHR system and need much more care with PHI/PII.  Here there is no real data, the text a visitor types is not written to the logs (only sizes, timings and outcomes), and keys stay on the server.  A real deployment would need all of that reviewed, an agreement with the model provider, access controls and an audit trail.  This was of course never validated on real patients, so it would also need clinical validation and regulatory review.

## Stack, code and contact

* Demo UI: Next.js on Vercel
* Model and inference API: Strands Agent, FastAPI on Vercel, Claude Haiku 5.5 as the assistant's model
* Evals: Inspect AI
* Training runs tracked with MLFlow

[Public code repository](https://github.com/bryanlandia/synthetic-medical-risk-agent). Contact: bryanlandia@gmail.com
