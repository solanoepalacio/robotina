# Formatting Examples

Real examples of notification messages before and after MarkdownV2 formatting.

#### Example 1: Simple confirmation

Before:
  The recipe has been saved successfully.

After:
  The recipe has been saved successfully\.

#### Example 2: Structured data

Before:
  Recipe added: Spaghetti Carbonara. Servings: 4, prep 10 min, cook 20 min.

After:
  *Recipe added:* Spaghetti Carbonara\.
  Servings: 4, prep 10 min, cook 20 min\.

#### Example 3: Bullet list

Before:
  This week's meal plan: Monday pasta, Tuesday soup, Wednesday salad, Thursday stir fry, Friday pizza.

After:
  *This week's meal plan:*
  \- Monday: pasta
  \- Tuesday: soup
  \- Wednesday: salad
  \- Thursday: stir fry
  \- Friday: pizza

#### Example 4: Special characters

Before:
  Ready in 30 min! (serves 4) — cost: ~€8.50

After:
  Ready in 30 min\! \(serves 4\) — cost: \~€8\.50

Key escapes: ! becomes \!, ( becomes \(, ) becomes \), ~ becomes \~, . becomes \.
Note: the em dash — does NOT need escaping (not in the 18 special chars).

## Common Mistakes

| Mistake | Wrong | Correct |
|---------|-------|---------|
| Unescaped period | 10 min. | 10 min\. |
| Unescaped exclamation | Done! | Done\! |
| Unescaped tilde | ~3 hours | \~3 hours |
| Unescaped hyphen (as literal) | Mon-Fri | Mon\-Fri |
| Unescaped parentheses | (optional) | \(optional\) |
