# TEL354 Lab 4 SDN

CLI en Python 3 para administrar conexiones proactivas en Floodlight 1.2 usando `staticflowpusher`.

## Archivos
- `lab4_sdn.py`: aplicación principal.
- `sample_data.yaml`: dataset de ejemplo.
- `test_lab4_sdn.py`: pruebas básicas.

## Requisitos
- Python 3.12+
- `requests`
- `PyYAML` es opcional. Si no está instalado, la app usa un parser YAML simple incluido en el proyecto.

## Uso
```powershell
python .\lab4_sdn.py --data .\sample_data.yaml --controller http://127.0.0.1:8080
```

## Flujo sugerido
1. Cargar el YAML con `Importar` o `--data`.
2. Revisar `Cursos`, `Alumnos` y `Servidores`.
3. Crear una conexión desde `Conexiones > Crear`.
4. Verificar los flows en Floodlight.
5. Borrar la conexión con el `handler`.

## Pruebas
```powershell
python -m unittest .\test_lab4_sdn.py -v
```
