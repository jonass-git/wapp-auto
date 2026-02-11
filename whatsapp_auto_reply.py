"""
WhatsApp Auto Reply Bot
=======================
Script que automatiza respuestas en WhatsApp Web utilizando Selenium
y la Gemini CLI instalada en el sistema.

Flujo:
1. Abre Chrome con un perfil persistente (para mantener la sesión del QR).
2. Espera a que el usuario escanee el código QR (solo la primera vez).
3. Monitorea la lista de chats buscando indicadores de "mensaje nuevo".
4. Al detectar uno, abre el chat, lee el último mensaje entrante.
5. Usa `subprocess` para invocar la Gemini CLI y generar una respuesta.
6. Escribe y envía la respuesta en el chat de WhatsApp.
7. Vuelve al paso 3.

Autor: Auto-generado
Fecha: 2026-02-10
"""

import os
import sys
import time
import logging
import subprocess
import re
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
    ElementClickInterceptedException,
)
from webdriver_manager.chrome import ChromeDriverManager

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────

# Ruta donde se guarda el perfil de Chrome para mantener la sesión de WhatsApp.
# Cámbiala si prefieres otra ubicación.
CHROME_PROFILE_DIR = str(Path(__file__).parent / "chrome_profile")

# Tiempo máximo (segundos) que el script espera a que cargue un elemento del DOM.
DEFAULT_WAIT = 20

# Intervalo (segundos) entre cada ciclo de monitoreo de mensajes nuevos.
POLL_INTERVAL = 5

# Timeout (segundos) para la ejecución de la Gemini CLI.
GEMINI_TIMEOUT = 60

# ─────────────────────────────────────────────────────────────────────────────
# SELECTORES
# ─────────────────────────────────────────────────────────────────────────────
# Centralizados aquí para facilitar el mantenimiento.
# WhatsApp Web cambia sus clases frecuentemente; los atributos como
# `data-testid`, `aria-label` y `role` suelen ser más estables.
#
# ESTRATEGIA DE SELECTORES (por prioridad):
#   1. data-testid  →  más estable, puesto por los desarrolladores de WhatsApp
#   2. aria-label / role  →  accesibilidad, cambian menos
#   3. Estructura DOM genérica  →  fallback de último recurso
#
# Si algún selector deja de funcionar, actualízalo aquí sin tocar la lógica.
# ─────────────────────────────────────────────────────────────────────────────

