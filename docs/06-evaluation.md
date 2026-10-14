# 6. Evaluation

Six questions, one or two per pipeline stage. Two are qualitative and should be
judged by someone with translation expertise, not by a script.

| # | Question | Kind |
|---|---|---|
| 1 | Are related languages successfully identified? | Objective |
| 2 | If open Bible translations are available for related languages, is their content successfully retrieved? | Objective |
| 3 | Is the correct related-language Bible text retrieved, given a target verse? | Objective |
| 4 | Is the related-language Bible text successfully back-translated into the LWC, given a target verse? | **Qualitative** |
| 5 | If figure-of-speech data exists for a target verse, is it successfully retrieved? | Objective |
| 6 | If figure-of-speech data exists for a target verse, is it successfully translated? | **Qualitative** |

## The qualitative questions

Question 4 has two axes: whether the back-translation is accurate, and whether
the result is *helpful*. These can come apart. An accurate back-translation of
an unhelpful related-language rendering passes the first and fails the second.
Record them separately.

Question 6 is likewise a judgment of translation quality.

## Notes on measurement

- Questions 2 and 5 are conditional. A target verse with no available
  related-language Bible, or no figure-of-speech data, is **not** a failure; it
  is out of scope for that run. The failure mode is RLR not *saying* that
  nothing was available
  ([02-jobs-to-be-done.md](02-jobs-to-be-done.md) §2.4, §2.5).
- Question 1 has no ground truth (see
  [07-limitations-and-future-work.md](07-limitations-and-future-work.md)).
  "Successfully identified" means "produces a defensible set".
- Question 3 is where versification bugs surface. Its fixtures should
  deliberately cross versification boundaries.
