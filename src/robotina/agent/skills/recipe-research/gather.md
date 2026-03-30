# Gather: Busqueda de recetas en la web

## Objetivo
Buscar recetas en multiples sitios web y extraer datos estructurados de cada resultado.

## Proceso

### 1. Construir terminos de busqueda
Crea 3 terminos de busqueda en espanol alrededor del nombre de la receta. Usa frases naturales que un cocinero argentino buscaria:
- Ejemplo para "Pasta Bolognesa": "Pasta Bolognesa facil de preparar", "pasta bolognesa deliciosa", "receta casera de salsa bolognesa"
- Prioriza sitios de recetas argentinos/latinoamericanos

### 2. Buscar con web-search
Usa la herramienta `web-search` para cada termino. Cada busqueda devuelve hasta 3 resultados con:
- `title`: titulo de la pagina
- `url`: URL del resultado
- `content`: resumen del contenido
- `raw_content`: contenido HTML completo (puede ser null)
- `score`: relevancia del resultado

### 3. Extraer datos de cada resultado
Para cada resultado con `raw_content` disponible, intenta extraer datos estructurados de la receta:
- Titulo, ingredientes, instrucciones, tiempos, porciones
- Si no puedes extraer datos estructurados del HTML, usa el campo `content` (resumen) como fuente alternativa

### 4. Manejo de errores
- Si un resultado no tiene datos utiles, saltalo y continua con el siguiente
- Solo falla si TODOS los resultados son inutilizables
- Al menos 1 fuente utilizable es suficiente para continuar

## Formato de salida
Tu respuesta final debe ser un JSON con la lista de recetas encontradas. Cada receta es un dict con los campos disponibles:
```json
{
  "recipes": [
    {
      "title": "nombre de la receta",
      "url": "URL fuente",
      "ingredients": ["ingrediente 1", "ingrediente 2"],
      "instructions": ["paso 1", "paso 2"],
      "prep_time": 15,
      "cook_time": 30,
      "total_time": 45,
      "servings": "4 porciones"
    }
  ]
}
```
Incluye todos los campos que puedas extraer. Los campos faltantes se omiten (no uses null).
