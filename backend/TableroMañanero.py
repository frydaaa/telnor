from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import tempfile
import os
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

def leer_con_encabezado(path, sheet_name=0, key="SGS", max_rows=80):
    temp = pd.read_excel(path, sheet_name=sheet_name, header=None, nrows=max_rows)
    header_row = None
    for i, row in temp.iterrows():
        if row.astype(str).str.contains(key, case=False, na=False).any():
            header_row = i
            break
    if header_row is None:
        df = pd.read_excel(path, sheet_name=sheet_name)
    else:
        df = pd.read_excel(path, sheet_name=sheet_name, header=header_row)
    df.columns = df.columns.astype(str).str.replace("\u00a0", " ").str.strip()
    return df

def _ensure_columns(df, mapping):
    for target, candidates in mapping.items():
        if target in df.columns:
            continue
        for cand in candidates:
            if cand in df.columns:
                df[target] = df[cand]
                break
    return df

def _missing_columns(df, required):
    return [c for c in required if c not in df.columns]

@app.post("/procesar")
async def procesar_archivos(
    documento: UploadFile = File(...),
    base: UploadFile = File(...),
    semana: int = Form(6)
):
    with tempfile.TemporaryDirectory() as tmp:
        doc_path = os.path.join(tmp, documento.filename)
        base_path = os.path.join(tmp, base.filename)

        with open(doc_path, "wb") as f:
            f.write(await documento.read())

        with open(base_path, "wb") as f:
            f.write(await base.read())

        # Documento
        df_ND = leer_con_encabezado(doc_path, sheet_name=0, key="SGS")
        df_ND.columns = df_ND.columns.str.upper()
        df_ND = df_ND.iloc[:, :6]

        if "SGS" not in df_ND.columns:
            return JSONResponse({"error": f"No encontré SGS en df_ND. Columnas: {df_ND.columns.tolist()}"}, status_code=400)

        df_ND = _ensure_columns(
            df_ND,
            {
                "PROG": ["PROGRAMA"],
                "DIST": ["DISTRITO"],
                "PTOS": ["PUERTOS", "PUERTOS CONSTRUIDOS", "PUERTOS_CONSTRUIDOS"],
                "PON": ["PON", "PON ", "PON."],
                "TERMINAL": ["TERMINALES", "TERMINAL", "TERMINAL."],
            },
        )

        faltantes_nd = _missing_columns(df_ND, ["PROG", "SGS", "DIST", "PTOS", "PON", "TERMINAL"])
        if faltantes_nd:
            return JSONResponse(
                {"error": f"Faltan columnas en documento: {faltantes_nd}. Columnas: {df_ND.columns.tolist()}"},
                status_code=400,
            )

        df_ND["SGS"] = df_ND["SGS"].fillna("N/A", inplace=False)

        # Base BD
        df_TP = leer_con_encabezado(base_path, sheet_name="BD", key="SGS")
        df_TP.columns = df_TP.columns.str.upper()

        if str(df_TP.columns[0]).startswith("Unnamed"):
            df_TP = df_TP.drop(columns=[df_TP.columns[0]])

        df_TP = _ensure_columns(
            df_TP,
            {
                "TERMINALES": ["TERMINAL"],
                "DISTRITO": ["DIST"],
                "SEM PROG": ["SEMPROG", "SEMANA", "SEMANA PROG"],
            },
        )

        faltantes_tp = _missing_columns(df_TP, ["SGS", "DISTRITO", "TERMINALES", "SEM PROG"])
        if faltantes_tp:
            return JSONResponse(
                {"error": f"Faltan columnas en BD: {faltantes_tp}. Columnas: {df_TP.columns.tolist()}"},
                status_code=400,
            )

        df_TP = df_TP.iloc[:, :19]
        df_TP["PUENTES"] = df_TP["PUENTES"].fillna("N/A", inplace=False)
        df_TP = df_TP[df_TP["SEM PROG"].isin([semana])].reset_index(drop=True)

        # Comparación
        y = 0
        df_C = pd.DataFrame(columns=["BUSCA X SGS","B X DISTRITO", "Ter x Dis", "¿Igual?"])

        for i in range(len(df_ND)):
            for n in range(len(df_TP)):
                if df_ND.loc[i, "SGS"] == df_TP.loc[n, "SGS"]:
                    df_C.loc[y, "BUSCA X SGS"] = df_TP.loc[n, "TERMINALES"]
                    y += 1
                    break
            else:
                df_C.loc[y, "BUSCA X SGS"] = "N/A"
                y += 1

        y = 0
        for i in range(len(df_ND)):
            for n in range(len(df_TP)):
                if df_ND.loc[i, "DIST"] == df_TP.loc[n, "DISTRITO"]:
                    df_C.loc[y, "B X DISTRITO"] = df_TP.loc[n, "SGS"]
                    y += 1
                    break
            else:
                df_C.loc[y, "B X DISTRITO"] = "N/A"
                y += 1

        y = 0
        for i in range(len(df_ND)):
            for n in range(len(df_TP)):
                if df_ND.loc[i, "DIST"] == df_TP.loc[n, "DISTRITO"]:
                    df_C.loc[y, "Ter x Dis"] = df_TP.loc[n, "TERMINALES"]
                    y += 1
                    break
            else:
                df_C.loc[y, "Ter x Dis"] = "N/A"
                y += 1

        for i in range(len(df_C)):
            if df_C.loc[i, "B X DISTRITO"] == df_ND.loc[i, "SGS"]:
                if df_ND.loc[i, "SGS"] == "N/A":
                    df_C.loc[i, "¿Igual?"] = "N/A"
                else:
                    df_C.loc[i, "¿Igual?"] = "SI"
            else:
                if df_C.loc[i, "BUSCA X SGS"] == "N/A" and df_C.loc[i, "B X DISTRITO"] == "N/A" and df_C.loc[i, "Ter x Dis"] == "N/A":
                    df_C.loc[i, "¿Igual?"] = "N/A"
                else:
                    df_C.loc[i, "¿Igual?"] = "NO"

        df = pd.concat([df_ND, df_C], axis=1)
        df = df[df['¿Igual?'].isin(["NO", "N/A"])].reset_index(drop=True)
        df["B X DISTRITO"] = df["B X DISTRITO"].fillna("N/A", inplace=False)

        df_NR = pd.DataFrame(columns=["PROG", "SGS", "DIST", "PTOS", "PON", "TERMINAL"])
        y = 0
        for i in range(len(df)):
            if df.loc[i, "¿Igual?"] == "N/A":
                df_NR.loc[y] = [df.loc[i, "PROG"], df.loc[i, "SGS"], df.loc[i, "DIST"], df.loc[i, "PTOS"], df.loc[i, "PON"], df.loc[i, "TERMINAL"]]
                y += 1
            elif df.loc[i, "TERMINAL"] != df.loc[i, "Ter x Dis"]:
                df_NR.loc[y] = [df.loc[i, "PROG"], df.loc[i, "SGS"], df.loc[i, "DIST"], df.loc[i, "PTOS"], df.loc[i, "PON"], df.loc[i, "TERMINAL"]]
                y += 1

        df_SGS = pd.DataFrame(columns=["SGS", "DIST", "TERMINAL"])
        y = 0
        for i in range(len(df)):
            if df.loc[i, "B X DISTRITO"] == "N/A" and df.loc[i, "TERMINAL"] == df.loc[i, "Ter x Dis"]:
                df_SGS.loc[y] = [df.loc[i, "SGS"], df.loc[i, "DIST"], df.loc[i, "TERMINAL"]]
                y += 1

        # KPIs + Hist
        total_registros = len(df_TP)
        programas_unicos = df_TP["PROGRAMA"].nunique() if "PROGRAMA" in df_TP.columns else 0
        servicios_unicos = df_TP["SERVICIO"].nunique() if "SERVICIO" in df_TP.columns else 0

        if "PRG_FIRM" in df_TP.columns:
            firm_count = df_TP["PRG_FIRM"].fillna("").astype(str).str.strip().ne("").sum()
            prg_firm_pct = round((firm_count / len(df_TP)) * 100, 2) if len(df_TP) else 0
        else:
            prg_firm_pct = 0

        hist_mes = df_TP["MES"].value_counts().head(6).to_dict() if "MES" in df_TP.columns else {}
        hist_serv = df_TP["SERVICIO"].value_counts().head(6).to_dict() if "SERVICIO" in df_TP.columns else {}

        preview = df_ND.head(5).to_dict(orient="records")

        # Archivo principal
        out_path = os.path.join(tmp, "diferencias.xlsx")
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            df_NR.to_excel(writer, index=False, sheet_name="Nuevos_Registros")
            df_SGS.to_excel(writer, index=False, sheet_name="Registrar_SGS")
            df.to_excel(writer, index=False, sheet_name="Faltantes")

        file_id = str(uuid.uuid4())
        saved_path = os.path.join(tempfile.gettempdir(), f"{file_id}.xlsx")
        with open(out_path, "rb") as src, open(saved_path, "wb") as dst:
            dst.write(src.read())
        DOWNLOADS[file_id] = saved_path

        # Archivo df_SGS
        sgs_path = os.path.join(tmp, "df_sgs.xlsx")
        df_SGS.to_excel(sgs_path, index=False)
        sgs_id = str(uuid.uuid4())
        saved_sgs = os.path.join(tempfile.gettempdir(), f"{sgs_id}.xlsx")
        with open(sgs_path, "rb") as src, open(saved_sgs, "wb") as dst:
            dst.write(src.read())
        DOWNLOADS[sgs_id] = saved_sgs

        return {
            "kpis": {
                "total": total_registros,
                "programas": programas_unicos,
                "servicios": servicios_unicos,
                "prg_firm_pct": prg_firm_pct
            },
            "hist_mes": hist_mes,
            "hist_serv": hist_serv,
            "preview": preview,
            "download_id": file_id,
            "download_sgs_id": sgs_id
        }

@app.get("/descargar/{file_id}")
def descargar(file_id: str):
    if file_id not in DOWNLOADS:
        return JSONResponse({"error": "Archivo no encontrado"}, status_code=404)
    path = DOWNLOADS[file_id]
    return FileResponse(path, filename="diferencias.xlsx")
