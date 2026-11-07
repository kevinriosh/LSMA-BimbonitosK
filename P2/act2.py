"""
================================================================================
Laboratorio de Sistemas Multiagente
Práctica 2 - Fase 2: Coordinación entre agentes
Coordinación de múltiples agentes mediante pizarrón compartido y mensajería
================================================================================

GUÍA DE LECTURA

Este archivo continúa directamente la Práctica 1. Se asume que ya se
comprenden los conceptos de clase, función, bucle y condicional
explicados en aquel archivo; aquí solo se introducen los conceptos
nuevos que exige la coordinación entre varios agentes.

Diccionario: una estructura de datos que asocia una llave con un valor,
de modo que el valor pueda recuperarse a partir de la llave. En este
archivo se utiliza, por ejemplo, para registrar qué agente reclamó cada
muestra: la llave es la posición de la muestra y el valor es el
identificador del agente.

PROPÓSITO DEL PROGRAMA

En la Práctica 1, un único agente exploraba el entorno. En esta
práctica, un EQUIPO de agentes (su número es un parámetro configurable)
explora el mismo entorno de manera simultánea, partiendo todos del
mismo punto de origen. Sin ningún mecanismo de coordinación, los
agentes tenderían a agruparse y a explorar las mismas zonas, duplicando
esfuerzo. El programa implementa y compara dos mecanismos distintos
para evitar esa duplicación:

    1. Pizarrón compartido (blackboard): una única estructura de datos,
       visible de manera instantánea para todos los agentes, registra
       qué celdas ya se exploraron y qué muestras ya fueron reclamadas.

    2. Mensajería directa (inspirada en el estándar FIPA-ACL): no existe
       ninguna estructura compartida. Cada agente únicamente conoce lo
       que percibió directamente, más lo que otros agentes le
       comunicaron mediante mensajes explícitos. Dichos mensajes
       tardan un número configurable de pasos en llegar a su
       destinatario, de modo que el conocimiento de cada agente sobre
       sus compañeros siempre está, en algún grado, desactualizado.

El "cerebro" individual de cada agente es idéntico en ambos mecanismos:
la única diferencia entre ambos es CÓMO cada agente se entera de lo que
el resto del equipo ya sabe. Esta es precisamente la comparación que
la práctica busca evidenciar.

ARCHIVOS QUE GENERA LA EJECUCIÓN

    1. Un reporte en la terminal con una tabla comparativa de desempeño
       de equipo y una bitácora de los eventos más relevantes,
       incluidas las disputas por muestras reclamadas por más de un
       agente al mismo tiempo.
    2. Un archivo de imagen (comparacion_practica2.png) con el mapa
       completo y la trayectoria de cada agente, para ambos mecanismos.
    3. Un archivo de animación (simulacion_practica2.gif) que reproduce
       el recorrido simultáneo de todos los agentes, paso a paso.

Ambos archivos se guardan automáticamente en la misma carpeta donde se
encuentra este script, sin importar desde qué ubicación se ejecute.

FORMA DE EJECUCIÓN

    python practica2_coordinacion_agentes.py
"""

from __future__ import annotations

import os
import random
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


def _ruta_junto_al_script(nombre_archivo: str) -> str:
    """
    Devuelve la ruta completa (absoluta) de un archivo de salida,
    ubicándolo siempre en la misma carpeta donde se encuentra este
    script, independientemente de la carpeta desde la que se ejecute.
    """
    carpeta_del_script = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(carpeta_del_script, nombre_archivo)


# =============================================================================
# SECCIÓN 0. PARÁMETROS CONFIGURABLES POR EL ESTUDIANTE
#
# Los valores definidos en esta clase son los únicos que se requiere
# modificar para experimentar con la práctica.
# =============================================================================

@dataclass
class ParametrosPractica:
    """Conjunto de parámetros configurables de la simulación de equipo."""

    # --- Geometría y dificultad del entorno (igual que en la Práctica 1) ---
    tamano_entorno: int = 12
    densidad_obstaculos: float = 0.15
    num_muestras: int = 6
    semilla: int = 42
    energia_maxima: int = 80

    # --- Parámetros propios de la coordinación entre agentes ---

    num_agentes: int = 3
    # Número de agentes que integran el equipo. Todos parten de la
    # misma celda de origen (0, 0).
    # Sugerencia: compare el resultado con 1 agente (equivalente a la
    # Práctica 1) contra 5 agentes, y observe cómo crece la redundancia
    # cuando no hay ningún mecanismo de coordinación de por medio
    # (puede simularlo momentáneamente ignorando las columnas de
    # "celdas conocidas por el equipo" en decidir_accion_agente).

    retraso_mensaje: int = 1
    # Número de pasos que tarda un mensaje en llegar a su destinatario.
    # Aplica únicamente al mecanismo de mensajería directa; el
    # pizarrón compartido siempre es instantáneo, por definición.
    # Sugerencia: pruebe con retraso_mensaje = 0 (comunicación
    # instantánea) y compare cuánto se reduce el número de disputas
    # resueltas respecto de un retraso de 3 pasos.

    # --- Pesos de la medida de desempeño del EQUIPO ---

    peso_muestra: float = 10.0
    peso_celda_explorada: float = 1.0
    peso_energia: float = 0.2
    peso_redundancia: float = 0.5
    # Puntos que se restan por cada celda que fue visitada más de una
    # vez por el equipo (ya sea por el mismo agente o por agentes
    # distintos). Es la medida central de esta práctica: cuantifica el
    # esfuerzo duplicado que cada mecanismo de coordinación logra
    # evitar.

    # --- Nombres de los archivos de salida ---
    ruta_figura: str = "comparacion_practica2.png"
    ruta_animacion: str = "simulacion_practica2.gif"


# =============================================================================
# SECCIÓN 1. Definición del entorno (idéntica a la Práctica 1)
# =============================================================================

class TipoCelda(Enum):
    LIBRE = "libre"
    OBSTACULO = "obstaculo"
    MUESTRA = "muestra"


