# BacterioScope — Resumen para Evaluadores BDIC 2026

Universidad de los Andes / Nodo de Innovación

---

## El problema

La resistencia antimicrobiana (RAM) mata aproximadamente 1.27 millones de personas al año y figura entre las diez principales amenazas para la salud global (OMS, 2019). El control eficaz de la RAM depende de un reporte rápido y preciso de sensibilidad antibiótica (AST), que permite al clínico prescribir el antibiótico correcto desde el primer día.

En América Latina, el método de referencia más accesible es el **antibiograma Kirby-Bauer por difusión en disco**: económico, estandarizado y disponible en prácticamente todo laboratorio clínico. Sin embargo, el paso final — medir con regla cada halo de inhibición y clasificarlo según la tabla CLSI — es **lento, operador-dependiente y sujeto a error humano**.

Los sistemas automatizados alternativos (VITEK 2, BD Phoenix, MicroScan) cuestan más de USD 80 000, requieren reactivos propietarios y cadenas de suministro que muchos hospitales de mediana y baja complejidad en la región no pueden sostener. El resultado: reportes de AST tardíos o variables que retrasan la prescripción antibiótica apropiada.

---

## La solución

**BacterioScope** convierte una fotografía ordinaria de una placa Kirby-Bauer en un reporte S/I/R completo sin intervención humana, en segundos, usando únicamente una cámara y un computador estándar.

```
Fotografía de la placa (cualquier cámara)
    |
    v
1. CALIBRACIÓN      Detecta el borde de la placa y calcula px/mm.
    v
2. DETECCIÓN        Localiza cada disco antibiótico.
    v
3. SEGMENTACIÓN     Mide el diámetro del halo de inhibición en mm.
    v
4. CLASIFICACIÓN    Clasifica S/I/R según CLSI M100-Ed33 2023.
    v
Reporte (JSON + HTML imprimible + imagen anotada)
```

### Propuesta de valor

| Dimensión | Método manual | BacterioScope |
|---|---|---|
| Tiempo de reporte | 10–30 min por placa | < 5 segundos |
| Costo de hardware adicional | USD 80 000+ (VITEK) | USD 0 (cámara ya existente) |
| Variabilidad inter-operador | Alta | Ninguna |
| Trazabilidad del resultado | Ninguna o manual | UUID, SHA-256, versión CLSI, commit |
| Estándares aplicados | CLSI M100-Ed33 2023 | CLSI M100-Ed33 2023 |

---

## Arquitectura técnica

El sistema está implementado en Python 3.10+ y opera en un pipeline modular:

**Calibración** (`utils/calibration.py`) — Transformada de Hough circular sobre el borde de la placa de 90 mm; calcula la razón px/mm que escala todas las medidas al sistema métrico real.

**Detección de discos** (`detection/detector.py`) — Fase 0: HoughCircles como línea base geométrica. Fase 2 (planificada): YOLOv8 detectará cada disco y leerá el antibiótico impreso, eliminando la asignación manual.

**Segmentación de zonas** (`segmentation/watershed.py`) — Umbralización de Otsu + watershed morfológico sobre un ROI recortado alrededor de cada disco. Reporta diámetro en mm y circularidad.

**Clasificación CLSI** (`classification/clsi.py`) — Tabla de puntos de corte CLSI M100-Ed33 2023, 15 antibióticos, Enterobacteriaceae. Flags automáticos para antibióticos de última línea (carbapenémicos).

**Reporte** (`evaluation/plate_report.py`) — HTML autocontenido con tira de miniaturas por disco, tabla de resultados con S/I/R codificado por color, barra de escala, proveniencia completa (SHA-256 de imagen, hash de commit, versión de software, edición CLSI) y apéndice JSON.

**Trazabilidad** — Cada análisis genera un UUID único (`analysis_id`), registra el SHA-256 del archivo de imagen, el hash del commit git en ejecución y la edición CLSI utilizada. Este nivel de trazabilidad cumple con los requisitos de auditabilidad para sistemas de diagnóstico de apoyo.

---

## Estado actual — Fase 0 completa

