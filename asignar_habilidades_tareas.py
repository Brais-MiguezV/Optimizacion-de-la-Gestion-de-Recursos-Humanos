# -------------------- Standard Library --------------------
import os
from datetime import date
import warnings
from typing import List, Dict, Any
from sklearn.pipeline import Pipeline
from pathlib import Path

# -------------------- Third-Party Libraries --------------------
import numpy as np
import pandas as pd
from colorama import Fore, Style, init
from sqlalchemy import create_engine, Engine, text
from dotenv import load_dotenv

# -------------------- Machine Learning - scikit-learn --------------------
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import MultiLabelBinarizer
import nlpaug.augmenter.word as naw
from transformers.utils import logging

load_dotenv()
logging.set_verbosity_error()
warnings.filterwarnings("ignore", category=UserWarning)
init(autoreset=True)

# Configuración de conexión
db_config: dict[str, str | int] = {
    "user": os.getenv("USUARIO", ""),
    "password": os.getenv("PASS_USUARIO", ""),
    "host": os.getenv("HOST", ""),
    "port": os.getenv("PORT", 0),
    "dbname": os.getenv("DATABASE", ""),
}

# Consulta a la base de datos para extraer datos de tareas y empleados
query: str = "SELECT * FROM tareas"
query_empleados: str = "SELECT codificacion, habilidades FROM empleados"

db_url: str = (
    f"postgresql+psycopg2://{db_config['user']}:{db_config['password']}"
    f"@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
)  # Cadena de conexión para SQLAlchemy

try:
    engine: Engine = create_engine(db_url)
    with engine.connect() as conn:
        pass
except Exception as e:
    print(
        Fore.RED
        + Style.BRIGHT
        + f"\n❌ Error al conectar con la base de datos: {e}\n"
        + Style.RESET_ALL
    )
    exit(1)

# Leer los datos directamente a un DataFrame
try:
    tasks_dat: pd.DataFrame = pd.read_sql_query(query, engine)
    empleados_dat: pd.DataFrame = pd.read_sql_query(query_empleados, engine)
except Exception as e:
    print(
        Fore.RED
        + Style.BRIGHT
        + f"\n❌ Error al leer datos de la base de datos: {e}\n"
        + Style.RESET_ALL
    )
    exit(1)


print(
    f"{Fore.GREEN}✅ Datos de tareas y empleados cargados correctamente\n{Style.RESET_ALL}"
)

ruta_preetiq = Path("data/tareas_preetiquetadas.csv")
if not ruta_preetiq.exists():
    print(
        Fore.RED
        + Style.BRIGHT
        + "\n❌ El archivo 'data/tareas_preetiquetadas.csv' no se ha encontrado.\n"
        + Style.RESET_ALL
    )
    exit(1)

try:
    tareas_etiquetadas: pd.DataFrame = pd.read_csv(ruta_preetiq)
except Exception as e:
    print(
        Fore.RED
        + Style.BRIGHT
        + f"\n❌ Error al leer 'data/tareas_preetiquetadas.csv': {e}\n"
        + Style.RESET_ALL
    )
    exit(1)

if tareas_etiquetadas.empty:
    print(
        Fore.RED
        + Style.BRIGHT
        + "\n❌ El archivo de tareas pre-etiquetadas está vacío.\n"
        + Style.RESET_ALL
    )
    exit(1)

tareas_etiquetadas["habilidades"] = tareas_etiquetadas["habilidades"].str.split(
    "|"
)  # Convertir habilidades a listas

# ------------------------------------------
# ----- Generar dataset de entrenamiento ---
# ------------------------------------------

claves: List[str] = tareas_etiquetadas["clave"].unique().tolist()

# Ejecutar consulta con cláusula IN segura
consulta: str = """
SELECT clave, texto
FROM tareas
WHERE clave = ANY(:claves)
"""

with engine.connect() as conn:
    tareas_texto: pd.DataFrame = pd.read_sql_query(
        text(consulta), conn, params={"claves": claves}
    )

# Unir etiquetas y texto
df: pd.DataFrame = tareas_etiquetadas.merge(tareas_texto, on="clave", how="left")

# ------------------------------------------
# Comprobación: que todas las claves existen en la base de datos
# ------------------------------------------
faltan_claves = df["texto"].isnull()
if faltan_claves.any():
    claves_faltantes = df.loc[faltan_claves, "clave"].tolist()
    print(
        Fore.RED
        + Style.BRIGHT
        + "\n❌ No se han encontrado todas las claves en la base de datos\n"
        + Fore.RESET
        + Style.RESET_ALL
    )
    exit(1)

# ------------------------------------------
# ------------ Aumentar Tareas -------------
# ------------------------------------------

ruta_aug = Path("data/tareas_aumentadas.csv")

