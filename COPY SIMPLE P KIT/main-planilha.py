import requests
import json
import pandas as pd
import os
import time

# ===================== CONFIGURAÇÕES =====================
API_URL_GET = "https://api.anymarket.com.br/v2/products/{id}"
API_URL_GET_BY_SKU = "https://api.anymarket.com.br/v2/products"
API_URL_POST = "https://api.anymarket.com.br/v2/products"
API_URL_STOCKS = "https://api.anymarket.com.br/v2/stocks"

TOKEN_ANY = "MjU5MDYzNTc1Lg==.MUfqIGh9hJCl8gZ0ji+YXHX7aX1SucmOJntr/d0/QjNRjd8WVDk1nXie3s2dX4yf99em09OD7rCS1OYo8Ek+Mw=="

HEADERS = {
    "Content-Type": "application/json",
    "gumgaToken": TOKEN_ANY
}

REQUEST_DELAY = 1.2
STOCK_LOCAL_ID = 45479
MAX_RETRIES = 4
BACKOFF_BASE_SEC = 1.5


# ===================== FUNÇÕES AUXILIARES =====================

#essa função remove os dados que não podem ser enviados no POST
def sanitize_product_for_post(prod):
    for campo in ['id', 'creationDate', 'modificationDate', 'dataSource', 'stockLocalId',
                  'partnerId', 'allowAutomaticSkuMarketplaceCreation', 'calculatedPrice',
                  'isProductActive', 'additionalStocks']:
        prod.pop(campo, None)
    prod.pop('brand', None)
    prod.pop('kitItens', None)
    prod.pop('kitComponents', None)
    return prod

# Executa requisições HTTP com repetição automática em caso de erro (429, 500, 502, etc)
# Caso a execução seja negada e faz uma nova tentativa
def get_json_with_retries(url, params=None, headers=None, method="GET", data=None, timeout=30):
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            if method == "GET":
                r = requests.get(url, headers=headers, params=params, timeout=timeout)
            else:
                r = requests.request(method, url, headers=headers, params=params, data=data, timeout=timeout)

            if r.status_code < 400:
                try:
                    return r.status_code, r.json()
                except Exception:
                    return r.status_code, r.text

            if r.status_code in (429, 500, 502, 503, 504):
                wait = r.headers.get("Retry-After")
                sleep_s = float(wait) if wait else BACKOFF_BASE_SEC * (2 ** attempt)
                print(f"⚠️  {r.status_code} em {url} — retry em {sleep_s:.1f}s (tentativa {attempt+1}/{MAX_RETRIES})")
                time.sleep(sleep_s)
                attempt += 1
                continue

            return r.status_code, r.text

        except Exception as e:
            sleep_s = BACKOFF_BASE_SEC * (2 ** attempt)
            print(f"⚠️  Erro '{e}' em {url} — retry em {sleep_s:.1f}s (tentativa {attempt+1}/{MAX_RETRIES})")
            time.sleep(sleep_s)
            attempt += 1

    return 599, "Erro após múltiplas tentativas"

# Pega o idSku interno a partir do partnerId (SKU externo).
def resolve_sku_id_from_partner(partner_id):
    """Resolve o idSku (necessário para kitComponents)"""
    code, data = get_json_with_retries(API_URL_GET_BY_SKU, params={"sku": str(partner_id)}, headers=HEADERS)
    if code != 200 or not isinstance(data, dict):
        print(f"⚠️  Falha ao buscar SKU {partner_id}: HTTP {code}")
        return None

    items = data.get("content") or []
    for prod in items:
        for sku in prod.get("skus", []):
            if str(sku.get("partnerId")) == str(partner_id):
                return sku.get("id")

    if items and items[0].get("skus"):
        return items[0]["skus"][0].get("id")

    return None

