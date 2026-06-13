# TP2 — Sistema Multi-Agente de Soporte Clínico para Diabetes

## Setup

1. Clonar el repo
2. Instalar uv: https://docs.astral.sh/uv/
3. Crear entorno e instalar dependencias:
   ```bash
   uv venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate  # Linux/macOS
   uv sync
   ```
4. Configurar variables de entorno:
   ```bash
   cp .env.example .env
   # completar con tus claves
   ```
5. Generar datos sintéticos:
   ```bash
   python data/generate_patients.py
   ```
6. Indexar guías clínicas:
   ```bash
   python rag/ingest.py
   ```
7. Levantar la interfaz:
   ```bash
   streamlit run interface/app.py
   ```
