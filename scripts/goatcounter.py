"""Trae de GoatCounter las visitas a appbitacora.es de los últimos días, por origen (?ref=),
y las escribe en datos/web.csv; y el uso anónimo de la app (las marcas «apartado/<vista>» y «uso/...» que
cuenta la app al abrir cada apartado) y los fallos («error/...», «aviso/...») en datos/apartados.csv. Lo ejecuta cada noche .github/workflows/goatcounter.yml.

Necesita el secreto GOATCOUNTER_TOKEN (clave de API con permiso de lectura de estadísticas).
Cada ejecución rehace los últimos DIAS días (GoatCounter puede tardar en cerrar un día) y deja
intactos los anteriores y la columna de altas, que llega por otro camino.
"""
import csv, datetime as dt, json, os, sys, time, urllib.parse, urllib.request

SITIO = os.environ.get('GOATCOUNTER_SITE', 'https://appbitacora.goatcounter.com')
TOKEN = os.environ.get('GOATCOUNTER_TOKEN')
DIAS = int(os.environ.get('DIAS', '7'))
CSV = os.path.join(os.path.dirname(__file__), '..', 'datos', 'web.csv')
CSV_USO = os.path.join(os.path.dirname(__file__), '..', 'datos', 'apartados.csv')


def api(ruta, **params):
    url = f'{SITIO}/api/v0/{ruta}?{urllib.parse.urlencode(params)}'
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'})
    for intento in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429:  # límite de peticiones de la API
                time.sleep(2 + intento * 2); continue
            raise SystemExit(f'GoatCounter respondió {e.code} en {ruta}: {e.read()[:300]!r}')
    raise SystemExit('GoatCounter: demasiadas peticiones seguidas')


def cifra(d):
    return d.get('count', d.get('count_unique', 0)) or 0


def visitas_del_dia(dia):
    # La API pide horas exactas (RFC 3339); con solo la fecha responde 404.
    ini, fin = f'{dia.isoformat()}T00:00:00Z', f'{(dia + dt.timedelta(days=1)).isoformat()}T00:00:00Z'
    total = api('stats/total', start=ini, end=fin).get('total', 0) or 0
    filas, vistos, offset = {}, 0, 0
    while True:
        r = api('stats/toprefs', start=ini, end=fin, limit=100, offset=offset)
        for ref in r.get('stats', []):
            nombre = (ref.get('name') or '').strip() or '(directo)'
            filas[nombre] = filas.get(nombre, 0) + cifra(ref)
        offset += len(r.get('stats', []))
        if not r.get('more') or not r.get('stats'): break
        time.sleep(0.3)
    vistos = sum(v for k, v in filas.items() if k != '(directo)')
    if total > vistos: filas['(directo)'] = max(filas.get('(directo)', 0), total - vistos)
    return filas


def uso_del_dia(dia):
    """Visitantes de cada marca de la app ese día: {ruta: (titulo, visitantes)}."""
    ini, fin = f'{dia.isoformat()}T00:00:00Z', f'{(dia + dt.timedelta(days=1)).isoformat()}T00:00:00Z'
    filas, vistos = {}, []
    while True:
        params = dict(start=ini, end=fin, limit=100)
        if vistos: params['exclude_paths'] = ','.join(map(str, vistos))
        r = api('stats/hits', **params)
        hits = r.get('hits', []) or []
        for h in hits:
            vistos.append(h.get('path_id'))
            ruta = (h.get('path') or '').lstrip('/')
            if ruta.startswith(('apartado/', 'uso/', 'error/', 'aviso/')):
                filas[ruta] = ((h.get('title') or '').strip(), cifra(h))
        if not r.get('more') or not hits: break
        time.sleep(0.3)
    return filas


def guardar_uso(dias):
    rehechos = {d.isoformat() for d in dias}
    previas = []
    if os.path.exists(CSV_USO):
        with open(CSV_USO, encoding='utf-8') as f:
            previas = [r for r in csv.DictReader(f) if r['fecha'] not in rehechos]
    nuevas = []
    for d in dias:
        for ruta, (titulo, n) in sorted(uso_del_dia(d).items()):
            if n: nuevas.append({'fecha': d.isoformat(), 'ruta': ruta, 'titulo': titulo, 'visitantes': str(n)})
        time.sleep(0.3)
    filas = sorted(previas + nuevas, key=lambda r: (r['fecha'], r['ruta']))
    with open(CSV_USO, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['fecha', 'ruta', 'titulo', 'visitantes'])
        w.writeheader(); w.writerows(filas)
    print(f'uso de la app: {len(nuevas)} filas nuevas; {len(filas)} en total')


def main():
    if not TOKEN: sys.exit('Falta el secreto GOATCOUNTER_TOKEN')
    hoy = dt.date.today()
    dias = [hoy - dt.timedelta(days=k) for k in range(DIAS, 0, -1)]
    rehechos = {d.isoformat() for d in dias}

    previas, altas = [], {}
    if os.path.exists(CSV):
        with open(CSV, encoding='utf-8') as f:
            for r in csv.DictReader(f):
                if r['fecha'] in rehechos:
                    if r.get('altas'): altas[(r['fecha'], r['ref'])] = r['altas']
                else:
                    previas.append(r)

    nuevas = []
    for d in dias:
        for ref, n in sorted(visitas_del_dia(d).items(), key=lambda x: -x[1]):
            if n: nuevas.append({'fecha': d.isoformat(), 'ref': ref, 'visitas': str(n), 'altas': altas.pop((d.isoformat(), ref), '')})
        time.sleep(0.3)
    for (fecha, ref), n in altas.items():  # altas de un origen que hoy no trae visitas: no se pierden
        nuevas.append({'fecha': fecha, 'ref': ref, 'visitas': '', 'altas': n})

    filas = sorted(previas + nuevas, key=lambda r: (r['fecha'], r['ref']))
    os.makedirs(os.path.dirname(CSV), exist_ok=True)
    with open(CSV, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['fecha', 'ref', 'visitas', 'altas'])
        w.writeheader(); w.writerows(filas)
    print(f'{len(nuevas)} filas de {DIAS} días; {len(filas)} en total')
    guardar_uso(dias)


if __name__ == '__main__':
    main()