@dataclass
class Entorno:
    """
    Cuadrícula NxN compartida por todo el equipo. Al igual que en la
    Práctica 1, esta clase conoce la disposición real del terreno; los
    agentes solo reciben lo que percibir_adyacentes() les entrega para
    su posición individual.
    """
    tamano: int
    densidad_obstaculos: float = 0.15
    num_muestras: int = 6
    semilla: int = 42

    terreno: list = field(init=False)
    muestras_restantes: set = field(init=False)

    def __post_init__(self) -> None:
        rng = random.Random(self.semilla)
        self.terreno = [
            [TipoCelda.LIBRE for _ in range(self.tamano)]
            for _ in range(self.tamano)
        ]
        for f in range(self.tamano):
            for c in range(self.tamano):
                if (f, c) == (0, 0):
                    continue
                if rng.random() < self.densidad_obstaculos:
                    self.terreno[f][c] = TipoCelda.OBSTACULO

        celdas_libres = [
            (f, c)
            for f in range(self.tamano)
            for c in range(self.tamano)
            if self.terreno[f][c] == TipoCelda.LIBRE and (f, c) != (0, 0)
        ]
        rng.shuffle(celdas_libres)
        posiciones_muestras = celdas_libres[: self.num_muestras]
        for (f, c) in posiciones_muestras:
            self.terreno[f][c] = TipoCelda.MUESTRA

        self.muestras_restantes = set(posiciones_muestras)

    def dentro_de_rango(self, pos: tuple[int, int]) -> bool:
        f, c = pos
        return 0 <= f < self.tamano and 0 <= c < self.tamano

    def es_transitable(self, pos: tuple[int, int]) -> bool:
        if not self.dentro_de_rango(pos):
            return False
        f, c = pos
        return self.terreno[f][c] != TipoCelda.OBSTACULO

    def celdas_obstaculo(self) -> list:
        return [
            (f, c)
            for f in range(self.tamano)
            for c in range(self.tamano)
            if self.terreno[f][c] == TipoCelda.OBSTACULO
        ]

    def percibir_adyacentes(self, pos: tuple[int, int]) -> dict:
        f, c = pos
        vecinos = [(f - 1, c), (f + 1, c), (f, c - 1), (f, c + 1)]
        percepto = {}
        for v in vecinos:
            if self.dentro_de_rango(v):
                percepto[v] = self.terreno[v[0]][v[1]]
        return percepto

    def recolectar_si_hay_muestra(self, pos: tuple[int, int]) -> bool:
        if pos in self.muestras_restantes:
            self.muestras_restantes.remove(pos)
            f, c = pos
            self.terreno[f][c] = TipoCelda.LIBRE
            return True
        return False


# =============================================================================
# SECCIÓN 2. Estado individual de cada agente y mensajería entre ellos
# =============================================================================

@dataclass
class Desempeno:
    """Registro individual de un agente, agregado después a nivel de equipo."""
    muestras_recolectadas: int = 0
    energia_consumida: int = 0
    movimientos_efectivos: int = 0
    veces_espero: int = 0


@dataclass
class Agente:
    """
    Representa a un agente dentro del equipo. Nótese que esta clase NO
    contiene ninguna lógica de decisión: solo guarda su identificador,
    su posición y su propio registro de desempeño. La decisión de qué
    hacer en cada paso la calcula la función decidir_accion_agente,
    definida más abajo, y es la MISMA función para ambos mecanismos de
    coordinación. Esto es intencional: permite aislar, en el diseño
    del programa, que la diferencia entre mecanismos está en la
    información disponible, no en la inteligencia individual de cada
    agente.
    """
    id_agente: int
    posicion: tuple[int, int]
    desempeno: Desempeno = field(default_factory=Desempeno)


@dataclass
class Mensaje:
    """
    Mensaje entre agentes, con una estructura simplificada inspirada en
    el estándar FIPA-ACL: un emisor, un destinatario (o None cuando el
    mensaje es un aviso general para todo el equipo), un performativo
    que indica la intención comunicativa del mensaje, y un contenido
    con la información concreta que se transmite.

    Se implementan dos performativos:
      - "informar": el emisor avisa al resto del equipo de un hecho
        (una celda nueva que exploró, o una muestra que reclamó).
      - "proponer": se utiliza únicamente para resolver una disputa,
        cuando el emisor (quien ganó el desempate) le propone al
        destinatario ceder una reclamación previa sobre una muestra.
    """
    emisor: int
    receptor: Optional[int]
    performativo: str
    contenido: dict
    paso_envio: int
    paso_entrega: int


# =============================================================================
# SECCIÓN 3. Regla de decisión común a ambos mecanismos
# =============================================================================

def decidir_accion_agente(
    posicion: tuple[int, int],
    percepto: dict,
    id_agente: int,
    celdas_conocidas_equipo: set,
    muestras_reclamadas_equipo: dict,
) -> tuple[str, Optional[tuple[int, int]], str]:
    """
    Calcula la acción de un agente a partir de tres cosas: lo que
    percibe directamente (percepto), y lo que CREE saber sobre el
    resto del equipo (celdas_conocidas_equipo y
    muestras_reclamadas_equipo). Esta función es idéntica para ambos
    mecanismos de coordinación: lo único que cambia entre ellos es
    cómo se construyen esos dos últimos argumentos antes de llamarla
    (véanse las Secciones 4 y 5).

    Devuelve una tupla con tres elementos: la acción a ejecutar, la
    posición de la muestra que el agente decide reclamar en este paso
    (o None si no reclama ninguna), y una justificación en español
    para la bitácora de ejecución.
    """
    # Regla 1: perseguir una muestra adyacente que nadie más haya
    # reclamado (o que el propio agente ya tenía reclamada).
    for pos_vecina, tipo in percepto.items():
        if tipo == TipoCelda.MUESTRA:
            reclamante_actual = muestras_reclamadas_equipo.get(pos_vecina)
            if reclamante_actual is None or reclamante_actual == id_agente:
                motivo = f"Percibe una muestra libre en {pos_vecina} y se dirige hacia ella."
                return _direccion_hacia(posicion, pos_vecina), pos_vecina, motivo

    # Regla 2: entre las celdas libres adyacentes, preferir una que el
    # equipo (según lo que este agente sabe) todavía no haya explorado.
    libres = [p for p, t in percepto.items() if t == TipoCelda.LIBRE]
    nuevas_para_el_equipo = [p for p in libres if p not in celdas_conocidas_equipo]
    if nuevas_para_el_equipo:
        destino = random.choice(nuevas_para_el_equipo)
        motivo = (
            f"No percibe muestras; se dirige a {destino}, celda que el equipo "
            "aún no ha explorado según su conocimiento actual."
        )
        return _direccion_hacia(posicion, destino), None, motivo

    # Regla 3: si todas las celdas libres adyacentes ya son conocidas
    # por el equipo, elegir una al azar entre ellas.
    if libres:
        destino = random.choice(libres)
        motivo = (
            f"Todas las celdas adyacentes ya son conocidas por el equipo; "
            f"elige al azar {destino}."
        )
        return _direccion_hacia(posicion, destino), None, motivo

    # Regla 4: no hay ninguna celda libre adyacente disponible.
    return "esperar", None, "No existe ninguna celda libre adyacente disponible; permanece en su posición."


def _direccion_hacia(origen: tuple[int, int], destino: tuple[int, int]) -> str:
    f, c = origen
    df, dc = destino
    if df < f:
        return "arriba"
    if df > f:
        return "abajo"
    if dc < c:
        return "izquierda"
    if dc > c:
        return "derecha"
    return "esperar"


def _calcular_destino(posicion: tuple[int, int], accion: str) -> tuple[int, int]:
    f, c = posicion
    return {
        "arriba": (f - 1, c),
        "abajo": (f + 1, c),
        "izquierda": (f, c - 1),
        "derecha": (f, c + 1),
        "esperar": (f, c),
    }[accion]


