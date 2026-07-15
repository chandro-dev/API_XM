# Análisis de datos energéticos para la región Caribe

## Contexto del proyecto

Este proyecto nació a partir de la conferencia **“Datos como nuevo mineral”**, realizada por el programa de Ingeniería de Sistemas de la **Universidad Popular del Cesar**, con participación del **Ministerio de Minas y Energía**.

Durante el evento se presentó el potencial de los datos públicos del sector minero-energético y se propusieron varios retos para explorar su uso mediante programación, analítica y construcción de soluciones basadas en evidencia. A partir de uno de estos retos desarrollé un repositorio de análisis con **Python**.

El propósito no es emitir juicios sobre empresas o instituciones, sino demostrar cómo los datos abiertos pueden organizarse, analizarse y convertirse en información útil para comprender un problema público.

## Pregunta de análisis

> ¿Qué variables permiten comprender mejor las presiones sobre la factura de energía y la sostenibilidad financiera del servicio eléctrico en la región Caribe?

El análisis parte de una idea importante: el consumo de energía, por sí solo, no explica el valor de la factura ni las obligaciones financieras del sistema. También influyen variables como el costo de compra de energía, las pérdidas, la contratación, la exposición al mercado de bolsa, el recaudo, los subsidios, la opción tarifaria y las inversiones en infraestructura.

## Datos y metodología

Se utilizaron datos de demanda comercial del conjunto `DemaCome / Agente` de XM para el periodo comprendido entre enero de 2022 y diciembre de 2024.

El proceso incluyó:

- extracción y preparación de datos;
- normalización de nombres y códigos de agentes;
- consolidación de series temporales;
- validación de unidades y registros duplicados;
- cálculo de indicadores agregados;
- construcción de un escenario exploratorio de exposición al precio de bolsa;
- revisión de información pública de XM, CREG, MinEnergía y Superservicios;
- propuesta de un modelo de datos para futuros tableros de seguimiento.

Para Air-e se consolidaron los códigos `CSSC` y `CSIC`, con el fin de mantener la continuidad de la serie después del cambio de identificación asociado a su intervención.

## Resultados exploratorios

| Comercializador identificado | Códigos XM | Demanda acumulada | Participación en el conjunto analizado |
|---|---|---:|---:|
| Afinia / Caribemar | CMMC | 26,50 TWh | 10,97 % |
| Air-e | CSSC + CSIC | 26,32 TWh | 10,89 % |
| **Total utilizado como proxy Caribe** | — | **52,82 TWh** | **21,86 %** |

Estos resultados representan la participación de los agentes comerciales identificados dentro del universo de datos analizado. No deben interpretarse como el consumo territorial exacto de todos los hogares de la región Caribe.

Uno de los principales aprendizajes fue diferenciar conceptos financieros que suelen aparecer juntos, pero que tienen naturalezas distintas:

| Concepto | Interpretación general |
|---|---|
| Cartera de usuarios | Facturas vencidas pendientes de pago al comercializador. |
| Saldo de opción tarifaria | Valor tarifario diferido y recuperable posteriormente bajo las reglas regulatorias. |
| Obligaciones del Mercado de Energía Mayorista | Compromisos del comercializador con otros agentes del mercado. |
| Subsidios por cobrar | Recursos causados y pendientes de giro al prestador. |

Estos valores no deberían agregarse directamente sin revisar su fecha de corte, naturaleza económica, deudor, acreedor y posible relación contable.

## Relación entre demanda, precio y riesgo

Como ejercicio analítico se construyó el siguiente indicador:

`valor proxy mensual = demanda comercial mensual × precio promedio mensual de bolsa`

Este cálculo permite identificar meses en los que una demanda elevada habría presentado mayor sensibilidad ante precios altos de bolsa. Se trata de un **escenario contrafactual aproximado**, no del costo real de compra de energía, debido a que los comercializadores combinan contratos bilaterales y compras en bolsa.

Una mejora futura sería realizar el cálculo con información horaria:

`valor proxy mensual = suma de demanda horaria × precio horario de bolsa`

Esto permitiría representar con mayor precisión la variación conjunta entre demanda y precio.

## Propuesta de arquitectura de datos

Como parte del reto se diseñó una estructura inicial para integrar nuevas fuentes de información. El modelo contempla datos de:

- demanda y compras de energía;
- componentes tarifarios;
- facturación, recaudo y cartera;
- pérdidas técnicas y no técnicas;
- obligaciones financieras;
- subsidios;
- calidad del servicio mediante indicadores como SAIDI y SAIFI.

Entre los indicadores propuestos se encuentran la exposición a bolsa, la cobertura contractual, la tarifa efectiva por kWh, el porcentaje de recaudo, la cartera vencida, las pérdidas de energía, los subsidios pendientes y la calidad del servicio.

## Alcance y limitaciones

El conjunto de datos utilizado permite analizar demanda comercial asociada a los agentes, pero no permite obtener directamente:

- deuda individual de los hogares;
- cartera por municipio o estrato;
- valor final de cada factura;
- recaudo efectivo;
- compras reales por contratos y bolsa;
- pérdidas técnicas y no técnicas por separado;
- indicadores territoriales completos de calidad del servicio.

Para avanzar hacia un análisis territorial sería necesario integrar información del SUI, SIMEM, CREG, MinEnergía, DANE y reportes financieros de los prestadores.

## Conocimientos aplicados

Este ejercicio me permitió fortalecer competencias en:

**Python · consumo y procesamiento de datos públicos · ETL · limpieza de datos · análisis de series temporales · calidad de datos · modelado dimensional · documentación técnica · Git y GitHub · uso responsable de herramientas de inteligencia artificial para programación.**

El principal resultado no fue únicamente obtener cifras, sino aprender a documentar supuestos, reconocer limitaciones y diferenciar entre un indicador exploratorio y una conclusión financiera oficial.

## Fuentes oficiales consultadas

- [XM: glosario e información del mercado eléctrico](https://www.xm.com.co/herramientas/glosario-xm)
- [CREG: componentes del costo unitario y opción tarifaria](https://normograma.superservicios.gov.co/NORMOGRAMA/compilacion/docs/concepto_creg_0002921_2025.htm)
- [MinEnergía: documentos relacionados con el mercado eléctrico de la región Caribe](https://www.minenergia.gov.co/documents/14754/Memoria_justificativa_MERCADO_REGION_CARIBE_24102025.pdf)
- [Superservicios: seguimiento a la prestación del servicio de Air-e](https://superservicios.gov.co/Sala-de-prensa/noticias/un-ano-de-la-intervencion-de-air-e-la-superservicios-ha-garantizado-la-prestacion-del-servicio-de-energia-los-14-millones-de-usuarios)

---