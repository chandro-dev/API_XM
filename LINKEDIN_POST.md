# Publicación sugerida para LinkedIn

⚡ ¿Cómo convertir más de 39 mil registros horarios del mercado eléctrico colombiano en un producto de datos útil?

Construí **Colombia Energy Intelligence**, un proyecto end-to-end que conecta ingeniería de datos, machine learning y Business Intelligence usando datos públicos de XM.

El pipeline:

→ consume y normaliza información horaria desde la API de XM  
→ valida continuidad, duplicados, nulos y rangos  
→ crea variables temporales sin usar información futura  
→ entrena y evalúa un modelo con backtesting temporal  
→ compara su desempeño contra un baseline simple  
→ construye data marts de demanda por agente  
→ entrega KPIs y visualizaciones en un dashboard ejecutivo

Resultados del corte analizado:

✅ 39.120 horas con 0 huecos, duplicados, nulos o precios negativos  
✅ R² de 0,872 en el periodo de prueba  
✅ mejora de 26,16% en RMSE frente al baseline de persistencia  
✅ análisis de concentración y evolución de la demanda comercial

En el último corte, el forecast de 24 horas presenta un promedio de **413,9 COP/kWh**, un **4,3% menor** que el promedio de las 24 horas anteriores. En la capa de demanda, analicé **241,6 TWh de 157 agentes**: los cinco primeros concentran el **59,0%** del total observado.

Más allá del modelo, quise demostrar algo que considero clave en datos: un resultado analítico solo genera confianza cuando existe trazabilidad desde la fuente, controles de calidad, una evaluación honesta y una capa de comunicación clara para negocio.

Stack: Python, Pandas, scikit-learn, XGBoost, Matplotlib, API REST, GitHub Actions y principios de BI.

Repositorio y dashboard: [PEGA AQUÍ TU ENLACE]

¿Qué variable sumarías al modelo: hidrología, clima, demanda o restricciones del sistema?

#DataEngineering #BusinessIntelligence #MachineLearning #Python #DataAnalytics #PowerBI #OpenData #EnergyAnalytics #Colombia #OpenToWork

## Recomendación de publicación

Publica las tres láminas de `portfolio/screenshots/` como carrusel, en orden. También puedes usar `portfolio/cover.png` como portada alternativa. Sustituye el enlace, etiqueta a XM solo como fuente de datos y evita afirmar que el modelo predice decisiones reales de mercado: es un caso técnico demostrativo.