# =============================================================================
# SECCIÓN 4. Mecanismo A: pizarrón compartido (blackboard)
# =============================================================================

def ejecutar_episodio_pizarron(parametros: ParametrosPractica) -> dict:
    """
    Simula al equipo completo utilizando un pizarrón compartido: una
    única estructura de datos (celdas_exploradas_equipo y
    muestras_reclamadas_equipo) que todos los agentes consultan y
    actualizan de manera instantánea.

    El aspecto clave de esta implementación es el ORDEN de las
    operaciones dentro de cada paso: los agentes se procesan uno por
    uno, en un orden fijo, y el pizarrón se actualiza inmediatamente
    después de que cada agente actúa, ANTES de que el siguiente agente
    decida. En consecuencia, si dos agentes perciben la misma muestra
    en el mismo paso, el primero en procesarse la reclama y el
    segundo, al consultar el pizarrón ya actualizado, la encuentra
    reclamada y elige otra acción. Esta es la razón por la que el
    mecanismo de pizarrón nunca produce disputas: la actualización
    instantánea y secuencial las evita por construcción.
    """
    entorno = Entorno(
        tamano=parametros.tamano_entorno,
        densidad_obstaculos=parametros.densidad_obstaculos,
        num_muestras=parametros.num_muestras,
        semilla=parametros.semilla,
    )
    obstaculos = entorno.celdas_obstaculo()
    muestras_originales = set(entorno.muestras_restantes)

    origen = (0, 0)
    agentes = [Agente(id_agente=i, posicion=origen) for i in range(parametros.num_agentes)]

    # Estas dos estructuras SON el pizarrón: no hay una copia por
    # agente, sino una sola, compartida.
    celdas_exploradas_equipo: set = {origen}
    muestras_reclamadas_equipo: dict = {}

    trayectorias = {r.id_agente: [origen] for r in agentes}
    muestras_recolectadas_en: dict = {}
    bitacora = []
    paso = 0

    while any(r.desempeno.energia_consumida < parametros.energia_maxima for r in agentes):
        paso += 1
        for r in agentes:
            if r.desempeno.energia_consumida >= parametros.energia_maxima:
                continue  # este agente ya agotó su energía individual

            percepto = entorno.percibir_adyacentes(r.posicion)
            accion, reclamo, motivo = decidir_accion_agente(
                r.posicion, percepto, r.id_agente,
                celdas_exploradas_equipo, muestras_reclamadas_equipo,
            )

            destino = _calcular_destino(r.posicion, accion)
            if accion != "esperar" and entorno.es_transitable(destino):
                r.posicion = destino
                r.desempeno.movimientos_efectivos += 1
            elif accion == "esperar":
                r.desempeno.veces_espero += 1
            r.desempeno.energia_consumida += 1

            # Actualización INSTANTÁNEA del pizarrón: se refleja de
            # inmediato, incluso para el siguiente agente que decida
            # dentro de este mismo paso.
            celdas_exploradas_equipo.add(r.posicion)
            if reclamo is not None:
                muestras_reclamadas_equipo.setdefault(reclamo, r.id_agente)

            recolecto = entorno.recolectar_si_hay_muestra(r.posicion)
            if recolecto:
                r.desempeno.muestras_recolectadas += 1
                muestras_recolectadas_en[r.posicion] = r.id_agente

            trayectorias[r.id_agente].append(r.posicion)
            bitacora.append({
                "paso": paso, "id_agente": r.id_agente, "accion": accion,
                "motivo": motivo, "posicion": r.posicion,
                "muestra_recolectada": recolecto,
            })

    return _empaquetar_resultados(
        agentes, trayectorias, obstaculos, muestras_originales,
        muestras_recolectadas_en, bitacora, parametros,
        mensajes_enviados=0, disputas_resueltas=0,
    )


# =============================================================================
# SECCIÓN 5. Mecanismo B: mensajería directa (FIPA-ACL simplificado)
# =============================================================================

def _aplicar_mensaje(
    mensaje: Mensaje,
    ids_equipo: list,
    celdas_conocidas_por_agente: dict,
    muestras_reclamadas_por_agente: dict,
) -> None:
    """
    Incorpora el contenido de un mensaje YA ENTREGADO al conocimiento
    privado de su destinatario (o de todos los destinatarios, si el
    mensaje era un aviso general).
    """
    if mensaje.receptor is not None:
        destinatarios = [mensaje.receptor]
    else:
        destinatarios = [id_ for id_ in ids_equipo if id_ != mensaje.emisor]

    for id_destinatario in destinatarios:
        if mensaje.performativo == "informar":
            if mensaje.contenido["tipo"] == "celda_explorada":
                celdas_conocidas_por_agente[id_destinatario].add(mensaje.contenido["posicion"])
            elif mensaje.contenido["tipo"] == "reclamo_muestra":
                muestras_reclamadas_por_agente[id_destinatario].setdefault(
                    mensaje.contenido["posicion"], mensaje.emisor
                )
        elif mensaje.performativo == "proponer":
            if mensaje.contenido["tipo"] == "ceder_reclamo":
                pos = mensaje.contenido["posicion"]
                # El destinatario libera su reclamo y reconoce que la
                # muestra corresponde a quien ganó el desempate.
                muestras_reclamadas_por_agente[id_destinatario][pos] = mensaje.emisor


