# 7. Success metrics

Six questions, tracking the pipeline stages. Two are explicitly qualitative and
should be judged by someone with translation expertise, not by a script.

| # | Question | Kind |
|---|---|---|
| 1 | Are related languages successfully identified? | Objective |
| 2 | If open Bible translations are available for related languages, is their content successfully retrieved? | Objective |
| 3 | Is the correct related-language Bible text retrieved, given a target verse? | Objective |
| 4 | Is the related-language Bible text successfully back-translated into the LWC, given a target verse? | **Qualitative** |
| 5 | If figure-of-speech data exists for a target verse, is it successfully retrieved? | Objective |
| 6 | If figure-of-speech data exists for a target verse, is it successfully translated? | **Qualitative** |

## On the qualitative ones

Metric 4 is a qualitative judgment on two axes: whether the back translation is
successful, and whether the translated result is *helpful*. These can come apart
— an accurate back-translation of an unhelpful related-language rendering is a
pass on the first axis and a fail on the second. Record them separately.

Metric 6 is likewise a judgment call.

## Notes on measurement

- Metrics 2 and 5 are conditional. A target verse with no available
  related-language Bible, or no figure-of-speech data, is **not** a failure — it
  is out of scope for that run. The corresponding failure mode is RLR failing to
  *say* that nothing was available
  ([02-jobs-to-be-done.md](02-jobs-to-be-done.md) §2.4, §2.5).
- Metric 1 has no ground truth available (see
  [06-open-questions.md](06-open-questions.md) §Q4). Treat "successfully
  identified" as "produces a defensible set", and expect to argue about it.
- Metric 3 is where versification bugs will surface. It deserves fixtures that
  deliberately cross versification boundaries.
