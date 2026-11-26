def numero_a_letras(numero: float) -> str:
    """
    Convierte un número flotante a su representación en letras en español
    con formato monetario peruano (ej. 850.50 -> OCHOCIENTOS CINCUENTA CON 50/100 SOLES).
    """
    unidades = ["", "UN", "DOS", "TRES", "CUATRO", "CINCO", "SEIS", "SIETE", "OCHO", "NUEVE"]
    decenas_10 = ["DIEZ", "ONCE", "DOCE", "TRECE", "CATORCE", "QUINCE", 
                  "DIECISEIS", "DIECISIETE", "DIECIOCHO", "DIECINUEVE"]
    decenas_20 = ["VEINTE", "VEINTIUNO", "VEINTIDOS", "VEINTITRES", "VEINTICUATRO", 
                  "VEINTICINCO", "VEINTISEIS", "VEINTISIETE", "VEINTIOCHO", "VEINTINUEVE"]
    decenas = ["", "", "", "TREINTA", "CUARENTA", "CINCUENTA", "SESENTA", "SETENTA", "OCHENTA", "NOVENTA"]
    centenas = ["", "CIENTO", "DOSCIENTOS", "TRESCIENTOS", "CUATROCIENTOS", "QUINIENTOS", 
                "SEISCIENTOS", "SETECIENTOS", "OCHOCIENTOS", "NOVECIENTOS"]

    def _seccion(num: int) -> str:
        if num == 0:
            return ""
        if num == 100:
            return "CIEN"
        
        c = num // 100
        d = (num % 100) // 10
        u = num % 10
        
        partes = []
        if c > 0:
            partes.append(centenas[c])
            
        if d == 1:
            partes.append(decenas_10[u])
        elif d == 2:
            partes.append(decenas_20[u])
        elif d > 2:
            if u > 0:
                partes.append(f"{decenas[d]} Y {unidades[u]}")
            else:
                partes.append(decenas[d])
        elif u > 0:
            partes.append(unidades[u])
            
        return " ".join(partes)

    entero = int(numero)
    centavos = int(round((numero - entero) * 100))
    
    if entero == 0:
        texto_entero = "CERO"
    elif entero < 1000:
        texto_entero = _seccion(entero)
    elif entero < 1000000:
        miles = entero // 1000
        resto = entero % 1000
        str_miles = "MIL" if miles == 1 else f"{_seccion(miles)} MIL"
        str_resto = _seccion(resto)
        texto_entero = f"{str_miles} {str_resto}".strip()
    else:
        millones = entero // 1000000
        resto_millones = entero % 1000000
        miles = resto_millones // 1000
        resto = resto_millones % 1000
        str_mill = "UN MILLON" if millones == 1 else f"{_seccion(millones)} MILLONES"
        str_miles = f"{_seccion(miles)} MIL" if miles > 0 else ""
        str_resto = _seccion(resto)
        texto_entero = f"{str_mill} {str_miles} {str_resto}".strip()

    return f"{texto_entero} Y {centavos:02d}/100 SOLES"

if __name__ == "__main__":
    for val in [800.0, 1200.50, 45.0, 1500.0, 100.0]:
        print(f"{val} -> {numero_a_letras(val)}")