def ejecutar_episodio_mensajeria(parametros: ParametrosPractica) -> dict:
    """
    Simula al equipo completo utilizando mensajería directa: no existe
    ninguna estructura compartida. Cada agente mantiene su propio
    conocimiento privado (celdas_conocidas_por_agente[id],
    muestras_reclamadas_por_agente[id]), que solo se actualiza mediante
    mensajes explícitos, entregados con un retraso de
    parametros.retraso_mensaje pasos.

    A diferencia del pizarrón, aquí SÍ pueden ocurrir disputas
    genuinas: dos agentes pueden reclamar la misma muestra dentro del
    mismo paso, precisamente porque ninguno de los dos se había
    enterado todavía de la decisión del otro. Para que esto sea
    posible, la percepción y la decisión de TODOS los agentes se
    calculan primero, usando el entorno tal como estaba al inicio del
    paso; solo después se ejecutan los movimientos, uno por uno. Las
    disputas detectadas se resuelven mediante un mensaje de tipo
    "proponer".
    """
    entorno = Entorno(
        tamano=parametros.tamano_entorno,
        densidad_obstaculos=parametros.densidad_obstaculos,
        num_muestras=parametros.num_muestras,
        semilla=parametros.semilla,
    )
    obstaculos = entorno.celdas_obstaculo()
    muestras_originales = set(entorno.muestras_restantes)

    origen = (0, 0)
    agentes = [Agente(id_agente=i, posicion=origen) for i in range(parametros.num_agentes)]
    ids_equipo = [r.id_agente for r in agentes]

    # A diferencia del pizarrón, aquí cada agente tiene SU PROPIA copia
    # del conocimiento del equipo, que puede estar desactualizada.
    celdas_conocidas_por_agente = {id_: {origen} for id_ in ids_equipo}
    muestras_reclamadas_por_agente = {id_: {} for id_ in ids_equipo}

    trayectorias = {id_: [origen] for id_ in ids_equipo}
    muestras_recolectadas_en: dict = {}
    bitacora = []
    mensajes_pendientes: list = []
    mensajes_enviados = 0
    disputas_resueltas = 0
    paso = 0

    # Estas tres estructuras existen ÚNICAMENTE para poder mostrar,
    # después, de forma explícita cómo viaja la información entre
    # agentes: el historial conserva cada mensaje aunque ya se haya
    # entregado; el conteo por paso permite graficar cuántos mensajes
    # están "en el aire" en cada instante; y los eventos de disputa se
    # guardan aparte para poder marcarlos en el mapa y en la animación.
    historial_mensajes: list = []
    mensajes_en_transito_por_paso: dict = {}
    disputas_eventos: list = []

    while any(r.desempeno.energia_consumida < parametros.energia_maxima for r in agentes):
        paso += 1

        # Paso 1: entregar los mensajes cuyo turno de entrega ya llegó.
        mensajes_por_entregar = [m for m in mensajes_pendientes if m.paso_entrega <= paso]
        mensajes_pendientes = [m for m in mensajes_pendientes if m.paso_entrega > paso]
        for m in mensajes_por_entregar:
            _aplicar_mensaje(m, ids_equipo, celdas_conocidas_por_agente, muestras_reclamadas_por_agente)

        # Paso 2 (fase de percepción): CADA agente percibe y decide su
        # acción con base en el estado del entorno TAL COMO ESTABA al
        # inicio de este paso -antes de que cualquier agente del equipo
        # se haya movido todavía-, y con base en su propio conocimiento
        # privado (posiblemente desactualizado). Es imprescindible
        # calcular todas las decisiones ANTES de ejecutar cualquier
        # movimiento: si un agente moviera y recolectara una muestra de
        # inmediato, el entorno compartido cambiaría a mitad del paso y
        # el siguiente agente ya no podría percibir esa muestra como
        # disponible, con lo que ninguna disputa llegaría a detectarse
        # nunca -precisamente el error que esta separación en dos fases
        # evita.
        decisiones = []
        reclamos_de_este_paso: dict = {}
        for r in agentes:
            if r.desempeno.energia_consumida >= parametros.energia_maxima:
                continue
            percepto = entorno.percibir_adyacentes(r.posicion)
            accion, reclamo, motivo = decidir_accion_agente(
                r.posicion, percepto, r.id_agente,
                celdas_conocidas_por_agente[r.id_agente],
                muestras_reclamadas_por_agente[r.id_agente],
            )
            decisiones.append((r, accion, reclamo, motivo))
            if reclamo is not None:
                # El agente conoce su propia reclamación de inmediato;
                # el retraso solo afecta a cuándo se enteran los demás.
                muestras_reclamadas_por_agente[r.id_agente][reclamo] = r.id_agente
                reclamos_de_este_paso.setdefault(reclamo, []).append(r.id_agente)

        # Paso 3 (fase de ejecución): se aplican los movimientos en un
        # orden fijo (el mismo orden en que se creó la lista "agentes").
        # Si dos agentes decidieron ir por la misma muestra, esta fase
        # determina cuál de los dos la alcanza físicamente primero
        # -siempre el de identificador más bajo, por procesarse
        # primero-, de forma consistente con la regla de desempate que
        # se aplica más abajo para la disputa social entre ellos.
        for r, accion, reclamo, motivo in decisiones:
            destino = _calcular_destino(r.posicion, accion)
            if accion != "esperar" and entorno.es_transitable(destino):
                r.posicion = destino
                r.desempeno.movimientos_efectivos += 1
            elif accion == "esperar":
                r.desempeno.veces_espero += 1
            r.desempeno.energia_consumida += 1

            es_celda_nueva = r.posicion not in celdas_conocidas_por_agente[r.id_agente]
            celdas_conocidas_por_agente[r.id_agente].add(r.posicion)

            if es_celda_nueva:
                # Avisa al resto del equipo que exploró una celda
                # nueva. El aviso tarda retraso_mensaje pasos en llegar.
                mensaje_celda = Mensaje(
                    emisor=r.id_agente, receptor=None, performativo="informar",
                    contenido={"tipo": "celda_explorada", "posicion": r.posicion},
                    paso_envio=paso, paso_entrega=paso + parametros.retraso_mensaje,
                )
                mensajes_pendientes.append(mensaje_celda)
                historial_mensajes.append(mensaje_celda)
                mensajes_enviados += 1

            # Esta llamada actúa sobre el entorno real y compartido: si
            # otro agente con un identificador más bajo ya reclamó y
            # recolectó la misma muestra en este mismo paso, aquí
            # sencillamente ya no queda nada que recolectar.
            recolecto = entorno.recolectar_si_hay_muestra(r.posicion)
            if recolecto:
                r.desempeno.muestras_recolectadas += 1
                muestras_recolectadas_en[r.posicion] = r.id_agente

            if reclamo is not None:
                mensaje_reclamo = Mensaje(
                    emisor=r.id_agente, receptor=None, performativo="informar",
                    contenido={"tipo": "reclamo_muestra", "posicion": reclamo},
                    paso_envio=paso, paso_entrega=paso + parametros.retraso_mensaje,
                )
                mensajes_pendientes.append(mensaje_reclamo)
                historial_mensajes.append(mensaje_reclamo)
                mensajes_enviados += 1

            trayectorias[r.id_agente].append(r.posicion)
            bitacora.append({
                "paso": paso, "id_agente": r.id_agente, "accion": accion,
                "motivo": motivo, "posicion": r.posicion,
                "muestra_recolectada": recolecto,
            })

        # Paso 4: resolver las disputas genuinas detectadas en la fase
        # de percepción (dos o más agentes reclamaron la misma muestra
        # sin haberse enterado todavía el uno del otro).
        for pos_muestra, ids_en_conflicto in reclamos_de_este_paso.items():
            if len(ids_en_conflicto) > 1:
                disputas_resueltas += 1
                # Regla de desempate: conserva la reclamación el agente
                # con el identificador numérico más bajo entre quienes
                # reclamaron la misma muestra en este paso.
                ganador = min(ids_en_conflicto)
                for id_perdedor in ids_en_conflicto:
                    if id_perdedor == ganador:
                        continue
                    mensaje_disputa = Mensaje(
                        emisor=ganador, receptor=id_perdedor, performativo="proponer",
                        contenido={"tipo": "ceder_reclamo", "posicion": pos_muestra},
                        paso_envio=paso, paso_entrega=paso + parametros.retraso_mensaje,
                    )
                    mensajes_pendientes.append(mensaje_disputa)
                    historial_mensajes.append(mensaje_disputa)
                    mensajes_enviados += 1
                    disputas_eventos.append({
                        "paso": paso, "posicion": pos_muestra,
                        "ganador": ganador, "perdedor": id_perdedor,
                    })
                    bitacora.append({
                        "paso": paso, "id_agente": id_perdedor, "accion": "disputa",
                        "motivo": (
                            f"Disputa: los agentes {ganador} y {id_perdedor} reclamaron la "
                            f"muestra en {pos_muestra} en el mismo paso, sin conocer todavía "
                            f"la decisión del otro. Por regla de desempate, el agente {ganador} "
                            "conserva la reclamación."
                        ),
                        "posicion": pos_muestra, "muestra_recolectada": False,
                    })

        # Se registra, para este paso, cuántos mensajes quedaron "en el
        # aire" (ya enviados, todavía no entregados a su destinatario).
        # Esta cifra es la que hace explícito, momento a momento, el
        # costo de la comunicación no instantánea.
        mensajes_en_transito_por_paso[paso] = len(mensajes_pendientes)

    return _empaquetar_resultados(
        agentes, trayectorias, obstaculos, muestras_originales,
        muestras_recolectadas_en, bitacora, parametros,
        mensajes_enviados=mensajes_enviados, disputas_resueltas=disputas_resueltas,
        historial_mensajes=historial_mensajes,
        mensajes_en_transito_por_paso=mensajes_en_transito_por_paso,
        disputas_eventos=disputas_eventos,
    )


