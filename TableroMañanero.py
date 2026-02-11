import pandas as pd


#Tabla con Nuevos Datos a agregar 
df_ND = pd.read_excel("Distritos nuevos Mara.xlsx")
df_ND = df_ND.iloc[:, :6]
df_ND["SGS"] = df_ND["SGS"].fillna('N/A', inplace=False)


#Tabla de Estados SGS
df_ESGS = pd.read_excel("Seguimiento PROGRAMAS FTTH-TBA_202604_Feb.xlsm", sheet_name="cat_eFTTH")
df_ESGS = df_ESGS.iloc[:, 5:7]  

#Tabla de Regiones
df_GZ = pd.read_excel("Seguimiento PROGRAMAS FTTH-TBA_202604_Feb.xlsm", sheet_name="GZ")
df_GZ = df_GZ.iloc[:, :11]

Sem = 6

#Tabla Principal
df_TP = pd.read_excel("Seguimiento PROGRAMAS FTTH-TBA_202604_Feb.xlsm", sheet_name="BD")
df_TP = df_TP.iloc[12:].reset_index(drop=True)
df_TP = df_TP.drop(df_TP.columns[:1], axis=1)
df_TP.columns = df_TP.iloc[0]
df_TP = df_TP.iloc[1:].reset_index(drop=True)
df_TP = df_TP.iloc[:, :19]
df_TP["PUENTES"] = df_TP['PUENTES'].fillna('N/A', inplace=False)
df_TP = df_TP[df_TP['SEM PROG'].isin([Sem])].reset_index(drop=True)


y = 0
df_C = pd.DataFrame(columns=["BUSCA X SGS","B X DISTRITO", "Ter x Dis", "¿Igual?"])

# Busqueda de SGS
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


# Busqueda de Distrito
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

# Busqueda de Terminales por Distrito
for i in range(len(df_ND)):
    for n in range(len(df_TP)):
        if df_ND.loc[i, "DIST"] == df_TP.loc[n, "DISTRITO"]:
            df_C.loc[y, "Ter x Dis"] = df_TP.loc[n, "Terminales"]
            y += 1
            break
    else:
        df_C.loc[y, "Ter x Dis"] = "N/A"
        y += 1

# Comparacion
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

"""print("Tabla Completa Antes de la Clasificacion:\n")
print(df,"\n")
print("--"*50,"\n")"""

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


            
"""print("Faltantes por clasificar:\n")
print(df,"\n")
print("--"*50,"\n")

print("Registrar solamente la clave SGS:\n")
print(df_SGS,"\n")
print("--"*50,"\n")"""

print("Nuevos Registros:\n")
print(df_NR,"\n")
print("--"*50,"\n")

print("Tabla principal:\n")
print(df_TP.iloc[:, 0:6].head(),"\n")
print("=="*25,"\n")
print(df_TP.iloc[:, 7:13].head(),"\n")
print("=="*25,"\n")
print(df_TP.iloc[:, 14:19].head(),"\n")
print("=="*25,"\n")
print(df_TP.columns,"\n")
print("--"*50,"\n")

print(df_ESGS.head(),"\n")
print("--"*50,"\n")
print(df_GZ.head(),"\n")

def zona_comercial(distrito):
    for i in range(len(df_GZ)):
        if df_GZ.loc[i, "DISTRITO"] == distrito:
            break
        return df_GZ.loc[i, "Zona"]
    
def prioridad_etapa(estado):
    for n in range(len(df_ESGS)):
        if df_ESGS.loc[n, "ESTADO"] == estado:
            break
        return df_ESGS.loc[n, "PRIORIDAD"]
            


"""# Agregar Nuevos Registros a la Tabla Principal
for i in range(len(df_NR)):

    df_TP.loc[len(df_TP), "GENERICO"] = "7. OTROS"

    df_TP.loc[len(df_TP), "PROGRAMA"] = df_NR.loc[i, "PROG"]
    
    df_TP.loc[len(df_TP), "SEM PROG"] = Sem
    
    df_TP.loc[len(df_TP), "DISTRITO"] = df_NR.loc[i, "DIST"]

    df_TP.loc[len(df_TP), "SGS"] = (
        df_NR.loc[i, "SGS"] if df_NR.loc[i, "SGS"] != "N/A" else ""
    )

    df_TP.loc[len(df_TP), "Terminales"] = df_NR.loc[i, "Terminal"]

    df_TP.loc[len(df_TP), "Puertos Construidos"] = df_NR.loc[i, "PTOS"]

    df_TP.loc[len(df_TP), "Prioridad etapa"] = (
        
    )

    df_TP.loc[len(df_TP), "ZONA COMERCIAL"] = zona_comercial(df_NR.loc[i, "DIST"])

    df_TP.loc[len(df_TP), "COPE"] = (

    )

    df_TP.loc[len(df_TP), "LOCALIDAD"] = (

    )

    df_TP.loc[len(df_TP), "FECHA PROG"] = (

    )

    df_TP.loc[len(df_TP), "FECHA PES"] = (

    )

    df_TP.loc[len(df_TP), "ETAPA SGS ACTUALIZADO"] = (

    )

    df_TP.loc[len(df_TP), "PUENTES"] = (

    )

    df_TP.loc[len(df_TP), "FastTrack"] = (

    )

    df_TP.loc[len(df_TP), "Comentarios"] = (

    )"""