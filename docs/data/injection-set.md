# Data card: injection set

| | |
|---|---|
| **What it is** | 24 short passages in the style of filing text: 12 that carry an instruction to an assistant, and 12 that use the same words innocently |
| **Files** | [`eval/injection/cases.jsonl`](../../eval/injection/cases.jsonl) |
| **Licence** | MIT, like the rest of the repository; written for this project |
| **Built** | 2026-10-26 |
| **Used for** | Checking the prompt-injection patterns that quote instructions out of retrieved sources (step 6.2; [guide](../concepts/prompt-injection.md)) |

## What's in it

Each line has an `id`, `injected` (true or false) and the `text`.

- **Injected (`i01` to `i12`):** one form each. An order to ignore earlier instructions, a "disregard the guidelines" demand, a fake system prompt, "you are now ...", "new instructions:", chat markers (`<|im_start|>`, `[INST]`), a line that starts `assistant:`, "do not follow your instructions", "respond only with", "as an AI language model", and a request to print the hidden instructions. Some sit after an ordinary sentence of filing text, so a check must find them mid-page.
- **Look-alikes (`b01` to `b12`):** sentences a filing might contain, built on the same words. A currency effect that "can be ignored", "our systems prompt customers", "you are responsible for", a software developer, "instructions for voting", a board that "may override prior determinations", "Assistant Secretary:", "we may not follow the same accounting treatment", artificial intelligence tools, a forgotten control number, assistant store managers.

## Limits

- **Written with the patterns.** The passages and the patterns were written together, so the set shows the patterns do what they were written to do; it is no test against someone who has read them.
- **Small and in English.** One passage per form; no obfuscation, translation or encoding tricks.
- **Look-alikes are invented.** The real check for false alarms is the scan of the parsed corpus, which flagged none of its 53,901 pages.
