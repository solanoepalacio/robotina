# Ingredients: Extraer y verificar ingredientes

## Objetivo
Extraer ingredientes de las instrucciones del borrador y verificar que existan en el sistema del hogar.

## Proceso

### 1. Extraer ingredientes
Lee las instrucciones del borrador e identifica todos los ingredientes mencionados con:
- Nombre del alimento en espanol (ej: "cebolla", "aceite de oliva")
- Cantidad (numero, ej: 2, 0.5)
- Unidad (ej: "unidad", "cucharada", "g", "ml", "taza")
- Nota opcional (ej: "picada finamente")

### 2. Verificar en household-manager
Para cada ingrediente, usa la herramienta `household-manager-api` para verificar que existe:
- Metodo: GET
- Path: `/api/foods?name={nombre_del_alimento}`
- Busca con el nombre en espanol directamente (ej: `GET /api/foods?name=cebolla`)

### 3. Manejar ingredientes no encontrados
Si un ingrediente no existe en el household-manager:
- Revisa las otras recetas del paso gather para buscar un sustituto
- Si encuentras un sustituto que si existe, usalo
- Si no hay sustituto disponible, omite el ingrediente por completo

### 4. No crear alimentos nuevos
No intentes crear alimentos nuevos en el household-manager. Solo usa los que ya existen.

## Formato de salida
Tu respuesta final debe ser un JSON con:
```json
{
  "ingredients": [
    {"food_name": "cebolla", "unit_name": "unidad", "quantity": 1.0, "note": "picada"},
    {"food_name": "aceite de oliva", "unit_name": "cucharada", "quantity": 2.0, "note": null}
  ]
}
```
Solo incluye ingredientes verificados que existen en el household-manager.
