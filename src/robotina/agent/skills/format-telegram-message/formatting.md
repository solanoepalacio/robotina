# MarkdownV2 Formatting Syntax

## Bold

Wrap with *text*:
- Input: Recipe saved
- Output: *Recipe saved*

## Italic

Wrap with _text_ (underscores — remember to escape underscores in non-italic text):
- Input: Note
- Output: _Note_

## Inline Code

Wrap with backticks:
- Input: carbonara
- Output: `carbonara`

## Hyperlink

[display text](url) — escape all special chars in display text:
- Input: link to recipe
- Output: [View recipe](https://example\.com/recipe)

## Bullet Lists

Use hyphen as bullet marker. Escape the hyphen marker itself:
- Each bullet line: \- Item text here
- Example:
  \- Monday: pasta
  \- Tuesday: soup
  \- Wednesday: salad

## Numbered Lists

MarkdownV2 has no native numbered list syntax. Use plain numbers with escaped period:
1\. First step
2\. Second step
3\. Third step

## Line Breaks

Use a single newline between lines in the formatted string.