| Componente | Estado |
|---|---|
| Pipeline extremo a extremo (calibración → clasificación) | Completo |
| Demo Streamlit (carga imagen, asignación de antibiótico, S/I/R en vivo) | Completo |
| Interfaz de línea de comandos (CLI) | Completo |
| API REST (FastAPI, `/health` + `/analyze`) | Completo |
| Módulo de evaluación clínica (CA, EA, VME, ME, mE — ISO 20776-2) | Completo |
| Reportes HTML científicos autocontenidos (9 secciones) | Completo |
| Sistema de paneles (asignación automática por posición angular) | Completo |
| Procesamiento por lotes con CSV de resultados y log de errores | Completo |
| Instrumentación de rendimiento (tiempos por etapa en ms) | Completo |
| Suite de pruebas | 228 pruebas, 93.9% de cobertura |
| CI (GitHub Actions) | Verde en Python 3.10, 3.11, 3.12 |

**Limitación de Fase 0:** la detección usa círculos geométricos (sin aprendizaje automático) y el antibiótico se asigna manualmente en la UI o mediante un panel predefinido. La Fase 2 elimina ambas restricciones mediante YOLOv8.

---

## Plan de validación clínica

La validación cuantitativa sigue el protocolo ISO 20776-2 / criterios FDA para sistemas AST:

**Dataset de referencia:** Dryad/UZH (Egli et al., 2023) — 225 aislados clínicos Gram-negativos fotografiados con configuración estandarizada y medidos por SIRscan (lector automatizado calibrado). Dataset de acceso abierto (CC0 1.0).

**Métricas objetivo para Fase 3:**

| Métrica | Descripción | Objetivo |
|---|---|---|
| EA (Essential Agreement) | Diámetro medido dentro de ±2 mm del de referencia | ≥ 90% |
| CA (Categorical Agreement) | Clasificación S/I/R coincide con referencia | ≥ 90% |
| VME (Very Major Error) | Predice S cuando la realidad es R | ≤ 1.5% |
| ME (Major Error) | Predice R cuando la realidad es S | ≤ 3.0% |
| mE (Minor Error) | Cualquier discordancia que involucra I | ≤ 10% |

El análisis de concordancia incluye gráficos de Bland-Altman (diferencia media, SD, límites ±1.96 SD) para evaluar el sesgo sistemático en la medición de diámetros.

---

## Plan de fases

| Fase | Alcance | Estado |
|---|---|---|
| **F0** | Pipeline completo con línea base Hough + clasificador CLSI + demo + CI | **Completa** |
| **F1** | Curación y anotación del dataset Dryad/UZH (225 aislados, ground truth clínico) | Planificada |
| **F2** | Entrenamiento de YOLOv8 para detección de discos y lectura de etiqueta impresa | Planificada |
| **F3** | Recalibración px/mm usando disco físico (6 mm); validación clínica completa | Planificada |
| **F4** | Paquete PyPI, imagen Docker, despliegue público, documentación MkDocs | Planificada |

---

## Equipo

| Rol | Integrante |
|---|---|
| Líder técnico / ML | Esteban A. Hernandez Sulvara — Ingeniería de Sistemas, Uniandes |
| Microbiología | Paula Becerra Lara — Microbiología, Uniandes |
| Microbiología | Farid — Uniandes |
| Interfaz y datos | Santiago Gomez — Uniandes |
| Asesor | Prof. Aurelio — Uniandes |
| Asesora | Astrid Berena Herrera — Uniandes |

---

## Consideraciones éticas y limitaciones

- **No es un dispositivo médico:** BacterioScope es una herramienta de investigación y apoyo. Toda decisión clínica final recae en el profesional de salud.
- **Cobertura de antibióticos:** Fase 0 cubre 15 antibióticos para Enterobacteriaceae. La extensión a otras familias bacterianas (Gram-positivos, no fermentadores) y a otras comisiones de standards (EUCAST) es trabajo futuro.
- **Calidad de imagen:** el rendimiento depende de condiciones de iluminación adecuadas y correcta enfoque de la placa. La Fase 3 incluirá guía de usuario para toma de fotografía reproducible.
- **Validación pendiente:** los objetivos de EA/CA/VME/ME/mE son metas de Fase 3; los valores actuales del pipeline de Fase 0 son preliminares hasta completar la validación con el dataset UZH.

---

*BacterioScope es de código abierto (MIT). Repositorio: github.com/EstebanHerna/bacterioscope*
