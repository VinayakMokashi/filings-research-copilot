# Data card: hybrid question set

| | |
|---|---|
| **What it is** | 10 questions that each need figures and an explanation: the figures are in the facts database, the reasons only in the filing's text |
| **Files** | [`eval/hybrid/questions.jsonl`](../../eval/hybrid/questions.jsonl) |
| **Licence** | MIT, like the rest of the repository; written for this project |
| **Built** | 2026-10-23, against the facts database and the 84-filing corpus of that date |
| **Used for** | The hybrid-answer prototype (step 4.6): does an answer give the right figures and explain them from the pages it cites? |

## What's in it

Each question names one dev company and is answered from one of its filings in the corpus. The file lists, for each, the figures a right answer gives and what its explanation should address.

| ID | Company | Filing | Asks for |
|---|---|---|---|
| h01 | 3M | 10-K, 2018 | Capital expenditure in 2017 and 2018, and what it went to |
| h02 | Coca-Cola | 10-K, 2017 | Net income in 2016 and 2017, and why it fell |
| h03 | Walmart | 10-K, fiscal 2019 | Operating income in fiscal 2018 and 2019, and the reasons for the change |
| h04 | Nike | 10-K, fiscal 2019 | Revenues in fiscal 2018 and 2019, and what drove the growth |
| h05 | MGM Resorts | 10-K, 2020 | Revenue in 2019 and 2020, and what caused the fall |
| h06 | Boeing | 10-K, 2018 | Revenue in 2017 and 2018, and which businesses drove the change |
| h07 | Adobe | 10-K, fiscal 2016 | Revenue in fiscal 2015 and 2016, and what the company credits for the growth |
| h08 | Block | 10-K, 2020 | Revenue in 2019 and 2020, and what drove the change |
| h09 | General Mills | 10-K, fiscal 2020 | Free cash flow in fiscal 2020, and what drove cash from operations |
| h10 | Boeing | 10-K, 2022 | Commercial Airplanes revenue in 2021 and 2022, and why it changed |

Two questions test the edges:

- **h06, a restated figure.** Boeing adopted the new revenue standard in 2018 and restated 2017: $93,392 million as first reported, $94,005 million in the 2018 10-K. The database holds both (`value` and `latest_value`), and either counts.
- **h10, a figure the database doesn't hold.** SEC's company facts have no segment figures ([data card](sec-company-facts.md)), so the database holds only Boeing's total revenue, $66,608 million for 2022. A right answer takes the segment's figures from the filing (PDF page 24), and the total mustn't stand in for them.

## How it was built

1. **Questions by hand,** on dev companies only (none of the 12 test companies), each about a filing in the corpus whose management discussion covers the figures.
2. **Figures as formulas** over annual values, such as `capital_expenditure[2018]`, or `operating_cash_flow[2020] - capital_expenditure[2020]` for free cash flow. `copilot.eval.hybrid.expected_values` evaluates them against the facts database. h10's figures are values, checked against the filing page.
3. **A test** checks that the set loads, that every formula parses, and that no question names a test company.

## Scoring

- **Figures:** a figure counts as given when a number in the answer is within 1% of it, allowing for thousands, millions and billions, the way the answer judge compares figures. `figures_given` is the share given; `all_figures` says whether all were.
- **Citations and support:** whether the answer cites the query result and a page, and whether the faithfulness judge finds each sentence supported by the sources it cites.
- **Explanation:** read by hand against the question's `explain` field: does the answer give the reasons the filing gives?

## Limits

Ten questions show whether the approach works and how it fails; they can't measure a rate precisely, since each question is ten points. The same project wrote the questions and the agents, so they test the intended use rather than unexpected wording.
