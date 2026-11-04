from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests

TIMEOUT = 15
HEADERS = {"User-Agent": "AgenteEconomico/1.0"}


def _get(url, params=None):
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        return {"_error": f"Fallo la conexion: {e}"}


def obtener_tipo_cambio(moneda_base, moneda_destino):
    base, destino = moneda_base.upper(), moneda_destino.upper()
    data = _get("https://api.frankfurter.app/latest", {"from": base, "to": destino})
    if "_error" not in data and data.get("rates", {}).get(destino):
        return {"fuente": "Frankfurter (BCE)", "moneda_base": base,
                "moneda_destino": destino, "tasa": data["rates"][destino],
                "fecha": data.get("date")}
    data = _get(f"https://open.er-api.com/v6/latest/{base}")
    if "_error" in data:
        return {"error": data["_error"]}
    tasa = data.get("rates", {}).get(destino)
    if tasa is None:
        return {"error": f"No existe tasa de {base} a {destino}."}
    return {"fuente": "Open Exchange Rate", "moneda_base": base,
            "moneda_destino": destino, "tasa": tasa,
            "fecha": data.get("time_last_update_utc")}


def convertir_moneda(monto, moneda_origen, moneda_destino):
    tc = obtener_tipo_cambio(moneda_origen, moneda_destino)
    if "error" in tc:
        return tc
    return {"fuente": tc["fuente"], "monto_original": float(monto),
            "moneda_origen": tc["moneda_base"], "moneda_destino": tc["moneda_destino"],
            "tasa_aplicada": tc["tasa"],
            "monto_convertido": round(float(monto) * tc["tasa"], 4),
            "fecha": tc["fecha"]}


def historico_tipo_cambio(moneda_base, moneda_destino, dias=30):
    base, destino = moneda_base.upper(), moneda_destino.upper()
    dias = max(1, min(int(dias), 365))
    hasta = datetime.now().date()
    desde = hasta - timedelta(days=dias)
    data = _get(f"https://api.frankfurter.app/{desde}..{hasta}",
                {"from": base, "to": destino})
    if "_error" in data:
        return {"error": data["_error"]}
    series = data.get("rates", {})
    if not series:
        return {"error": f"Sin datos para {base}/{destino}."}
    fechas_ordenadas = sorted(series.keys())
    serie = [{"fecha": f, "tasa": series[f][destino]} for f in fechas_ordenadas if destino in series[f]]
    valores = [p["tasa"] for p in serie]
    primero, ultimo = valores[0], valores[-1]
    return {"fuente": "Frankfurter (BCE)", "par": f"{base}/{destino}",
            "periodo": f"{desde} a {hasta}", "tasa_inicial": primero,
            "tasa_final": ultimo, "minimo": min(valores), "maximo": max(valores),
            "promedio": round(sum(valores) / len(valores), 6),
            "variacion_porcentual": round(((ultimo - primero) / primero) * 100, 2),
            "observaciones": len(valores), "serie": serie}


def precio_cripto(criptomoneda, moneda="usd"):
    alias = {"btc": "bitcoin", "eth": "ethereum", "usdt": "tether",
             "bnb": "binancecoin", "sol": "solana", "xrp": "ripple",
             "ada": "cardano", "doge": "dogecoin"}
    cripto = alias.get(criptomoneda.lower().strip(), criptomoneda.lower().strip())
    fiat = moneda.lower().strip()
    data = _get("https://api.coingecko.com/api/v3/simple/price",
                {"ids": cripto, "vs_currencies": fiat,
                 "include_24hr_change": "true", "include_market_cap": "true"})
    if "_error" in data:
        return {"error": data["_error"]}
    if cripto not in data:
        return {"error": f"No se encontro '{criptomoneda}'."}
    info = data[cripto]
    return {"fuente": "CoinGecko", "criptomoneda": cripto, "moneda": fiat.upper(),
            "precio": info.get(fiat),
            "cambio_24h_porcentaje": round(info.get(f"{fiat}_24h_change", 0), 2),
            "capitalizacion_mercado": info.get(f"{fiat}_market_cap")}


INDICADORES = {"pib": "NY.GDP.MKTP.CD", "pib_per_capita": "NY.GDP.PCAP.CD",
               "crecimiento_pib": "NY.GDP.MKTP.KD.ZG", "inflacion": "FP.CPI.TOTL.ZG",
               "desempleo": "SL.UEM.TOTL.ZS", "poblacion": "SP.POP.TOTL",
               "deuda_publica": "GC.DOD.TOTL.GD.ZS", "exportaciones": "NE.EXP.GNFS.ZS"}


def indicador_macro(pais, indicador):
    clave = indicador.lower().strip()
    if clave not in INDICADORES:
        return {"error": f"Indicador '{indicador}' no disponible.",
                "validos": list(INDICADORES.keys())}
    data = _get(f"https://api.worldbank.org/v2/country/{pais.strip().upper()}"
                f"/indicator/{INDICADORES[clave]}",
                {"format": "json", "per_page": 10, "mrnev": 5})
    if isinstance(data, dict) and "_error" in data:
        return {"error": data["_error"]}
    if not isinstance(data, list) or len(data) < 2 or not data[1]:
        return {"error": f"Sin datos para {pais} / {clave}."}
    obs = [{"anio": d["date"], "valor": d["value"]} for d in data[1]
           if d.get("value") is not None]
    if not obs:
        return {"error": f"Sin valores publicados para {pais} / {clave}."}
    obs_ascendente = sorted(obs, key=lambda x: x["anio"])
    return {"fuente": "Banco Mundial", "pais": data[1][0]["country"]["value"],
            "indicador": clave, "ultimo_dato": obs_ascendente[-1],
            "serie_reciente": obs_ascendente}


def comparar_monedas(moneda_base, monedas):
    base = moneda_base.upper()
    lista = [m.strip().upper() for m in monedas.split(",") if m.strip()]
    if not lista:
        return {"error": "Indique al menos una moneda destino."}
    data = _get(f"https://open.er-api.com/v6/latest/{base}")
    if "_error" in data:
        return {"error": data["_error"]}
    rates = data.get("rates", {})
    return {"fuente": "Open Exchange Rate", "moneda_base": base,
            "tasas": {m: rates.get(m, "no disponible") for m in lista},
            "fecha": data.get("time_last_update_utc")}


def fecha_hora_actual(zona_horaria="America/Guatemala"):
    try:
        ahora = datetime.now(ZoneInfo(zona_horaria))
    except Exception:
        return {"error": f"Zona horaria '{zona_horaria}' no valida."}
    return {"zona_horaria": zona_horaria, "fecha": ahora.strftime("%Y-%m-%d"),
            "hora": ahora.strftime("%H:%M:%S"), "dia_semana": ahora.strftime("%A")}


FUNCIONES_DISPONIBLES = {
    "obtener_tipo_cambio": obtener_tipo_cambio,
    "convertir_moneda": convertir_moneda,
    "historico_tipo_cambio": historico_tipo_cambio,
    "precio_cripto": precio_cripto,
    "indicador_macro": indicador_macro,
    "comparar_monedas": comparar_monedas,
    "fecha_hora_actual": fecha_hora_actual,
}