---
phase: quick
plan: 260330-ggw
type: execute
wave: 1
depends_on: []
files_modified:
  - src/robotina/agent/prompts/robotina/V001.md
  - src/robotina/agent/prompts/send-notification/V001.md
  - src/robotina/agent/skills/household-manager/shared.md
  - experiments/send_notification.py
autonomous: true
must_haves:
  truths:
    - "Robotina main agent responds to users in Spanish"
    - "Send-notification agent preserves Spanish content and formats in Spanish"
    - "Shared skill notes that API data is in Spanish"
    - "Experiment test cases use Spanish text"
  artifacts:
    - path: "src/robotina/agent/prompts/robotina/V001.md"
      provides: "Spanish response directive"
      contains: "Spanish"
    - path: "src/robotina/agent/prompts/send-notification/V001.md"
      provides: "Spanish content preservation directive"
      contains: "Spanish"
    - path: "src/robotina/agent/skills/household-manager/shared.md"
      provides: "API data language note"
      contains: "Spanish"
    - path: "experiments/send_notification.py"
      provides: "Spanish test cases"
      contains: "receta"
  key_links: []
---

<objective>
Add Spanish language support to Robotina agents by updating system prompts, skill files, and experiment test cases.

Purpose: Robotina serves a Spanish-speaking household. All user-facing responses must be in Spanish, while internal instructions (prompts, tool descriptions, skill documentation) remain in English.

Output: Updated prompt files, shared skill file, and experiment test cases.
</objective>

<execution_context>
@/home/solanoe/code/robotina-gsd/.claude/get-shit-done/workflows/execute-plan.md
@/home/solanoe/code/robotina-gsd/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/robotina/agent/prompts/robotina/V001.md
@src/robotina/agent/prompts/send-notification/V001.md
@src/robotina/agent/skills/household-manager/shared.md
@experiments/send_notification.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add Spanish directives to system prompts and shared skill</name>
  <files>src/robotina/agent/prompts/robotina/V001.md, src/robotina/agent/prompts/send-notification/V001.md, src/robotina/agent/skills/household-manager/shared.md</files>
  <action>
Three files to update. All instructions stay in English; only add directives about outputting in Spanish.

1. **src/robotina/agent/prompts/robotina/V001.md** — Insert the following block as the VERY FIRST lines, before "# Robotina -- V001":

```
> **IMPORTANT: You MUST always respond to the user in Spanish. Use natural, conversational Spanish appropriate for a family household context. All user-facing text you produce — answers, clarifications, queued messages — must be in Spanish.**
```

Leave everything else in the file unchanged.

2. **src/robotina/agent/prompts/send-notification/V001.md** — Insert the following block as the VERY FIRST lines, before "# Notification Agent -- V001":

```
> **IMPORTANT: The messages you receive are already in Spanish. Preserve the Spanish content exactly as-is. Your reformatted output must remain in Spanish. Do NOT translate to English. Apply MarkdownV2 formatting and escaping to the Spanish text.**
```

Leave everything else in the file unchanged.

3. **src/robotina/agent/skills/household-manager/shared.md** — Add a new section at the END of the file (after the "Filtering reference lists" section), before any trailing newline:

```markdown

## Data language

All user-facing data returned by the household-manager API — recipe names, food names, unit names, descriptions, meal plan entries — is stored in Spanish. Use these values as-is in your responses without translating them.
```
  </action>
  <verify>
    <automated>grep -q "MUST always respond.*Spanish" src/robotina/agent/prompts/robotina/V001.md && grep -q "Spanish content exactly" src/robotina/agent/prompts/send-notification/V001.md && grep -q "stored in Spanish" src/robotina/agent/skills/household-manager/shared.md && echo "PASS" || echo "FAIL"</automated>
  </verify>
  <done>All three files contain their Spanish directives. Prompt instructions, tool descriptions, and remaining skill content remain in English.</done>
</task>

<task type="auto">
  <name>Task 2: Update experiment test cases to Spanish</name>
  <files>experiments/send_notification.py</files>
  <action>
Replace the TEST_CASES list (lines 36-59) in experiments/send_notification.py with Spanish equivalents. Keep the same structure (4 cases, same keys: label, text, description). Descriptions stay in English (developer-facing).

New TEST_CASES:

```python
TEST_CASES = [
    {
        "label": "Case 1: Baseline plain text",
        "text": "La receta se ha guardado correctamente.",
        "description": "Simple confirmation in Spanish — minimal escaping needed (just the period)",
    },
    {
        "label": "Case 2: Structured data",
        "text": "Receta agregada: Espaguetis a la Carbonara. Porciones: 4, preparacion 10 min, coccion 20 min.",
        "description": "Multiple periods and colon — tests period escaping in structured data",
    },
    {
        "label": "Case 3: Bullet list",
        "text": (
            "Menu de la semana: lunes pasta, martes sopa, miercoles ensalada, "
            "jueves salteado, viernes pizza."
        ),
        "description": "Long list — tests bullet list formatting and trailing period",
    },
    {
        "label": "Case 4: Special characters stress test",
        "text": "Listo en 30 min! (4 porciones) — costo: ~8.50 EUR",
        "description": "!, (, ), ~, . all require escaping — Telegram BadRequest if missed",
    },
]
```

Do NOT change any other code in the file — only the TEST_CASES list content.
  </action>
  <verify>
    <automated>python -c "import ast; tree = ast.parse(open('experiments/send_notification.py').read()); print('SYNTAX OK')" && grep -q "receta" experiments/send_notification.py && grep -q "Espaguetis" experiments/send_notification.py && echo "PASS" || echo "FAIL"</automated>
  </verify>
  <done>All 4 test cases use Spanish text. Labels and descriptions remain in English. File parses without syntax errors. No other code changed.</done>
</task>

</tasks>

<verification>
1. All four files modified, no others
2. System prompt instructions remain in English
3. Spanish directives appear at the correct positions
4. Experiment file has valid Python syntax
5. No Python code logic changed
</verification>

<success_criteria>
- grep confirms Spanish directives in both prompt files
- grep confirms API data language note in shared.md
- experiments/send_notification.py parses without syntax errors and contains Spanish test text
- git diff shows only content changes in the 4 specified files, no logic modifications
</success_criteria>

<output>
After completion, create `.planning/quick/260330-ggw-add-spanish-language-support-to-robotina/260330-ggw-SUMMARY.md`
</output>
