from flask import Flask, request, Response
import json

app = Flask(__name__)

# Base de datos simulada (Configuración de la interfaz)
network_config = {
    "ietf-interfaces:interfaces": {
        "interface": [
            {
                "name": "GigabitEthernet1",
                "description": "Enlace Principal",
                "type": "iana-if-type:ethernetCsmacd",
                "enabled": True,
                "ietf-ip:ipv4": {
                    "address": [
                        {
                            "ip": "192.168.1.1",
                            "netmask": "255.255.255.0"
                        }
                    ]
                }
            }
        ]
    }
}

# =====================================================================
# SIMULACIÓN RESTCONF (Usa HTTP estándar + JSON/YANG)
# =====================================================================
@app.route('/restconf/data/ietf-interfaces:interfaces', methods=['GET'])
def get_restconf():
    # Devuelve la configuración en formato JSON (Media Type de RESTCONF)
    return Response(
        json.dumps(network_config), 
        status=200, 
        mimetype='application/yang-data+json'
    )

@app.route('/restconf/data/ietf-interfaces:interfaces', methods=['PUT'])
def put_restconf():
    global network_config
    if not request.is_json:
        return Response('{"error": "Debe ser JSON"}', status=400, mimetype='application/yang-data+json')
    
    # Actualiza la configuración
    network_config = request.get_json()
    return Response(status=204)


# =====================================================================
# SIMULACIÓN NETCONF (Expuesta vía HTTP para pruebas en Postman)
# =====================================================================
@app.route('/netconf/rpc', methods=['POST'])
def netconf_rpc():
    xml_data = request.data.decode('utf-8')
    
    # Validar si es una solicitud <get-config>
    if "<get-config>" in xml_data:
        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<rpc-reply message-id="101" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <data>
    <interfaces xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces">
      <interface>
        <name>GigabitEthernet1</name>
        <enabled>true</enabled>
      </interface>
    </interfaces>
  </data>
</rpc-reply>"""
        return Response(xml_response, status=200, mimetype='application/xml')
    
    # Validar si es una solicitud <edit-config>
    elif "<edit-config>" in xml_data:
        xml_response = """<?xml version="1.0" encoding="UTF-8"?>
<rpc-reply message-id="102" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <ok/>
</rpc-reply>"""
        return Response(xml_response, status=200, mimetype='application/xml')
    
    # Respuesta por defecto si no se reconoce el RPC
    error_response = """<?xml version="1.0" encoding="UTF-8"?>
<rpc-reply message-id="100" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <rpc-error>
    <error-type>application</error-type>
    <error-tag>operation-not-supported</error-tag>
    <error-severity>error</error-severity>
  </rpc-error>
</rpc-reply>"""
    return Response(error_response, status=400, mimetype='application/xml')

if __name__ == '__main__':
    # Corre el servidor en el puerto 5000
    app.run(debug=True, port=5000)







"""


Pruebas de RESTCONF

• Obtener configuración (GET):
	• Método: GET
	• URL: http://127.0.0
	• Headers: Agrega la llave Accept con el valor application/yang-data+json.
	• Resultado esperado: Código 200 OK y el JSON con los datos de GigabitEthernet1.
• Modificar configuración (PUT):
	• Método: PUT
	• URL: http://127.0.0
	• Body: Selecciona raw -> JSON y pega un cuerpo modificado, por ejemplo cambiando "enabled": False.
	• Resultado esperado: Código 204 No Content.

Pruebas de NETCONF (Simulado en HTTP)

• Enviar RPC  (POST):
	• Método: POST
	• URL: http://127.0.0
	• Body: Selecciona raw -> XML y pega la estructura RPC:
xml
<rpc message-id="101" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <get-config>
    <source><running/></source>
  </get-config>
</rpc>


• Resultado esperado: Código 200 OK con la respuesta XML conteniendo <rpc-reply> y los tags de la interfaz.
• Enviar RPC  (POST):
	• Método: POST
	• URL: http://127.0.0
	• Body: Selecciona raw -> XML y usa:
xml
<rpc message-id="102" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">
  <edit-config>
    <target><running/></target>
    <config>
      <!-- Cambios aquí -->
    </config>
  </edit-config>
</rpc>

• Resultado esperado: Código 200 OK junto con la etiqueta <ok/>.






¿Qué es NETCONF y RESTCONF?

Ambos son protocolos de gestión de redes estandarizados por la IETF. Nacieron para reemplazar a la vieja e insegura CLI (línea de comandos tradicional) y a SNMP, permitiendo automatizar la configuración de routers, switches y firewalls de forma programática.
Para entenderlos de forma sencilla, funcionan bajo un modelo de tres capas:
1. El "Idioma" (Modelo de datos): Ambos utilizan un lenguaje llamado YANG para definir exactamente qué se puede configurar en el equipo (direcciones IP, VLANs, etc.).
2. El "Formato" (Estructura): Cómo se empaquetan los datos (XML o JSON).
3. El "Transporte" (Protocolo): El canal por el que viajan los datos (SSH o HTTP).

Direct Comparación: NETCONF vs. RESTCONF

Característica	NETCONF (RFC 6241)	RESTCONF (RFC 8040)
Protocolo Base	SSH (Subsistema seguro dedicado)	HTTP/S (REST)
Formato de Datos	Estrictamente XML	JSON o XML
Operaciones	Bloques de código RPC (<get-config>, <edit-config>)	Métodos estándar HTTP (GET, POST, PUT, DELETE)
Complejidad	Alta. Diseñado para transacciones robustas y seguras.	Baja. Diseñado para ser amigable con desarrolladores web.
Transacciones	Soporta estados (candidate, running, startup) y rollbacks.	No tiene estados complejos. La petición se ejecuta de inmediato.

Usos Reales en la Industria

En el mundo de las telecomunicaciones y la infraestructura IT, estos protocolos son la columna vertebral de la Programabilidad de Redes (Network Programmability):
• Orquestadores y SDN (Redes Definidas por Software): Plataformas de software (como Cisco DNA Center, Nokia NSP o la herramienta de código abierto OpenDaylight) utilizan NETCONF para conectarse a miles de routers en segundos. Si un operador necesita crear 500 circuitos de datos, el software envía los RPCs en lote, asegurando que si un equipo falla, toda la transacción se cancele (rollback).
• Automatización con Ansible o Python: En lugar de crear scripts de Python que "escriban" comandos en la consola (lo cual es propenso a errores si el prompt cambia), los ingenieros usan librerías como ncclient (para NETCONF) o llamadas requests (para RESTCONF). Esto permite tratar a la red como si fuera software (Infrastructure as Code).
• Monitoreo y Telemetría: Se utilizan para suscribirse a flujos de datos en tiempo real. El switch "avisa" de forma proactiva cuando una interfaz se cae, en lugar de que el sistema de monitoreo le esté preguntando cada 5 minutos.

¿Cuándo se usa cuál?

• NETCONF es el preferido para el núcleo de la red (Core) y por grandes proveedores de internet (Telcos), donde la seguridad transaccional absoluta y la gestión de configuraciones masivas son críticas.
• RESTCONF se utiliza habitualmente en entornos donde los ingenieros de software o herramientas web necesitan interactuar de forma rápida con la red, ya que cualquier programador sabe cómo hacer un GET o un POST desde una app web o desde Postman.

Mostrando netconfi-restconfig.txt.
"""