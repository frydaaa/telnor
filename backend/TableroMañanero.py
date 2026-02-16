from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import tempfile
import os
import re
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DOWNLOADS = {}

HOJA_OBJETIVO = "Nodos"
OUTPUT_FILE_NAME = "semaforo_limpio.xlsx"


@app.get("/")
def root():
    return {"status": "ok", "message": "Backend LimpiezaControl activo"}


def limpiar_probe_group_device(valor):
    if pd.isna(valor):
        return ""
    if not isinstance(valor, str):
        valor = str(valor)
    valor = valor.replace("\u00a0", " ")
    valor = re.sub(r"\s+", " ", valor).strip()
    partes = re.split(r"\s*»\s*", valor)
    valor = partes[-1].strip()
    valor = valor.split(".", 1)[0].strip()
    return valor


def limpiar_kbits(valor):
    if pd.isna(valor):
        return None
    if isinstance(valor, (int, float)):
        return valor
    valor = str(valor).replace("\u00a0", " ").strip()
    valor = re.sub(r"\s*kbits?/s\s*$", "", valor, flags=re.IGNORECASE).strip()
    valor = valor.replace(",", "")
    return pd.to_numeric(valor, errors="coerce")


def extraer_vlan(sensor_val):
    if pd.isna(sensor_val):
        return None
    s = str(sensor_val).replace("\u00a0", " ").strip()
    m = re.search(r":\s*\d+\.(\d+)", s)
    if m:
        return pd.to_numeric(m.group(1), errors="coerce")
    m = re.search(r"/\s*\d+\.(\d+)", s)
    if m:
        return pd.to_numeric(m.group(1), errors="coerce")
    return None


def extraer_nom_equipo(sensor_val):
    if pd.isna(sensor_val):
        return ""
    s = str(sensor_val).replace("\u00a0", " ").strip()
    m = re.search(r"DSL\[[^\]]+\]\[([^\]]+)\]", s, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return ""


def _buscar_fila_encabezado(df_temp):
    for idx, row in df_temp.iterrows():
        fila = row.astype(str).str.lower().str.strip()
        if fila.str.contains("sensor").any():
            return idx
    return -1


async def _limpiar_impl(archivo: UploadFile):
    with tempfile.TemporaryDirectory() as tmp:
        input_path = os.path.join(tmp, archivo.filename)
        with open(input_path, "wb") as f:
            f.write(await archivo.read())

        # ✅ Detectar hoja (usa "Nodos" si existe, si no la primera)
        xls = pd.ExcelFile(input_path)
        hoja_usar = HOJA_OBJETIVO if HOJA_OBJETIVO in xls.sheet_names else xls.sheet_names[0]

        # ✅ Buscar fila de encabezado
        df_temp = pd.read_excel(input_path, sheet_name=hoja_usar, header=None, nrows=60)
        fila_encabezado = _buscar_fila_encabezado(df_temp)
        if fila_encabezado == -1:
            return JSONResponse({"error": "No encontré la fila que contiene 'Sensor'."}, status_code=400)

        df = pd.read_excel(input_path, sheet_name=hoja_usar, header=fila_encabezado)

        # ✅ Limpiar encabezados
        df.columns = (
            df.columns.astype(str)
            .str.replace("\u00a0", " ")
            .str.strip()
        )
        df = df.loc[:, ~df.columns.str.contains(r"^Unnamed", na=False)]

        if "Probe Group Device" in df.columns:
            df["Probe Group Device"] = df["Probe Group Device"].apply(limpiar_probe_group_device)
        else:
            return JSONResponse({"error": "No encontré la columna 'Probe Group Device'."}, status_code=400)

        columnas_velocidad = [c for c in df.columns if c.strip().lower() in ["average","minimum","maximum","percentile","percentil"]]
        for col in columnas_velocidad:
            df[col] = df[col].apply(limpiar_kbits)

        if "Sensor" in df.columns:
            df["VLAN"] = df["Sensor"].apply(extraer_vlan)
            df["NomEquipo"] = df["Sensor"].apply(extraer_nom_equipo)

        col_percentil = next((c for c in df.columns if c.strip().lower() in ["percentile","percentil"]), None)
        if col_percentil:
            df[col_percentil] = pd.to_numeric(df[col_percentil], errors="coerce")
            df = df.sort_values(by=col_percentil, ascending=False)

        if "Sensor" in df.columns:
            df = df.dropna(subset=["Sensor"])
            df = df[df["Sensor"].astype(str).str.strip() != ""]

        df = df.fillna("")

        if "NomEquipo" in df.columns:
            columnas = ["NomEquipo"] + [c for c in df.columns if c != "NomEquipo"]
            df = df[columnas]

        # ✅ Guardar archivo limpio
        output_path = os.path.join(tmp, OUTPUT_FILE_NAME)
        df.to_excel(output_path, index=False)

        file_id = str(uuid.uuid4())
        saved_path = os.path.join(tempfile.gettempdir(), f"{file_id}.xlsx")
        with open(output_path, "rb") as src, open(saved_path, "wb") as dst:
            dst.write(src.read())

        DOWNLOADS[file_id] = saved_path
        return {"message": "Limpieza completada", "download_id": file_id}


@app.post("/limpiar")
async def limpiar_archivo(archivo: UploadFile = File(...)):
    return await _limpiar_impl(archivo)

# Alias opcional si accidentalmente llaman /procesar
@app.post("/procesar")
async def procesar_alias(archivo: UploadFile = File(...)):
    return await _limpiar_impl(archivo)


@app.get("/descargar/{file_id}")
def descargar(file_id: str):
    if file_id not in DOWNLOADS:
        return JSONResponse({"error": "Archivo no encontrado"}, status_code=404)
    path = DOWNLOADS[file_id]
    return FileResponse(path, filename=OUTPUT_FILE_NAME)