# =============================================================================
# SECCIÓN 6. Empaquetado de resultados y medida de desempeño de equipo
# =============================================================================

def _empaquetar_resultados(
    agentes: list, trayectorias: dict, obstaculos: list, muestras_originales: set,
    muestras_recolectadas_en: dict, bitacora: list, parametros: ParametrosPractica,
    mensajes_enviados: int, disputas_resueltas: int,
    historial_mensajes: Optional[list] = None,
    mensajes_en_transito_por_paso: Optional[dict] = None,
    disputas_eventos: Optional[list] = None,
) -> dict:
    """
    Reúne los resultados de una simulación (de cualquiera de los dos
    mecanismos) en un único diccionario, y calcula las métricas de
    desempeño A NIVEL DE EQUIPO, no por agente individual.

    Los últimos tres parámetros solo aplican al mecanismo de
    mensajería (el pizarrón los deja en sus valores por defecto: listas
    y diccionarios vacíos), y existen para poder mostrar de forma
    explícita, tanto en las figuras como en el reporte de texto, CÓMO
    se comparte la información entre agentes y qué tanto retraso tiene
    en cada momento de la simulación.
    """
    if historial_mensajes is None:
        historial_mensajes = []
    if mensajes_en_transito_por_paso is None:
        mensajes_en_transito_por_paso = {}
    if disputas_eventos is None:
        disputas_eventos = []

    # La cobertura del equipo es la unión de las celdas visitadas por
    # TODOS los agentes (sin importar si un agente ya había estado ahí).
    celdas_exploradas_equipo: set = set()
    for trayectoria in trayectorias.values():
        celdas_exploradas_equipo.update(trayectoria)

    # La redundancia compara el total de pasos recorridos por el
    # equipo (sumando a todos los agentes, con repeticiones) contra el
    # número de celdas realmente distintas que se llegaron a explorar.
    # La diferencia es, exactamente, el número de veces que una celda
    # fue visitada de más -ya sea por el mismo agente o por otro.
    total_pasos_recorridos = sum(len(trayectoria) for trayectoria in trayectorias.values())
    redundancia_equipo = total_pasos_recorridos - len(celdas_exploradas_equipo)

    energia_total = sum(r.desempeno.energia_consumida for r in agentes)
    muestras_totales_recolectadas = sum(r.desempeno.muestras_recolectadas for r in agentes)

    puntaje = (
        muestras_totales_recolectadas * parametros.peso_muestra
        + len(celdas_exploradas_equipo) * parametros.peso_celda_explorada
        - energia_total * parametros.peso_energia
        - redundancia_equipo * parametros.peso_redundancia
    )

    return {
        "trayectorias": trayectorias,
        "obstaculos": obstaculos,
        "muestras_originales": muestras_originales,
        "muestras_recolectadas_en": muestras_recolectadas_en,
        "bitacora": bitacora,
        "historial_mensajes": historial_mensajes,
        "mensajes_en_transito_por_paso": mensajes_en_transito_por_paso,
        "disputas_eventos": disputas_eventos,
        "celdas_exploradas_equipo": len(celdas_exploradas_equipo),
        "redundancia_equipo": redundancia_equipo,
        "energia_total": energia_total,
        "muestras_totales_recolectadas": muestras_totales_recolectadas,
        "total_muestras": parametros.num_muestras,
        "mensajes_enviados": mensajes_enviados,
        "disputas_resueltas": disputas_resueltas,
        "puntaje": puntaje,
        "num_agentes": parametros.num_agentes,
        "tamano_entorno": parametros.tamano_entorno,
    }


def comparar_mecanismos(parametros: ParametrosPractica) -> dict:
    """
    Ejecuta ambos mecanismos de coordinación sobre un entorno idéntico
    (misma semilla) y con el mismo número de agentes, para permitir una
    comparación controlada.
    """
    resultados = {}

    random.seed(parametros.semilla)
    resultados["Pizarrón compartido"] = ejecutar_episodio_pizarron(parametros)

    random.seed(parametros.semilla)
    resultados["Mensajería directa"] = ejecutar_episodio_mensajeria(parametros)

    return resultados


# =============================================================================
# SECCIÓN 7. Reporte en terminal
# =============================================================================

def imprimir_comparacion(resultados: dict, parametros: ParametrosPractica) -> None:
    print("=" * 78)
    print("COMPARACIÓN DE MECANISMOS - PRÁCTICA 2: COORDINACIÓN ENTRE AGENTES")
    print(
        f"Entorno: {parametros.tamano_entorno}x{parametros.tamano_entorno}  |  "
        f"Agentes: {parametros.num_agentes}  |  Muestras: {parametros.num_muestras}  |  "
        f"Energía: {parametros.energia_maxima}  |  Retraso de mensaje: {parametros.retraso_mensaje}"
    )
    print("=" * 78)

    encabezado = f"{'Métrica':<34}{'Pizarrón compartido':>22}{'Mensajería directa':>22}"
    print(encabezado)
    print("-" * 78)

    p = resultados["Pizarrón compartido"]
    m = resultados["Mensajería directa"]
    total_muestras = p["total_muestras"]

    filas = [
        ("Celdas exploradas (equipo)", p["celdas_exploradas_equipo"], m["celdas_exploradas_equipo"]),
        (f"Muestras recolectadas (de {total_muestras})", p["muestras_totales_recolectadas"], m["muestras_totales_recolectadas"]),
        ("Energía total consumida", p["energia_total"], m["energia_total"]),
        ("Redundancia (celdas visitadas de más)", p["redundancia_equipo"], m["redundancia_equipo"]),
        ("Mensajes intercambiados", p["mensajes_enviados"], m["mensajes_enviados"]),
        ("Disputas resueltas", p["disputas_resueltas"], m["disputas_resueltas"]),
        ("Puntaje de desempeño", round(p["puntaje"], 1), round(m["puntaje"], 1)),
    ]

    for etiqueta, val_p, val_m in filas:
        print(f"{etiqueta:<34}{val_p:>22}{val_m:>22}")

    print("=" * 78)


