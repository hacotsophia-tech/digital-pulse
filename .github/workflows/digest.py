#!/usr/bin/env python3
"""
Digital Pulse — genera latest.json con el digest diario de noticias de IA.

Llama a la API de Google Gemini con la herramienta de búsqueda web y escribe un
único archivo JSON en la raíz del repo. El historial queda en los commits de git.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import google.generativeai as genai

MODEL = "gemini-3.7-flash"
MAX_SEARCHES = 14
OUTPUT = "latest.json"

CATEGORIAS = ["Modelos", "Automation-NoCode", "Contenido", "Marketing-SMM", "Análisis"]

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

ART = timezone(timedelta(hours=-3))


def build_prompt(hoy: datetime) -> str:
    fecha = hoy.strftime("%Y-%m-%d")
    dia = DIAS[hoy.weekday()]
    return f"""Sos un editor de noticias de IA. Hoy es {dia} {fecha} (hora de Argentina).
Armá un digest curado de las noticias de IA de las últimas ~24 horas.
Todo el texto va en ESPAÑOL rioplatense, tono directo, sin relleno ni adjetivos de marketing.

CONTEXTO DE LA LECTORA
Sophie, conduce el podcast "THS the hacotidrama's show". Estudia AI automation,
full stack y creación de contenido con IA. Quiere ver de un vistazo lo importante
del día con links a las fuentes.

PASO 1 — BUSCAR (exhaustivo)
Buscá noticias, lanzamientos y análisis de las últimas 24 horas. Prioridad, en este orden:
1. Lanzamientos y updates de modelos y funciones nuevas (OpenAI, Anthropic/Claude,
   Google DeepMind/Gemini, Meta/Llama, Mistral, xAI, DeepSeek, Qwen y otros).
2. AI automation y herramientas no-code/low-code para builders (agentes, workflows,
   n8n, Make, Zapier AI, etc.).
3. IA para creación de contenido: escritura, video, audio/voz, imagen.
4. IA para branding, marketing y social media (SMM, growth, herramientas de marketing).
5. Análisis y opinión de referentes: tendencias, ética, carreras y mercado laboral en IA.

Fuentes de referencia (NO te limites a estas, hacé también búsqueda abierta):
- Breaking/producto: TechCrunch AI, The Verge AI, VentureBeat AI, ZDNet AI, Ars Technica AI.
- Newsletters: TLDR AI, The Rundown AI, Ben's Bites, Superhuman AI.
- Técnico/modelos: The Decoder, MarkTechPost, Hugging Face Blog, Synced.
- Análisis: MIT Technology Review (AI), The Batch (DeepLearning.AI), Import AI, Latent Space, Stanford HAI.
- Fuentes primarias: blogs de OpenAI, Anthropic, Google DeepMind, Meta AI, NVIDIA AI, Mistral.
- Marketing/contenido: HubSpot, Marketing AI Institute, y lanzamientos de Canva, Runway,
  ElevenLabs, HeyGen, Descript.

Verificá que cada ítem venga de fuente confiable y sea de las últimas 24 h (o muy reciente).
Descartá rumores sin fuente y contenido promocional disfrazado de noticia.

PASO 2 — CURAR
Elegí entre 8 y 12 ítems, los de mayor señal. Evitá duplicados: si tres medios cubren lo
mismo, un solo ítem con el mejor link. Si el día está flojo de novedades, poné menos ítems
y marcá "hay_novedades": false. No infles el digest.

PASO 3 — SALIDA
Respondé ÚNICAMENTE con un objeto JSON válido, sin texto antes ni después, sin bloque de
código markdown. Esta es la estructura exacta:

{{
  "fecha": "{fecha}",
  "dia_semana": "{dia}",
  "hay_novedades": true,
  "resumen_dia": [
    "2 o 3 strings con lo imperdible del día, una línea cada uno"
  ],
  "items": [
    {{
      "titulo": "título corto en español",
      "resumen": "2-3 líneas: qué pasó y por qué importa",
      "url": "link directo a la fuente",
      "fuente": "nombre del medio o empresa",
      "categoria": "una de: {' | '.join(CATEGORIAS)}"
    }}
  ],
  "para_ths": "1-2 líneas conectando alguna noticia del día con ideas de guion para el podcast o con creación de contenido/no-code. String vacío si no hay nada relevante."
}}
"""


def extract_json(text: str) -> dict:
    """Saca el objeto JSON de la respuesta, tolerando fences o texto suelto."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("No se encontró ningún objeto JSON en la respuesta.")
        text = text[start : end + 1]
    return json.loads(text)


def validate(data: dict) -> None:
    for key in ("fecha", "dia_semana", "hay_novedades", "resumen_dia", "items", "para_ths"):
        if key not in data:
            raise ValueError(f"Falta la clave obligatoria '{key}' en el JSON.")
    if not isinstance(data["items"], list) or not data["items"]:
        raise ValueError("'items' tiene que ser una lista con al menos un elemento.")
    for i, item in enumerate(data["items"]):
        for key in ("titulo", "resumen", "url", "fuente", "categoria"):
            if not item.get(key):
                raise ValueError(f"items[{i}] no tiene '{key}'.")
        if not item["url"].startswith("http"):
            raise ValueError(f"items[{i}] tiene una url inválida: {item['url']}")
        if item["categoria"] not in CATEGORIAS:
            raise ValueError(
                f"items[{i}] tiene categoría inválida '{item['categoria']}'. "
                f"Válidas: {CATEGORIAS}"
            )


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: falta el secret ANTHROPIC_API_KEY.", file=sys.stderr)
        return 1

    hoy = datetime.now(ART)
    client = anthropic.Anthropic()

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": build_prompt(hoy)}],
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": MAX_SEARCHES,
            }
        ],
    )

    text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text")
    data = extract_json(text)
    validate(data)

    data["generado_en"] = hoy.isoformat(timespec="seconds")
    data["modelo"] = MODEL

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"OK — {len(data['items'])} ítems escritos en {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
