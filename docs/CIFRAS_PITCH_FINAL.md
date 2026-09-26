# Cifras para el pitch final (28 de septiembre)

Toda cifra que se va a decir en voz alta el 28 vive en este documento, con el
comando exacto que la reproduce. Si alguien del comité pregunta de dónde
salió un número, la respuesta es un comando, no una memoria.

Regenerado y verificado el 26 de septiembre de 2026. Regenerar cualquier
fila antes del evento si el código cambió después de esta fecha.

Filas que NO se reproducen con un solo comando (marcadas con un asterisco
donde aparecen): la cobertura sale de la línea final de la salida de
pytest, no de un comando que imprima solo ese número, y el estado de CI
solo se ve en GitHub Actions, no localmente. Las cifras de tiempo dependen
de la máquina (ver su sección).

---

## Calidad de código

| Cifra | Valor | Comando |
|---|---|---|
| Tests automatizados | 261 pasan (1 omitido) | `pytest tests/ -v` |
| Cobertura de línea (*) | 94.9% | `pytest tests/ -q` (línea `TOTAL` del reporte) |
| Lint | limpio | `ruff check src/ tests/` |
| Tipos estrictos | limpio | `mypy src/bacterioscope/` |
| Seguridad estática | 0 hallazgos | `bandit -r src/bacterioscope/ -c pyproject.toml` |
| CI (*) | verde en Python 3.10/3.11/3.12 | Pestaña Actions de GitHub, `.github/workflows/ci.yml` (no reproducible localmente) |

## Exactitud de medición (20 imágenes UZH identity-matched, 316 pares disco-antibiótico)

| Cifra | Valor | Comando |
|---|---|---|
| Pares disco-antibiótico con medición de referencia | **316** (20 imágenes) | `python scripts/validate_measurement.py --subset 80 --max-annotated 25` (fila "Disk-antibiotic pairs (identity)" de `docs/VALIDATION_REPORT.md`; 944 es el conteo rank-order, otra cifra) |
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
| Tiempo mediano por placa | 2.5 – 5.2 s según la ejecución y la carga de la máquina (tres ejecuciones: 2.49, 5.12, 5.19) | `python scripts/measure_processing_time.py` |
| Placa de 16 discos, mismo comando | del orden de segundos, no minutos | (mismo comando, sección "Slowest") |

**No decir en voz alta media ni máximo.** Se midieron tres veces y no son
reproducibles: la media salió 7.79 s, 3.94 s y 178 s, y el máximo 55.7 s,
17.5 s y 13 215 s. El valor de 13 215 s (3.7 horas para una placa) es la
computadora suspendiéndose durante la ejecución, porque el reloj de pared
sigue corriendo; ningún estado del pipeline tarda eso. Por eso solo la
mediana es defendible, y aun ella varía cerca de 2x entre ejecuciones
según la carga de la máquina.

**Corrección de una explicación anterior**: una versión previa de este
documento atribuía el máximo a "el costo de la partición de Voronoi en
placas densas". Medido, no se sostiene: el tiempo no correlaciona con el
número de discos (r = -0.24 y 0.06 en dos ejecuciones) y la etapa dominante
en las placas más lentas cambia entre ejecuciones (calibración, detección,
segmentación, clasificación). La variación es de la máquina, no de la
complejidad de la placa. Respuesta honesta si preguntan: "segundos por
placa en un portátil corriente; no lo hemos medido en hardware dedicado".

## Panorama competitivo

| Sistema | Estado | Fuente |
|---|---|---|
| Antibiogo (Fundación MSF) | Certificado CE-IVD desde mayo 2022, desplegado en labs reales | Página oficial de Fondation MSF, verificado directamente |
| Repositorio `astimp` (librería base de Antibiogo) | Sin cambios de código desde marzo 2021 | API de GitHub, verificado directamente |
| BacterioScope | Fase 0 completa, Fase 3 en progreso, no certificado | Este repositorio |

## Imagen recomendada para las láminas

`examples/real/real_plate_box4.jpg`, captura a resolución nativa
(3096x4128) en `data/processed/pitch_capture/` (no versionada, regenerable):

```
python scripts/render_full_resolution_capture.py
```

Con la barra visual estricta (relleno del recorte < 0.80 y sin banderas),
7 de 16 discos tienen un contorno limpio. Otros 3 no llevan bandera pero su
contorno es visiblemente algo cuadrado (relleno 0.80 – 0.90), y 6 llevan
bandera de baja confianza y se dibujan con un anillo ámbar. Hay que decirlo
así: "7 de 16 limpios, 6 marcados por el propio sistema como de baja
confianza", no "10 de 16" (cifra de una versión anterior, con una barra más
laxa). Dos de los 7 limpios (11.9 mm y 15.0 mm) muestran una pequeña cola
del contorno hacia un vecino; no mostrarlos como ejemplo de contorno
perfecto. Ningún panel real da el 100% defendible; esta es la mejor
disponible. La comparación entre imágenes se reproduce con:

```
python scripts/survey_pitch_images.py
```

Salida en `data/processed/pitch_candidates/` (no versionada, regenerable).
