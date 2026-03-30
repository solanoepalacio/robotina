# Instructions: Crear instrucciones base por consenso

## Objetivo
Analizar todas las recetas encontradas y crear instrucciones base usando un enfoque de consenso.

## Proceso

### 1. Analizar recetas
Lee todas las recetas del paso gather. Identifica:
- Pasos comunes que aparecen en la mayoria de las recetas
- Tecnicas de coccion compartidas
- Orden tipico de preparacion

### 2. Consenso
Usa el enfoque "mayoria gana":
- Si 6 de 10 recetas mencionan salar la carne antes, incluyelo
- Si solo 1 receta menciona un paso inusual, omitelo
- En caso de empate, incluye el paso (mejor tener mas informacion)

### 3. Redactar instrucciones
Escribe instrucciones claras y concisas en espanol:
- Cada paso debe ser una accion especifica
- Incluye tiempos aproximados cuando sea relevante (ej: "cocinar 5 minutos")
- Usa vocabulario de cocina argentino/latinoamericano

## Formato de salida
Tu respuesta final debe ser un JSON con:
```json
{
  "draft_name": "Nombre de la receta en espanol",
  "draft_description": "Descripcion breve de la receta",
  "draft_instructions": [
    {"body": "Paso 1 de la receta", "title": null},
    {"body": "Paso 2 de la receta", "title": null}
  ]
}
```
