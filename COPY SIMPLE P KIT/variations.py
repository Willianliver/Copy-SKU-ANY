# copy_kit_from_excel.py
import requests
import json
import pandas as pd
import time
import csv
import os

# ========== CONFIGURAÇÕES ==========
API_URL_GET = "https://api.anymarket.com.br/v2/products/{id}"
API_URL_POST = "https://api.anymarket.com.br/v2/products"

# Token fixo (troque se necessário)
TOKEN_ANY = "MjU5MDYzNTc1Lg==.MUfqIGh9hJCl8gZ0ji+YXHX7aX1SucmOJntr/d0/QjNRjd8WVDk1nXie3s2dX4yf99em09OD7rCS1OYo8Ek+Mw=="

HEADERS = {
    "Content-Type": "application/json",
    "gumgaToken": TOKEN_ANY
}

LOG_FILE = "log_resultados.csv"
REQUEST_DELAY = 1.2
# ===================================


def parse_composition_field(cell_value):
    """Converte '1234,1235' ou '1234/1235' em lista ['1234','1235'].""" 
    if cell_value is None:
        return []
    if isinstance(cell_value, (float, int)):
        return [str(int(cell_value))]
    s = str(cell_value).strip()
    if s == "":
        return []
    if "," in s:
        parts = [p.strip() for p in s.split(",") if p.strip()]
    elif "/" in s:
        parts = [p.strip() for p in s.split("/") if p.strip()]
    else:
        parts = [s]
    return parts


def parse_list_field(cell_value):
    """Converte 'A,B' ou 'A/B' em ['A','B'] (string -> lista). Retorna [] se vazio/None."""
    if cell_value is None:
        return []
    if isinstance(cell_value, (int, float)):
        return [str(int(cell_value))]
    s = str(cell_value).strip()
    if not s or s.lower() == "nan":
        return []
    sep = "," if "," in s else ("/" if "/" in s else None)
    return [p.strip() for p in (s.split(sep) if sep else [s]) if p.strip()]


def sanitize_product_for_post(prod):
    """Remove campos que geralmente quebram a criação (ID, datas, stockLocalId, additionalStocks...)."""
    keys_to_remove = [
        "id", "creationDate", "modificationDate", "dataSource",
        "stockLocalId", "partnerId", "allowAutomaticSkuMarketplaceCreation",
        "calculatedPrice", "isProductActive", "additionalStocks"
    ]
    for k in keys_to_remove:
        prod.pop(k, None)
    # Marca/brand costuma precisar ser um objeto válido; removendo evita 422
    prod.pop("brand", None)
    return prod


def get_product_by_id(product_id):
    """
    Busca o produto pelo ID (ou SKU, se for apenas numérico e não existir como ID).
    """
    url = API_URL_GET.format(id=product_id)
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        return r.json()
    elif r.status_code == 404:
        # tentar buscar pelo partnerId (sku)
        print(f"⚠️ Produto {product_id} não encontrado por ID, tentando buscar por partnerId...")
        url_sku = f"https://api.anymarket.com.br/v2/products?sku={product_id}"
        r2 = requests.get(url_sku, headers=HEADERS)
        if r2.status_code == 200:
            data = r2.json()
            if 'content' in data and len(data['content']) > 0:
                return data['content'][0]
    print(f"❌ Falha ao buscar produto id {product_id} (HTTP {r.status_code})")
    return None


def letter_suffix(idx):
    """Gera sufixos A, B, C..."""
    s = ""
    n = idx + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def create_kit_from_simple(produto, novo_sku, novo_ean, comp_list):
    """Cria KIT simples baseado no produto original."""
    p = sanitize_product_for_post(produto.copy())
    p['type'] = "KIT"

    preco_base = produto['skus'][0].get('cost') or produto['skus'][0].get('sellPrice') or produto['skus'][0].get('price') or 0
    if not preco_base or preco_base <= 0:
        print(f"⚠️ Produto {produto.get('title', '')} sem custo definido — usando preço de venda como base.")

    p['skus'] = [
        {
            "partnerId": str(novo_sku),
            "ean": str(novo_ean) if novo_ean else "",
            "title": produto.get("title", "") + " - KIT",
            "active": True,
            "amount": 0,
            "price": preco_base,
            "sellPrice": preco_base
        }
    ]

    kit_items = [{"sku": str(c), "amount": 1} for c in comp_list]
    p['kitItens'] = kit_items
    return p


