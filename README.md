# Retinal Pipeline API

API con **FastAPI** para preprocesamiento, segmentación con LUNet,
extracción de biomarcadores con PVBM y clasificación por proximidad difusa.

## Organización

```text
app/
  main.py                 # Crea FastAPI y carga el servicio al arrancar
  config.py               # Variables de entorno y rutas
  schemas.py              # Contrato de entrada y salida
  api/
    routes.py             # Endpoints y validación HTTP
    dependencies.py       # Acceso al servicio de la aplicación
  services/
    pipeline.py           # Coordina las etapas
    preprocessing.py      # Redimensionamiento de imágenes
    segmentation.py       # Inferencia LUNet y máscaras
    biomarkers.py         # Mediciones PVBM y conversión de unidades
    classification.py     # Reglas y puntuaciones difusas
  infrastructure/
    model_loader.py       # Carga de modelos y configuración TensorFlow/GPU
    storage.py            # Directorios e imágenes generadas
    logging.py            # Logger y medición de tiempos
models/                   # Código de LUNet/PVBM y sus pesos
scripts/                  # Arranque WSL y descarga del modelo PVBM
tests/                    # Pruebas y referencias anteriores al refactor
runtime/                  # Entradas, máscaras y resultados; ignorado por Git
archive/lunet-model-backups/ # Respaldos históricos; fuera de Docker
```

La API recibe y valida la petición; `pipeline.py` coordina las etapas y prepara
las respuestas. La clasificación puede importarse sin FastAPI ni TensorFlow.
Los modelos se cargan una vez por instancia del servicio, durante el arranque.
Importar `app.main` no carga los pesos ni inicializa TensorFlow.

## Endpoints

- `GET /health` — valida que la API esté viva.
- `POST /predict` — recibe una imagen de fondo de ojo y devuelve:
  - biomarcadores (`CRAE`, `CRVE`, `AVR`, `tortuosidad`)
  - clasificación difusa
  - rutas de artefactos generados
- `POST /classify-from-biomarkers` — clasifica biomarcadores sin ejecutar segmentación.
- `GET /ping` — alias de salud utilizado por Runpod; oculto en OpenAPI.
- `POST /stages/preprocess` — ejecuta el preprocesamiento.
- `POST /stages/lunet` — ejecuta preprocesamiento y segmentación.
- `POST /stages/pvbm` — ejecuta preprocesamiento, segmentación y biomarcadores.
- `POST /stages/fuzzy-proximity-tree` — recibe biomarcadores y devuelve estos junto con su clasificación.
- `POST /pipeline/sequential` — ejecuta todas las etapas y devuelve sus respuestas agrupadas.

Los endpoints de imágenes reciben un archivo multipart en el campo `file`.
Los de clasificación reciben JSON con `imagen`, `craek_um`, `crvek_um`,
`avr_knudtson` y `median_tortuosity`; los campos numéricos admiten `null`.
Las etapas de LUNet y PVBM ejecutan sus pasos previos sobre la imagen recibida;
no consumen un identificador de una petición anterior.

## Qué cambió respecto a tu notebook

1. Se eliminó la dependencia directa de Colab (`drive.mount`, `!pip install`, `!git clone`).
2. Los modelos se cargan una sola vez al iniciar la app.
3. El pipeline ya no se ejecuta al importar el archivo; ahora corre solo cuando llamas al endpoint.
4. La entrada ya no es una carpeta fija, sino un archivo enviado por HTTP.
5. La salida principal es JSON, aunque también se guardan máscaras y artefactos en disco.

## Variables de entorno sugeridas

La configuración está en `app/config.py`. Las rutas relativas se resuelven
desde la raíz del proyecto, y las variables de entorno tienen prioridad.
En local se detecta `models/`; Docker declara las rutas `/app/models/...`.

Para partir de un ejemplo local, copia `.env.example` a `.env` y ajusta sus
valores. El archivo `.env` se carga únicamente cuando se indica `--env-file .env`
al ejecutar Uvicorn. La configuración del contenedor conserva el puerto 80 y
LUNet en `/GPU:0`; la configuración local predeterminada usa `/CPU:0`.

