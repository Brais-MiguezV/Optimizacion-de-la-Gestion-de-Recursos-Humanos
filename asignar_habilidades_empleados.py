# -------------------- Standard Library --------------------
import os
from datetime import date, datetime
from typing import Any
import warnings

# -------------------- Third-Party Libraries --------------------
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from colorama import Fore, Style, init

# -------------------- Inicialización --------------------
warnings.filterwarnings("ignore", category=UserWarning)
load_dotenv()
init(autoreset=True)

# -------------------- Configuración de conexión --------------------
db_config = {
    "user": os.getenv("USUARIO", "test"),
    "password": os.getenv("PASS_USUARIO", "test"),
    "host": os.getenv("HOST", "postgres"),
    "port": os.getenv("PORT", 5432),
    "dbname": os.getenv("DATABASE", "Jira"),
}

db_url = (
    f"postgresql+psycopg2://{db_config['user']}:{db_config['password']}"
    f"@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
)
try:
    engine = create_engine(db_url)
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

# -------------------- Consultas SQL --------------------
query = """
SELECT
    t.assignee,
    h.habilidad,
    SUM(CAST(h.experiencia AS NUMERIC)) AS total_experiencia
FROM tareas t,
     UNNEST(t.habilidades_extraidas) AS h(habilidad, experiencia, fecha_modificacion)
GROUP BY t.assignee, h.habilidad
ORDER BY t.assignee, h.habilidad
"""

query_max_fecha = (
    "SELECT tareas.assignee, max(tareas.fecha) as fecha FROM tareas GROUP BY assignee"
)
query_min_fecha = "SELECT assignee, fecha FROM tareas"
query_empleados = "SELECT codificacion, habilidades FROM empleados"

# -------------------- Cargar datos --------------------
try:
    with engine.begin() as conn:
        tasks_dat = pd.read_sql(text(query), conn)
        empleados_dat = pd.read_sql(text(query_empleados), conn)
        empleados_fecha = pd.read_sql(text(query_max_fecha), conn)
        tareas_min_fecha = pd.read_sql(text(query_min_fecha), conn)
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
# ------------------------------------------
# Guardar experiencia por empleado
# ------------------------------------------

empleados_fecha["is_active"] = empleados_fecha["fecha"].apply(
    lambda x: x > pd.Timestamp(date.today() - pd.Timedelta(days=60))
)


# -------------------- Funciones auxiliares --------------------
def escapar_pg(valor: str) -> str:
    return valor.replace("'", "''")


def construir_array_habilidades(
    df: pd.DataFrame, fecha_primera_tarea: pd.Timestamp, max_dias_antiguedad: int
) -> str:
    if df.empty:
        return "ARRAY[]::habilidades_empleado[]"

    min_exp = df["total_experiencia"].min()
    max_exp = df["total_experiencia"].max()

    def calcular_nivel(exp: float) -> float:
        experiencia_norm = (
            0.5 if min_exp == max_exp else (exp - min_exp) / (max_exp - min_exp)
        )
        dias_antiguedad = (pd.Timestamp(date.today()) - fecha_primera_tarea).days
        antiguedad_norm = min(dias_antiguedad / max_dias_antiguedad, 1.0)
        return 1 + 9 * (0.7 * experiencia_norm + 0.3 * antiguedad_norm)

    filas = [
        f"ROW('{escapar_pg(row['habilidad'])}', {calcular_nivel(row['total_experiencia'])}, '{date.today()}')::habilidades_empleado"
        for _, row in df.iterrows()
    ]
    return f"ARRAY[{', '.join(filas)}]::habilidades_empleado[]"


# ------------------------------------------
# Procesar tareas por empleado
# ------------------------------------------

tareas_min_fecha["fecha"] = pd.to_datetime(tareas_min_fecha["fecha"])
antiguedad_max = (
    tareas_min_fecha.groupby("assignee")["fecha"]
    .min()
    .apply(lambda x: (pd.Timestamp(date.today()) - x).days)
    .max()
)

print(f"{Fore.YELLOW}⚙️ Procesando habilidades de empleados...\n{Style.RESET_ALL}")
try:
    with engine.begin() as conn:
        for employee in tasks_dat["assignee"].dropna().unique():
            print(
                f"{Fore.CYAN}\t🔄 Procesando habilidades para: {employee}{Style.RESET_ALL}"
            )
            employee_tasks = tasks_dat[tasks_dat["assignee"] == employee]
            fecha_empleado_df = empleados_fecha[empleados_fecha["assignee"] == employee]

            fecha_primera = tareas_min_fecha[tareas_min_fecha["assignee"] == employee][
                "fecha"
            ].min()

            habilidades_pg = construir_array_habilidades(
                employee_tasks,
                fecha_primera_tarea=fecha_primera,
                max_dias_antiguedad=antiguedad_max,
            )

            codificacion = employee.lower().replace(" ", "_")
            fecha_modificacion = datetime.now()
            is_active = (
                bool(fecha_empleado_df["is_active"].values[0])
                if not fecha_empleado_df.empty
                else False
            )

            update_sql = f"""
                UPDATE empleados
                SET habilidades = {habilidades_pg},
                    fecha_modificacion = :fecha_modificacion,
                    is_active = :is_active
                WHERE codificacion = :codificacion
            """
            conn.execute(
                text(update_sql),
                {
                    "fecha_modificacion": fecha_modificacion,
                    "is_active": is_active,
                    "codificacion": codificacion,
                },
            )
            
            
except Exception as e:
    print(
        Fore.RED
        + Style.BRIGHT
        + f"\n❌ Error al actualizar la base de datos: {e}\n"
        + Style.RESET_ALL
    )
    exit(1)

print(f"{Fore.GREEN}\n✅ Habilidades actualizadas correctamente{Style.RESET_ALL}")
