# MarkdownV2 Character Escaping

All 18 special characters MUST be escaped with a backslash when they appear as
literal text (not as formatting markers). Failure to escape causes Telegram to
return: Bad Request: Can't parse entities

## Characters Requiring Escape

| Character | Escaped Form | Common Context |
|-----------|--------------|----------------|
| _ | \_ | Underscores in words |
| * | \* | Asterisks in text |
| [ | \[ | Square bracket open |
| ] | \] | Square bracket close |
| ( | \( | Parenthesis open |
| ) | \) | Parenthesis close |
| ~ | \~ | Tilde (approximate sign) |
| ` | \` | Backtick |
| > | \> | Greater-than |
| # | \# | Hash / number sign |
| + | \+ | Plus sign |
| - | \- | Hyphen / dash |
| = | \= | Equals sign |
| | | \| | Pipe / vertical bar |
| { | \{ | Curly brace open |
| } | \} | Curly brace close |
| . | \. | Period / full stop |
| ! | \! | Exclamation mark |

## Rules

1. Escape ALL occurrences, not just the first.
2. Do NOT double-escape. If the character is already escaped (\.), leave it.
3. Inside code spans (backtick-delimited), only backtick and backslash need escaping.
4. Inside pre blocks (triple-backtick), only backtick and backslash need escaping.

## Quick Examples

| Input text | Correct MarkdownV2 |
|------------|-------------------|
| Ready in 30 min! | Ready in 30 min\! |
| (serves 4) | \(serves 4\) |
| cost: ~8.50 | cost: \~8\.50 |
| prep: 10 min. | prep: 10 min\. |
| Mon-Fri | Mon\-Fri |
| step 1 + step 2 | step 1 \+ step 2 |
