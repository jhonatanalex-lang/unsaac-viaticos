import requests
import re

def test_ruc(ruc):
    url = "https://www.datosperu.org/buscador_empresas.php"
    params = {"buscar": ruc}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    r = requests.get(url, params=params, headers=headers, timeout=6)
    links = re.findall(r'href="(/empresa-[^"]+)"', r.text)
    print("Links encontrados para", ruc, ":", links)
    if links:
        url_comp = "https://www.datosperu.org" + links[0]
        r_comp = requests.get(url_comp, headers=headers, timeout=6)
        html = r_comp.text
        
        # Extraer Estado
        match_est = re.search(r"Estado\s*(?:del\s*Contribuyente)?\s*:?\s*</td>\s*<td[^>]*>\s*([^<]+)", html, re.I)
        # Extraer Condicion
        match_cond = re.search(r"Condici[oó]n\s*(?:del\s*Contribuyente)?\s*:?\s*</td>\s*<td[^>]*>\s*([^<]+)", html, re.I)
        # Extraer Actividad Economica / CIIU
        match_act = re.search(r"(?:Actividad\s*Econ[oó]mica|CIIU)\s*:?\s*</td>\s*<td[^>]*>\s*([^<]+)", html, re.I)
        
        print("Estado:", match_est.group(1).strip() if match_est else "N/D")
        print("Condicion:", match_cond.group(1).strip() if match_cond else "N/D")
        print("Actividad:", match_act.group(1).strip() if match_act else "N/D")

if __name__ == "__main__":
    test_ruc("10072486892")
    test_ruc("20100047218")
