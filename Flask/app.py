from flask import Flask, jsonify, redirect, render_template_string, request, url_for
import ipaddress
import json
from pathlib import Path
import re


VALID_PROTOCOLS = (
    "OSPF",
    "OSPFv2",
    "OSPFv3",
    "BGP",
    "RIP",
    "RIPng",
    "IS-IS",
    "EIGRP",
    "EIGRP for IPv6",
    "STP",
    "RSTP",
    "MSTP",
    "VRRP",
    "HSRP",
    "LACP",
    "LLDP",
    "ARP",
    "DHCP",
    "DNS",
    "TCP",
    "UDP",
    "ICMP",
    "IPv4",
    "IPv6",
)
MAC_ADDRESS_PATTERN = re.compile(
    r"(?:[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}"
    r"|[0-9A-Fa-f]{2}(?:-[0-9A-Fa-f]{2}){5}"
    r"|[0-9A-Fa-f]{4}(?:\.[0-9A-Fa-f]{4}){2})"
)

with Path(__file__).with_name("api.json").open("r", encoding="utf-8") as json_api:
    datos_json = json.load(json_api)
print (datos_json)


def guardar_datos_json():
    archivo_json = Path(__file__).with_name("api.json")
    archivo_temporal = archivo_json.with_suffix(".json.tmp")
    archivo_temporal.write_text(
        json.dumps(datos_json, ensure_ascii=False, indent=4) + "\n",
        encoding="utf-8"
    )
    archivo_temporal.replace(archivo_json)


def validar_mac(mac):
    if not MAC_ADDRESS_PATTERN.fullmatch(mac):
        raise ValueError("La MAC debe ser una dirección válida de 48 bits.")


def validar_ipv4(ip):
    try:
        ipaddress.IPv4Address(ip)
    except ipaddress.AddressValueError as error:
        raise ValueError("La IP debe ser una dirección IPv4 válida.") from error


def leer_vlans(formulario, vlans_anteriores=None):
    nombres = formulario.getlist("vlan_name")
    ips = formulario.getlist("vlan_ip")
    politicas = formulario.getlist("vlan_policy")
    if not (len(nombres) == len(ips) == len(politicas)):
        raise ValueError("Los datos de VLAN están incompletos.")

    nuevas_vlans = {}
    vlans_anteriores = vlans_anteriores or {}
    for nombre, ip, politica in zip(nombres, ips, politicas):
        nombre, ip, politica = nombre.strip(), ip.strip(), politica.strip()
        if not nombre and not ip and not politica:
            continue
        if not nombre or not ip or not politica:
            raise ValueError("Cada VLAN necesita nombre, IP y política.")
        validar_ipv4(ip)
        if nombre in nuevas_vlans:
            raise ValueError("Los nombres de VLAN deben ser únicos por dispositivo.")

        vlan = dict(vlans_anteriores.get(nombre, {}))
        vlan.update({"IP": ip, "Policies": politica})
        vlan.setdefault("Ports", [])
        vlan.setdefault("ET", False)
        vlan.setdefault("SSH", False)
        nuevas_vlans[nombre] = vlan
    return nuevas_vlans

app = Flask(__name__)  # espacio dentro de memoria

