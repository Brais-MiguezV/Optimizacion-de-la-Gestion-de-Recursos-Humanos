# -------------------- Librerías estándar --------------------
import os
import warnings
from datetime import date, datetime
from typing import Any, List, Tuple

# -------------------- Terceros --------------------
import pandas as pd
from colorama import Fore, Style, init
from dotenv import load_dotenv
from sqlalchemy import create_engine, Engine, text
from collections import defaultdict
import ast

# -------------------- Machine Learning --------------------
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# -------------------- Configuración --------------------
warnings.filterwarnings("ignore", category=UserWarning)
load_dotenv()
init(autoreset=True)

db_config = {
    "user": os.getenv("USUARIO", ""),
    "password": os.getenv("PASS_USUARIO", ""),
    "host": os.getenv("HOST", ""),
    "port": os.getenv("PORT", 0),
    "dbname": os.getenv("DATABASE", ""),
}

db_url = f"postgresql+psycopg2://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
try:
    engine: Engine = create_engine(db_url)
    with engine.connect() as conn:
        pass  # test de conexión
except Exception as e:
    print(
        Fore.RED
        + Style.BRIGHT
        + f"\n❌ Error al conectar con la base de datos: {e}\n"
        + Style.RESET_ALL
    )
    exit(1)

# -------------------- Consultas --------------------
query_tareas = """
SELECT
    t.id AS tarea_id,
    t.clave,
    t.habilidades_extraidas,
    t.timespent_real,
    t.issue_type,
    t.status_text,
    t.texto,
    t.fecha,
    e.codificacion AS empleado_id,
    e.habilidades AS habilidades_empleado
FROM Tareas t
JOIN Empleados e ON t.assignee = e.codificacion
WHERE t.habilidades_extraidas IS NOT NULL
  AND e.habilidades IS NOT NULL
"""

query_empleados = (
    "SELECT codificacion, habilidades FROM empleados where is_active = true"
)

query_antiguedad = """
SELECT assignee AS codificacion, MIN(fecha) AS primera_fecha
FROM tareas
GROUP BY assignee
"""

try:
    with engine.connect() as conn:
        tasks_dat = pd.read_sql(text(query_tareas), conn)
        empleados_dat = pd.read_sql(text(query_empleados), conn)
        antiguedad_dat = pd.read_sql(text(query_antiguedad), conn)
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


# -------------------- Calcular antigüedad normalizada --------------------
hoy = pd.Timestamp(date.today())
antiguedad_dat["primera_fecha"] = pd.to_datetime(antiguedad_dat["primera_fecha"])
antiguedad_dat["antiguedad_dias"] = (hoy - antiguedad_dat["primera_fecha"]).dt.days

# Normalización entre 0 y 1
max_antiguedad = antiguedad_dat["antiguedad_dias"].max()
antiguedad_dat["antiguedad_norm"] = antiguedad_dat["antiguedad_dias"] / max_antiguedad

# Mapeo de codificacion -> antigüedad normalizada
antiguedad_dict = antiguedad_dat.set_index("codificacion")["antiguedad_norm"].to_dict()


# -------------------- Funciones --------------------
def parsear_habilidad(entry: Any) -> Tuple[str | None, str | None]:
    if isinstance(entry, tuple) and len(entry) >= 2:
        return entry[0], entry[1]
    elif isinstance(entry, str) and entry.startswith("("):
        partes = entry.strip("()").split(",")
        if len(partes) >= 2:
            return partes[0], partes[1]
    return None, None


def get_hab_info(hab, tipo="empleado"):

    if isinstance(hab, dict):
        if tipo == "empleado":
            return hab.get("habilidad"), hab.get("nivel_actual")
        else:
            return hab.get("habilidad"), hab.get("experiencia")
    elif isinstance(hab, tuple):

        return hab[0], hab[1]
    elif isinstance(hab, str):

        try:
            tup = ast.literal_eval(hab)
            return tup[0], tup[1]
        except Exception:
            return None, None
    return None, None


def cumple_experiencia_minima(habs_tarea, habs_empleado):
    if not habs_tarea or not habs_empleado:
        return False

    dict_emp = {}
    for h in habs_empleado:
        hab, nivel = get_hab_info(h, tipo="empleado")
        if hab and nivel:
            try:
                dict_emp[hab] = int(nivel)
            except ValueError:
                continue

    dict_tar = {}
    for h in habs_tarea:
        hab, exp = get_hab_info(h, tipo="tarea")
        if hab and exp:
            try:
                dict_tar[hab] = int(exp)
            except ValueError:
                continue

    for hab, exp_req in dict_tar.items():
        nivel_emp = dict_emp.get(hab)
        if nivel_emp is None or nivel_emp < exp_req:
            return False
    return True


def calcular_match(
    habs_tarea: List[str | None], habs_empleado: List[str | None]
) -> float:
    set_tarea = set(h[0] for h in map(parsear_habilidad, habs_tarea or []) if h[0])
    set_emp = set(h[0] for h in map(parsear_habilidad, habs_empleado or []) if h[0])
    if not set_tarea:
        return 0.0
    interseccion = set_tarea & set_emp
    return len(interseccion) / len(set_tarea)


# -------------------- Preprocesamiento --------------------
corpus_textos = tasks_dat["texto"].fillna("").tolist()
tfidf = TfidfVectorizer(max_features=250, stop_words=None)
X_tfidf = tfidf.fit_transform(corpus_textos)