def imprimir_bitacora(resultados: dict, max_eventos: int = 3) -> None:
    print("\nBITÁCORA DE EJECUCIÓN (eventos relevantes)")
    print("-" * 78)

    for nombre, datos in resultados.items():
        print(f"\n[{nombre}]")
        bitacora = datos["bitacora"]

        primeros = bitacora[:max_eventos]
        for evento in primeros:
            print(f"  Paso {evento['paso']:>3} (Agente {evento['id_agente']}): {evento['motivo']}")

        disputas = [e for e in bitacora if e["accion"] == "disputa"]
        if disputas:
            print("  (...)")
            for evento in disputas:
                print(f"  Paso {evento['paso']:>3}: {evento['motivo']}")
        else:
            print("  (...) no se registró ninguna disputa en este mecanismo.")

    print("\nINTERPRETACIÓN")
    print("-" * 78)
    print(
        "El mecanismo de pizarrón compartido no puede producir disputas: al\n"
        "actualizarse de manera instantánea y procesar a los agentes en un orden\n"
        "fijo dentro de cada paso, cualquier reclamación ya es visible para el\n"
        "siguiente agente antes de que este decida. En la mensajería directa, en\n"
        "cambio, el retraso en la entrega de los mensajes puede provocar que dos\n"
        "agentes reclamen la misma muestra sin saberlo; dichas disputas, y su\n"
        "resolución, quedan documentadas arriba. Se espera, en consecuencia, que\n"
        "el pizarrón compartido logre una menor redundancia que la mensajería,\n"
        "a costa de requerir una estructura de datos centralizada que en un\n"
        "sistema real distribuido no siempre es posible mantener."
    )


def imprimir_ejemplos_mensajes(resultados: dict, max_ejemplos: int = 5) -> None:
    """
    Muestra ejemplos reales de mensajes intercambiados durante la
    simulación de mensajería directa, con su paso de envío y de
    entrega, para que el retraso de comunicación deje de ser un
    concepto abstracto y se pueda ver, con números concretos de esta
    ejecución, cuánto tiempo tarda la información en propagarse.
    """
    print("\nEJEMPLOS DE MENSAJES INTERCAMBIADOS (mecanismo de mensajería)")
    print("-" * 78)

    datos = resultados["Mensajería directa"]
    historial = datos["historial_mensajes"]

    if not historial:
        print("  No se generó ningún mensaje durante este episodio.")
    else:
        for mensaje in historial[:max_ejemplos]:
            destino = f"Agente {mensaje.receptor}" if mensaje.receptor is not None else "todo el equipo"
            retraso_real = mensaje.paso_entrega - mensaje.paso_envio
            print(
                f"  Enviado en el paso {mensaje.paso_envio:>3}, entregado en el paso "
                f"{mensaje.paso_entrega:>3} (retraso de {retraso_real} paso(s)): "
                f"Agente {mensaje.emisor} '{mensaje.performativo}' a {destino} -> {mensaje.contenido}"
            )
        restantes = len(historial) - max_ejemplos
        if restantes > 0:
            print(f"  (...) y {restantes} mensaje(s) más durante el resto del episodio.")

    valores_en_transito = list(datos["mensajes_en_transito_por_paso"].values())
    if valores_en_transito:
        promedio = sum(valores_en_transito) / len(valores_en_transito)
        maximo = max(valores_en_transito)
        print(
            f"\n  Mensajes en tránsito por paso durante todo el episodio: "
            f"promedio {promedio:.1f}, máximo {maximo}."
        )

    mensajes_pizarron = resultados["Pizarrón compartido"]["mensajes_enviados"]
    print(
        f"\n  En contraste, el pizarrón compartido utilizó {mensajes_pizarron} "
        "mensajes en total: toda actualización ahí es instantánea, por lo que "
        "nunca hay información 'en camino'."
    )


# =============================================================================
# SECCIÓN 8. Figura comparativa
# =============================================================================

