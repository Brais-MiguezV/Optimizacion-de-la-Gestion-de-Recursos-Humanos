# 🚀 Optimizacion-de-la-Gestion-de-Recursos-Humanos

Bienvenido/a al repositorio de mi **TFM** necesario para obtener el Máster Universitario en Tecnologías de Análisis de Datos Masivos: Big Data por la Universidad de Santiago de Compostela.

👥 **La gestión eficiente de los recursos humanos (RRHH)** es un pilar fundamental para asegurar la productividad, la eficiencia operativa y la viabilidad de los proyectos dentro de una organización.

⚡ En un entorno empresarial dinámico y en constante transformación, las organizaciones deben enfrentarse al desafío de asignar a sus empleados de manera óptima. Esta tarea implica considerar diversos factores como las competencias individuales, la carga de trabajo existente y posibles incidencias que puedan afectar la planificación, tales como vacaciones 🏖️, bajas laborales 🤒 o huelgas ✊.

📊 El proyecto tiene como objetivo el desarrollo de un modelo que facilite una asignación eficiente del personal a los diferentes proyectos de la empresa, integrando múltiples variables que influyen en dicha gestión. Este modelo no solo permitirá optimizar el uso de los recursos humanos, sino que también contribuirá a:

- ✅ Evaluar la viabilidad de los proyectos en relación con sus fecha de inicio previstas.
- 👨‍💻 Detectar necesidades adicionales de personal.
- 🚩 Identificar proyectos con bajo rendimiento o resultados no esperados.
- 💸 Analizar el desempeño de los proyectos en función de los costes asociados.

🔍 Además, el sistema posibilitará el análisis del rendimiento de los proyectos basándose en los costes asociados, proporcionando información clave para la toma de decisiones estratégicas dentro de la organización y generar los informes económicos y KPIs de rendimiento básicos de estas.

🛠️ En etapas posteriores, el modelo podrá ampliarse para incluir estrategias de refuerzo en períodos críticos (como pueden ser los meses estivales 🌞), teniendo en cuenta la experiencia previa en proyectos similares y aspectos motivacionales del personal. De este modo, se busca lograr una planificación más eficaz y una mejor asignación de los recursos disponibles.

🌐 Con este enfoque integral, el proyecto aspira a mejorar la gestión de los recursos humanos y los proyectos dentro de las organizaciones, ofreciendo una herramienta que promueva la optimización operativa y contribuya a la sostenibilidad empresarial.

🗂️ **El proyecto está preparado para obtener las tareas a partir de la API de Jira**

ℹ️ En este README encontrarás toda la información necesaria para poner en marcha el entorno, ejecutar el proyecto y trabajar cómodamente usando contenedores Docker.

---

## 🗂️ Índice

- [📦 Requisitos](#requisitos)
- [⚙️ Instalación](#instalación)
- [🚦 Ejecución del Proyecto](#ejecución-del-proyecto)

---

## 📦 Requisitos

- 🐳 [Docker](https://docs.docker.com/get-docker/) instalado en tu máquina.
- 🧩 [Docker Compose](https://docs.docker.com/compose/install/) (si se usa).
- 📝 Variables de entorno configuradas (ver `.env`).
- 🐍 (Opcional) Python 3.x y pip (solo si quieres ejecutar fuera de Docker).

---

## ⚙️ Instalación

1. **Clona este repositorio:**

   ```bash
   git clone https://github.com/Brais-MiguezV/Optimizacion-de-la-Gestion-de-Recursos-Humanos.git
   cd Optimizacion-de-la-Gestion-de-Recursos-Humanos
   ```

2. **Copia el archivo de variables de entorno si es necesario:**

   Rellena los valores necesarios en el archivo `.env` para que el proyecto funcione correctamente. Sin este archivo, el proyecto no podrá acceder a las configuraciones necesarias, por lo que no podrá extraer las tareas de ninguna fuente de datos.

---

## 🚦 Ejecución del Proyecto

Existen dos formas de ejecutar el proyecto: usando Docker (recomendado) o de forma local sin Docker. A continuación, te explico ambas opciones.

### 1️⃣ Usando Docker (recomendado)

> 🐳 Con Docker tendrás todo el entorno aislado y listo en segundos.

**a. Levanta los contenedores:**

```bash
docker compose up --build
```

*Esto descargará las imágenes necesarias, construirá los servicios y ejecutará el entorno.*

**b. Accede al contenedor:**

- Una vez que los contenedores estén en marcha, puedes acceder al contenedor principal (por ejemplo, el de la aplicación) con:

```bash
docker attach python_app
```

*Reemplaza **``** con el nombre del servicio definido en tu **``**.*

**c. Parar los contenedores:**

```bash
docker compose down
```

### 2️⃣ Ejecución Local (sin Docker)

> ⚠️ No recomendado salvo que tengas el entorno controlado.

1. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```
2. Ejecuta el planificador:
   ```bash
   ./ejecucion_total
   ```

---

