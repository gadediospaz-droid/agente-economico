# Agente Económico IA

Agente de IA con interfaz de chat en Streamlit, desarrollado para el curso de Data Analytics (Universidad Rafael Landívar, 2026).

## Qué hace
Responde preguntas económicas usando datos reales en vez de inventar cifras. El modelo decide qué herramienta necesita, la ejecuta y explica el resultado, con gráficas cuando aplica.

## Componentes
- **Cerebro:** modelo de Groq (openai/gpt-oss-120b)
- **Memoria:** historial de la conversación
- **Herramientas:** 7 funciones conectadas a APIs públicas
- **Objetivo:** definido en el system prompt
- **Persistencia:** Supabase (registro de consultas)

## Herramientas
| Herramienta | Fuente |
|---|---|
| Tipo de cambio actual | Frankfurter (BCE) / Open Exchange Rate |
| Conversión de montos | Frankfurter (BCE) / Open Exchange Rate |
| Histórico de tipo de cambio | Frankfurter (BCE) |
| Precio de criptomonedas | CoinGecko |
| Indicadores macroeconómicos | Banco Mundial |
| Comparación de monedas | Open Exchange Rate |
| Fecha y hora | Zona horaria local |

## Ejecución local
```bash
pip install -r requirements.txt
streamlit run app.py
```
Requiere un archivo `.env` con `GROQ_API_KEY`.
