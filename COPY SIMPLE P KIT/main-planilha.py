import requests
import json
import pandas as pd
from dotenv import load_dotenv
import os
import time

load_dotenv()

# ===================== Config API =====================
API_URL_GET = "https://api.anymarket.com.br/v2/products/{id}"
API_URL_GET_BY_SKU = "https://api.anymarket.com.br/v2/products"  # ?sku={partnerId}
API_URL_POST = "https://api.anymarket.com.br/v2/products"
API_URL_STOCKS = "https://api.anymarket.com.br/v2/stocks"

TOKEN_ANY = os.getenv("ANYMARKET_TOKEN") or "MjU5MDYzNTc1Lg==.MUfqIGh9hJCl8gZ0ji+YXHX7aX1SucmOJntr/d0/QjNRjd8WVDk1nXie3s2dX4yf99em09OD7rCS1OYo8Ek+Mw=="
HEADERS = {
    "Content-Type": "application/json",
    "gumgaToken": TOKEN_ANY
}

REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.0"))  # um pouco menor
# Agregação se houver mais de um registro (no mesmo local): max | min | avg
COST_AGGREGATION = (os.getenv("COST_AGGREGATION", "max") or "max").lower()

# Filtro obrigatório do estoque (só buscar desse local)
STOCK_LOCAL_ID = os.getenv("STOCK_LOCAL_ID", "45479").strip()  # defina 45479 no .env

# Retry/backoff para evitar 429/limite
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "4"))
BACKOFF_BASE_SEC = float(os.getenv("BACKOFF_BASE_SEC", "1.5"))


# ===================== Helpers =====================
def safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip().replace(",", ".")
        return float(s)
    except:
        return default

def sanitize_product_for_post(prod):
    for campo in ['id', 'creationDate', 'modificationDate', 'dataSource', 'stockLocalId',
                  'partnerId', 'allowAutomaticSkuMarketplaceCreation', 'calculatedPrice',
                  'isProductActive', 'additionalStocks']:
        prod.pop(campo, None)
    prod.pop('brand', None)
    prod.pop('kitItens', None)
    prod.pop('kitComponents', None)
    return prod

def aggregate(values):
    values = [v for v in values if v is not None]
    if not values:
        return 0.0
    if COST_AGGREGATION == "min":
        return min(values)
    if COST_AGGREGATION == "avg":
        return sum(values) / len(values)
    return max(values)  # default

def get_json_with_retries(url, params=None, headers=None, method="GET", data=None, timeout=30):
    """
    Requisição com retries e backoff. Respeita Retry-After se vier no header.
    Retorna (status_code, json|text).
    """
    attempt = 0
    while True:
        try:
            if method == "GET":
                r = requests.get(url, headers=headers, params=params, timeout=timeout)
            else:
                r = requests.request(method, url, headers=headers, params=params, data=data, timeout=timeout)

            # sucesso
            if r.status_code < 400:
                try:
                    return r.status_code, r.json()
                except Exception:
                    return r.status_code, r.text

            # 429 ou 5xx -> retry com backoff
            if r.status_code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                wait = r.headers.get("Retry-After")
                if wait:
                    try:
                        sleep_s = float(wait)
                    except:
                        sleep_s = BACKOFF_BASE_SEC * (2 ** attempt)
                else:
                    sleep_s = BACKOFF_BASE_SEC * (2 ** attempt)
                print(f"⚠️  {r.status_code} em {url} — retry em {sleep_s:.1f}s (tentativa {attempt+1}/{MAX_RETRIES})")
                time.sleep(sleep_s)
                attempt += 1
                continue

            # erro final
            return r.status_code, (r.text if hasattr(r, "text") else None)

        except Exception as e:
            if attempt < MAX_RETRIES:
                sleep_s = BACKOFF_BASE_SEC * (2 ** attempt)
                print(f"⚠️  Erro '{e}' em {url} — retry em {sleep_s:.1f}s (tentativa {attempt+1}/{MAX_RETRIES})")
                time.sleep(sleep_s)
                attempt += 1
                continue
            return 599, str(e)


# ===================== Resolver skuId a partir de partnerId =====================
def resolve_sku_id_from_partner(partner_id):
    """
    Usa /v2/products?sku={partnerId} e retorna o sku.id correspondente (match exato).
    """
    code, data = get_json_with_retries(API_URL_GET_BY_SKU, params={"sku": str(partner_id)}, headers=HEADERS)
    if code != 200 or not isinstance(data, dict):
        print(f"⚠️  GET products?sku={partner_id} HTTP {code}: {(str(data)[:200])}")
        return None

    items = data.get("content") or []
    # match exato
    for prod in items:
        for sku in prod.get("skus", []):
            if str(sku.get("partnerId")) == str(partner_id):
                return sku.get("id")
    # fallback: primeiro sku.id
    for prod in items:
        if prod.get("skus"):
            return prod["skus"][0].get("id")
    return None