# Diccionario global para que todas las rutas puedan acceder y modificarlo
dispositivos = {
    101: {
        "ip": "192.168.1.10",
        "device_name": "Router Principal",
        "policy": {"type": "ALLOW_ALL"},
        "status": "Activo"
    },
    102: {
        "ip": "192.168.1.20",
        "device_name": "Switch Piso 1",
        "policy": {"type": "BLOCK_IP", "blocked_ip": "192.168.1.20"},
        "status": "Activo"
    },
    103: {
        "ip": "192.168.1.30",
        "device_name": "Firewall",
        "policy": {"type": "RESTRICT"},
        "status": "Inactivo"
    },
    104: {
            "ip": "192.168.1.40",
            "device_name": "Servidor Web",
            "policy": {
            "type": "REQUIRED_IP",
            "required_ip": "192.168.1.50"
                    },
            "status": "Inactivo"
        },
    105: {
            "ip": "192.168.1.50",
            "device_name": "Access Point",
            "policy": {
    
            "type": "ALLOW_ALL"
            },
            "status": "Activo"
            },
                
    # Elementos nuevos
    106: {
        "ip": "192.168.1.60",
        "device_name": "Servidor Web",
        "policy": {"type": "ALLOW_ALL"},
        "status": "Activo"
    },
    107: {
        "ip": "192.168.1.70",
        "device_name": "Base de Datos",
        "policy": {"type": "INTERNAL_ONLY"},
        "status": "Activo"
    },
    108: {
        "ip": "192.168.1.80",
        "device_name": "Access Point Recepción",
        "policy": {"type": "GUEST_WIFI"},
        "status": "Inactivo"
    },
    109: {
        "ip": "192.168.1.90",
        "device_name": "Switch Piso 2",
        "policy": {"type": "ALLOW_ALL"},
        "status": "Activo"
    },
    110: {
        "ip": "192.168.1.100",
        "device_name": "Cámara de Seguridad",
        "policy": {"type": "VIDEO_ONLY"},
        "status": "Activo"
    }
}

# Lista global para la función de agregar elementos
registro_nombres = ["Router Principal"]

# Endpoint HTML original
@app.route('/')
def inicio():
    print("Cambio")
    return datos_json

