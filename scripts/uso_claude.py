"""Actualiza datos/uso_claude.json (uso de Claude Code, abajo del todo en el panel) y lo sube.

    py scripts/uso_claude.py [--plan '<json de get_usage>' | --plan @archivo.json] [--sin-subir]

Los tokens salen de las conversaciones de Claude Code guardadas en este ordenador (~/.claude/projects/*/*.jsonl):
solo se cuentan cifras por día, nunca el texto ni los títulos. Los límites del plan (cuánto queda de las 5 horas y
de la semana) no están en esos archivos: los pasa Claude con --plan cada vez que los lee, al empezar o terminar una
tarea. El repositorio es público: aquí no va nada más que números.
"""
import datetime, json, subprocess, sys
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO = RAIZ / 'datos' / 'uso_claude.json'
DIAS = 14

def leer_conversaciones():
    vistos, dias = set(), defaultdict(lambda: {'entrada': 0, 'salida': 0, 'cache_escrita': 0, 'cache_leida': 0, 'respuestas': 0, 'sesiones': set()})
    desde = datetime.date.today() - datetime.timedelta(days=DIAS - 1)
    for f in (Path.home() / '.claude' / 'projects').glob('*/*.jsonl'):
        try:
            if datetime.date.fromtimestamp(f.stat().st_mtime) < desde: continue
            lineas = f.open(encoding='utf-8', errors='ignore')
        except OSError: continue
        for l in lineas:
            if '"usage"' not in l: continue
            try: d = json.loads(l)
            except ValueError: continue
            m = d.get('message') or {}
            u = m.get('usage')
            if not u or d.get('type') != 'assistant': continue
            # Una respuesta larga se guarda en varias líneas con el mismo id: se cuenta una vez.
            clave = m.get('id') or d.get('uuid')
            if clave in vistos: continue
            vistos.add(clave)
            try: dia = datetime.datetime.fromisoformat(d['timestamp'].replace('Z', '+00:00')).astimezone().date()
            except (KeyError, ValueError): continue
            if dia < desde: continue
            x = dias[dia.isoformat()]
            x['entrada'] += u.get('input_tokens', 0) or 0
            x['salida'] += u.get('output_tokens', 0) or 0
            x['cache_escrita'] += u.get('cache_creation_input_tokens', 0) or 0
            x['cache_leida'] += u.get('cache_read_input_tokens', 0) or 0
            x['respuestas'] += 1
            if d.get('sessionId'): x['sesiones'].add(d['sessionId'])
    return [{**{k: v for k, v in x.items() if k != 'sesiones'}, 'dia': k, 'sesiones': len(x['sesiones'])} for k, x in sorted(dias.items())]

def main():
    args = sys.argv[1:]
    previo = {}
    if ARCHIVO.exists():
        try: previo = json.loads(ARCHIVO.read_text(encoding='utf-8'))
        except ValueError: previo = {}
    plan = previo.get('plan')
    if '--plan' in args:
        v = args[args.index('--plan') + 1]
        # PowerShell 5 se come las comillas al pasar JSON a un programa: con @archivo se lee de un archivo.
        p = json.loads(Path(v[1:]).read_text(encoding='utf-8-sig') if v.startswith('@') else v)
        if isinstance(p.get('plan'), dict): p = p['plan']
        plan = {'nombre': p.get('plan'), 'leido': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
                'ventanas': [{'nombre': w.get('label'), 'usado': w.get('percentUsed'), 'renueva': w.get('resetsAt')} for w in p.get('windows', [])],
                'extra': bool((p.get('extraUsage') or {}).get('enabled'))}
    datos = {'actualizado': datetime.datetime.now().astimezone().isoformat(timespec='seconds'), 'plan': plan, 'dias': leer_conversaciones()}
    ARCHIVO.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding='utf-8')
    print('uso de claude:', len(datos['dias']), 'días', '(con plan)' if plan else '(sin plan)')
    if '--sin-subir' in args: return
    g = lambda *c: subprocess.run(['git', '-C', str(RAIZ), *c], capture_output=True, text=True)
    g('add', str(ARCHIVO))
    if g('diff', '--cached', '--quiet').returncode == 0: return
    g('commit', '-m', 'Pulso: uso de Claude')
    if g('push', '-q', 'origin', 'main').returncode != 0:
        g('pull', '-q', '--rebase'); g('push', '-q', 'origin', 'main')

if __name__ == '__main__':
    main()