n_svd_components = min(5, X_tfidf.shape[1])
svd = TruncatedSVD(n_components=n_svd_components, random_state=42)
X_texto = svd.fit_transform(X_tfidf)

# -------------------- Entrenamiento --------------------
X, y = [], []
max_time = tasks_dat["timespent_real"].max()

print(f"{Fore.YELLOW}Entrenando modelo de asignación...\n{Style.RESET_ALL}")

for i, row in tasks_dat.iterrows():
    match = calcular_match(row["habilidades_extraidas"], row["habilidades_empleado"])
    antiguedad = antiguedad_dict.get(row["empleado_id"], 0.0)

    features = [
        match,
        len(row["habilidades_extraidas"] or []),
        len(row["habilidades_empleado"] or []),
        antiguedad,
        row["status_text"] == "Resolved",
        row["status_text"] == "Closed",
        row["issue_type"] == "Sub-task",
        *X_texto[i].tolist(),
    ]
    X.append(features)
    y.append((max_time - row["timespent_real"]) / max_time)

pipeline = Pipeline(
    [
        ("scaler", StandardScaler()),
        (
            "gb",
            GradientBoostingRegressor(
                n_estimators=200, learning_rate=0.05, max_depth=5
            ),
        ),
    ]
)
pipeline.fit(X, y)


# -------------------- Predicción --------------------
def construir_features(tarea, empleado):
    texto_vec = svd.transform(tfidf.transform([tarea["texto"] or ""]))[0]
    antiguedad = antiguedad_dict.get(empleado["codificacion"], 0.0)
    return [
        calcular_match(tarea["habilidades_extraidas"], empleado["habilidades"]),
        len(tarea["habilidades_extraidas"] or []),
        len(empleado["habilidades"] or []),
        antiguedad,
        tarea["status_text"] == "Resolved",
        tarea["status_text"] == "Closed",
        tarea["issue_type"] == "Sub-task",
        *texto_vec.tolist(),
    ]


def predecir_top_empleados(tarea, empleados, modelo):
    resultados = [
        (emp["codificacion"], modelo.predict([construir_features(tarea, emp)])[0])
        for _, emp in empleados.iterrows()
    ]
    return sorted(resultados, key=lambda x: x[1], reverse=True)[:3]


# -------------------- Resultados --------------------
print(f"{Fore.YELLOW}Realizando predicciones para las tareas...\n{Style.RESET_ALL}")

horas_estimadas_por_empleado_mes = defaultdict(lambda: defaultdict(float))
LIMITE_HORAS_MENSUAL = 160
predicciones_df = []

for _, row in tasks_dat.iterrows():
    tarea = row[
        ["habilidades_extraidas", "status_text", "texto", "issue_type", "fecha"]
    ].to_dict()

    if tarea["fecha"] is None:
        continue

    fecha_tarea = pd.to_datetime(tarea["fecha"])
    mes_clave = fecha_tarea.strftime("%Y-%m")
    top3_bruto = predecir_top_empleados(tarea, empleados_dat, pipeline)

    top3_filtrado = []
    for emp_id, score in top3_bruto:
        empleado = empleados_dat[empleados_dat["codificacion"] == emp_id].iloc[0]

        if not cumple_experiencia_minima(
            row["habilidades_extraidas"], empleado["habilidades"]
        ):
            continue

        horas_actuales = horas_estimadas_por_empleado_mes[emp_id][mes_clave]
        horas_estimadas = max_time * (1 - score)
        if horas_actuales + horas_estimadas <= LIMITE_HORAS_MENSUAL:
            top3_filtrado.append((emp_id, score))
            horas_estimadas_por_empleado_mes[emp_id][mes_clave] += horas_estimadas

        if len(top3_filtrado) == 3:
            break

# -------------------- Guardar resultados con SQLAlchemy --------------------
try:
    with engine.begin() as conn:
        tareas_db = conn.execute(text("SELECT id, texto FROM Tareas")).fetchall()
        texto_to_id = {texto: tarea_id for tarea_id, texto in tareas_db}

        for pred in predicciones_df:
            tarea_id = texto_to_id.get(pred["tarea"])
            if tarea_id is None:
                continue

            top3 = pred["top3_empleados"]
            empleados_pg = ", ".join(
                f"ROW('{emp}', {round(score, 4)}, '{date.today()}')::Candidatos"
                for emp, score in top3
            )

            assignee_en_top3 = pred.get("assignee_en_top3", False)

            update_sql = text(
                f"""
                UPDATE Tareas
                SET candidatos = ARRAY[{empleados_pg}]::Candidatos[],
                    fecha_modificacion = date_trunc('second', now()),
                    assignee_in_candidatos = :assignee_en_top3
                WHERE id = :tarea_id
            """
            )
            conn.execute(
                update_sql, {"tarea_id": tarea_id, "assignee_en_top3": assignee_en_top3}
            )


except Exception as e:
    print(
        Fore.RED
        + Style.BRIGHT
        + f"\n❌ Error al guardar los resultados en la base de datos: {e}\n"
        + Style.RESET_ALL
    )
    exit(1)

print(
    f"{Fore.GREEN}✅ Predicciones de empleados actualizadas correctamente{Style.RESET_ALL}"
)