def create_kit_from_variation(produto, novos_skus, novos_eans):
    """
    Cria KIT VARIATION: um SKU por variação do produto original.
    'novos_skus' e 'novos_eans' são listas (podem ser menores que o nº de variações).
    """
    p = sanitize_product_for_post(produto.copy())
    p['type'] = "KIT"
    p['hasVariations'] = True

    # Captura tipos de variação (ex.: Cor, Tamanho)
    variations_types = None
    if 'variations' in produto and produto['variations']:
        variations_types = produto['variations']
    elif 'skus' in produto and isinstance(produto['skus'], list) and len(produto['skus']) > 0:
        first = produto['skus'][0]
        if 'variations' in first:
            variations_types = []
            for v in first['variations']:
                if 'type' in v:
                    variations_types.append(v['type'])
    if variations_types:
        p['variations'] = variations_types

    new_skus = []
    for i, orig_sku in enumerate(produto.get('skus', [])):
        # partnerId/ ean exclusivos por variação
        if i < len(novos_skus) and novos_skus[i]:
            partner_new = str(novos_skus[i])
        elif novos_skus:
            # usa o primeiro + sufixo A,B,C... para garantir unicidade
            partner_new = str(novos_skus[0]) + letter_suffix(i)
        else:
            # fallback: base no original + sufixo
            partner_new = str(orig_sku.get('partnerId') or orig_sku.get('id')) + letter_suffix(i)

        if i < len(novos_eans) and novos_eans[i]:
            ean_new = str(novos_eans[i])
        else:
            ean_new = (str(novos_eans[0]) if novos_eans else "")

        preco_base = orig_sku.get('cost') or orig_sku.get('price') or orig_sku.get('sellPrice') or 1

        # Normaliza variações no formato exigido
        sku_variations = {}
        if 'variations' in orig_sku:
            for var in orig_sku['variations']:
                if 'type' in var and 'description' in var:
                    variation_name = var['type']['name']
                    variation_value = var['description']
                    sku_variations[variation_name] = variation_value

        new_sku_obj = {
            "partnerId": partner_new,
            "ean": ean_new,
            "title": produto.get("title", "") + "",
            "price": preco_base,
            "sellPrice": preco_base,
            "amount": 0,
            "active": True,
            "variations": sku_variations,
            # cada variação do KIT é composta pela variação simples correspondente
            "kitItens": [{"sku": str(orig_sku.get('partnerId') or orig_sku.get('id')), "amount": 1}]
        }
        new_skus.append(new_sku_obj)

    p['skus'] = new_skus
    return p


def post_product(payload):
    r = requests.post(API_URL_POST, headers=HEADERS, data=json.dumps(payload))
    return r.status_code, r.text


def write_log_row(log_path, row):
    file_exists = os.path.isfile(log_path)
    with open(log_path, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["id_prod_hub", "novo_sku", "status", "http_code", "message"])
        writer.writerow(row)


