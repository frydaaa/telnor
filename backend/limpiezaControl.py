import pandas as pd
import os
import re

# --- CONFIGURACIÓN ---
INPUT_FOLDER = 'input'
OUTPUT_FOLDER = 'output'
HOJA_OBJETIVO = 'Nodos'
OUTPUT_FILE_NAME = 'semaforo_limpio.xlsx'


def obtener_archivo():
    if not os.path.exists(INPUT_FOLDER):
        os.makedirs(INPUT_FOLDER)
        return None

    archivos = [
        f for f in os.listdir(INPUT_FOLDER)
        if f.endswith(('.xlsx', '.xls')) and not f.startswith('~$')
    ]
    return os.path.join(INPUT_FOLDER, archivos[0]) if archivos else None


def limpiar_probe_group_device(valor):
    """
    Local Probe » TIJUANA » BASTIJ26.TELNOR.NET -> BASTIJ26
    """
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
    """
    5,082,895 kbit/s -> 5082895 (numérico)
    """
    if pd.isna(valor):
        return None

    if isinstance(valor, (int, float)):
        return valor

    valor = str(valor).replace("\u00a0", " ").strip()

    # Quitar unidad (kbit/s, kbits/s, mayúsculas, etc.)
    valor = re.sub(r"\s*kbits?/s\s*$", "", valor, flags=re.IGNORECASE).strip()

    # Quitar comas de miles
    valor = valor.replace(",", "")

    return pd.to_numeric(valor, errors="coerce")


def extraer_vlan(sensor_val):
    """
    Extrae VLAN desde Sensor soportando:
    - xe-11/1/0:1.1775 -> 1775
    - TenGigE0/6/0/1.1431 -> 1431
    - xe-8/1/1:2.1772 -> 1772
    """
    if pd.isna(sensor_val):
        return None

    s = str(sensor_val).replace("\u00a0", " ").strip()

    # Caso A: con ":" -> :<num>.<VLAN>
    m = re.search(r":\s*\d+\.(\d+)", s)
    if m:
        return pd.to_numeric(m.group(1), errors="coerce")

    # Caso B: sin ":" -> /<num>.<VLAN>
    m = re.search(r"/\s*\d+\.(\d+)", s)
    if m:
        return pd.to_numeric(m.group(1), errors="coerce")

    return None


def extraer_nom_equipo(sensor_val):
    """
    Extrae NomEquipo desde Sensor:
    "... DSL[GPON][BCNGBAHIA-07][10G] ..." -> "BCNGBAHIA-07"
    Regla: DSL[<tecnologia>][<NomEquipo>]...
    """
    if pd.isna(sensor_val):
        return ""

    s = str(sensor_val).replace("\u00a0", " ").strip()

    m = re.search(r"DSL\[[^\]]+\]\[([^\]]+)\]", s, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()

    return ""


def procesar_datos():
    print("\n--- INICIANDO LIMPIEZA ---\n")

    ruta_archivo = obtener_archivo()
    if not ruta_archivo:
        print(" No hay archivo en la carpeta input.")
        return

    try:
        print(f" Archivo encontrado: {ruta_archivo}")

        # 1) Buscar fila de encabezado donde aparezca "Sensor"
        df_temp = pd.read_excel(
            ruta_archivo,
            sheet_name=HOJA_OBJETIVO,
            header=None,
            nrows=50
        )

        fila_encabezado = -1
        for idx, row in df_temp.iterrows():
            if "Sensor" in row.astype(str).str.cat(sep=" "):
                fila_encabezado = idx
                break

        if fila_encabezado == -1:
            print(" No encontré la fila que contiene 'Sensor'.")
            return

        # 2) Cargar datos reales
        df = pd.read_excel(
            ruta_archivo,
            sheet_name=HOJA_OBJETIVO,
            header=fila_encabezado
        )

        # 3) Limpiar encabezados y quitar columnas vacías
        df.columns = (
            df.columns
            .astype(str)
            .str.replace("\u00a0", " ")
            .str.strip()
        )
        df = df.loc[:, ~df.columns.str.contains(r"^Unnamed", na=False)]

        print(" Columnas detectadas:")
        print(df.columns.tolist())

        # 4) Limpiar Probe Group Device
        if "Probe Group Device" in df.columns:
            print(" Limpiando 'Probe Group Device'...")
            df["Probe Group Device"] = df["Probe Group Device"].apply(limpiar_probe_group_device)
            print(" Probe Group Device limpio.")
        else:
            print(" No encontré la columna 'Probe Group Device'.")
            print("DEBUG columnas (repr):", [repr(c) for c in df.columns])
            return

        # 5) Limpiar columnas de velocidad (incluye Percentile/Percentil)
        columnas_velocidad = [
            c for c in df.columns
            if c.strip().lower() in ["average", "minimum", "maximum", "percentile", "percentil"]
        ]
        for col in columnas_velocidad:
            print(f" Limpiando columna {col} (quitando kbit/s)...")
            df[col] = df[col].apply(limpiar_kbits)

        # 6) Crear VLAN y NomEquipo desde Sensor
        if "Sensor" in df.columns:
            print(" Extrayendo VLAN desde 'Sensor'")
            df["VLAN"] = df["Sensor"].apply(extraer_vlan)
            print(" Columna 'VLAN' creada.")

            print(" Extrayendo NomEquipo desde 'Sensor'...")
            df["NomEquipo"] = df["Sensor"].apply(extraer_nom_equipo)
            print(" Columna 'NomEquipo' creada.")
        else:
            print(" No existe la columna 'Sensor', no pude crear 'VLAN' ni 'NomEquipo'.")

        # 7) Ordenar por Percentile/Percentil si existe
        col_percentil = next((c for c in df.columns if c.strip().lower() in ["percentile", "percentil"]), None)
        if col_percentil:
            print(f" Ordenando por {col_percentil}...")
            df[col_percentil] = pd.to_numeric(df[col_percentil], errors="coerce")
            df = df.sort_values(by=col_percentil, ascending=False)

        # 8) Eliminar filas vacías en Sensor
        if "Sensor" in df.columns:
            df = df.dropna(subset=["Sensor"])
            df = df[df["Sensor"].astype(str).str.strip() != ""]

        df = df.fillna("")

        # 9) Reordenar columnas: NomEquipo al inicio (columna A)
        if "NomEquipo" in df.columns:
            columnas = ["NomEquipo"] + [c for c in df.columns if c != "NomEquipo"]
            df = df[columnas]
            print(" 'NomEquipo' movido a la primera columna.")

        # 10) Guardar archivo limpio
        if not os.path.exists(OUTPUT_FOLDER):
            os.makedirs(OUTPUT_FOLDER)

        ruta_salida = os.path.join(OUTPUT_FOLDER, OUTPUT_FILE_NAME)
        df.to_excel(ruta_salida, index=False)

        print("\n" + "="*50)
        print(" LIMPIEZA COMPLETADA")
        print(f"Archivo generado en: {ruta_salida}")
        print("="*50)

    except PermissionError:
        print(" El archivo de salida está abierto. Ciérralo e intenta nuevamente.")
    except Exception as e:
        print(f"\n Error inesperado: {e}")


if __name__ == "__main__":
    procesar_datos()