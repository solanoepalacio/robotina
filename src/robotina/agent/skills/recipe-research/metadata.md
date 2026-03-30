# Metadata: Estimar tiempos y porciones

## Objetivo
Producir la receta final completa con todos los metadatos estimados.

## Proceso

### 1. Analizar fuentes de metadatos
Lee los metadatos de todas las recetas del paso gather (tiempos, porciones) y las instrucciones del borrador.

### 2. Estimar tiempos
- **prep_time**: tiempo de preparacion en minutos. Estima basandote en la cantidad y complejidad de ingredientes.
- **cook_time**: tiempo de coccion en minutos. Estima basandote en las instrucciones (temperatura, tecnicas de coccion).
- **total_time**: prep_time + cook_time.
- IMPORTANTE: Los campos de tiempo NUNCA deben ser null. Siempre estima aunque no haya datos de las recetas. Usa la complejidad de las instrucciones como guia (ej: pasta con 10 ingredientes -> ~30 min de coccion).

### 3. Estimar porciones
- **servings_qty**: numero de porciones (entero). Si las recetas no lo especifican, estima 4 porciones como valor por defecto razonable.
- **servings_unit**: siempre "porciones".

### 4. Construir RecipeData final
Combina toda la informacion recopilada en los pasos anteriores en la estructura final.

## Formato de salida
Tu respuesta final debe ser un JSON con la estructura completa de RecipeData:
```json
{
  "recipe": {
    "name": "Nombre de la receta",
    "description": "Descripcion breve",
    "servings_qty": 4,
    "servings_unit": "porciones",
    "prep_time": 15,
    "cook_time": 30,
    "total_time": 45,
    "source_url": "http://...",
    "ingredients": [
      {"food_name": "...", "unit_name": "...", "quantity": 1.0, "note": null}
    ],
    "steps": [
      {"body": "Paso 1...", "title": null}
    ]
  }
}
```
Todos los campos de tiempo deben tener valores numericos (nunca null).