@app.route('/tabla', methods=['GET', 'POST'])
def mostrar_tabla():
    error = None
    if request.method == "POST":
        action = request.form.get("action")
        mac = request.form.get("mac", "").strip()
        try:
            if action == "delete":
                if mac not in datos_json:
                    raise ValueError("El dispositivo ya no existe.")
                del datos_json[mac]
            elif action in {"add", "update"}:
                nombre = request.form.get("name", "").strip()
                if not mac or not nombre:
                    raise ValueError("MAC y nombre son obligatorios.")
                validar_mac(mac)
                protocolos = request.form.getlist("protocols")
                if any(protocolo not in VALID_PROTOCOLS for protocolo in protocolos):
                    raise ValueError("Seleccione solo protocolos de red válidos.")
                if len(protocolos) != len(set(protocolos)):
                    raise ValueError("No se pueden repetir protocolos.")
                if action == "add" and mac in datos_json:
                    raise ValueError("Ya existe un dispositivo con esa MAC.")
                mac_original = request.form.get("original_mac", mac)
                if action == "update" and mac_original not in datos_json:
                    raise ValueError("El dispositivo ya no existe.")
                anterior = datos_json.get(mac_original, {})
                if action == "update" and mac != mac_original and mac in datos_json:
                    raise ValueError("Ya existe un dispositivo con esa MAC.")

                datos_json[mac] = {
                    "Name": nombre,
                    "Protocolos": protocolos,
                    "VLANs": leer_vlans(request.form, anterior.get("VLANs", {})),
                    "Status": request.form.get("status", anterior.get("Status", "Online"))
                }
                if action == "update" and mac != mac_original:
                    del datos_json[mac_original]
            else:
                raise ValueError("Acción no reconocida.")

            guardar_datos_json()
            print(datos_json)
            return redirect(url_for("mostrar_tabla", q=request.args.get("q", "")))
        except ValueError as error_formulario:
            error = str(error_formulario)

    filtro = request.args.get("q", "").strip()
    filtro_normalizado = filtro.casefold()
    elementos_visibles = {
        mac: elemento for mac, elemento in datos_json.items()
        if not filtro_normalizado or filtro_normalizado in mac.casefold()
        or filtro_normalizado in json.dumps(elemento, ensure_ascii=False).casefold()
    }

    return render_template_string("""
    <!doctype html>
    <html lang="es">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Elementos de red</title>
        <style>
            :root { color-scheme: light; --ink: #202a31; --line: #d8e0dc; --canvas: #f1f5f2; --accent: #087f70; }
            * { box-sizing: border-box; }
            body { margin: 0; padding: 40px 24px; background: var(--canvas); color: var(--ink); font: 15px/1.5 "Segoe UI", sans-serif; }
            main { max-width: 1180px; margin: 0 auto; }
            .heading, .actions, .row-actions, .search { display: flex; align-items: center; gap: 8px; }
            .heading { justify-content: space-between; gap: 20px; margin-bottom: 20px; }
            h1 { margin: 0; font-size: 26px; font-weight: 650; }
            .toolbar { display: flex; align-items: center; gap: 12px; }
            .action-icon { display: inline-grid; place-items: center; width: 36px; height: 36px; padding: 0; border: 1px solid var(--line); border-radius: 5px; background: white; color: var(--ink); font: inherit; font-size: 18px; line-height: 1; cursor: pointer; }
            .action-icon:hover { border-color: var(--accent); color: var(--accent); }
            .add { color: var(--accent); }
            input, textarea, select { width: 100%; padding: 9px 10px; border: 1px solid var(--line); border-radius: 4px; color: var(--ink); font: inherit; }
            .search input { width: min(30vw, 260px); }
            .error { margin: 0 0 16px; color: #a33232; }
            dialog { width: min(720px, calc(100% - 28px)); max-height: 90vh; padding: 24px; border: 1px solid var(--line); border-radius: 6px; color: var(--ink); }
            dialog::backdrop { background: #17221f88; }
            dialog h2 { margin: 0 0 18px; }
            .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
            .field { display: grid; gap: 5px; }
            .field.full, .vlan-list, .form-actions { grid-column: 1 / -1; }
            .vlan-fields { display: grid; grid-template-columns: 1fr 1fr 1fr 36px; gap: 8px; margin: 8px 0; }
            .form-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
            .form-actions button { padding: 9px 14px; border: 1px solid var(--line); border-radius: 4px; background: white; color: var(--ink); cursor: pointer; }
            .form-actions .primary { border-color: var(--accent); background: var(--accent); color: white; }
            .table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 6px; background: white; }
            table { width: 100%; min-width: 760px; border-collapse: collapse; }
            th, td { padding: 14px 16px; text-align: left; vertical-align: top; }
            th { background: #e9efeb; color: #46544f; font-size: 12px; text-transform: uppercase; }
            tbody tr + tr { border-top: 1px solid var(--line); }
            code { color: var(--accent); }
            .vlan + .vlan { margin-top: 5px; }
            .status { display: inline-block; padding: 3px 9px; border-radius: 12px; background: #e0f2ed; color: #126455; white-space: nowrap; }
            @media (max-width: 600px) { body { padding: 24px 14px; } h1 { font-size: 22px; } }
            @media (max-width: 600px) { .heading, .toolbar { align-items: flex-start; flex-direction: column; } .search input { width: 100%; } .form-grid, .vlan-fields { grid-template-columns: 1fr; } .field.full, .vlan-list, .form-actions { grid-column: auto; } }
        </style>
    </head>
    <body>
        <main>
            <header class="heading">
                <h1>Elementos de red</h1>
                <div class="toolbar">
                    <form class="search" method="get" action="{{ url_for('mostrar_tabla') }}">
                        <input type="search" name="q" value="{{ filtro }}" placeholder="Buscar elementos" aria-label="Buscar elementos">
                        <button class="action-icon" type="submit" aria-label="Buscar" title="Buscar">🔍</button>
                    </form>
                    <button class="action-icon add" type="button" id="open-add" aria-label="Agregar dispositivo" title="Agregar dispositivo">＋</button>
                </div>
            </header>
            <div class="table-wrap">
                <table>
                    <thead><tr><th scope="col">MAC</th><th scope="col">Nombre</th><th scope="col">Protocolos</th><th scope="col">VLAN</th><th scope="col">Estado</th><th scope="col">Acciones</th></tr></thead>
                    <tbody>
                        {% for mac, element in elements.items() %}
                        <tr>
                            <td><code>{{ mac }}</code></td>
                            <td>{{ element.get('Name', '-') }}</td>
                            <td>{{ element.get('Protocolos', []) | join(', ') }}</td>
                            <td>{% for vlan_name, vlan in element.get('VLANs', {}).items() %}<div class="vlan"><strong>{{ vlan_name }}</strong> · {{ vlan.get('IP', '-') }} · {{ vlan.get('Policies', '-') }}</div>{% else %}-{% endfor %}</td>
                            <td><span class="status">{{ element.get('Status', '-') }}</span></td>
                            <td>
                                <div class="row-actions">
                                    <button class="action-icon edit-device" type="button" data-mac="{{ mac }}" aria-label="Modificar {{ mac }}" title="Modificar">✎</button>
                                    <form method="post" onsubmit="return confirm('¿Eliminar este dispositivo?')">
                                        <input type="hidden" name="action" value="delete">
                                        <input type="hidden" name="mac" value="{{ mac }}">
                                        <button class="action-icon" type="submit" aria-label="Eliminar {{ mac }}" title="Eliminar">🗑</button>
                                    </form>
                                </div>
                            </td>
                        </tr>
                        {% else %}
                        <tr><td colspan="6">No hay elementos.</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </main>
        {% if error %}<p class="error" role="alert">{{ error }}</p>{% endif %}
        <dialog id="add-dialog">
            <form method="post" class="form-grid">
                <h2 class="field full">Agregar dispositivo</h2>
                <input type="hidden" name="action" value="add">
                <label class="field">MAC<input name="mac" required pattern="(?:[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}|[0-9A-Fa-f]{2}(?:-[0-9A-Fa-f]{2}){5}|[0-9A-Fa-f]{4}(?:\\.[0-9A-Fa-f]{4}){2})" title="Use seis pares hexadecimales separados por dos puntos o guiones, o el formato Cisco xxxx.xxxx.xxxx." autocomplete="off"></label>
                <label class="field">Nombre<input name="name" required></label>
                <label class="field full">Protocolos<select name="protocols" multiple aria-label="Protocolos de red" size="5">{% for protocol in valid_protocols %}<option value="{{ protocol }}">{{ protocol }}</option>{% endfor %}</select><span>Puede seleccionar varios protocolos con Ctrl (Windows) o Command (Mac).</span></label>
                <div class="field full vlan-list"><span>VLAN (nombre, IP y política)</span><div id="add-vlans"></div><button type="button" class="add-vlan" data-container="add-vlans">＋ Agregar VLAN</button></div>
                <input type="hidden" name="status" value="Online">
                <div class="form-actions"><button type="button" data-close="add-dialog">Cancelar</button><button class="primary" type="submit">Guardar</button></div>
            </form>
        </dialog>
        <dialog id="edit-dialog">
            <form method="post" class="form-grid" id="edit-form">
                <h2 class="field full">Modificar dispositivo</h2>
                <input type="hidden" name="action" value="update">
                <input type="hidden" name="original_mac" id="edit-original-mac">
                <label class="field">MAC<input name="mac" id="edit-mac" required pattern="(?:[0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5}|[0-9A-Fa-f]{2}(?:-[0-9A-Fa-f]{2}){5}|[0-9A-Fa-f]{4}(?:\\.[0-9A-Fa-f]{4}){2})" title="Use seis pares hexadecimales separados por dos puntos o guiones, o el formato Cisco xxxx.xxxx.xxxx." autocomplete="off"></label>
                <label class="field">Nombre<input name="name" id="edit-name" required></label>
                <label class="field full">Protocolos<select name="protocols" id="edit-protocols" multiple aria-label="Protocolos de red" size="5">{% for protocol in valid_protocols %}<option value="{{ protocol }}">{{ protocol }}</option>{% endfor %}</select><span>Puede seleccionar varios protocolos con Ctrl (Windows) o Command (Mac).</span></label>
                <div class="field full vlan-list"><span>VLAN (nombre, IP y política)</span><div id="edit-vlans"></div><button type="button" class="add-vlan" data-container="edit-vlans">＋ Agregar VLAN</button></div>
                <input type="hidden" name="status" id="edit-status">
                <div class="form-actions"><button type="button" data-close="edit-dialog">Cancelar</button><button class="primary" type="submit">Guardar cambios</button></div>
            </form>
        </dialog>
        <template id="vlan-template">
            <div class="vlan-fields">
                <input name="vlan_name" placeholder="Nombre" aria-label="Nombre de VLAN">
                <input name="vlan_ip" placeholder="IPv4" aria-label="IP de VLAN" inputmode="decimal" pattern="(?:(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])\\.){3}(?:25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])" title="Ingrese una dirección IPv4 válida.">
                <input name="vlan_policy" placeholder="Política" aria-label="Política de VLAN">
                <button type="button" class="action-icon remove-vlan" aria-label="Quitar VLAN">×</button>
            </div>
        </template>
        <script>
            const allElements = {{ all_elements|tojson }};
            const addDialog = document.getElementById('add-dialog');
            const editDialog = document.getElementById('edit-dialog');

            function addVlanRow(container, name = '', ip = '', policy = '') {
                const row = document.getElementById('vlan-template').content.cloneNode(true);
                row.querySelector('[name="vlan_name"]').value = name;
                row.querySelector('[name="vlan_ip"]').value = ip;
                row.querySelector('[name="vlan_policy"]').value = policy;
                const fields = [...row.querySelectorAll('input')];
                const updateRequiredFields = () => {
                    const hasAnyValue = fields.some(input => input.value.trim());
                    fields.forEach(input => input.required = hasAnyValue);
                };
                updateRequiredFields();
                fields.forEach(field => field.addEventListener('input', updateRequiredFields));
                document.getElementById(container).appendChild(row);
            }

            document.getElementById('open-add').addEventListener('click', () => {
                document.getElementById('add-vlans').replaceChildren();
                addVlanRow('add-vlans');
                addDialog.showModal();
            });
            document.querySelectorAll('.add-vlan').forEach(button => button.addEventListener('click', () => addVlanRow(button.dataset.container)));
            document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => document.getElementById(button.dataset.close).close()));
            document.addEventListener('click', event => {
                if (event.target.closest('.remove-vlan')) event.target.closest('.vlan-fields').remove();
            });
            document.querySelectorAll('.edit-device').forEach(button => button.addEventListener('click', () => {
                const mac = button.dataset.mac;
                const element = allElements[mac];
                document.getElementById('edit-original-mac').value = mac;
                document.getElementById('edit-mac').value = mac;
                document.getElementById('edit-name').value = element.Name || '';
                const selectedProtocols = new Set(element.Protocolos || []);
                document.querySelectorAll('#edit-protocols option').forEach(option => {
                    option.selected = selectedProtocols.has(option.value);
                });
                document.getElementById('edit-status').value = element.Status || 'Online';
                const container = document.getElementById('edit-vlans');
                container.replaceChildren();
                Object.entries(element.VLANs || {}).forEach(([name, vlan]) => addVlanRow('edit-vlans', name, vlan.IP || '', vlan.Policies || ''));
                if (!container.children.length) addVlanRow('edit-vlans');
                editDialog.showModal();
            }));
        </script>
    </body>
    </html>
    """, elements=elementos_visibles, all_elements=datos_json, filtro=filtro, error=error, valid_protocols=VALID_PROTOCOLS)