```bash
export RETINAL_API_BASE_DIR=/app/runtime
export LUNET_DIR=/app/models/LUNet
export PVBM_DIR=/app/models/PVBM
export LUNET_WEIGHTS=/app/models/LUNet/lunet_modelbest.h5
export LUNET_TF_DEVICE=/CPU:0
export TF_GPU_MEMORY_GROWTH=true
export RETINAL_API_CORS_ALLOW_ORIGINS=*
# Alternativa más restrictiva:
# export RETINAL_API_CORS_ALLOW_ORIGINS=https://tu-frontend.example.com,https://otro-origen.example.com
# export RETINAL_API_CORS_ALLOW_ORIGIN_REGEX=https://.*\\.cloudspaces\\.litng\\.ai
# export RETINAL_API_CORS_ALLOW_CREDENTIALS=false
```

## Ejecutar localmente

Usa un entorno compatible con las dependencias de `requirements.txt`.
Para el entorno WSL existente, el script usa por defecto
`~/miniforge3/envs/retinal`; puede cambiarse mediante `CONDA_ENV` o `PYTHON_BIN`.

Los pesos LUNet deben existir en `models/LUNet/lunet_modelbest.h5`
(o en `LUNET_WEIGHTS`). Prepara el modelo de disco óptico antes de arrancar:

```bash
pip install -r requirements.txt
python scripts/download_models.py
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Con configuración en `.env`:

```bash
python -m uvicorn app.main:app --env-file .env --host 0.0.0.0 --port 8000
```

En WSL, para solicitar la GPU NVIDIA:

```bash
LUNET_TF_DEVICE=/GPU:0 bash scripts/run_wsl_gpu.sh
```

Se conservan `uvicorn app:app` y `bash run_wsl_gpu.sh` como entradas de
compatibilidad. El script de WSL resuelve la aplicación desde la raíz del
proyecto aunque se invoque desde otro directorio.

## Docker

El Dockerfile copia el paquete `app/`, los modelos y el script de descarga.
La preparación de PVBM se ejecuta al construir la imagen. El contenedor arranca
con `app.main:app`; requiere un host con acceso a GPU NVIDIA para el comando
siguiente:

```bash
docker build -t retinal-api .
docker run --gpus all -p 8000:80 -v retinal-runtime:/app/runtime retinal-api
```

El volumen conserva los archivos generados entre contenedores. La documentación
interactiva queda en `http://localhost:8000/docs`. Los valores de `artifact_paths`
son rutas del servidor, no enlaces de descarga.

## Probar con curl

```bash
curl -X POST "http://localhost:8000/predict" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@/ruta/a/tu/imagen.jpg"
```

## Respuesta esperada

```json
{
  "request_id": "...",
  "filename": "imagen.jpg",
  "biomarkers": {
    "imagen": "imagen_xxx",
    "craek_um": 145.2,
    "crvek_um": 212.4,
    "avr_knudtson": 0.68,
    "median_tortuosity": 1.14
  },
  "classification": {
    "etiqueta": "Sospecha de retinopatía hipertensiva",
    "regla_id": 2,
    "pct_sano": 10.5,
    "pct_sospecha_rh": 72.8,
    "pct_alto_riesgo_rh": 8.1,
    "pct_sospecha_rd": 5.3,
    "pct_alto_riesgo_rd": 3.3
  },
  "artifact_paths": {
    "input": "...",
    "preprocessed": "...",
    "artery_mask": "...",
    "vein_mask": "...",
    "vessel_mask": "..."
  }
}
```

## Pruebas

En un entorno con las dependencias del proyecto:

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Las pruebas verifican el contrato OpenAPI anterior, las salidas de clasificación,
el preprocesamiento, los endpoints, el orden de las etapas, la validación de
archivos y la carga única del servicio. Las pruebas HTTP sustituyen los modelos
por adaptadores de prueba; no requieren una GPU ni descargar pesos.

Para verificar una modificación de inferencia también es necesario ejecutar
imágenes de referencia con los pesos reales y comparar las máscaras y los
biomarcadores, usando el mismo tamaño de imagen y dispositivo en ambas versiones.

## Mantenimiento de modelos

El código activo de LUNet ya contiene la adaptación a
`tf.keras.layers.Maximum()`. La API no reescribe su código durante el arranque.
Si se usa `LUNET_DIR` externo, esa copia debe incluir la adaptación compatible.
Los respaldos anteriores se conservan en `archive/lunet-model-backups/`.
