import numpy as np
import pandas as pd
from dotenv import load_dotenv
import os
from colorama import Fore, Style, init
from sqlalchemy import create_engine, Engine, text


load_dotenv()

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


# Leer los datos directamente a un DataFrame
db_url: str = (
    f"postgresql+psycopg2://{db_config['user']}:{db_config['password']}"
    f"@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
)

try:
    engine: Engine = create_engine(db_url)
    # Probar conexión
    with engine.connect() as conn:
        pass  # Si falla, salta al except
except Exception as e:
    print(
        Fore.RED
        + Style.BRIGHT
        + f"\n❌ Error al conectar con la base de datos: {e}\n"
        + Style.RESET_ALL
    )
    exit(1)

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


j_aux: int = 1  # Variable auxiliar para el progreso

# 1. Asignar timespent_real = 0 para todas las tareas en "To Do"
tasks_dat.loc[tasks_dat["status_text"] == "To Do", "timespent_real"] = 0

# 2. Identificar tareas que necesitan estimación
tareas_a_estimar: pd.DataFrame = tasks_dat.copy()

# 3. Estimación por proyecto y empleado
print(f"{Fore.YELLOW}\n⚙️ Estimando tiempos para tareas\n{Style.RESET_ALL}")
for p in tareas_a_estimar["project_key"].unique():

    print(
        f"{Fore.CYAN}\t🧮 Estimando tiempos para el proyecto {p} ({j_aux}/{len(tareas_a_estimar['project_key'].unique())}){Style.RESET_ALL}"
    )

    j_aux += 1  # Incrementar el contador de progreso

    tareas_proyecto: pd.DataFrame = tasks_dat[
        (tasks_dat["project_key"] == p)
    ]  # Filtrar tareas del proyecto actual

    empleados: np.ndarray = (
        tareas_a_estimar[tareas_a_estimar["project_key"] == p]["assignee"]
        .dropna()
        .unique()
    )  # Obtener empleados que tienen tareas en el proyecto actual

    if (
        empleados.size == 0
    ):  # Si no hay empleados asignados, continuar al siguiente proyecto
        continue

    for e in empleados:  # Recorrer cada empleado asignado al proyecto

        tareas_empleado: pd.DataFrame = tareas_proyecto[
            tareas_proyecto["assignee"] == e
        ]  # Filtrar tareas del empleado actual

        if not tareas_empleado.empty:  # Si el empleado tiene tareas asignadas
            media_timespent: float = tareas_empleado[
                "timespent_real"
            ].mean()  # Calcular la media de timespent_real

        elif (
            not tareas_proyecto.empty
        ):  # Si el empleado no tiene tareas asignadas pero hay tareas en el proyecto
            media_timespent: float = tareas_proyecto[
                "timespent_real"
            ].mean()  # Calcular la media de timespent_real del proyecto

        else:  # Si no hay tareas en el proyecto
            media_timespent: float = 0

        mask: pd.Series = (
            (tasks_dat["project_key"] == p)
            & (tasks_dat["assignee"] == e)
            & (tasks_dat["status_text"] != "To Do")
        )  # Crear una máscara para las tareas del proyecto y empleado actual

        tasks_dat.loc[mask, "timespent_estimado"] = (
            media_timespent  # Asignar la media de timespent_real a las tareas del empleado
        )

    # Estimar tareas sin asignar
    sin_asignar_mask: pd.Series = (
        (tasks_dat["project_key"] == p)
        & (tasks_dat["assignee"].isnull())
        & (tasks_dat["status_text"] != "To Do")
    )  # Crear una máscara para las tareas sin asignar en el proyecto actual

    if not tareas_proyecto.empty:  # Si hay tareas en el proyecto
        media_timespent: float = tareas_proyecto[
            "timespent_real"
        ].mean()  # Calcular la media de timespent_real del proyecto

    else:  # Si no hay tareas en el proyecto
        media_timespent: float = 0  # Asignar 0 como media de timespent_real

    tasks_dat.loc[sin_asignar_mask, "timespent_estimado"] = (
        media_timespent  # Asignar la media de timespent_real a las tareas sin asignar
    )

# 4. Guardar resultados en la base de datos
# Rellenar nulos antes de insertar
tasks_dat["timespent_estimado"] = (
    tasks_dat["timespent_estimado"].fillna(0).astype(float)
)
tasks_dat["timespent_real"] = tasks_dat["timespent_real"].fillna(0).astype(float)

update_query = text(
    """
    UPDATE tareas
    SET timespent_real = :real, timespent_estimado = :estimado, bien_estimado = :bien
    WHERE clave = :clave
"""
)

with engine.connect() as conn:
    with conn.begin():  # Maneja commit/rollback automáticamente
        for _, row in tasks_dat.iterrows():
            conn.execute(
                update_query,
                {
                    "real": float(row["timespent_real"] / 3600),
                    "estimado": float(row["timespent_estimado"] / 3600),
                    "bien": (
                        bool(
                            abs(row["timespent_real"] - row["timespent_estimado"])
                            <= 0.05 * row["timespent_estimado"]
                        )
                        if pd.notnull(row["timespent_estimado"])
                        else None
                    ),
                    "clave": row["clave"],
                },
            )

    print(f"\n{Fore.GREEN}✅ Cambios efectuados en base de datos{Style.RESET_ALL}\n")