# ===================== /v2/stocks (uma chamada, filtrando por local) =====================
def fetch_prices_from_stocks_single_call(sku_id=None, partner_id=None):
    """
    Busca preços no /v2/stocks **somente** para 1 local (STOCK_LOCAL_ID),
    com **apenas uma chamada** (sem paginação).
    >>> Prioridade: sku (partnerId) -> skuId <<<
    Retorna lista de prices (0 ou 1 normalmente, por causa do filtro).
    """
    attempts = []
    if partner_id:
        attempts.append({"sku": str(partner_id), "stockLocalId": STOCK_LOCAL_ID})
    if sku_id:
        attempts.append({"skuId": str(sku_id), "stockLocalId": STOCK_LOCAL_ID})

    for params in attempts:
        code, data = get_json_with_retries(API_URL_STOCKS, params=params, headers=HEADERS)
        if code != 200:
            print(f"⚠️  /stocks {params} HTTP {code}: {(str(data)[:200])}")
            continue

        content = []
        if isinstance(data, dict) and isinstance(data.get("content"), list):
            content = data["content"]
        elif isinstance(data, list):
            content = data

        prices = []
        for it in content:
            if not isinstance(it, dict):
                continue
            stock_local = it.get("stockLocal") or {}
            if str(stock_local.get("id")) != STOCK_LOCAL_ID:
                continue  # defensivo
            prices.append(safe_float(it.get("price"), 0.0))

        if prices:
            return prices

    return []


# ===================== Preço do KIT a partir do SKU de composição =====================
def choose_kit_price_from_component(component_sku_or_id):
    """
    Preço do KIT = price do /v2/stocks do **SKU de composição**.
    >>> Trata SEMPRE como partnerId primeiro; depois tenta skuId resolvido. <<<
    """
    s = str(component_sku_or_id).strip()
    partner_id = s if s else None

    # 1) tenta direto por partnerId
    prices = fetch_prices_from_stocks_single_call(sku_id=None, partner_id=partner_id)

    # 2) se não achar, resolve skuId via /products?sku=... e tenta por skuId
    if not prices and partner_id:
        sku_id = resolve_sku_id_from_partner(partner_id)
        if sku_id:
            prices = fetch_prices_from_stocks_single_call(sku_id=sku_id, partner_id=None)

    if prices:
        return aggregate(prices)

    # último recurso
    return 1.0


# ===================== Função principal =====================
def clonar_produto_como_kit(id_prod_hub, novo_sku, novo_ean, sku_composicao):
    try:
        # 1) Buscar produto base
        url_get = API_URL_GET.format(id=id_prod_hub)
        code, data = get_json_with_retries(url_get, headers=HEADERS)
        if code != 200 or not isinstance(data, dict):
            print(f"❌ Erro ao buscar produto {id_prod_hub}: HTTP {code}")
            print(str(data)[:300])
            return False

        produto_base = data

        # 2) Sanitizar para POST
        produto = sanitize_product_for_post(produto_base.copy())

        # 3) Tipo KIT simples (1 SKU)
        produto['type'] = "KIT"
        produto['hasVariations'] = False

        # 4) Preço do KIT = estoque do SKU de composição (no local selecionado)
        preco_base = choose_kit_price_from_component(sku_composicao)
        if preco_base <= 0:
            print("⚠️  Preço calculado <= 0, ajustando para 1.0")
            preco_base = 1.0

        # Debug para auditarmos caso dê discrepância
        print(f"[DEBUG] comp_sku={sku_composicao} -> preco_estoque={preco_base} (stockLocalId={STOCK_LOCAL_ID})")

        # 5) Substituir SKUs
        produto['skus'] = [{
            "partnerId": str(novo_sku),
            "ean": str(novo_ean) if novo_ean is not None else "",
            "title": (produto.get("title") or "") + " - KIT",
            "active": True,
            "amount": 0,
            "price": preco_base,
            "sellPrice": preco_base
        }]

        # 6) Definir composição do kit
        produto['kitItens'] = [{
            "sku": str(sku_composicao),
            "amount": 1
        }]

        # 7) POST com retries
        code_post, data_post = get_json_with_retries(API_URL_POST, headers=HEADERS, method="POST", data=json.dumps(produto), timeout=40)
        if code_post in (200, 201):
            print(f"✅ KIT criado com sucesso: {novo_sku}")
            return True
        else:
            print(f"❌ Erro ao criar KIT {novo_sku}: HTTP {code_post}")
            print(str(data_post)[:600])
            return False

    except Exception as e:
        print(f"❌ Erro inesperado com {novo_sku}: {e}")
        return False


# ===================== Execução em lote via planilha =====================
if __name__ == "__main__":
    print("=== Criador de KITs em Massa (AnyMarket • estoque fixo por stockLocalId) ===")

    planilha = os.getenv("PLANILHA_KITS") or r"C:\__AUTOMAÇÕES\Copy-SKU-Any\Copy-SKU-ANY\COPY SIMPLE P KIT\kits.xlsx"

    # Carrega planilha
    try:
        if planilha.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(planilha, dtype=str)
        else:
            try:
                df = pd.read_csv(planilha, dtype=str)
            except:
                df = pd.read_csv(planilha, sep=";", dtype=str)
    except Exception as e:
        print("❌ Erro ao ler planilha:", e)
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

        print(f"\n➡️ [{i+1}/{total}] Criando KIT {novo_sku} a partir de {id_prod} (comp={sku_comp})...")
        ok = clonar_produto_como_kit(id_prod, novo_sku, novo_ean, sku_comp)
        if ok:
            sucesso += 1

        time.sleep(REQUEST_DELAY)

    print(f"\n✅ Finalizado! {sucesso}/{total} kits criados com sucesso.")
