
----------------------------------------------------
------Script de creación de la base de datos -------
----------------------------------------------------

-- Tipo que almacena los mejores empleados para una determinada tarea
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_type 
        WHERE typname = 'candidatos'
    ) THEN
        CREATE TYPE Candidatos AS (
            codificacion varchar,
            porcentaje_acierto numeric,
            fecha_modificacion TIMESTAMP 
        );
    END IF;
END$$;


-- Tipo que sirve para representar las habilidades de un empleado o las habilidades extraidas de una determinada tarea
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_type 
        WHERE typname = 'habilidades_tarea'
    ) THEN
        create type habilidades_tarea as (
            habilidad varchar,
            experiencia varchar,
            fecha_modificacion TIMESTAMP 
        );
    END IF;
END$$;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_type 
        WHERE typname = 'habilidades_proyecto'
    ) THEN
        create type habilidades_proyecto as (
            habilidad varchar,
            nivel_necesario varchar,
            fecha_modificacion TIMESTAMP 
        );
    END IF;
END$$;


DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM pg_type 
        WHERE typname = 'habilidades_empleado'
    ) THEN
        create type habilidades_empleado as (
            habilidad varchar,
            nivel_actual varchar,
            fecha_modificacion TIMESTAMP
        );
    END IF;
END$$;


-- Tabla en la que se guardan los proyectos de los que se han leido tareas
create table if not exists Proyectos (
    id serial primary key,
    codificacion varchar unique not null,
    proyecto varchar unique not null,
    habilidades_necesarias habilidades_proyecto[],
    fecha_modificacion TIMESTAMP DEFAULT date_trunc('second', now())
);

-- Tabla en la que se guardan los empleados de los que se han leido tareas
create table if not exists Empleados (
    id serial primary key,
    codificacion varchar unique not null,
    empleado varchar unique not null,
    habilidades habilidades_empleado[],
    is_active boolean,
    fecha_modificacion TIMESTAMP DEFAULT date_trunc('second', now())
);

-- Tabla dedicada a almacenar las tareas extraidas
create table if not exists Tareas (
    id serial primary key,
    clave varchar unique not null,
    fecha timestamp,
    timespent_real numeric default 0.0,
    timespent_estimado numeric default 0.0,
    bien_estimado boolean default null,
    project_key varchar,
    assignee varchar,
    status_text varchar,
    issue_type varchar,
    texto varchar,
    candidatos Candidatos[],
    habilidades_extraidas habilidades_tarea[],
    assignee_in_candidatos boolean default false,
    fecha_modificacion TIMESTAMP DEFAULT date_trunc('second', now()),
    foreign key (project_key) references Proyectos(codificacion),
    foreign key (assignee) references Empleados(codificacion)
);