SELECTORS = {
    # ── PANEL LATERAL (indica que WhatsApp cargó tras el QR) ──

    # Opción 1: el div#side que contiene toda la barra lateral.
    "side_panel": (By.ID, "side"),
    # Opción 2: la lista de chats con data-testid.
    "side_panel_alt": (By.CSS_SELECTOR, 'div[data-testid="chat-list"]'),
    # Opción 3: el contenedor de la app con role="application".
    "side_panel_alt2": (By.CSS_SELECTOR, 'div[role="application"]'),

    # ── BADGES DE MENSAJES NO LEÍDOS ──

    # Opción 1: span con data-testid para el ícono de conteo.
    "unread_badge": (By.CSS_SELECTOR, 'span[data-testid="icon-unread-count"]'),
    # Opción 2: span con aria-label que contenga "no leído" o "unread".
    "unread_badge_alt": (
        By.XPATH,
        '//span[contains(@aria-label, "no le") or contains(@aria-label, "unread") '
        'or contains(@aria-label, "sin leer")]',
    ),

    # ── FILA DE CHAT (contenedor clicable) ──

    # Opción 1: ancestor con data-testid="cell-frame-container".
    "chat_row": (
        By.XPATH,
        './/ancestor::div[@data-testid="cell-frame-container"]',
    ),
    # Opción 2: ancestor con role="listitem" (WAWeb usa listas accesibles).
    "chat_row_alt": (
        By.XPATH,
        './/ancestor::div[@role="listitem"]',
    ),
    # Opción 3: ancestor con role="row" o role="option".
    "chat_row_alt2": (
        By.XPATH,
        './/ancestor::div[@role="row" or @role="option"]',
    ),

    # ── PANEL DE CONVERSACIÓN ──

    "message_panel": (
        By.CSS_SELECTOR,
        'div[data-testid="conversation-panel-messages"]',
    ),
    "message_panel_alt": (
        By.CSS_SELECTOR,
        'div[role="application"] div[role="row"]',
    ),

    # ── TEXTO DE MENSAJES ENTRANTES ──
    #
    # Los mensajes entrantes tienen la clase "message-in" en un div padre.
    # El texto está dentro de un <span> con clase "selectable-text".
    # NOTA: NO usamos clases con prefijo _ (ej: _ao3e) porque cambian.

    "incoming_msg_text": (
        By.CSS_SELECTOR,
        'div.message-in span.selectable-text span',
    ),
    # Fallback: buscar por copyable-text (otra clase estable).
    "incoming_msg_text_alt": (
        By.CSS_SELECTOR,
        'div.message-in span.copyable-text span.selectable-text span',
    ),
    # Fallback 2: buscar cualquier span con dir="ltr" dentro de message-in.
    "incoming_msg_text_alt2": (
        By.XPATH,
        '//div[contains(@class, "message-in")]//div[@data-testid="msg-container"]//span[@dir="ltr"]',
    ),

    # ── NOMBRE DEL CONTACTO EN LA CABECERA ──

    "contact_header": (
        By.CSS_SELECTOR,
        'header span[data-testid="conversation-info-header-chat-title"] span',
    ),
    "contact_header_alt": (
        By.CSS_SELECTOR,
        'header div[data-testid="conversation-title"] span',
    ),
    # Fallback: cualquier span con title dentro del header.
    "contact_header_alt2": (
        By.CSS_SELECTOR,
        'header span[title]',
    ),

    # ── CAJA DE TEXTO PARA ESCRIBIR ──

    "message_input": (
        By.CSS_SELECTOR,
        'div[data-testid="conversation-compose-box-input"] div[contenteditable="true"]',
    ),
    "message_input_alt": (
        By.CSS_SELECTOR,
        'footer div[contenteditable="true"][role="textbox"]',
    ),
    "message_input_alt2": (
        By.CSS_SELECTOR,
        'footer div[contenteditable="true"]',
    ),
    # Fallback: buscar por data-tab (suele ser "10" para la caja de mensaje).
    "message_input_alt3": (
        By.XPATH,
        '//div[@contenteditable="true"][@data-tab="10"]',
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("whatsapp-bot")


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES AUXILIARES DE SELECTORES
# ─────────────────────────────────────────────────────────────────────────────


def _try_find_element(driver_or_element, *selector_keys: str):
    """
    Intenta encontrar un elemento usando múltiples selectores en orden.
    Retorna el primer elemento encontrado o None si ninguno funciona.
    """
    for key in selector_keys:
        try:
            by, value = SELECTORS[key]
            el = driver_or_element.find_element(by, value)
            if el:
                return el
        except (NoSuchElementException, KeyError, StaleElementReferenceException):
            continue
    return None


def _try_find_elements(driver_or_element, *selector_keys: str) -> list:
    """
    Intenta encontrar múltiples elementos usando múltiples selectores en orden.
    Retorna la primera lista no vacía o una lista vacía.
    """
    for key in selector_keys:
        try:
            by, value = SELECTORS[key]
            elements = driver_or_element.find_elements(by, value)
            if elements:
                return elements
        except (NoSuchElementException, KeyError, StaleElementReferenceException):
            continue
    return []


def _wait_for_any(driver, timeout, *selector_keys: str):
    """
    Espera hasta que cualquiera de los selectores dados esté presente en el DOM.
    Retorna el primer elemento encontrado.
    """
    end_time = time.time() + timeout
    while time.time() < end_time:
        el = _try_find_element(driver, *selector_keys)
        if el:
            return el
        time.sleep(0.5)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES PRINCIPALES
# ─────────────────────────────────────────────────────────────────────────────


def setup_driver() -> webdriver.Chrome:
    """
    Configura e inicializa el navegador Chrome con un perfil persistente.

    Se usa `webdriver_manager` para descargar/gestionar ChromeDriver
    automáticamente, sin necesidad de descargarlo manualmente.

    El perfil persistente permite que la sesión de WhatsApp Web se mantenga
    entre ejecuciones, evitando tener que escanear el QR cada vez.
    """
    chrome_options = Options()

    # Perfil persistente: guarda cookies, Local Storage, etc.
    chrome_options.add_argument(f"--user-data-dir={CHROME_PROFILE_DIR}")

    # Evitar la detección de automatización (reduce probabilidad de bloqueo).
    chrome_options.add_argument(
        "--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option(
        "excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # Desactivar notificaciones del navegador para no interferir.
    chrome_options.add_argument("--disable-notifications")

    # Iniciar maximizado para que los elementos sean visibles.
    chrome_options.add_argument("--start-maximized")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    # Ocultar la propiedad navigator.webdriver que delata automatización.
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )

    log.info("Chrome iniciado correctamente.")
    return driver


def wait_for_login(driver: webdriver.Chrome) -> None:
    """
    Espera a que el usuario escanee el código QR y la sesión se cargue.

    Busca el panel lateral que aparece cuando WhatsApp Web está listo.
    Si es la primera ejecución, el usuario debe escanear el QR manualmente.
    Intenta múltiples selectores para mayor robustez.
    """
    log.info("Abriendo WhatsApp Web...")
    driver.get("https://web.whatsapp.com")

    log.info("Esperando inicio de sesion (escanea el QR si es necesario)...")

    # Esperar hasta 120 segundos intentando múltiples selectores.
    panel = _wait_for_any(
        driver, 120,
        "side_panel", "side_panel_alt", "side_panel_alt2",
    )

    if panel:
        log.info("Sesion iniciada. WhatsApp Web cargado correctamente.")
    else:
        log.error("Timeout esperando el inicio de sesion. Escaneaste el QR?")
        raise SystemExit(1)


def find_new_messages(driver: webdriver.Chrome) -> list:
    """
    Busca chats con mensajes no leídos en el panel lateral.

    Detecta los badges de notificación (círculo verde con número) y devuelve
    una lista de elementos clicables (las filas de chat con notificaciones).
    """
    try:
        # Buscar badges con múltiples selectores.
        badges = _try_find_elements(driver, "unread_badge", "unread_badge_alt")

        if not badges:
            return []

        chat_rows = []
        for badge in badges:
            try:
                # Intentar localizar la fila del chat navegando hacia arriba.
                chat_row = _try_find_element(
                    badge,
                    "chat_row", "chat_row_alt", "chat_row_alt2",
                )

                if chat_row:
                    chat_rows.append(chat_row)
                else:
                    # Último recurso: subir N niveles en el DOM con JavaScript.
                    try:
                        chat_row = driver.execute_script(
                            """
                            let el = arguments[0];
                            for (let i = 0; i < 10; i++) {
                                el = el.parentElement;
                                if (!el) return null;
                                if (el.getAttribute('data-testid') === 'cell-frame-container') return el;
                                if (el.getAttribute('role') === 'listitem') return el;
                                if (el.getAttribute('role') === 'row') return el;
                                if (el.getAttribute('role') === 'option') return el;
                            }
                            return null;
                            """,
                            badge,
                        )
                        if chat_row:
                            chat_rows.append(chat_row)
                        else:
                            log.warning(
                                "Badge encontrado pero no se pudo localizar su chat.")
                    except Exception:
                        log.warning(
                            "Badge encontrado pero no se pudo localizar su chat (JS).")

            except StaleElementReferenceException:
                continue
            except Exception as e:
                log.debug(f"Error navegando al chat del badge: {e}")
                continue

        if chat_rows:
            log.info(
                f"{len(chat_rows)} chat(s) con mensajes nuevos detectado(s).")

        return chat_rows

    except StaleElementReferenceException:
        return []
    except Exception as e:
        log.debug(f"Error buscando mensajes nuevos: {e}")
        return []


def read_last_message(driver: webdriver.Chrome) -> str | None:
    """
    Lee el texto del último mensaje entrante en el chat actualmente abierto.

    Busca todas las burbujas de mensajes entrantes (message-in) y toma la
    última para obtener el texto más reciente.
    """
    try:
        # Esperar a que el panel de conversación cargue (con fallback).
        panel = _wait_for_any(
            driver, DEFAULT_WAIT,
            "message_panel", "message_panel_alt",
        )

        if not panel:
            log.warning("Timeout esperando el panel de conversacion.")
            return None

        # Breve pausa para que los mensajes terminen de renderizarse.
        time.sleep(1.5)

        # Buscar los textos de los mensajes entrantes con múltiples selectores.
        messages = _try_find_elements(
            driver,
            "incoming_msg_text",
            "incoming_msg_text_alt",
            "incoming_msg_text_alt2",
        )

        if not messages:
            log.warning("No se encontraron mensajes entrantes de texto.")
            return None

        # Tomar el último mensaje (el más reciente).
        last_msg = messages[-1]
        text = last_msg.text.strip()

        if text:
            preview = text[:80] + ("..." if len(text) > 80 else "")
            log.info(f'Ultimo mensaje recibido: "{preview}"')
            return text
        else:
            log.warning(
                "El ultimo mensaje esta vacio (puede ser imagen/audio/sticker).")
            return None

    except StaleElementReferenceException:
        log.warning("El DOM cambio al leer mensajes. Se reintentara.")
        return None
    except Exception as e:
        log.error(f"Error leyendo el ultimo mensaje: {e}")
        return None


def get_contact_name(driver: webdriver.Chrome) -> str:
    """
    Obtiene el nombre del contacto desde la cabecera del chat abierto.

    Retorna 'Contacto' como valor por defecto si no lo encuentra.
    """
    element = _try_find_element(
        driver,
        "contact_header", "contact_header_alt", "contact_header_alt2",
    )
    if element:
        try:
            name = element.text.strip() or element.get_attribute("title") or ""
            if name:
                return name
        except StaleElementReferenceException:
            pass
    return "Contacto"


def generate_reply(contact_name: str, message: str) -> str | None:
    """
    Genera una respuesta automática usando la Gemini CLI.

    ╔══════════════════════════════════════════════════════════════════════════╗
    ║  INTEGRACIÓN CON GEMINI CLI vía subprocess                            ║
    ╠══════════════════════════════════════════════════════════════════════════╣
    ║                                                                        ║
    ║  Se usa `subprocess.run()` para ejecutar el comando `gemini` con el   ║
    ║  flag `--prompt` (o `-p`) para modo NO INTERACTIVO.                   ║
    ║                                                                        ║
    ║  SIN --prompt, gemini abre un chat interactivo que NUNCA termina,     ║
    ║  causando timeout. CON --prompt, ejecuta la consulta y sale.          ║
    ║                                                                        ║
    ║  - `capture_output=True`:  captura stdout y stderr para leer la       ║
    ║    respuesta generada por Gemini.                                      ║
    ║                                                                        ║
    ║  - `text=True`:  decodifica la salida como texto (str) en vez de      ║
    ║    bytes.                                                              ║
    ║                                                                        ║
    ║  - `timeout=GEMINI_TIMEOUT`:  evita que el script se quede colgado    ║
    ║    si la CLI no responde (por ej. sin conexión a internet).            ║
    ║                                                                        ║
    ║  - `shell=True`:  necesario en Windows para que encuentre el comando  ║
    ║    `gemini` en el PATH del sistema.                                    ║
    ║                                                                        ║
    ╚══════════════════════════════════════════════════════════════════════════╝

    Args:
        contact_name: nombre del contacto que envió el mensaje.
        message: texto del mensaje recibido.

    Returns:
        str con la respuesta generada, o None si hubo un error.
    """
    # Sanitizar el mensaje: eliminar caracteres que puedan romper el comando.
    safe_message = re.sub(r'["\'\n\r\\`$!]', " ", message).strip()
    safe_name = re.sub(r'["\'\n\r\\`$!]', " ", contact_name).strip()

    # Construir el prompt para Gemini.
    prompt = (
        f"El usuario {safe_name} me escribio: {safe_message}. "
        f"Estoy ocupado programando. "
        f"Genera una respuesta corta, amable y profesional diciendo que "
        f"respondere en breve. Solo devuelve el texto de la respuesta, "
        f"sin comillas, sin explicaciones adicionales, sin formato markdown."
    )

    # ═══════════════════════════════════════════════════════════════════════
    # IMPORTANTE: Usamos `gemini -p "prompt"` (flag --prompt / -p)
    # para ejecutar en MODO NO INTERACTIVO.
    #
    # Sin este flag, `gemini` abre un chat interactivo que nunca termina,
    # y subprocess.run() esperaría infinitamente (hasta el timeout).
    #
    # Con `-p`, Gemini procesa el prompt, imprime la respuesta y sale.
    # ═══════════════════════════════════════════════════════════════════════
    command = f'gemini -p "{prompt}"'

    log.info(f"Generando respuesta con Gemini CLI para {contact_name}...")

    try:
        # ═══════════════════════════════════════════════════════════════════
        # subprocess.run() ejecuta el comando en un proceso separado.
        #
        # - capture_output=True  →  equivale a stdout=PIPE, stderr=PIPE.
        #   Esto permite leer lo que Gemini imprime en la terminal.
        #
        # - text=True  →  la salida se devuelve como str (no bytes).
        #
        # - timeout  →  si Gemini CLI tarda más de GEMINI_TIMEOUT segundos,
        #   se lanza subprocess.TimeoutExpired y se maneja abajo.
        #
        # - shell=True  →  ejecuta el comando a través del shell del sistema.
        #   Necesario en Windows para resolver el PATH correctamente.
        # ═══════════════════════════════════════════════════════════════════
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=GEMINI_TIMEOUT,
            shell=True,
            encoding="utf-8",
        )

        # Verificar que el comando se ejecutó correctamente (código de retorno 0).
        if result.returncode != 0:
            log.error(f"Gemini CLI retorno codigo {result.returncode}.")
            if result.stderr:
                log.error(f"   stderr: {result.stderr.strip()[:200]}")
            return None

        # Extraer y limpiar la respuesta de stdout.
        # Eliminar posibles secuencias de escape ANSI que la CLI pueda emitir.
        raw_reply = result.stdout.strip()
        # Quitar códigos ANSI (colores, negrita, etc.).
        reply = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', raw_reply).strip()

        if not reply:
            log.warning("Gemini CLI no devolvio respuesta (stdout vacio).")
            if result.stderr:
                log.debug(f"stderr: {result.stderr.strip()[:200]}")
            return None

        preview = reply[:100] + ("..." if len(reply) > 100 else "")
        log.info(f'Respuesta generada: "{preview}"')
        return reply

    except subprocess.TimeoutExpired:
        log.error(
            f"Gemini CLI excedio el timeout de {GEMINI_TIMEOUT}s. Saltando.")
        return None

    except FileNotFoundError:
        log.error(
            "No se encontro el comando 'gemini'. "
            "Asegurate de que la Gemini CLI este instalada y en el PATH."
        )
        return None

    except Exception as e:
        log.error(f"Error inesperado al ejecutar Gemini CLI: {e}")
        return None


def send_reply(driver: webdriver.Chrome, reply_text: str) -> bool:
    """
    Escribe y envía un mensaje de respuesta en el chat actualmente abierto.

    Busca la caja de texto de WhatsApp, escribe la respuesta y presiona Enter.

    Returns:
        True si se envió correctamente, False en caso contrario.
    """
    try:
        # Buscar la caja de texto con múltiples selectores.
        input_box = _wait_for_any(
            driver, DEFAULT_WAIT,
            "message_input", "message_input_alt",
            "message_input_alt2", "message_input_alt3",
        )

        if not input_box:
            log.error("No se encontro la caja de texto de WhatsApp.")
            return False

        # Hacer clic para asegurar el foco.
        try:
            input_box.click()
        except ElementClickInterceptedException:
            # Si algo bloquea el click, usar ActionChains.
            ActionChains(driver).move_to_element(input_box).click().perform()

        time.sleep(0.3)

        # Escribir la respuesta línea por línea.
        # Si la respuesta tiene múltiples líneas, usar Shift+Enter para saltos.
        lines = reply_text.split("\n")
        for i, line in enumerate(lines):
            input_box.send_keys(line)
            if i < len(lines) - 1:
                # Shift+Enter para nueva línea sin enviar.
                input_box.send_keys(Keys.SHIFT, Keys.ENTER)

        # Breve pausa antes de enviar.
        time.sleep(0.5)

        # Presionar Enter para enviar el mensaje.
        input_box.send_keys(Keys.ENTER)

        log.info("Mensaje enviado correctamente.")
        return True

    except Exception as e:
        log.error(f"Error al enviar el mensaje: {e}")
        return False


def process_chat(driver: webdriver.Chrome, chat_element) -> None:
    """
    Procesa un chat individual: lo abre, lee el último mensaje,
    genera una respuesta con Gemini y la envía.
    """
    try:
        # 1. Hacer clic en el chat para abrirlo.
        try:
            chat_element.click()
        except ElementClickInterceptedException:
            ActionChains(driver).move_to_element(
                chat_element).click().perform()

        time.sleep(2)  # Esperar a que cargue la conversación.

        # 2. Obtener el nombre del contacto.
        contact_name = get_contact_name(driver)
        log.info(f"Chat abierto con: {contact_name}")

        # 3. Leer el último mensaje entrante.
        last_message = read_last_message(driver)
        if not last_message:
            log.info("No se pudo leer un mensaje de texto. Saltando este chat.")
            return

        # 4. Generar respuesta con Gemini CLI.
        reply = generate_reply(contact_name, last_message)
        if not reply:
            log.info("No se genero respuesta. Saltando este chat.")
            return

        # 5. Enviar la respuesta.
        send_reply(driver, reply)

    except StaleElementReferenceException:
        log.warning("El elemento del chat ya no es valido (DOM actualizado).")
    except Exception as e:
        log.error(f"Error procesando chat: {e}")


def main() -> None:
    """
    Función principal. Ejecuta el bucle de monitoreo de mensajes.
    """
    driver = None

    try:
        # ── Paso 1: Configurar el navegador ──
        driver = setup_driver()

        # ── Paso 2: Esperar inicio de sesión ──
        wait_for_login(driver)

        log.info("Iniciando monitoreo de mensajes nuevos...")
        log.info(f"   Intervalo de sondeo: {POLL_INTERVAL}s")
        log.info("   Presiona Ctrl+C para detener el bot.\n")

        # Set para rastrear chats ya procesados y evitar responder dos veces.
        # Clave: usamos el aria-label o texto del nombre del contacto visible.
        processed_chats: set[str] = set()
        cycle_count = 0
        RESET_PROCESSED_EVERY = 60  # Limpiar set cada N ciclos (~5 minutos).

        # ── Paso 3: Bucle principal de monitoreo ──
        while True:
            try:
                # Buscar chats con mensajes no leídos.
                new_chats = find_new_messages(driver)

                if new_chats:
                    for chat in new_chats:
                        try:
                            # Obtener un identificador del chat.
                            # Usamos aria-label o el texto visible (nombre del contacto).
                            chat_id = (
                                chat.get_attribute("aria-label")
                                or chat.get_attribute("data-testid")
                                or ""
                            )
                            # Si no se pudo obtener, intentar con texto visible.
                            if not chat_id:
                                try:
                                    chat_id = chat.text.split("\n")[0][:40]
                                except Exception:
                                    chat_id = str(id(chat))

                            if chat_id in processed_chats:
                                continue

                            process_chat(driver, chat)
                            processed_chats.add(chat_id)

                            # Esperar entre chats para no ir demasiado rápido.
                            time.sleep(3)

                        except StaleElementReferenceException:
                            log.debug(
                                "Elemento stale, reintentando en el proximo ciclo.")
                            break

                # Incrementar contador de ciclos.
                cycle_count += 1
                if cycle_count >= RESET_PROCESSED_EVERY:
                    processed_chats.clear()
                    cycle_count = 0
                    log.debug("Set de chats procesados limpiado.")

                # Esperar antes del siguiente ciclo de monitoreo.
                time.sleep(POLL_INTERVAL)

            except WebDriverException as e:
                if "disconnected" in str(e).lower() or "not reachable" in str(e).lower():
                    log.error("El navegador se desconecto. Cerrando...")
                    break
                log.error(f"Error de WebDriver: {e}")
                time.sleep(POLL_INTERVAL)

            except Exception as e:
                log.error(f"Error en el bucle principal: {e}")
                time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        log.info("\nBot detenido por el usuario (Ctrl+C).")

    except Exception as e:
        log.error(f"Error fatal: {e}")

    finally:
        if driver:
            log.info("Cerrando navegador...")
            try:
                driver.quit()
            except Exception:
                pass
        log.info("Hasta luego!")


# ─────────────────────────────────────────────────────────────────────────────
# PUNTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    main()
