# Serie de publicaciones

Sustituye únicamente los elementos entre corchetes. No copies las notas internas al post.

## Publicación 1 — Lanzamiento

**Formato:** documento PDF `portfolio/linkedin_carousel.pdf`  
**Título del documento:** Colombia Energy Intelligence — Del dato público a la decisión

⚡ ¿Cómo pasar de una API pública a un producto de datos que pueda defenderse ante un equipo técnico y uno de negocio?

Construí **Colombia Energy Intelligence**, un proyecto end-to-end aplicado al mercado eléctrico colombiano.

La solución conecta:

→ extracción desde la API pública de XM  
→ normalización y controles de calidad  
→ feature engineering temporal  
→ backtesting contra un baseline  
→ data marts de demanda comercial  
→ dashboard ejecutivo y despliegue automatizado

Resultados del corte:

• 39.120 horas validadas, sin huecos, duplicados ni nulos  
• R² de 0,872 y MAPE de 11,24%  
• 26,2% de mejora en RMSE frente al baseline  
• 241,6 TWh analizados entre 157 agentes

Mi principal aprendizaje: el valor no está solo en entrenar un modelo. Está en construir confianza desde la fuente hasta la decisión.

Dashboard: https://chandro-dev.github.io/API_XM/  
Código: https://github.com/chandro-dev/API_XM

¿Qué variable exógena priorizarías para la siguiente versión: hidrología, clima, demanda o restricciones del sistema?

#DataEngineering #BusinessIntelligence #MachineLearning #Python #EnergyAnalytics

**Texto alternativo del documento:** Carrusel de tres páginas sobre un pipeline de datos del mercado eléctrico colombiano. Resume calidad de 39.120 horas, desempeño del forecast y concentración de demanda entre 157 agentes.

## Publicación 2 — Ingeniería de datos

**Formato:** imagen `01_resumen_ejecutivo.png`

Un dashboard confiable empieza mucho antes de la visualización.

En este proyecto, la respuesta diaria de XM llega en formato ancho, con una columna por cada hora. Antes de pensar en modelos tuve que construir un contrato de datos:

1. transformar wide-to-long;
2. estandarizar timestamps y tipos;
3. ordenar y deduplicar;
4. validar continuidad horaria;
5. separar datos analíticos de la capa de presentación.

Resultado: 39.120 horas de precio con 0 huecos, 0 duplicados, 0 nulos y 0 valores negativos.

También incorporé un modo estricto: si falla un control crítico, el pipeline se detiene. Prefiero un proceso que falle de forma visible a un dashboard que muestre datos silenciosamente incorrectos.

La arquitectura y el código están aquí: https://github.com/chandro-dev/API_XM

¿Qué validación consideras indispensable en una serie temporal productiva?

#DataEngineering #DataQuality #ETL #Python #APIs

## Publicación 3 — Machine Learning responsable

**Formato:** imagen `02_forecast_precio.png`

Un R² alto no sirve si la evaluación temporal está mal construida.

Para el forecast del Precio de Bolsa Nacional:

• todas las variables usan únicamente información pasada;  
• el test corresponde al tramo final de la serie;  
• el modelo se compara contra persistencia, no contra cero;  
• entrenamiento e inferencia comparten el mismo contrato temporal.

En 1.441 horas fuera de muestra, XGBoost alcanzó R² de 0,872, MAPE de 11,24% y redujo el RMSE 26,2% frente al baseline.

El forecast del corte muestra un promedio de 413,9 COP/kWh para las siguientes 24 horas, 4,3% por debajo del promedio de las últimas 24 horas.

Es un resultado demostrativo, no una recomendación operativa. La siguiente versión debería incorporar variables exógenas y monitoreo de drift.

¿Qué prueba adicional usarías antes de llevar este modelo a producción?

#MachineLearning #TimeSeries #MLOps #XGBoost #DataScience

## Publicación 4 — BI y negocio

**Formato:** imagen `03_demanda_agentes.png`

El reto de BI no es mostrar más métricas. Es elegir las que cambian una conversación.

Al transformar la demanda comercial de XM en un data mart por agente encontré:

• 241,6 TWh acumulados en el universo analizado;  
• 157 agentes observados;  
• el Top 5 concentra 59,0%;  
• el Top 10 concentra 76,4%.

La visualización permite pasar del detalle horario a una pregunta ejecutiva: ¿cómo está distribuida la demanda y qué actores explican la mayor parte?

Separé el corte de demanda —diciembre de 2024— del corte de precio —junio de 2026— para no sugerir una comparación temporal que los datos no soportan.

Dashboard interactivo: https://chandro-dev.github.io/API_XM/

¿Qué KPI sumarías para analizar mejor la concentración o evolución del mercado?

#BusinessIntelligence #DataAnalytics #BI #EnergyAnalytics #DataStorytelling

