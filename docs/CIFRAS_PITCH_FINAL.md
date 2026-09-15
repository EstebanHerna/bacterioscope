# Cifras para el pitch final (28 de septiembre)

Toda cifra que se va a decir en voz alta el 28 vive en este documento, con el
comando exacto que la reproduce. Si alguien del comité pregunta de dónde
salió un número, la respuesta es un comando, no una memoria.

Generado y verificado el 15 de septiembre de 2026. Regenerar cualquier fila
antes del evento si el código cambió después de esta fecha.

---

## Calidad de código

| Cifra | Valor | Comando |
|---|---|---|
| Tests automatizados | 261 | `pytest tests/ -v` |
| Cobertura de línea | 94.9% | `pytest tests/ -q` (línea final del reporte) |
| Lint | limpio | `ruff check src/ tests/` |
| Tipos estrictos | limpio | `mypy src/bacterioscope/` |
| Seguridad estática | 0 hallazgos | `bandit -r src/bacterioscope/ -c pyproject.toml` |
| CI | verde en Python 3.10/3.11/3.12 | GitHub Actions, `.github/workflows/ci.yml` |

## Exactitud de medición (20 imágenes UZH identity-matched, 316 pares disco-antibiótico)

| Cifra | Valor | Comando |
|---|---|---|
| EA identity-matched (todas las mediciones, la cifra defendible) | **32.9%** | `python scripts/validate_measurement.py --subset 80 --max-annotated 25` |
| MAE identity-matched | 6.28 mm | (mismo comando, ver `docs/VALIDATION_REPORT.md`) |
| Pearson r identity-matched | 0.193 | (mismo comando) |
| EA rank-order (cota optimista, no la cifra del proyecto) | 38.1% | (mismo comando) |
| Objetivo clínico (ISO 20776-2 / EUCAST EDef 13.2) | ≥ 90% EA | — |

## El indicador de confianza (nuevo, Fase 3)

Mide si un disco confía en su propia medición: si la máscara medida llena
casi todo su propio recorte de búsqueda, es el borde del recorte, no un
borde biológico real. Umbral elegido barriendo la curva completa, no
adivinado — ver la tabla completa en `scripts/measure_confidence_indicator.py`.

| Cifra | Valor | Comando |
|---|---|---|
| EA de las mediciones marcadas como confiables (umbral 0.90) | **42.8%** | `python scripts/measure_confidence_indicator.py` |
| EA de las mediciones marcadas como no confiables | 21.0% | (mismo comando) |
| Fracción de mediciones marcadas como no confiables | 45.3% (143/316) | (mismo comando) |
| Correlación circularidad vs. error absoluto | 0.038 (no lineal, no monótona) | (mismo comando) |

**Cómo decirlo en el pitch**: "el sistema separa sus propias mediciones en
confiables y no confiables, y cuando confía, acierta 10 puntos porcentuales
más — 42.8% contra el 32.9% de línea base." Es un resultado presentable por
sí mismo, no un truco para inflar la cifra principal (la cifra principal
sigue siendo 32.9% sobre todas las mediciones).

## Detección de discos (80 fotografías reales UZH)

| Cifra | Valor | Comando |
|---|---|---|
| Hough (detector por defecto del pipeline) — acierto exacto de conteo | 73.8% (59/80) | `python scripts/measure_detection_rate.py` |
| Hough — error absoluto medio en conteo | 0.39 discos | (mismo comando) |
| Detector YOLOv8 single-class (conf=0.28) — acierto exacto de conteo | 76.2% (61/80) | (mismo comando) |
| Detector YOLOv8 single-class — error absoluto medio en conteo | 0.49 discos | (mismo comando) |

## Tiempo de procesamiento (80 fotografías reales UZH)

| Cifra | Valor | Comando |
|---|---|---|
| Tiempo medio por placa | 7.79 s | `python scripts/measure_processing_time.py` |
| Tiempo mediano por placa | 5.12 s | (mismo comando) |
| Rango observado | 1.29 s – 55.7 s | (mismo comando) |

**Nota sobre el rango**: el máximo (55.7s) está muy por encima de la mediana
(5.1s) — corresponde a las placas más densas (hasta 16 discos), donde el
costo de la partición de Voronoi crece con el número de discos vecinos. Si
preguntan por el peor caso, la respuesta honesta es "hasta un minuto en la
placa más densa del dataset de investigación, segundos en un panel clínico
normal de 6-12 discos" — no medido todavía sobre un panel clínico normal
por separado.

## Panorama competitivo

| Sistema | Estado | Fuente |
|---|---|---|
| Antibiogo (Fundación MSF) | Certificado CE-IVD desde mayo 2022, desplegado en labs reales | Página oficial de Fondation MSF, verificado directamente |
| Repositorio `astimp` (librería base de Antibiogo) | Sin cambios de código desde marzo 2021 | API de GitHub, verificado directamente |
| BacterioScope | Fase 0 completa, Fase 3 en progreso, no certificado | Este repositorio |

## Imagen recomendada para las láminas

`examples/real/real_plate_box4.jpg` — 10 de 16 discos con contorno medido
confiable (mejoró desde 7/16 antes de los arreglos de Fase 3 de esta
ronda). Ningún panel real da el 100% defendible; esta es la mejor
disponible. Reproducible con:

```
python scripts/survey_pitch_images.py
```

Salida en `data/processed/pitch_candidates/` (no versionada, regenerable).
