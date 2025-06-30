import os
import time
import json
import hashlib
from typing import List, Tuple, Any
from dotenv import load_dotenv
import os
from colorama import Fore, Style, init

import requests
from requests import Response
from dateutil import parser
import psycopg2
from psycopg2 import sql


load_dotenv()
# Credenciales
email: str = os.getenv("EMAIL", "")
api_token: str = os.getenv("API_TOKEN", "")


# Encabezados
headers: dict[str, str] = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# Autenticación
auth: tuple[str, str] = (email, api_token)

users_codifications: List[dict[str, str]] = (
    []
)  # Array que va a contener a todos los usuarios junto con el alias que se le va a dar durante el procesado por temas de anonimizar

i_max: int = (
    -1
)  # Variable axiliar para saber el numero maximo de tareas que se van a extraer

projects_entorno: str = os.getenv("PROYECTOS", "")
projects: List[str] = projects_entorno.split(",")
projects.sort()


projects_codif: List[str] = (
    []
)  # Array que va a contener los codigos de los proyectos que se van a procesar

total_errores: int = (
    0  # Contador de errores que se van a producir durante la ejecución del script
)

# Nombre de la base de datos que queremos usar o crear
target_db: str = os.getenv("DATABASE", "")

# Credenciales para conectar al servidor PostgreSQL
db_config: dict[str, str | int] = {
    "user": os.getenv("USUARIO", ""),
    "password": os.getenv("PASS_USUARIO", ""),
    "host": os.getenv("HOST", ""),
    "port": os.getenv("PORT", 0),
}


# -----------------------------------------------------
# Paso 1: Verificamos y creamos la base si es necesario
# -----------------------------------------------------

try:
    conn: psycopg2.extensions.connection = psycopg2.connect(
        dbname="postgres", **db_config
    )  # Conectamos a la base de datos por defecto para crear la nueva base en caso de que no exista

    conn.autocommit = True  # Necesario para crear bases de datos
    cur = conn.cursor()  # Creamos un cursor para ejecutar comandos SQL

    cur.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s", (target_db,)
    )  # Verificamos si la base de datos ya existe

    exists: tuple | None = (
        cur.fetchone()
    )  # Si existe, fetchone devolverá una tupla con un valor, si no, devolverá None

    if not exists:  # Si no existe, creamos la base de datos
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_db)))

    cur.close()  # Cerramos el cursor
    conn.close()  # Cerramos la conexión

except Exception as e:  # En caso de error, mostramos un mensaje
    print(
        Fore.RED
        + Style.BRIGHT
        + f"\n❌ Error al verificar o crear la base de datos: {e}\n"
        + Style.RESET_ALL
    )
    exit(1)


# -----------------------------------------------------
# Paso 2: Conexión a la base y verificación de tablas
# -----------------------------------------------------

