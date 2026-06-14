"""
Se carga el archivo .env para que las variables de entorno estén disponibles durante la ejecución de los tests.
Pytest busca automáticamente este archivo en el directorio de tests antes de correr cualquier test. 
"""

import os
from dotenv import load_dotenv

load_dotenv()