# Endpoint JSON original modificado para devolver el diccionario global
@app.route('/api/saludo')
def saludo():
    return jsonify(dispositivos)


@app.route('/api/dispositivo/<int:id_disp>')
def obtener_dispositivo(id_disp):
    """
    Autor: Indira Almanza Roman
    Fecha: 23092026
    Funcion que retorna un elemento segun su ID
    
    """
    if id_disp in dispositivos:
        return jsonify(dispositivos[id_disp])
    return jsonify({"error": "Dispositivo no encontrado"}), 404


@app.route('/api/activos')
def obtener_activos():
    """
    
    """
    activos = {}
    for key, value in dispositivos.items():
        if value["status"] == "Activo":
            activos[key] = value
    return jsonify(activos)

# 3. Mostrar solo los dispositivos Inactivos usando un ciclo for
@app.route('/api/inactivos')
def obtener_inactivos():
    inactivos = {}
    for key, value in dispositivos.items():
        if value["status"] == "Inactivo":
            inactivos[key] = value
    return jsonify(inactivos)

# 4. Obtener solo los nombres de todos los dispositivos
@app.route('/api/nombres')
def obtener_nombres():
    nombres = []
    for value in dispositivos.values():
        nombres.append(value["device_name"])
    return jsonify({"nombres_dispositivos": nombres})

