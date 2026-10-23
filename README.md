# Panel de Bitácora

Panel de métricas de los vídeos de Bitácora, publicado en https://jaandrix.github.io/bitacora-panel/.

Los datos van en `datos/` (`videos.csv`, `web.csv`, `seguidores.csv`); el formato está en la pestaña Ajustes del panel. El panel los vuelve a leer cada minuto.

Este repositorio es público: aquí solo van el panel y las métricas, nada del cerebro del proyecto.

## Tareas

La pestaña Tareas lee `datos/tareas.json`, que Claude actualiza desde el chat con `scripts/tarea.py` (cada cambio es un commit y el panel lo vuelve a leer cada 20 s). Los recordatorios son las incidencias abiertas de este repositorio, y «en directo» mezcla el registro de Claude con los últimos commits de `jaandrix/agenda`. Como el repositorio es público, ahí no va nada privado.
