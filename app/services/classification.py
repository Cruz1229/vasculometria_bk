from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class Intervalo:
    low: Optional[float] = None
    high: Optional[float] = None
    include_low: bool = True
    include_high: bool = True

    def contiene(self, x: float) -> bool:
        if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
            return False
        if self.low is not None:
            if self.include_low:
                if x < self.low:
                    return False
            elif x <= self.low:
                return False
        if self.high is not None:
            if self.include_high:
                if x > self.high:
                    return False
            elif x >= self.high:
                return False
        return True


@dataclass(frozen=True)
class Regla:
    id: int
    etiqueta: str
    restricciones: Dict[str, Intervalo]

    def cumple(self, valores: Dict[str, float]) -> bool:
        for var, intervalo in self.restricciones.items():
            x = valores.get(var)
            if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
                return False
            if not intervalo.contiene(float(x)):
                return False
        return True


REGLAS = [
    Regla(id=1, etiqueta="Patrón microvascular normal", restricciones={
        "crae": Intervalo(130, 160, True, True),
        "crve": Intervalo(190, 230, True, True),
        "avr": Intervalo(0.78, 0.88, True, True),
        "tortuosidad": Intervalo(1.00, 1.20, True, True),
    }),
    Regla(id=2, etiqueta="Sospecha de retinopatía hipertensiva", restricciones={
        "crae": Intervalo(120, 135, True, False),
        "crve": Intervalo(190, 230, True, True),
        "avr": Intervalo(0.70, 0.78, True, False),
        "tortuosidad": Intervalo(1.10, 1.40, True, True),
    }),
    Regla(id=3, etiqueta="Alto riesgo de retinopatía hipertensiva", restricciones={
        "crae": Intervalo(None, 120, True, False),
        "crve": Intervalo(190, 230, True, True),
        "avr": Intervalo(None, 0.70, True, False),
        "tortuosidad": Intervalo(1.20, None, True, True),
    }),
    Regla(id=4, etiqueta="Sospecha de retinopatía diabética", restricciones={
        "crae": Intervalo(130, None, True, True),
        "crve": Intervalo(230, 250, True, True),
        "avr": Intervalo(0.70, None, True, True),
        "tortuosidad": Intervalo(1.20, 1.35, True, True),
    }),
    Regla(id=5, etiqueta="Alto riesgo de retinopatía diabética", restricciones={
        "crae": Intervalo(None, 130, True, True),
        "crve": Intervalo(250, None, False, True),
        "avr": Intervalo(None, 0.70, True, True),
        "tortuosidad": Intervalo(1.35, None, True, True),
    }),
]

DEFAULT_MARGINS = {
    "crae": 10.0,
    "crve": 12.0,
    "avr": 0.03,
    "tortuosidad": 0.06,
}


def _interval_distance(intervalo: Intervalo, x: float) -> float:
    if intervalo.contiene(x):
        return 0.0
    if intervalo.low is not None and x < intervalo.low:
        return float(intervalo.low - x)
    if intervalo.high is not None and x > intervalo.high:
        return float(x - intervalo.high)
    return 0.0


def _interval_score(intervalo: Intervalo, x: float, margin: float) -> float:
    if x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))):
        return 0.0
    d = _interval_distance(intervalo, float(x))
    if margin <= 0:
        return 1.0 if d == 0 else 0.0
    return float(math.exp(-((d / margin) ** 2)))


def _rule_score(regla: Regla, valores: Dict[str, float], margins: Dict[str, float]) -> float:
    per_var = [
        _interval_score(intervalo, valores.get(var), float(margins.get(var, 1.0)))
        for var, intervalo in regla.restricciones.items()
    ]
    if not per_var:
        return 0.0
    prod = 1.0
    for score in per_var:
        prod *= max(1e-12, float(score))
    return float(prod ** (1.0 / len(per_var)))


def _regla_por_id(rule_id: int) -> Optional[Regla]:
    for regla in REGLAS:
        if regla.id == rule_id:
            return regla
    return None


def clasificar_patron_microvascular(crae: float, crve: float, avr: float, tortuosidad: float) -> Tuple[str, int]:
    valores = {
        "crae": crae,
        "crve": crve,
        "avr": avr,
        "tortuosidad": tortuosidad,
    }
    for regla in REGLAS:
        if regla.cumple(valores):
            return regla.etiqueta, regla.id
    return "Perfil mixto o indeterminado", 6


def probabilidades_5_clases(
    crae: float,
    crve: float,
    avr: float,
    tortuosidad: float,
    margins: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    margins = margins or DEFAULT_MARGINS
    valores = {
        "crae": crae,
        "crve": crve,
        "avr": avr,
        "tortuosidad": tortuosidad,
    }
    rule_scores: Dict[int, float] = {r.id: _rule_score(r, valores, margins) for r in REGLAS}
    class_scores: Dict[str, float] = {
        "sano": float(rule_scores.get(1, 0.0)),
        "sospecha_rh": float(rule_scores.get(2, 0.0)),
        "alto_riesgo_rh": float(rule_scores.get(3, 0.0)),
        "sospecha_rd": float(rule_scores.get(4, 0.0)),
        "alto_riesgo_rd": float(rule_scores.get(5, 0.0)),
    }
    total = sum(class_scores.values())
    probs = {k: (v / total if total > 0 else 0.0) for k, v in class_scores.items()}
    pct = {k: float(v * 100.0) for k, v in probs.items()}
    best_score = max(rule_scores.values()) if rule_scores else 0.0
    best_id = max(rule_scores.items(), key=lambda kv: kv[1])[0] if best_score > 0 else None
    return {
        "probs": probs,
        "pct": pct,
        "rule_scores": rule_scores,
        "best_rule_soft": best_id,
        "best_rule_soft_label": _regla_por_id(best_id).etiqueta if best_id else None,
    }


def classify_metrics(biomarkers: Dict[str, Any]) -> Dict[str, Any]:
    crae = biomarkers.get("craek_um")
    crve = biomarkers.get("crvek_um")
    avr = biomarkers.get("avr_knudtson")
    tort = biomarkers.get("median_tortuosity")

    proba = probabilidades_5_clases(
        crae if crae is not None else float("nan"),
        crve if crve is not None else float("nan"),
        avr if avr is not None else float("nan"),
        tort if tort is not None else float("nan"),
    )
    pct = proba["pct"]
    best_rule_soft = proba.get("best_rule_soft")
    best_rule_soft_label = proba.get("best_rule_soft_label")
    etiqueta = best_rule_soft_label or "Perfil mixto o indeterminado"
    regla_id = int(best_rule_soft) if best_rule_soft is not None else 6

    return {
        "etiqueta": etiqueta,
        "regla_id": regla_id,
        "pct_sano": round(float(pct.get("sano", 0.0)), 2),
        "pct_sospecha_rh": round(float(pct.get("sospecha_rh", 0.0)), 2),
        "pct_alto_riesgo_rh": round(float(pct.get("alto_riesgo_rh", 0.0)), 2),
        "pct_sospecha_rd": round(float(pct.get("sospecha_rd", 0.0)), 2),
        "pct_alto_riesgo_rd": round(float(pct.get("alto_riesgo_rd", 0.0)), 2),
        "best_rule_soft": best_rule_soft,
        "best_rule_soft_label": best_rule_soft_label,
    }