# 5. Buscar un dispositivo por su IP exacta
@app.route('/api/buscar_ip/<ip_buscada>')
def buscar_por_ip(ip_buscada):
    for key, value in dispositivos.items():
        if value["ip"] == ip_buscada:
            return jsonify({key: value})
    return jsonify({"mensaje": "IP no encontrada"})

# 6. Cambiar el estado de un dispositivo específico
@app.route('/api/cambiar_estado/<int:id_disp>/<nuevo_estado>')
def cambiar_estado(id_disp, nuevo_estado):
    if id_disp in dispositivos:
        dispositivos[id_disp]["status"] = nuevo_estado
        return jsonify({"mensaje": "Estado actualizado", "dispositivo": dispositivos[id_disp]})
    return jsonify({"error": "Dispositivo no encontrado"})

# 7. Cambiar TODOS los dispositivos a "Inactivo" usando un ciclo
@app.route('/api/apagar_todos')
def apagar_todos():
    for key in dispositivos:
        dispositivos[key]["status"] = "Inactivo"
    return jsonify({"mensaje": "Todos los dispositivos han sido apagados", "datos": dispositivos})

# 8. Cambiar TODOS los dispositivos a "Activo" usando un ciclo
@app.route('/api/encender_todos')
def encender_todos():
    for key in dispositivos:
        dispositivos[key]["status"] = "Activo"
    return jsonify({"mensaje": "Todos los dispositivos han sido encendidos", "datos": dispositivos})

