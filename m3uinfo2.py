#TOKEN = '7876126426:AAHxxF9HT6zZKv_rxlsiz6VAdcOc5HeEgog'
import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
import re
import socket
from datetime import datetime

# Configuración del bot
TOKEN = '7876126426:AAHxxF9HT6zZKv_rxlsiz6VAdcOc5HeEgog'

# Configuración del logging para depuración
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Función para registrar actividad en un archivo de texto con codificación UTF-8
def registrar_uso(usuario, mensaje):
    with open("registro_uso.txt", "a", encoding="utf-8") as archivo:  # Especificamos la codificación
        archivo.write(f"{datetime.now()} - Usuario: {usuario} - Mensaje: {mensaje}\n")

# Función para manejar el comando /start
async def start(update: Update, context):
    user = update.message.from_user  # Obtener el usuario que envía el mensaje
    user_name = user.full_name if user.full_name else user.username  # Usar el nombre completo o el username
    await update.message.reply_text(f'¡Hola, {user_name}! Envíame una URL M3U para analizar.')

    # Registrar actividad del usuario
    registrar_uso(user_name, "/start")

# Función para procesar la URL M3U y obtener la información del servidor y contenido
def procesar_m3u(url):
    try:
        # Verificamos si la URL está online
        url_online = verificar_url_online(url)

        # Realizamos una solicitud a la URL M3U solo si está online
        if url_online:
            response = requests.get(url)
            if response.status_code == 200:
                print("Servidor: ON_LINE")
                
                # Extraer el username, password y el puerto desde la URL M3U
                parametros = dict(re.findall(r'(\w+)=(\w+)', url.split('?')[-1]))
                username = parametros.get('username', 'Desconocido')
                password = parametros.get('password', 'Desconocido')
                port = url.split('/')[2].split(':')[1] if ':' in url.split('/')[2] else 'Desconocido'

                # Extraer la URL base (Host) incluyendo el protocolo, dominio y puerto
                host_url = url.split('?')[0]  # Extrae la parte de la URL hasta el puerto, sin parámetros
                
                # Cambiamos 'get.php' por 'player_api.php' en la URL para obtener información adicional del servidor
                payload_url = re.sub(r'get\.php', 'player_api.php', url)
                server_response = requests.get(payload_url)

                if server_response.status_code == 200:
                    # Buscamos la información en la respuesta JSON del servidor
                    message_match = re.search(r'"message":"(.*?)"', server_response.text)
                    timezone_match = re.search(r'"timezone":"(.*?)"', server_response.text)
                    active_cons_match = re.search(r'"active_cons":"(.*?)"', server_response.text)
                    max_connections_match = re.search(r'"max_connections":"(.*?)"', server_response.text)
                    expiration_date_match = re.search(r'"exp_date":"(.*?)"', server_response.text)

                    # Extraemos y asignamos valores por defecto si no se encuentran
                    message = message_match.group(1) if message_match else "Desconocido"
                    timezone = timezone_match.group(1).replace("\\/", "/") if timezone_match else "Desconocido"
                    active_cons = active_cons_match.group(1) if active_cons_match else "Desconocido"
                    max_connections = max_connections_match.group(1) if max_connections_match else "Desconocido"

                    # Convertir la fecha de expiración (timestamp Unix) a un formato legible
                    if expiration_date_match:
                        expiration_value = expiration_date_match.group(1)
                        if expiration_value == "0":  # Valor 0 puede significar "𝐔𝐧𝐥𝐢𝐦𝐢𝐭𝐞𝐝"
                            expiration_date = "𝐔𝐧𝐥𝐢𝐦𝐢𝐭𝐞𝐝"
                        else:
                            expiration_timestamp = int(expiration_value)
                            expiration_date = datetime.utcfromtimestamp(expiration_timestamp).strftime('%d/%m/%Y %H:%M:%S')
                    else:
                        expiration_date = "𝐔𝐧𝐥𝐢𝐦𝐢𝐭𝐞𝐝"

                    # Extraemos la IP del servidor a partir del dominio de la URL
                    domain = url.split('/')[2].split(':')[0]  # Solo obtenemos el dominio, sin el puerto
                    try:
                        # Verificar si el dominio es correcto
                        print(f"Intentando obtener la IP para el dominio: {domain}")
                        ip = socket.gethostbyname(domain)
                    except socket.gaierror as e:
                        print(f"Error al intentar resolver la IP para el dominio {domain}: {e}")
                        ip = "No disponible"

                    # Extraemos canales, películas y series del archivo M3U
                    canales, peliculas, series = extraer_contenido_m3u(response.text)

                    # Retornamos la información extraída
                    return {
                        "url_online": url_online,
                        "message": message,
                        "timezone": timezone,
                        "active_cons": active_cons,
                        "max_connections": max_connections,
                        "expiration_date": expiration_date,
                        "ip": ip,
                        "username": username,
                        "password": password,
                        "port": port,
                        "m3u_url": url,
                        "host_url": host_url,
                        "canales": canales,
                        "peliculas": peliculas,
                        "series": series
                    }
                else:
                    return {"error": "No se pudo recuperar la información de la API del Player."}
            else:
                return {"error": f"Link M3U no funcional: {url}"}
        else:
            return {"error": f"La URL {url} está OFFLINE"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Error al realizar la solicitud HTTP: {e}"}

# Función para verificar si la URL está online
def verificar_url_online(url):
    try:
        response = requests.head(url, timeout=5)
        return response.status_code in [200, 301, 302]
    except requests.ConnectionError:
        return False

# Función para extraer los canales, películas y series de la respuesta M3U
def extraer_contenido_m3u(contenido):
    canales = []
    peliculas = []
    series = []

    lineas = contenido.splitlines()
    for linea in lineas:
        if '#EXTINF' in linea:
            nombre = linea.split(',')[-1].strip()

            if 'CANAL' in nombre.upper() or 'TV' in nombre.upper():
                canales.append(nombre)
            elif 'MOVIE' in nombre.upper() or 'PELÍCULA' in nombre.upper():
                peliculas.append(nombre)
            elif 'SERIE' in nombre.upper() or 'EPISODE' in nombre.upper():
                series.append(nombre)

    return canales, peliculas, series

# Función para generar la respuesta del bot
def generar_respuesta(info, user_name):
    if "error" in info:
        return f"❗️ {info['error']}"

    num_canales = len(info['canales'])
    num_peliculas = len(info['peliculas'])
    num_series = len(info['series'])

    casados = f"{info['username']}💍{info['password']}"
    estado_url = "ONLINE 🟢" if info['url_online'] else "OFFLINE 🔴"

    respuesta = (
        f"✅ 𝙄𝙉𝙁𝙊𝙍𝙈𝘼𝘾𝙄𝙊𝙉 𝘿𝙀𝙇 𝙎𝙀𝙍𝙑𝙄𝘿𝙊𝙍 𝙄𝙋𝙏𝙑\n   𝙋𝘼𝙍𝘼 𝙀𝙇 𝙐𝙎𝙐𝘼𝙍𝙄𝙊 👉 @{user_name}🤪\n\n"
        f"🌍 Mᴇɴsᴀᴊᴇ ➥ {info['message']}\n"
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"🙎‍♂️ Usᴜᴀʀɪᴏ ➥ {info['username']}\n"
        f"🔐 Cᴏɴᴛʀᴀsᴇñᴀ ➥ {info['password']}\n"
        f"👩‍❤️‍👨 Cᴀsᴀᴅᴏs ➥  {casados}\n"
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"👨 Cᴏɴᴇxɪᴏɴᴇs Aᴄᴛɪᴠᴀs ➥ {info['active_cons']}\n"
        f"👨‍👩‍👦 Máxɪᴍᴀs Cᴏɴᴇxɪᴏɴᴇs ➥ {info['max_connections']}\n"
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"🕒 Zᴏɴᴀ Hᴏʀᴀʀɪᴀ ➥ {info['timezone']}\n"
        f"🗓 Fᴇᴄʜᴀ ᴅᴇ Exᴘɪʀᴀᴄɪóɴ ➥ {info['expiration_date']}\n"
        f"🌐 Dᴏᴍɪɴɪᴏ:⮕ {info['host_url']}\n"  # Añadimos el Host
        f"⚙️ Pᴜᴇʀᴛᴏ ➥ {info['port']}\n"
        f"🌐 IP ᴅᴇʟ sᴇʀᴠɪᴅᴏʀ ➥ {info['ip']}\n"
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
        f"🔗 M3U Oɴʟɪɴᴇ ➥ {estado_url}\n"
        f"🔎 M3U Lɪɴᴋ ➥ <a href='{info['m3u_url']}'>Click aquí</a> ✅\n"
        "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬"
        f"\n"
        f"📺 Total de Canales ➥ {num_canales}\n"
        f"🎬 Total de Películas ➥ {num_peliculas}\n"
        f"🎥 Total de Series ➥ {num_series}\n"
        f"▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬'\n"
    )

    # Añadimos una muestra de canales, películas y series si están disponibles
    if info['canales']:
        respuesta += "\n📺 𝘾𝘼𝙉𝘼𝙇𝙀𝙎 ➥\n" + "\n".join(info['canales'][:20]) + ('...' if len(info['canales']) > 20 else '') + "\n\n"
    if info['peliculas']:
        respuesta += "🎬 𝙋𝙀𝙇𝙄𝘾𝙐𝙇𝘼𝙎 ➥\n" + "\n".join(info['peliculas'][:10]) + ('...' if len(info['peliculas']) > 10 else '') + "\n\n"
    if info['series']:
        respuesta += "🎥 𝙎𝙀𝙍𝙄𝙀𝙎 ➥\n" + "\n".join(info['series'][:10]) + ('...' if len(info['series']) > 10 else '') + "\n\n"
     # Añadimos la leyenda al final
    respuesta += "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
    respuesta += "🔖 by @m3uinfobot"       
    return respuesta

# Función que maneja los mensajes que contienen URLs
async def handle_message(update: Update, context):
    text = update.message.text
    user = update.message.from_user  # Obtener el usuario que envía el mensaje
    user_name = user.full_name if user.full_name else user.username  # Usar el nombre completo o el username

    # Registrar actividad del usuario
    registrar_uso(user_name, text)

    if text.startswith('http') and 'm3u' in text:
        await update.message.reply_text(f'Analizando la URL M3U para 👉 {user_name} ...')
        
        # Procesamos la URL y generamos la respuesta
        info = procesar_m3u(text)
        respuesta = generar_respuesta(info, user_name)
        
        await update.message.reply_text(respuesta, parse_mode='HTML')
    else:
        await update.message.reply_text('Por favor, envíame una URL válida que contenga M3U.')

# Función principal para inicializar el bot
def main():
    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler('start', start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()
