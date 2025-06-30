#!/bin/bash

BLUE="\033[1;34m"
RED="\033[1;31m"
NC="\033[0m"  # Reset color

# Función para imprimir en marco
print_box() {
  local msg="$1"
  local color="$2"
  local len=${#msg}
  local border=$(printf '%*s' "$((len + 4))" '' | tr ' ' '-')

  echo -e "\n${color}+${border}+"
  echo -e "|  $msg  |"
  echo -e "+${border}+${NC}\n"
}

# Función para ejecutar y verificar scripts
run_script() {
  local script="$1"
  local label="$2"

  print_box "Ejecutando script $script" "$BLUE"
  python3 "$script"
  if [ $? -ne 0 ]; then
    print_box "Error en $script. Abortando ejecución." "$RED"
    exit 1
  fi
}

# Lista de scripts a ejecutar
run_script "leer_datos.py" "Leer datos"
run_script "estimacion_tiempos.py" "Estimación de tiempos"
run_script "asignar_habilidades_tareas.py" "Asignar habilidades a tareas"
run_script "asignar_habilidades_empleados.py" "Asignar habilidades a empleados"
run_script "asignar_tareas_empleados.py" "Asignar tareas a empleados"
run_script "guardar_excel.py" "Guardar Excel"