def generar_figura_comparativa(resultados: dict, parametros: ParametrosPractica) -> None:
    """
    Genera una imagen con, para cada mecanismo de coordinación: el
    entorno real, las muestras (distinguiendo las recolectadas), y la
    trayectoria de cada agente en un color distinto.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
        from matplotlib.lines import Line2D
    except ImportError:
        print("\nNota: la biblioteca matplotlib no está disponible; no se generó la figura comparativa.")
        return

    tamano = parametros.tamano_entorno
    num_agentes = parametros.num_agentes
    # Un color distinto por agente, tomado de una paleta cualitativa
    # estándar de matplotlib (hasta 10 colores bien diferenciados).
    colores_agente = [plt.cm.tab10(i % 10) for i in range(num_agentes)]

    fig, ejes = plt.subplots(1, 2, figsize=(13, 6.5))

    for eje, (nombre, datos) in zip(ejes, resultados.items()):
        if datos["obstaculos"]:
            of = [p[0] for p in datos["obstaculos"]]
            oc = [p[1] for p in datos["obstaculos"]]
            eje.scatter(oc, of, marker="s", s=430, color="#4B5563", zorder=2)

        # Trayectoria de cada agente, en su propio color.
        for id_agente, trayectoria in datos["trayectorias"].items():
            filas_tray = [p[0] for p in trayectoria]
            cols_tray = [p[1] for p in trayectoria]
            color = colores_agente[id_agente]
            eje.plot(cols_tray, filas_tray, "-", linewidth=1.0, color=color, alpha=0.55, zorder=3)
            eje.scatter([cols_tray[-1]], [filas_tray[-1]], s=110, color=color, marker="X", edgecolors="white", linewidths=1.3, zorder=6)

        # Punto de origen común a todos los agentes.
        eje.scatter([0], [0], s=150, color="#16A34A", edgecolors="white", linewidths=1.5, zorder=7)

        for (f, c) in datos["muestras_originales"]:
            recolectada = (f, c) in datos["muestras_recolectadas_en"]
            eje.scatter(
                c, f, marker="*", s=380,
                color="#F59E0B" if recolectada else "white",
                edgecolors="#B45309", linewidths=1.3, zorder=5,
            )

        # Marca explícita de cada disputa: un anillo discontinuo rojo
        # sobre la celda en disputa, con una etiqueta que indica en qué
        # paso ocurrió y qué agentes participaron. En el pizarrón
        # compartido esta lista siempre está vacía (nunca hay
        # disputas), así que ese panel simplemente no muestra ningún
        # anillo -lo cual es, en sí mismo, una comparación visual
        # directa entre ambos mecanismos.
        for evento in datos["disputas_eventos"]:
            f_disputa, c_disputa = evento["posicion"]
            eje.scatter(
                c_disputa, f_disputa, s=700, facecolors="none",
                edgecolors="#DC2626", linewidths=2.4, linestyle="--", zorder=8,
            )
            eje.annotate(
                f"Disputa (paso {evento['paso']}): Agente {evento['ganador']} vs. Agente {evento['perdedor']}",
                xy=(c_disputa, f_disputa), xytext=(c_disputa + 0.7, f_disputa - 0.7),
                fontsize=7, color="#DC2626", fontweight="bold",
            )

        # Métricas de equipo, como subtítulo por encima de la
        # cuadrícula (no sobre ella), igual que en la Práctica 1.
        texto = (
            f"Celdas: {datos['celdas_exploradas_equipo']}   "
            f"Muestras: {datos['muestras_totales_recolectadas']}/{datos['total_muestras']}   "
            f"Energía: {datos['energia_total']}   "
            f"Redundancia: {datos['redundancia_equipo']}   "
            f"Puntaje: {datos['puntaje']:.1f}"
        )
        if datos["mensajes_enviados"] > 0 or datos["disputas_resueltas"] > 0:
            texto += (
                f"\nMensajes: {datos['mensajes_enviados']}   "
                f"Disputas resueltas: {datos['disputas_resueltas']}"
            )
        eje.text(
            0.5, 1.02, texto, transform=eje.transAxes, fontsize=8.5,
            va="bottom", ha="center", family="monospace",
        )

        eje.set_title(nombre, fontsize=13, fontweight="bold", pad=44)
        eje.set_xlim(-1, tamano)
        eje.set_ylim(tamano, -1)
        eje.set_aspect("equal")
        eje.set_xticks([])
        eje.set_yticks([])
        eje.set_xticks([x - 0.5 for x in range(tamano + 1)], minor=True)
        eje.set_yticks([y - 0.5 for y in range(tamano + 1)], minor=True)
        eje.grid(which="minor", color="#E5E7EB", linewidth=0.6)
        eje.tick_params(which="minor", bottom=False, left=False)
        for spine in eje.spines.values():
            spine.set_visible(False)

    elementos_leyenda = [
        Patch(facecolor="#4B5563", label="Obstáculo"),
        Line2D([0], [0], marker="*", color="w", markerfacecolor="#F59E0B", markeredgecolor="#B45309", markersize=14, label="Muestra recolectada"),
        Line2D([0], [0], marker="*", color="w", markerfacecolor="white", markeredgecolor="#B45309", markersize=14, label="Muestra no recolectada"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#16A34A", markersize=10, label="Origen común"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="none", markeredgecolor="#DC2626", markeredgewidth=2, markersize=12, label="Disputa (solo mensajería)"),
    ]
    for id_agente in range(num_agentes):
        elementos_leyenda.append(
            Line2D([0], [0], color=colores_agente[id_agente], marker="X", markersize=8, label=f"Agente {id_agente}")
        )
    fig.legend(handles=elementos_leyenda, loc="lower center", ncol=4, fontsize=8.5, frameon=False, bbox_to_anchor=(0.5, -0.04))

    fig.suptitle(
        "Coordinación de agentes: pizarrón compartido frente a mensajería directa",
        fontsize=12,
    )
    fig.tight_layout(rect=[0, 0.08, 1, 0.90])

    ruta_absoluta = _ruta_junto_al_script(parametros.ruta_figura)
    fig.savefig(ruta_absoluta, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nFigura comparativa generada correctamente. Ubicación:\n  {ruta_absoluta}")


# =============================================================================
# SECCIÓN 9. Animación del recorrido conjunto
# =============================================================================

def generar_animacion(resultados: dict, parametros: ParametrosPractica, fps: int = 8) -> None:
    """
    Genera un archivo GIF que reproduce, cuadro a cuadro, el
    desplazamiento simultáneo de todos los agentes del equipo, para
    ambos mecanismos de coordinación en paralelo.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.animation as animation
    except ImportError:
        print("\nNota: la biblioteca matplotlib no está disponible; no se generó la animación.")
        return

    try:
        import PIL  # noqa: F401
    except ImportError:
        print(
            "\nNota: no se generó la animación porque la biblioteca Pillow no está "
            "instalada.\nPara instalarla, ejecute: pip install pillow"
        )
        return

    tamano = parametros.tamano_entorno
    num_agentes = parametros.num_agentes
    colores_agente = [plt.cm.tab10(i % 10) for i in range(num_agentes)]

    # El número de cuadros lo determina el episodio más largo entre
    # ambos mecanismos (pueden diferir, ya que las disputas y los
    # retrasos de mensaje pueden alterar cuántos pasos tarda cada
    # agente en agotar su energía... aunque, dado que cada agente consume
    # exactamente una unidad de energía por paso, ambos mecanismos
    # producen episodios de la misma longitud; se calcula de todas
    # formas de manera genérica, sin asumirlo).
    num_frames = 1 + max(
        max(len(t) for t in datos["trayectorias"].values())
        for datos in resultados.values()
    )

    fig, ejes = plt.subplots(1, 2, figsize=(13, 6.8))
    referencias_por_eje = {}

    for eje, (nombre, datos) in zip(ejes, resultados.items()):
        if datos["obstaculos"]:
            of = [p[0] for p in datos["obstaculos"]]
            oc = [p[1] for p in datos["obstaculos"]]
            eje.scatter(oc, of, marker="s", s=420, color="#4B5563", zorder=2)

        muestras_orden = list(datos["muestras_originales"])
        scatter_muestras = eje.scatter(
            [p[1] for p in muestras_orden], [p[0] for p in muestras_orden],
            marker="*", s=380, facecolors="white", edgecolors="#B45309",
            linewidths=1.3, zorder=5,
        )

        eje.scatter([0], [0], s=90, marker="o", facecolors="none", edgecolors="#16A34A", linewidths=2, zorder=6)

        # Un rastro y un marcador de posición actual POR CADA agente.
        lineas_rastro = {}
        marcadores_agente = {}
        for id_agente in datos["trayectorias"]:
            color = colores_agente[id_agente]
            (linea,) = eje.plot([], [], "-", linewidth=1.3, color=color, alpha=0.6, zorder=3)
            marcador = eje.scatter([], [], s=200, color=color, edgecolors="white", linewidths=1.5, zorder=6)
            lineas_rastro[id_agente] = linea
            marcadores_agente[id_agente] = marcador

        texto_estado = eje.text(
            0.5, 1.02, "", transform=eje.transAxes, fontsize=8.5,
            va="bottom", ha="center", family="monospace",
        )

        # Marcador de disputa: un anillo rojo, inicialmente invisible
        # (sin posición), que se activa únicamente durante los cuadros
        # cercanos al paso en que ocurrió una disputa real. Junto con
        # el texto que lo acompaña, hace explícito EN QUÉ MOMENTO y EN
        # QUÉ CELDA dos agentes reclamaron la misma muestra sin saberlo.
        marcador_disputa = eje.scatter(
            [], [], s=750, facecolors="none", edgecolors="#DC2626",
            linewidths=2.6, zorder=9,
        )
        texto_disputa = eje.text(
            0.5, -0.05, "", transform=eje.transAxes, fontsize=9,
            va="top", ha="center", color="#DC2626", fontweight="bold",
        )

        eje.set_title(nombre, fontsize=13, fontweight="bold", pad=32)
        eje.set_xlim(-1, tamano)
        eje.set_ylim(tamano, -1)
        eje.set_aspect("equal")
        eje.set_xticks([])
        eje.set_yticks([])
        eje.set_xticks([x - 0.5 for x in range(tamano + 1)], minor=True)
        eje.set_yticks([y - 0.5 for y in range(tamano + 1)], minor=True)
        eje.grid(which="minor", color="#E5E7EB", linewidth=0.6)
        eje.tick_params(which="minor", bottom=False, left=False)
        for spine in eje.spines.values():
            spine.set_visible(False)

        referencias_por_eje[nombre] = {
            "scatter_muestras": scatter_muestras,
            "lineas_rastro": lineas_rastro,
            "marcadores_agente": marcadores_agente,
            "texto_estado": texto_estado,
            "marcador_disputa": marcador_disputa,
            "texto_disputa": texto_disputa,
            "muestras_orden": muestras_orden,
        }

    fig.suptitle("Simulación del recorrido conjunto, paso a paso", fontsize=13)
    fig.tight_layout(rect=[0, 0.04, 1, 0.90])

    # Duración, en cuadros, de cada "destello" visual de disputa: lo
    # suficientemente breve para asociarse con un instante preciso,
    # pero lo bastante largo para que el ojo humano alcance a verlo.
    ventana_disputa = 6

    def actualizar(frame):
        artistas = []
        for nombre, datos in resultados.items():
            ref = referencias_por_eje[nombre]

            recolectadas_hasta_ahora = set()
            celdas_hasta_ahora = set()
            for id_agente, trayectoria in datos["trayectorias"].items():
                tramo = trayectoria[: min(frame + 1, len(trayectoria))]
                celdas_hasta_ahora.update(tramo)
                filas = [p[0] for p in tramo]
                cols = [p[1] for p in tramo]
                ref["lineas_rastro"][id_agente].set_data(cols, filas)
                ref["marcadores_agente"][id_agente].set_offsets([[cols[-1], filas[-1]]])

            eventos_hasta_ahora = [e for e in datos["bitacora"] if e["paso"] <= frame]
            for evento in eventos_hasta_ahora:
                if evento["muestra_recolectada"]:
                    recolectadas_hasta_ahora.add(evento["posicion"])

            colores = [
                "#F59E0B" if pos in recolectadas_hasta_ahora else "white"
                for pos in ref["muestras_orden"]
            ]
            ref["scatter_muestras"].set_facecolor(colores)

            # Mensajes en tránsito en este instante: cuantifica, cuadro
            # a cuadro, cuánta información ya fue enviada pero todavía
            # no ha llegado a su destinatario. En el pizarrón compartido
            # esta cifra es siempre 0, por construcción.
            mensajes_en_transito = datos["mensajes_en_transito_por_paso"].get(frame, 0)
            ref["texto_estado"].set_text(
                f"Paso: {frame}/{parametros.energia_maxima}   "
                f"Celdas: {len(celdas_hasta_ahora)}   "
                f"Muestras: {len(recolectadas_hasta_ahora)}/{datos['total_muestras']}   "
                f"Mensajes en tránsito: {mensajes_en_transito}"
            )

            # Destello de disputa: se activa únicamente durante los
            # cuadros cercanos al paso exacto en que ocurrió, y en la
            # celda exacta donde ocurrió.
            disputa_activa = None
            for evento in datos["disputas_eventos"]:
                if evento["paso"] <= frame <= evento["paso"] + ventana_disputa:
                    disputa_activa = evento
                    break
            if disputa_activa is not None:
                f_d, c_d = disputa_activa["posicion"]
                ref["marcador_disputa"].set_offsets([[c_d, f_d]])
                ref["texto_disputa"].set_text(
                    f"Disputa en el paso {disputa_activa['paso']}: "
                    f"Agente {disputa_activa['ganador']} conserva la muestra "
                    f"sobre Agente {disputa_activa['perdedor']}"
                )
            else:
                # Para "ocultar" el marcador de disputa cuando no hay
                # ninguna activa, se le asigna una coordenada NaN: es
                # la forma correcta de vaciar un scatter en matplotlib
                # (una lista vacía no tiene la forma que set_offsets
                # espera) y matplotlib simplemente omite los puntos NaN
                # al dibujar.
                ref["marcador_disputa"].set_offsets([[float("nan"), float("nan")]])
                ref["texto_disputa"].set_text("")

            artistas.extend(ref["lineas_rastro"].values())
            artistas.extend(ref["marcadores_agente"].values())
            artistas.append(ref["scatter_muestras"])
            artistas.append(ref["texto_estado"])
            artistas.append(ref["marcador_disputa"])
            artistas.append(ref["texto_disputa"])
        return artistas

    anim = animation.FuncAnimation(fig, actualizar, frames=num_frames, interval=1000 / fps, blit=False)

    ruta_absoluta = _ruta_junto_al_script(parametros.ruta_animacion)
    try:
        anim.save(ruta_absoluta, writer=animation.PillowWriter(fps=fps))
        print(f"Animación generada correctamente. Ubicación:\n  {ruta_absoluta}")
    except Exception as exc:
        print(f"\nNota: no fue posible generar la animación. Detalle del error:\n  {exc}")
    finally:
        plt.close(fig)


# =============================================================================
# SECCIÓN 10. Punto de entrada del programa
# =============================================================================

if __name__ == "__main__":
    parametros = ParametrosPractica()  # modifique los valores en la Sección 0

    carpeta_de_salida = os.path.dirname(os.path.abspath(__file__))
    print(f"Los archivos generados por esta ejecución se guardarán en:\n  {carpeta_de_salida}\n")

    resultados = comparar_mecanismos(parametros)
    imprimir_comparacion(resultados, parametros)
    imprimir_bitacora(resultados)
    imprimir_ejemplos_mensajes(resultados)
    generar_figura_comparativa(resultados, parametros)
    generar_animacion(resultados, parametros)