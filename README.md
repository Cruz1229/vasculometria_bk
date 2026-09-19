# Retinal Pipeline API

Este proyecto implementa una **API desarrollada con FastAPI** para ejecutar el proceso completo de análisis de imágenes de fondo de ojo. El flujo incluye el preprocesamiento de la imagen, la segmentación de vasos sanguíneos mediante **LUNet**, la extracción de biomarcadores utilizando **PVBM** y, finalmente, una clasificación basada en proximidad difusa.

## Organización

La estructura principal del proyecto es la siguiente:

```text
app/
  main.py                 # Inicializa FastAPI y carga el servicio
  config.py               # Configuración, variables de entorno y rutas
  schemas.py              # Define las entradas y salidas de la API
  api/
    routes.py             # Endpoints y validaciones HTTP
    dependencies.py       # Acceso al servicio principal
  services/
    pipeline.py           # Coordina las diferentes etapas del procesamiento
    preprocessing.py      # Redimensionamiento y preparación de imágenes
    segmentation.py       # Segmentación con LUNet y generación de máscaras
    biomarkers.py         # Obtención de biomarcadores con PVBM
    classification.py     # Clasificación mediante reglas y proximidad difusa
  infrastructure/
    model_loader.py       # Carga de modelos y configuración de TensorFlow/GPU
    storage.py            # Manejo de directorios y archivos generados
    logging.py            # Registro de eventos y tiempos de ejecución
models/                   # Código y pesos utilizados por LUNet y PVBM
scripts/                  # Scripts auxiliares para WSL y descarga de modelos
tests/                    # Pruebas del proyecto
runtime/                  # Imágenes de entrada, máscaras y resultados generados
archive/lunet-model-backups/ # Respaldos anteriores del modelo LUNet
```

La API se encarga de recibir y validar las solicitudes, mientras que `pipeline.py` coordina las diferentes etapas del procesamiento.

Los modelos se cargan una sola vez cuando inicia el servicio para evitar cargarlos nuevamente en cada petición. Además, importar `app.main` no provoca que TensorFlow se inicialice ni que los pesos de los modelos se carguen automáticamente.

## Endpoints

La API cuenta con los siguientes endpoints:

- `GET /health` — permite verificar que la API se encuentre disponible.
- `POST /predict` — ejecuta el pipeline completo a partir de una imagen de fondo de ojo.
- `POST /classify-from-biomarkers` — realiza únicamente la clasificación a partir de biomarcadores previamente obtenidos.
- `GET /ping` — endpoint de comprobación utilizado por Runpod y oculto en OpenAPI.
- `POST /stages/preprocess` — ejecuta únicamente el preprocesamiento.
- `POST /stages/lunet` — realiza el preprocesamiento y posteriormente la segmentación con LUNet.
- `POST /stages/pvbm` — ejecuta el preprocesamiento, segmentación y extracción de biomarcadores.
- `POST /stages/fuzzy-proximity-tree` — recibe los biomarcadores y obtiene su clasificación.
- `POST /pipeline/sequential` — ejecuta todas las etapas de forma secuencial y devuelve los resultados agrupados.

En los endpoints que trabajan con imágenes, el archivo se envía mediante `multipart/form-data` utilizando el campo `file`.

Para los endpoints de clasificación se utiliza un JSON con los siguientes valores:

- `imagen`
- `craek_um`
- `crvek_um`
- `avr_knudtson`
- `median_tortuosity`

Los valores numéricos también pueden enviarse como `null`.

Cada endpoint correspondiente a LUNet o PVBM ejecuta las etapas anteriores que necesita directamente sobre la imagen recibida. Esto significa que no es necesario conservar o enviar el identificador de una petición anterior.

## Cambios realizados respecto al notebook original

La versión inicial del proyecto estaba desarrollada principalmente para ejecutarse desde un notebook. Para convertirla en una API fue necesario realizar algunos cambios:

1. Se eliminaron las dependencias específicas de Google Colab, como `drive.mount`, `!pip install` y `!git clone`.
2. Los modelos ahora se cargan una sola vez cuando inicia la aplicación.
3. El pipeline dejó de ejecutarse automáticamente al importar el código y ahora solo se ejecuta cuando se llama al endpoint correspondiente.
4. La entrada ya no depende de una carpeta fija; las imágenes se reciben directamente mediante HTTP.
5. Los resultados principales se devuelven en formato JSON, aunque las máscaras y otros archivos generados también se almacenan en disco.

## Variables de entorno

La configuración principal se encuentra en:

```text
app/config.py
```

Las rutas relativas se resuelven a partir de la raíz del proyecto y las variables de entorno tienen prioridad sobre los valores predeterminados.

Cuando el proyecto se ejecuta localmente se detecta el directorio `models/`. En Docker, las rutas de los modelos se encuentran dentro de `/app/models/`.

Para utilizar una configuración local se puede copiar:

```text
.env.example
```

como:

```text
.env
```

y modificar los valores necesarios.

El archivo `.env` se carga al ejecutar Uvicorn indicando explícitamente:

```bash
--env-file .env
```