# Busca o preço de um SKU no estoque definido
def fetch_price_from_stocks(sku_partner):
    """Busca o preço do SKU no estoque definido"""
    code, data = get_json_with_retries(API_URL_STOCKS, params={"sku": sku_partner, "stockLocalId": STOCK_LOCAL_ID}, headers=HEADERS)
    if code != 200 or not isinstance(data, (dict, list)):
        print(f"⚠️  Falha ao buscar preço do SKU {sku_partner}: HTTP {code}")
        return 1.0

    if isinstance(data, dict):
        content = data.get("content", [])
    else:
        content = data

    for it in content:
        stock_local = it.get("stockLocal", {})
        if str(stock_local.get("id")) == str(STOCK_LOCAL_ID):
            return float(it.get("price") or 1.0)

    return 1.0


# ===================== PRINCIPAL =====================
def clonar_produto_como_kit(id_prod_hub, novo_sku, novo_ean, sku_composicao):
    url_get = API_URL_GET.format(id=id_prod_hub)
    code, produto_data = get_json_with_retries(url_get, headers=HEADERS)

    if code != 200 or not isinstance(produto_data, dict):
        print(f"❌ Erro ao buscar produto {id_prod_hub}: HTTP {code}")
        return False

    produto = sanitize_product_for_post(produto_data.copy())
    produto['type'] = "KIT"
    produto['hasVariations'] = False

    # Preço base a partir do SKU de composição
    preco_base = fetch_price_from_stocks(sku_composicao)
    if preco_base <= 0:
        preco_base = 1.0

    # Resolve idSku do componente
    id_sku_comp = resolve_sku_id_from_partner(sku_composicao)
    if not id_sku_comp:
        print(f"⚠️  Não foi possível resolver idSku para {sku_composicao}")
        return False

    # Define o SKU principal
    produto['skus'] = [{
        "partnerId": str(novo_sku),
        "ean": str(novo_ean or ""),
        "title": (produto.get("title") or "") + " - KIT",
        "active": True,
        "amount": 1,
        "price": preco_base,
        "sellPrice": preco_base,
        "stockLocalId": STOCK_LOCAL_ID
        
    }]

    # Define os componentes do KIT   #IMPORTANTEE
    produto['kitComponents'] = [{
        "idInClient": str(sku_composicao),
        "idSku": id_sku_comp,
        "stockLocalId": STOCK_LOCAL_ID,
        "percentage": 100,
        "quantity": 1,
        "isMainComponent": True,
        "price": preco_base,
        "priceFactor": 2.8
    }]

    # Envio para criação
    code_post, data_post = get_json_with_retries(API_URL_POST, headers=HEADERS, method="POST", data=json.dumps(produto))
    if code_post in (200, 201):
        print(f"✅ KIT criado com sucesso: {novo_sku}")
        return True
    else:
        print(f"❌ Erro criando {novo_sku}: HTTP {code_post} -> {data_post}")
        return False


# ===================== EXECUÇÃO VIA PLANILHA =====================
if __name__ == "__main__":
    print("=== CRIADOR DE KITS ANYMARKET ===")

    planilha = r"C:\__AUTOMAÇÕES\Copy-SKU-Any\Copy-SKU-ANY\COPY SIMPLE P KIT\kits.xlsx"

    try:
        if planilha.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(planilha, dtype=str)
        else:
            df = pd.read_csv(planilha, dtype=str)
    except Exception as e:
        print("❌ Erro ao abrir planilha:", e)
        exit(1)

    obrigatorias = ['id_prod_hub', 'novo_sku', 'novo_ean', 'sku_composicao']
    for col in obrigatorias:
        if col not in df.columns:
            print(f"❌ Coluna obrigatória ausente: {col}")
            exit(1)

    total = len(df)
    sucesso = 0

    for i, row in df.iterrows():
        id_prod = row['id_prod_hub']
        novo_sku = row['novo_sku']
        novo_ean = row['novo_ean']
        sku_comp = row['sku_composicao']

        print(f"\n➡️ [{i+1}/{total}] Criando KIT {novo_sku} com base em {id_prod} (composição: {sku_comp})")
        if clonar_produto_como_kit(id_prod, novo_sku, novo_ean, sku_comp):
            sucesso += 1

        time.sleep(REQUEST_DELAY)

    print(f"\n✅ Finalizado! {sucesso}/{total} kits criados com sucesso.")