if ruta_aug.exists():
    print(
        f"{Fore.CYAN}\n📄 Archivo de aumentos encontrado. Cargando tareas aumentadas...\n{Style.RESET_ALL}"
    )
    df_aug = pd.read_csv(ruta_aug)
    df_aug["habilidades"] = df_aug["habilidades"].apply(
        lambda x: x.split("|") if isinstance(x, str) else []
    )
else:
    print(
        f"{Fore.BLUE}🧪 Archivo de aumentos no encontrado. Generando tareas aumentadas...\n{Style.RESET_ALL}"
    )

    aug = naw.ContextualWordEmbsAug(
        model_path="./modelos/", action="substitute", model_type="bert"
    )

    tareas_aug = []
    for i, row in df.iterrows():
        texto = row["texto"]
        habilidades = row["habilidades"]
        clave = row["clave"]

        print(f"{Fore.YELLOW}\tAumentando tarea: {i + 1}{Style.RESET_ALL}")

        try:
            resultados = aug.augment(texto, n=5)
        except Exception as e:
            print(
                f"{Fore.RED}\t⚠️ Error al aumentar tarea '{clave}': {e}{Style.RESET_ALL}"
            )
            continue

        for j, t in enumerate(resultados):
            tareas_aug.append(
                {
                    "clave": f"{clave}_aug{j}",
                    "texto": t,
                    "habilidades": "|".join(habilidades),
                }
            )

    df_aug = pd.DataFrame(tareas_aug)
    ruta_aug.parent.mkdir(parents=True, exist_ok=True)
    df_aug.to_csv(ruta_aug, index=False)
    print(
        f"{Fore.GREEN}\n✅ Archivo de tareas aumentadas guardado en: {ruta_aug}{Style.RESET_ALL}"
    )

# Convertir de nuevo habilidades a listas
df_aug["habilidades"] = df_aug["habilidades"].apply(
    lambda x: x.split("|") if isinstance(x, str) else []
)

# Concatenar tareas etiquetadas + aumentadas
df = pd.concat([df, df_aug], ignore_index=True)
df["habilidades"] = df["habilidades"].apply(lambda x: x if isinstance(x, list) else [])

# --------------------------------------------
# -------- Entrenamiento del modelo ----------
# --------------------------------------------

mlb: MultiLabelBinarizer = MultiLabelBinarizer()
y: np.ndarray = mlb.fit_transform(df["habilidades"])
X: pd.Series = df["texto"].fillna("")

pipeline: Pipeline = make_pipeline(
    TfidfVectorizer(),
    OneVsRestClassifier(RandomForestClassifier(n_estimators=100, n_jobs=-1)),
)
pipeline.fit(X, y)

# --------------------------------------------
# --------- Predicción de habilidades --------
# --------------------------------------------
X_pred: pd.Series = tasks_dat["texto"].fillna("")
y_pred: np.ndarray = pipeline.predict(X_pred)
habilidades_pred = mlb.inverse_transform(y_pred)


# --------------------------------------------
# ---- Actualización de la base de datos -----
# --------------------------------------------


def formatear_habilidades_sql(habs: List[str], tarea: pd.Series) -> str:
    """
    Formatea las habilidades para ser insertadas en la base de datos PostgreSQL.
    """
    if not habs:
        return "null"
    rows = [
        f"""ROW('{h.replace("'", "''")}', {tarea['timespent_real']}, '{date.today()}')::habilidades_tarea"""
        for h in habs
    ]
    return f"ARRAY[{', '.join(rows)}]"


tasks_dat["habilidades_pg_sql"] = [
    formatear_habilidades_sql(habs, row)
    for habs, (_, row) in zip(habilidades_pred, tasks_dat.iterrows())
]

try:
    with engine.begin() as connection:
        print(
            f"\n{Fore.YELLOW}Actualizando habilidades extraídas en la base de datos...\n{Style.RESET_ALL}"
        )
        for _, row in tasks_dat.iterrows():
            if row["habilidades_pg_sql"] == "null":
                continue  # No actualizar si no hay habilidades

            query_sql = f"""
                UPDATE tareas
                SET habilidades_extraidas = {row["habilidades_pg_sql"]}, fecha_modificacion = date_trunc('second', now())
                WHERE clave = :clave
            """
            connection.execute(text(query_sql), {"clave": row["clave"]})

        # Commit changes
        connection.commit()
except Exception as e:
    print(
        Fore.RED
        + Style.BRIGHT
        + f"\n❌ Error al actualizar la base de datos: {e}\n"
        + Style.RESET_ALL
    )
    exit(1)

print(
    f"{Fore.GREEN}✅ Habilidades extraídas y actualizadas correctamente en la base de datos{Style.RESET_ALL}"
)
