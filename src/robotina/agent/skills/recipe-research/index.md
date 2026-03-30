# Skill: recipe-research

Pipeline de investigacion de recetas en 4 pasos. Cada agente ejecuta un paso especifico.

## Pasos

1. **gather** — Busca recetas en la web usando terminos en espanol. Lee `recipe-research/gather.md` para instrucciones detalladas.
2. **instructions** — Crea instrucciones base usando consenso de las recetas encontradas. Lee `recipe-research/instructions.md`.
3. **ingredients** — Extrae y verifica ingredientes contra la API del household-manager. Lee `recipe-research/ingredients.md`.
4. **metadata** — Estima tiempos de preparacion, coccion y porciones. Lee `recipe-research/metadata.md`.

## Importante

- Todo el contenido (nombres de recetas, ingredientes, instrucciones, descripciones) debe estar en **espanol**.
- Los terminos de busqueda deben ser frases naturales que un cocinero argentino usaria.
- Usa la herramienta `read-skill` con la ruta `recipe-research/<paso>.md` para obtener instrucciones especificas de tu paso.