def process_row(id_prod_hub, novo_sku_cell, novo_ean_cell, sku_composicao_cell):
    produto = get_product_by_id(id_prod_hub)
    if not produto:
        msg = f"Falha ao buscar produto id {id_prod_hub}"
        print(msg)
        write_log_row(LOG_FILE, [id_prod_hub, novo_sku_cell, "ERROR_GET_PRODUCT", "", msg])
        return

    has_variations = produto.get("hasVariations") or produto.get("type") == "VARIATION"

    # >>> Parse das listas vindas da planilha
    novos_skus = parse_list_field(novo_sku_cell)     # ex: "118500ML,118501ML" -> ["118500ML","118501ML"]
    novos_eans = parse_list_field(novo_ean_cell)     # ex: "7891,7892" -> ["7891","7892"]
    comp_list  = parse_composition_field(sku_composicao_cell)

    if has_variations:
        print(f"Produto {id_prod_hub} é VARIATION -> criando produto VARIATION com variações replicadas.")
        payload = create_kit_from_variation(produto, novos_skus, novos_eans)

        print("Payload resumido para envio:")
        debug_keys = {k: payload.get(k) for k in ["title", "type", "skus", "kitItens", "variations"] if k in payload}
        print(json.dumps(debug_keys, indent=2, ensure_ascii=False))

        code, text = post_product(payload)
        if code in (200, 201):
            ok_sku = ",".join(novos_skus) if novos_skus else "(auto)"
            print(f"✅ Sucesso criando {ok_sku} (HTTP {code})")
            write_log_row(LOG_FILE, [id_prod_hub, ok_sku, "SUCCESS", code, text])
        else:
            err_sku = ",".join(novos_skus) if novos_skus else "(auto)"
            print(f"❌ Erro criando {err_sku}: HTTP {code} -> {text}")
            write_log_row(LOG_FILE, [id_prod_hub, err_sku, "ERROR", code, text])

    else:
        print(f"Produto {id_prod_hub} é SIMPLE -> criando KIT(s) simples.")
        # fallback da composição: se vazio, usa o próprio SKU simples original
        if not comp_list:
            orig_sk = produto.get('skus', [])
            if orig_sk and isinstance(orig_sk, list):
                first_partner = orig_sk[0].get('partnerId')
                if first_partner:
                    comp_list = [str(first_partner)]

        # Se vierem vários novos SKUs, cria um produto por SKU
        target_skus = novos_skus if novos_skus else [str(novo_sku_cell)]
        for i, ns in enumerate(target_skus):
            ne = novos_eans[i] if i < len(novos_eans) else (novos_eans[0] if novos_eans else "")
            payload = create_kit_from_simple(produto, ns, ne, comp_list)

            print("Payload resumido para envio:")
            debug_keys = {k: payload.get(k) for k in ["title", "type", "skus", "kitItens", "variations"] if k in payload}
            print(json.dumps(debug_keys, indent=2, ensure_ascii=False))

            code, text = post_product(payload)
            if code in (200, 201):
                print(f"✅ Sucesso criando {ns} (HTTP {code})")
                write_log_row(LOG_FILE, [id_prod_hub, ns, "SUCCESS", code, text])
            else:
                print(f"❌ Erro criando {ns}: HTTP {code} -> {text}")
                write_log_row(LOG_FILE, [id_prod_hub, ns, "ERROR", code, text])
            time.sleep(REQUEST_DELAY)


def main():
    print("=== COPY KIT FROM EXCEL (AnyMarket) ===")
    # ajuste o caminho da sua planilha aqui:
    planilha = r"C:\__AUTOMAÇÕES\Copy-SKU-Any\Copy-SKU-ANY\COPY SIMPLE P KIT\kits.xlsx"
    try:
        if planilha.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(planilha, dtype=str)
        else:
            try:
                df = pd.read_csv(planilha, dtype=str)
            except Exception:
                df = pd.read_csv(planilha, sep=";", dtype=str)
    except Exception as e:
        print("❌ Erro ao abrir planilha:", e)
        return

    expected = ['id_prod_hub', 'novo_sku', 'novo_ean', 'sku_composicao']
    for col in expected:
        if col not in df.columns:
            print(f"❌ Coluna obrigatória ausente: {col}")
            return

    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    total = len(df)
    print(f"Iniciando processamento de {total} linhas...")
    for idx, row in df.iterrows():
        id_prod = row['id_prod_hub']
        novo_sku_cell = row['novo_sku']
        novo_ean_cell = row['novo_ean'] if 'novo_ean' in row and not pd.isna(row['novo_ean']) else ""
        sku_comp_cell = row['sku_composicao'] if 'sku_composicao' in row else ""

        print(f"\n[{idx+1}/{total}] id_prod_hub={id_prod} novo_sku={novo_sku_cell} novo_ean={novo_ean_cell} sku_composicao={sku_comp_cell}")
        try:
            process_row(id_prod, novo_sku_cell, novo_ean_cell, sku_comp_cell)
        except Exception as ex:
            print("❌ Erro inesperado:", ex)
            write_log_row(LOG_FILE, [id_prod, novo_sku_cell, "EXCEPTION", "", str(ex)])

        time.sleep(REQUEST_DELAY)

    print("\nProcessamento finalizado. Verifique", LOG_FILE)


if __name__ == "__main__":
    main()