# 9. Obtener una lista de todos los tipos de políticas de seguridad
@app.route('/api/politicas')
def obtener_politicas():
    politicas = []
    for value in dispositivos.values():
        tipo = value["policy"]["type"]
        if tipo not in politicas: # Evitar duplicados
            politicas.append(tipo)
    return jsonify({"tipos_de_politicas": politicas})

# 10. Actualizar la IP de un dispositivo específico
@app.route('/api/cambiar_ip/<int:id_disp>/<nueva_ip>')
def cambiar_ip(id_disp, nueva_ip):
    if id_disp in dispositivos:
        dispositivos[id_disp]["ip"] = nueva_ip
        return jsonify({"mensaje": "IP actualizada exitosamente", "dispositivo": dispositivos[id_disp]})
    return jsonify({"error": "Dispositivo no encontrado"})


# --- 1 FUNCIÓN PARA AGREGAR A UNA LISTA ---

# Agregar un nuevo nombre a la lista global 'registro_nombres'
@app.route('/api/lista/agregar/<nuevo_nombre>')
def agregar_a_lista(nuevo_nombre):
    registro_nombres.append(nuevo_nombre)
    return jsonify({
        "mensaje": "Elemento agregado a la lista", 
        "lista_actualizada": registro_nombres
    })

if __name__ == '__main__':
    app.run(debug=True)