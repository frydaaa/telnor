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

@app.post("/procesar")
async def procesar_archivos(
    documento: UploadFile = File(...),
    base: UploadFile = File(...),
    semana: int = Form(6)  # <-- SEM viene del frontend
):
    with tempfile.TemporaryDirectory() as tmp:
        doc_path = os.path.join(tmp, documento.filename)
        base_path = os.path.join(tmp, base.filename)

        with open(doc_path, "wb") as f:
            f.write(await documento.read())

        with open(base_path, "wb") as f:
            f.write(await base.read())

        # === TU LÓGICA ===
        df_ND = pd.read_excel(doc_path)
        df_ND = df_ND.iloc[:, :6]
        df_ND["SGS"] = df_ND["SGS"].fillna('N/A', inplace=False)

        df_ESGS = pd.read_excel(base_path, sheet_name="cat_eFTTH")
        df_ESGS = df_ESGS.iloc[:, 5:7]

        df_GZ = pd.read_excel(base_path, sheet_name="GZ")
        df_GZ = df_GZ.iloc[:, :11]

        Sem = semana  # <-- ahora depende del frontend

        df_TP = pd.read_excel(base_path, sheet_name="BD")
        df_TP = df_TP.iloc[12:].reset_index(drop=True)
        df_TP = df_TP.drop(df_TP.columns[:1], axis=1)
        df_TP.columns = df_TP.iloc[0]
        df_TP = df_TP.iloc[1:].reset_index(drop=True)
        df_TP = df_TP.iloc[:, :19]
        df_TP["PUENTES"] = df_TP['PUENTES'].fillna('N/A', inplace=False)
        df_TP = df_TP[df_TP['SEM PROG'].isin([Sem])].reset_index(drop=True)

        y = 0
        df_C = pd.DataFrame(columns=["BUSCA X SGS","B X DISTRITO", "Ter x Dis", "¿Igual?"])

        for i in range(len(df_ND)):
            for n in range(len(df_TP)):
                if df_ND.loc[i, "SGS"] == df_TP.loc[n, "SGS"]:
                    df_C.loc[y, "BUSCA X SGS"] = df_TP.loc[n, "Terminales"]
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
                    df_C.loc[y, "Ter x Dis"] = df_TP.loc[n, "Terminales"]
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
        df["B X DISTRITO"] = df["B X DISTRITO"].fillna('N/A', inplace=False)

        df_NR = pd.DataFrame(columns=["PROG", "SGS", "DIST", "PTOS", "Pon", "Terminal"])
        y = 0
        for i in range(len(df)):
            if df.loc[i, "¿Igual?"] == "N/A":
                df_NR.loc[y] = [df.loc[i, "PROG"], df.loc[i, "SGS"], df.loc[i, "DIST"], df.loc[i, "PTOS"], df.loc[i, "Pon"], df.loc[i, "Terminal"]]
                y += 1
            elif df.loc[i, "Terminal"] != df.loc[i, "Ter x Dis"]:
                df_NR.loc[y] = [df.loc[i, "PROG"], df.loc[i, "SGS"], df.loc[i, "DIST"], df.loc[i, "PTOS"], df.loc[i, "Pon"], df.loc[i, "Terminal"]]
                y += 1

        for i in range(len(df_NR)):
            for n in range(len(df)):
                if df_NR.loc[i, "PROG"] == df.loc[n, "PROG"] and df_NR.loc[i, "SGS"] == df.loc[n, "SGS"] and df_NR.loc[i, "DIST"] == df.loc[n, "DIST"] and df_NR.loc[i, "Terminal"] == df.loc[n, "Terminal"]:
                    df.drop(n, inplace=True)
                    df.reset_index(drop=True, inplace=True)
                    break

        df_SGS = pd.DataFrame(columns=["SGS", "DIST", "Terminal"])
        y = 0
        for i in range(len(df)):
            if df.loc[i, "B X DISTRITO"] == "N/A" and df.loc[i, "Terminal"] == df.loc[i, "Ter x Dis"]:
                df_SGS.loc[y] = [df.loc[i, "SGS"], df.loc[i, "DIST"], df.loc[i, "Terminal"]]
                y += 1

        for i in (df_SGS.index):
            for n in (df).index:
                if df_SGS.loc[i, "SGS"] == df.loc[n, "SGS"] and df_SGS.loc[i, "DIST"] == df.loc[n, "DIST"] and df_SGS.loc[i, "Terminal"] == df.loc[n, "Terminal"]:
                    df.drop(n, inplace=True)
                    df.reset_index(drop=True, inplace=True)
                    break

        i = 0
        while i < len(df):
            if df.loc[i, "Terminal"] == df.loc[i, "Ter x Dis"]:
                df.drop(i, inplace=True)
                df.reset_index(drop=True, inplace=True)
            else:
                i += 1

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
