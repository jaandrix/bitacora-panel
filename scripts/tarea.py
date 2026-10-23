"""Actualiza datos/tareas.json (pestaña Tareas del panel) y lo sube. Lo usa Claude desde el chat.

    py scripts/tarea.py <orden> [argumentos] [+ <orden> ...]

Órdenes (se pueden encadenar con « + » para subir una sola vez; con « / » Git Bash lo convierte en una ruta):
    sesion <trabajando|esperando|parado> [titulo]
    curso <id> <titulo> [detalle]     tarea en curso (si existe, la pasa a «curso»)
    cola <id> <titulo> [detalle]      tarea en cola, para después
    espera <id> [detalle]             tarea a la espera de Alejandro
    hecho <id>                        tarea terminada
    quitar <id>                       la borra de «en curso»
    limpiar                           borra las terminadas
    log <texto>                       una línea en «en directo»
    pendiente <id> <alta|media|baja> <area> <titulo> [detalle] [quien]
    resuelto <id>                     quita un pendiente
Opciones: --sin-subir (solo escribe el archivo).

Nunca se apunta aquí nada privado ni fallos de seguridad sin arreglar: el repositorio es público.
"""
import datetime, json, subprocess, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO = RAIZ / 'datos' / 'tareas.json'
MAX_REGISTRO = 80


def ahora():
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec='seconds')


def cargar():
    if ARCHIVO.exists():
        return json.loads(ARCHIVO.read_text(encoding='utf-8'))
    return {'actualizado': None, 'sesion': {}, 'en_curso': [], 'pendientes': [], 'registro': []}


def buscar(lista, id_):
    return next((t for t in lista if t['id'] == id_), None)


def aplicar(d, orden, a):
    resumen = None
    if orden == 'sesion':
        d['sesion'] = {'estado': a[0], 'titulo': a[1] if len(a) > 1 else d.get('sesion', {}).get('titulo', '')}
    elif orden in ('curso', 'cola'):
        estado = 'curso' if orden == 'curso' else 'pendiente'
        t = buscar(d['en_curso'], a[0])
        if t:
            t['estado'] = estado
            if len(a) > 1: t['titulo'] = a[1]
            if len(a) > 2: t['detalle'] = a[2]
        else:
            t = {'id': a[0], 'titulo': a[1], 'detalle': a[2] if len(a) > 2 else '', 'estado': estado}
            d['en_curso'].append(t)
        t['cuando'] = ahora()
        if orden == 'curso': resumen = f'empiezo: {t["titulo"]}'
    elif orden in ('espera', 'hecho'):
        t = buscar(d['en_curso'], a[0])
        if not t: sys.exit(f'no existe la tarea {a[0]}')
        t['estado'] = 'esperando' if orden == 'espera' else 'hecho'
        if orden == 'espera' and len(a) > 1: t['detalle'] = a[1]
        t['cuando'] = ahora()
        resumen = (f'te espera: {t["titulo"]}' if orden == 'espera' else f'hecho: {t["titulo"]}')
    elif orden == 'quitar':
        d['en_curso'] = [t for t in d['en_curso'] if t['id'] != a[0]]
    elif orden == 'limpiar':
        d['en_curso'] = [t for t in d['en_curso'] if t['estado'] != 'hecho']
    elif orden == 'log':
        resumen = ' '.join(a)
    elif orden == 'pendiente':
        p = buscar(d['pendientes'], a[0]) or {'id': a[0]}
        p.update({'prioridad': a[1], 'area': a[2], 'titulo': a[3]})
        if len(a) > 4: p['detalle'] = a[4]
        if len(a) > 5: p['quien'] = a[5]
        if p not in d['pendientes']: d['pendientes'].append(p)
    elif orden == 'resuelto':
        p = buscar(d['pendientes'], a[0])
        d['pendientes'] = [x for x in d['pendientes'] if x['id'] != a[0]]
        if p: resumen = f'resuelto: {p["titulo"]}'
    else:
        sys.exit(f'orden desconocida: {orden}')
    if resumen:
        d['registro'] = ([{'hora': ahora(), 'texto': resumen}] + d.get('registro', []))[:MAX_REGISTRO]
    return resumen or orden


def git(*args):
    return subprocess.run(['git', '-C', str(RAIZ), *args], capture_output=True, text=True, encoding='utf-8')


def main():
    args = sys.argv[1:]
    subir = '--sin-subir' not in args
    args = [x for x in args if x != '--sin-subir']
    if not args: sys.exit(__doc__)
    grupos, actual = [], []
    for x in args:
        if x == '+':
            if actual: grupos.append(actual)
            actual = []
        else:
            actual.append(x)
    if actual: grupos.append(actual)
    if subir: git('pull', '-q', '--rebase', '--autostash')
    d = cargar()
    hechos = [aplicar(d, g[0], g[1:]) for g in grupos]
    d['actualizado'] = ahora()
    ARCHIVO.parent.mkdir(exist_ok=True)
    ARCHIVO.write_text(json.dumps(d, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    if subir:
        git('add', 'datos/tareas.json')
        git('commit', '-q', '-m', 'tareas: ' + '; '.join(hechos)[:120])
        r = git('push', '-q')
        if r.returncode:
            git('pull', '-q', '--rebase')
            r = git('push', '-q')
        print('subido' if not r.returncode else 'NO SUBIDO: ' + r.stderr.strip()[:300])


if __name__ == '__main__':
    main()