En Docker se mantiene el puerto `80` y LUNet utiliza `/GPU:0`. Para una ejecución local, de forma predeterminada se utiliza `/CPU:0`.

Ejemplo de configuración:

```bash
export RETINAL_API_BASE_DIR=/app/runtime
export LUNET_DIR=/app/models/LUNet
export PVBM_DIR=/app/models/PVBM
export LUNET_WEIGHTS=/app/models/LUNet/lunet_modelbest.h5
export LUNET_TF_DEVICE=/CPU:0
export TF_GPU_MEMORY_GROWTH=true
export RETINAL_API_CORS_ALLOW_ORIGINS=*

# Ejemplo para limitar los orígenes permitidos:
# export RETINAL_API_CORS_ALLOW_ORIGINS=https://tu-frontend.example.com,https://otro-origen.example.com
# export RETINAL_API_CORS_ALLOW_ORIGIN_REGEX=https://.*\.cloudspaces\.litng\.ai
# export RETINAL_API_CORS_ALLOW_CREDENTIALS=false
```

## Ejecución local

Primero es necesario utilizar un entorno compatible con las dependencias definidas en:

```text
requirements.txt
```

En el entorno WSL utilizado durante el desarrollo se emplea de forma predeterminada:

```text
~/miniforge3/envs/retinal
```

Este valor se puede modificar mediante `CONDA_ENV` o `PYTHON_BIN`.

También es necesario contar con los pesos de LUNet en:

```text
models/LUNet/lunet_modelbest.h5
```

o indicar otra ubicación mediante `LUNET_WEIGHTS`.

Antes de iniciar la API se prepara el modelo de disco óptico ejecutando:

```bash
pip install -r requirements.txt
python scripts/download_models.py
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Si se utiliza un archivo `.env`, la ejecución sería:

```bash
python -m uvicorn app.main:app --env-file .env --host 0.0.0.0 --port 8000
```

Para ejecutar el proyecto desde WSL utilizando una GPU NVIDIA:

```bash
LUNET_TF_DEVICE=/GPU:0 bash scripts/run_wsl_gpu.sh
```

También se mantienen las siguientes opciones por compatibilidad:

```bash
uvicorn app:app
bash run_wsl_gpu.sh
```

El script de WSL puede localizar la aplicación desde la raíz del proyecto aunque se ejecute desde otro directorio.

## Docker

El proyecto también puede ejecutarse mediante Docker.

El `Dockerfile` incluye el paquete `app/`, los modelos necesarios y el script utilizado para preparar PVBM.

Durante la construcción de la imagen se realiza la preparación de PVBM y, al iniciar el contenedor, la aplicación se ejecuta desde:

```text
app.main:app
```

Para utilizar la GPU NVIDIA, el host donde se ejecuta el contenedor debe tener soporte para GPU.

La imagen se puede construir y ejecutar de la siguiente manera:

```bash
docker build -t retinal-api .
docker run --gpus all -p 8000:80 -v retinal-runtime:/app/runtime retinal-api
```

El volumen `retinal-runtime` permite conservar los archivos generados aunque el contenedor sea reemplazado.

Una vez iniciada la API, la documentación interactiva de FastAPI se encuentra disponible en:

```text
http://localhost:8000/docs
```

Es importante considerar que los valores incluidos en `artifact_paths` representan rutas internas del servidor y no enlaces directos de descarga.

## Prueba con curl

Para realizar una prueba del endpoint principal se puede utilizar:

```bash
curl -X POST "http://localhost:8000/predict"   -H "accept: application/json"   -H "Content-Type: multipart/form-data"   -F "file=@/ruta/a/tu/imagen.jpg"
```

## Respuesta esperada

Una respuesta del endpoint `/predict` mantiene una estructura similar a la siguiente:

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

Para ejecutar las pruebas del proyecto primero se deben instalar las dependencias de desarrollo:

```bash
pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Las pruebas permiten verificar diferentes partes del funcionamiento de la API, entre ellas:

- el contrato OpenAPI;
- las respuestas de clasificación;
- el preprocesamiento;
- los endpoints;
- el orden de ejecución de las etapas;
- la validación de archivos;
- la carga única del servicio.

Para las pruebas HTTP se sustituyen los modelos reales por adaptadores de prueba, por lo que no es necesario contar con una GPU ni descargar los pesos de los modelos.

Sin embargo, cuando se realizan modificaciones relacionadas directamente con la inferencia, es recomendable ejecutar imágenes de referencia utilizando los pesos reales y comparar las máscaras y biomarcadores obtenidos.

Para que la comparación sea válida se debe utilizar el mismo tamaño de imagen y el mismo dispositivo en ambas ejecuciones.

## Mantenimiento de modelos

El código utilizado actualmente por LUNet ya incluye la adaptación correspondiente a:

```python
tf.keras.layers.Maximum()
```

La API no modifica automáticamente el código de LUNet durante su inicialización.

Por esta razón, si se utiliza una versión externa mediante `LUNET_DIR`, esa copia también debe contener la adaptación necesaria para mantener la compatibilidad.

Las versiones anteriores del modelo se conservan en:

```text
archive/lunet-model-backups/
```