try:
    conn = psycopg2.connect(
        dbname=target_db, **db_config
    )  # Conectamos a la base de datos creada o verificada

    cur = conn.cursor()  # Creamos un cursor para ejecutar comandos SQL

    # Verificamos si existen las tablas
    cur.execute(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name IN ('tareas', 'empleados', 'proyectos');
    """
    )  # Ejecutamos una consulta para obtener los nombres de las tablas existentes
    tablas_existentes = {
        row[0] for row in cur.fetchall()
    }  # Fetchall devuelve todas las filas, y las convertimos a un set para facilitar la verificación

    if {"tareas", "empleados", "proyectos"}.issubset(
        tablas_existentes
    ):  # Verificamos si todas las tablas necesarias existen
        print(
            Fore.GREEN
            + Style.BRIGHT
            + "\nLas tablas ya existen.\n"
            + Style.RESET_ALL
            + Fore.RESET
        )

    else:  # Si faltan tablas, ejecutamos el script SQL para crearlas
        print(
            Fore.YELLOW
            + Style.BRIGHT
            + f"""\n⚙️  Faltan una o más tablas. Ejecutando script '{os.getenv("FICHERO_TABLAS")}'...\n"""
            + Style.RESET_ALL
        )

        if os.path.exists(
            f"""{os.getenv("FICHERO_TABLAS")}"""
        ):  # Verificamos si el archivo 'Tablas.sql' existe

            with open(
                f"""{os.getenv("FICHERO_TABLAS")}""", "r", encoding="utf-8"
            ) as f:  # Abrimos el archivo en modo lectura
                sql_script = f.read()  # Leemos el contenido del archivo SQL
                cur.execute(
                    sql_script
                )  # Ejecutamos el script SQL para crear las tablas

            print(
                Fore.GREEN
                + Style.BRIGHT
                + f"""\n✅ Tablas creadas desde '{os.getenv("FICHERO_TABLAS")}'.\n"""
                + Style.RESET_ALL
            )
        else:
            print(
                Fore.RED
                + Style.BRIGHT
                + f"""\n❌ El archivo '{os.getenv("FICHERO_TABLAS")}' no fue encontrado.\n"""
                + Style.RESET_ALL
            )
            exit(1)

    cur.close()  # Cerramos el cursor
    conn.commit()  # Hacemos commit de los cambios
    conn.close()  # Cerramos la conexión

except Exception as e:  # En caso de error, mostramos un mensaje y paramos la ejecución
    print(
        Fore.RED
        + Style.BRIGHT
        + f"\n❌ Error al conectar o al ejecutar el script SQL: {e}\n"
        + Style.RESET_ALL
    )
    exit(1)


def extraer_texto(obj: dict) -> str:
    """
    Función recursiva para extraer y concatenar todos los valores de 'text' a lo largo de una tarea dada.

    @param obj: Objeto JSON a analizar.
    @return: Tupla con el texto concatenado, si contiene código, el código y el lenguaje del código.
    """
    # -----------------------------------------------------
    # Declaración de variables auxiliares
    # -----------------------------------------------------

    texto_concatenado: str = ""  # Texto concatenado

    # -----------------------------------------------------
    # Cuerpo de la función
    # -----------------------------------------------------

    if isinstance(obj, dict):  # Si es un diccionario

        if "text" in obj:  # Si contiene la clave 'text', concatenar su valor
            texto_concatenado += obj["text"] + " "  # Concatenar el texto

        for key, value in obj.items():  # Recorrer los elementos del diccionario

            if (
                key != "text"
            ):  # Si la clave no es 'text', llamar recursivamente a la función

                aux_texto: str = extraer_texto(value)  # Llamada recursiva
                texto_concatenado += aux_texto + " "  # Concatenar el texto

    elif isinstance(obj, list):  # Si es una lista
        for item in obj:  # Recorrer los elementos de la lista
            aux_texto = extraer_texto(item)  # Llamada recursiva
            texto_concatenado += aux_texto + " "  # Concatenar el texto

    # Eliminar espacios extra y retornar el texto concatenado
    texto_concatenado = texto_concatenado.strip()

    return texto_concatenado


def obtener_todas_las_tareas(jira_url) -> list:
    """
    Obtiene todas las tareas de un proyecto de Jira paginando si es necesario.
    Por defecto, la API de Jira solo permite conseguir 50 resultados de un proyecto, con esta funcion se obtienen todas las tareas
    haciendo tantas llamadas a la API como sean necesarias.

    @param jira_url: url del proyecto de Jira.
    @return: Lista con todas las tareas de un proyecto.
    """

    # -----------------------------------------------------
    # Declaración de variables auxiliares
    # -----------------------------------------------------

    start_at: int = 0  # Iniciar en la página 0
    max_results: int = 100  # Limite de Jira en algunas instancias
    all_tasks: List[dict] = []  # Lista para almacenar todas las tareas
    global total_errores

    # -----------------------------------------------------
    # Cuerpo de la función
    # -----------------------------------------------------

    while True:  # Interar hasta que se hayan obtenido todas las tareas de un proyecto.

        if len(all_tasks) <= i_max:  # Si se ha alcanzado el límite de tareas
            break  # Salir del bucle

        # Dada la Url de un proyecto, paginar para obtener todas las tareas
        url: str = f"{jira_url}&maxResults={max_results}&startAt={start_at}"
        try:
            response: Response = requests.get(
                url, headers=headers, auth=auth
            )  # Realizar la solicitud a la API de Jira con autenticación necesaria
        except Exception as e:  # Si hay un error en la solicitud
            print(f"\t\t{Fore.RED}Error de conexión: {e}{Fore.RESET}")
            total_errores += 1  # Incrementar el contador de errores
            break  # Salir del bucle
        
        if response.status_code != 200:  # Si hay un error, imprimirlo y salir del bucle
            print(f"\t\t{Fore.RED}Error: {response.status_code}, {response.text}{Fore.RESET}")
            total_errores += 1  # Incrementar el contador de errores
            break

        data: dict[str, Any] = response.json()
        tasks: List[dict] = data.get("issues", [])  # Extraer las tareas de la respuesta

        if not tasks:
            break  # Si ya no hay más tareas, salir del bucle

        all_tasks.extend(tasks)  # Agregar las tareas a la lista

        start_at += max_results  # Pasamos a la siguiente página

        time.sleep(
            2
        )  # Esperar 2 segundos para resetear el time de las peticiones y que no bloquee la cuenta

    return all_tasks  # Retornar la lista con todas las tareas


def anonimizar_tareas(tareas: List[dict]) -> Tuple[List[dict], List[dict], List[dict]]:
    """
    Función que dada una tarea anonimiza el empleado y el proyecto al que pertenece.

    @param tareas: lista de las tareas obtenidas
    @return tuple: tupla con las tareas anonimizadas, los usuarios codificados y los proyectos codificados
    """

    # -----------------------------------------------------
    # Declaración de variables auxiliares
    # -----------------------------------------------------

    users_codifications: List[tuple[str, str]] = []
    projects_codif: List[tuple[str, str]] = []

    # -----------------------------------------------------
    # Cuerpo de la función
    # -----------------------------------------------------

    for tarea in tareas:  # Recorrer el array de las tareas

        empleado: str = tarea["assignee"]  # Obtener el empleado de la tarea
        proyecto: str = tarea[
            "project_key"
        ]  # Obtener el proyecto al que pertenece la tarea

        if (
            "," in empleado
        ):  # Si el empleado tiene una coma, se reorganiza el nombre y apellido
            aux = empleado.split(",")
            empleado = aux[1].strip() + " " + aux[0].strip()

        if empleado == "":  # Si no hay empleado
            tarea["assignee"] = None  # Se pone a null

        else:
            empleado_codificado = hashlib.sha256(
                empleado.encode()
            ).hexdigest()  # Se codifica el empleado con SHA-256

            if (
                empleado_codificado,
                empleado,
            ) not in users_codifications:  # Si el empleado no está en la lista de codificaciones
                users_codifications.append(
                    (empleado_codificado, empleado)
                )  # Se añade a la lista de codificaciones

            tarea["assignee"] = (
                empleado_codificado  # Se cambia el empleado por la versión anonimizada
            )

        if proyecto == "":  # Si no hay proyecto
            tarea["project_key"] = None  # Se pone a null

        else:
            proyecto_codificado = hashlib.sha256(
                proyecto.encode()
            ).hexdigest()  # Se codifica el proyecto con SHA-256

            if (
                proyecto_codificado,
                proyecto,
            ) not in projects_codif:  # Si el proyecto no está en la lista de codificaciones
                projects_codif.append(
                    (proyecto_codificado, proyecto)
                )  # Se añade a la lista de codificaciones

            tarea["project_key"] = (
                proyecto_codificado  # Se cambia el proyecto por la versión anonimizada
            )

            tarea["key"] = tarea["key"].replace(
                proyecto, proyecto_codificado
            )  # Se cambia la clave de la tarea para que coincida con el proyecto codificado

    return (
        tareas,
        users_codifications,
        projects_codif,
    )  # Se devuelve la tupla de las tareas, usuarios codificados y proyectos codificados


j_aux = 1

print(
    Fore.YELLOW
    + Style.BRIGHT
    + f"\n🔍 Procesando {len(projects)} proyectos de Jira...\n"
    + Style.RESET_ALL
)

for p in projects:  # Recorrer el array de los proyectos

    jira_url: str = os.getenv("URL_JIRA", "") + p  # URL de la API de Jira

    print(
        f"{Fore.CYAN}\t📁 Procesando proyecto {j_aux}: {Fore.BLUE}{jira_url}{Style.RESET_ALL}"
    )

    # Obtener todas las tareas
    tareas: List[dict] = obtener_todas_las_tareas(jira_url=jira_url)

    if total_errores >= len(projects):  # Si ha habido errores, salir del bucle
        print(
            Fore.RED
            + Style.BRIGHT
            + "\n❌ Se han producido demasiados errores, abortando la ejecución.\n"
            + Style.RESET_ALL
        )
        exit(1)

    processed_tasks: List[dict] = (
        []
    )  # Array que va a contener todas las tareas extraidas y procesadas

    for tarea in tareas:  # Recorrer las tareas

        json_tarea: dict[str, Any] = (
            {}
        )  # Diccionario para almacenar la información de la tarea

        json_tarea["key"] = tarea.get("key", "")  # Extraer la clave de la tarea

        iso_date = tarea["fields"].get(
            "statuscategorychangedate", None
        )  # Extraer la fecha de cambio de estado

        if iso_date:  # Si la fecha no es nula
            try:  # Intentar parsear la fecha
                dt = parser.parse(iso_date)  # Parsear la fecha
                iso_date = dt.strftime(
                    "%Y-%m-%d %H:%M:%S"
                )  # Convertir a formato legible

            except Exception as e:  # Si hay un error al parsear la fecha
                iso_date = "9999-12-31 23:59:59"
        else:
            iso_date = "9999-12-31 00:00:00"  # Si la fecha es nula, poner una fecha por defecto

        json_tarea["fecha"] = iso_date  # Extraer la fecha de cambio de estado

        json_tarea["timespent_real"] = tarea["fields"].get(
            "timespent", 0
        )  # Extraer el tiempo invertido

        json_tarea["project_key"] = tarea["fields"]["project"][
            "key"
        ]  # Extraer la clave del proyecto

        json_tarea["assignee"] = (tarea.get("fields") or {}).get(
            "assignee"
        ) or {}  # Extraer el empleado asignado

        json_tarea["assignee"] = json_tarea["assignee"].get(
            "displayName", ""
        )  # Extraer el correo del empleado asignado

        json_tarea["status"] = (tarea.get("fields") or {}).get(
            "status"
        ) or {}  # Extraer el estado de la tarea

        json_tarea["status"] = json_tarea["status"].get(
            "name", ""
        )  # Extraer el nombre del estado

        json_tarea["issuetype"] = (tarea.get("fields") or {}).get(
            "issuetype"
        ) or {}  # Extraer el estado de la tarea

        json_tarea["issuetype"] = json_tarea["issuetype"].get(
            "name", ""
        )  # Extraer el nombre del estado

        description = extraer_texto(
            (tarea.get("fields") or {}).get("description") or {}
        )  # Extraer el texto de la descripción

        json_tarea["texto"] = json_tarea["summary"] = (
            tarea["fields"].get("summary", "") + "\n" + description
        )  # Extraer el texto

        processed_tasks.append(
            json_tarea
        )  # Agregar la información de la tarea al JSON final

    processed_tasks, users_codifications, projects_codif = anonimizar_tareas(
        processed_tasks
    )  # Llamar a la función para anonimizar las tareas

    try:
        conn = psycopg2.connect(
            dbname=target_db, **db_config
        )  # Conectar a la base de datos
        cur = conn.cursor()

        # MERGE para TAREAS (por clave)
        upsert_query_tareas = """
            INSERT INTO TAREAS (
                clave, fecha, timespent_real, project_key, assignee, status_text,
                issue_type, texto, fecha_modificacion
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (clave) DO UPDATE SET
                fecha = EXCLUDED.fecha,
                timespent_real = EXCLUDED.timespent_real,
                project_key = EXCLUDED.project_key,
                assignee = EXCLUDED.assignee,
                status_text = EXCLUDED.status_text,
                issue_type = EXCLUDED.issue_type,
                texto = EXCLUDED.texto,

                fecha_modificacion = date_trunc('second', now())
        """

        # MERGE para EMPLEADOS (por empleado)
        upsert_query_empleados = """
            INSERT INTO EMPLEADOS (codificacion, empleado, habilidades, is_active, fecha_modificacion)
            VALUES (%s, %s, null, true, now())
            ON CONFLICT (empleado) DO UPDATE SET
                codificacion = EXCLUDED.codificacion,
                habilidades = EXCLUDED.habilidades,
                is_active = EXCLUDED.is_active,
                fecha_modificacion = date_trunc('second', now())
        """

        # MERGE para PROYECTOS (por proyecto)
        upsert_query_proyectos = """
            INSERT INTO PROYECTOS (codificacion, proyecto, habilidades_necesarias, fecha_modificacion)
            VALUES (%s, %s, null, now())
            ON CONFLICT (proyecto) DO UPDATE SET
                codificacion = EXCLUDED.codificacion,
                habilidades_necesarias = EXCLUDED.habilidades_necesarias,
                fecha_modificacion = date_trunc('second', now())
        """

        # Preparamos los datos como listas de tuplas
        tareas_values = [
            (
                tarea.get("key"),
                tarea.get("fecha"),
                (tarea.get("timespent_real") or 0),
                tarea.get("project_key"),
                tarea.get("assignee"),
                tarea.get("status"),
                tarea.get("issuetype"),
                tarea.get("texto"),
            )
            for tarea in processed_tasks
        ]

        # Ejecutamos en bloque
        cur.executemany(upsert_query_proyectos, projects_codif)
        cur.executemany(upsert_query_empleados, users_codifications)
        cur.executemany(upsert_query_tareas, tareas_values)

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        print(
            Fore.RED
            + Style.BRIGHT
            + f"❌ Error al insertar datos: {e}"
            + Style.RESET_ALL
        )
        exit(1)

    j_aux += 1

print(
    Fore.GREEN
    + Style.BRIGHT
    + "\n✅ Datos insertados correctamente en la base de datos.\n"
    + Style.RESET_ALL
)
