"""
Gestión de slots de la dmsMessageTable para Daktronics VFC.

El panel expone 500 slots de memory_type=3 (changeable). SlotManager
lleva un registro en memoria de cuáles están libres, ocupados o corruptos,
y garantiza que dos hilos nunca reciban el mismo slot.
"""

import threading
from enum import Enum, auto


class SlotState(Enum):
    FREE      = auto()   # disponible para su uso
    IN_USE    = auto()   # ocupado por un mensaje activo
    CORRUPTED = auto()   # falló en el panel; nunca volver a usar


class SlotManager:
    """
    Gestor de slots de la dmsMessageTable (memory_type=3, changeable).

    Thread-safe: todas las operaciones de lectura/escritura sobre el estado
    interno están protegidas por un Lock.

    Uso típico:
        slot = manager.acquire()
        try:
            driver._write_and_activate(slot, multi_string)
        except Exception:
            manager.mark_corrupted(slot)
            raise
        # el slot se libera cuando el mensaje ya no se necesita:
        manager.release(slot)
    """

    def __init__(self, total_slots: int = 500) -> None:
        """
        Inicializa el gestor con todos los slots en FREE.

        Args:
            total_slots: número total de slots del panel (por defecto 500).
        """
        self._lock = threading.Lock()
        self._slots: dict[int, SlotState] = {
            slot: SlotState.FREE for slot in range(1, total_slots + 1)
        }
        self._total = total_slots

    # ─── API pública ──────────────────────────────────────────────────────────

    def acquire(self) -> int:
        """
        Reserva y devuelve el número del primer slot libre (orden ascendente).

        El slot pasa a IN_USE de forma atómica, por lo que dos hilos
        concurrentes nunca obtendrán el mismo número.

        Returns:
            Número de slot reservado (1-based).

        Raises:
            RuntimeError: si no hay ningún slot FREE disponible.
        """
        with self._lock:
            for slot, state in self._slots.items():
                if state is SlotState.FREE:
                    self._slots[slot] = SlotState.IN_USE
                    return slot
            raise RuntimeError(
                f"No hay slots disponibles (total={self._total}, "
                f"todos en uso o corruptos)"
            )

    def release(self, slot: int) -> None:
        """
        Marca el slot como FREE para que pueda ser reutilizado.

        No hace nada si el slot está CORRUPTED (un slot corrupto
        solo puede ser limpiado reiniciando el SlotManager).

        Args:
            slot: número de slot a liberar.

        Raises:
            KeyError: si el número de slot no existe en el panel.
        """
        with self._lock:
            self._validate(slot)
            if self._slots[slot] is not SlotState.CORRUPTED:
                self._slots[slot] = SlotState.FREE

    def mark_corrupted(self, slot: int) -> None:
        """
        Marca el slot como CORRUPTED permanentemente.

        Usar cuando el panel devuelve un error irrecuperable para ese slot
        (p. ej., messageStatus == error tras múltiples intentos de rollback).
        El slot no volverá a ser entregado por acquire().

        Args:
            slot: número de slot a invalidar.

        Raises:
            KeyError: si el número de slot no existe en el panel.
        """
        with self._lock:
            self._validate(slot)
            self._slots[slot] = SlotState.CORRUPTED

    def is_available(self, slot: int) -> bool:
        """
        Indica si el slot está libre (FREE).

        Args:
            slot: número de slot a consultar.

        Returns:
            True si el slot está en estado FREE, False en cualquier otro caso.

        Raises:
            KeyError: si el número de slot no existe en el panel.
        """
        with self._lock:
            self._validate(slot)
            return self._slots[slot] is SlotState.FREE

    def status(self) -> dict:
        """
        Devuelve un resumen del estado actual de todos los slots.

        Returns:
            Dict con las claves:
                free      (int) — slots disponibles
                in_use    (int) — slots ocupados
                corrupted (int) — slots inutilizables
                total     (int) — slots totales del panel
        """
        with self._lock:
            counts = {state: 0 for state in SlotState}
            for state in self._slots.values():
                counts[state] += 1
            return {
                "free":      counts[SlotState.FREE],
                "in_use":    counts[SlotState.IN_USE],
                "corrupted": counts[SlotState.CORRUPTED],
                "total":     self._total,
            }

    def is_tracked(self, slot: int) -> bool:
        """
        Indica si el slot está dentro del rango conocido por este SlotManager.

        A diferencia de is_available(), no lanza KeyError para slots fuera
        de rango — simplemente devuelve False.

        Args:
            slot: número de slot a consultar.

        Returns:
            True si el slot existe en este SlotManager, False si no.
        """
        with self._lock:
            return slot in self._slots

    def in_use_slots(self) -> list[int]:
        """
        Devuelve la lista de slots actualmente en estado IN_USE.

        Returns:
            Lista ordenada de números de slot ocupados.
        """
        with self._lock:
            return sorted(s for s, state in self._slots.items() if state is SlotState.IN_USE)

    # ─── Internos ─────────────────────────────────────────────────────────────

    def _validate(self, slot: int) -> None:
        """Lanza KeyError si el slot está fuera del rango del panel."""
        if slot not in self._slots:
            raise KeyError(f"Slot {slot} fuera de rango (1–{self._total})")
