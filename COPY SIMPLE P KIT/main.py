import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()

# Configurações da API
API_URL_GET = "https://api.anymarket.com.br/v2/products/{id}"
API_URL_POST = "https://api.anymarket.com.br/v2/products"

TOKEN_ANY = "MjU5MDYzNTc1Lg==.MUfqIGh9hJCl8gZ0ji+YXHX7aX1SucmOJntr/d0/QjNRjd8WVDk1nXie3s2dX4yf99em09OD7rCS1OYo8Ek+Mw=="  # pode trocar para ANY_2 se quiser

HEADERS = {
    "Content-Type": "application/json",
    "gumgaToken": TOKEN_ANY
}

def clonar_produto_como_kit(id_prod_hub, novo_sku, novo_ean, sku_composicao, preco_kit=None):
    # 1. Buscar produto pelo ID
    url_get = API_URL_GET.format(id=id_prod_hub)
    response = requests.get(url_get, headers=HEADERS)

    if response.status_code != 200:
        print("❌ Erro ao buscar produto:", response.status_code, response.text)
        return

    produto = response.json()

    # 2. Remover campos que não podem ser enviados
    for campo in ['id', 'creationDate', 'modificationDate', 'dataSource', 'stockLocalId']:
        produto.pop(campo, None)
        produto.pop('brand', None)

    # 3. Forçar que seja KIT
    produto['type'] = "KIT"

    # 4. Atualizar SKU principal
    if 'sku' in produto and isinstance(produto['sku'], dict):
        produto['sku']['partnerId'] = novo_sku
        produto['sku']['ean'] = novo_ean
    else:
        produto['sku'] = {
            'partnerId': novo_sku,
            'ean': novo_ean
        }

    # 5. Substituir lista de SKUs por apenas o SKU novo do kit
    # Herdamos preço do primeiro SKU original, se existir
    preco_base = 0
    if 'skus' in produto and isinstance(produto['skus'], list) and len(produto['skus']) > 0:
        preco_base = produto['skus'][0].get("sellPrice") or produto['skus'][0].get("price") or 0

    produto['skus'] = [
        {
            "partnerId": novo_sku,
            "ean": novo_ean,
            "title": produto.get("title", "") + " - KIT",
            "active": True,
            "amount": 0,  # estoque do kit é controlado pelos componentes
            "price": preco_base,
            "sellPrice": preco_base
        }
    ]

    # 6. Criar o campo kitItens
    produto['kitItens'] = [
        {
            "sku": sku_composicao,
            "amount": 1
        }
    ]

    # 7. Calcular o preço do KIT somando os preços dos componentes
    preco_total_kit = sum([comp['price'] * comp['quantity'] for comp in produto.get('kitComponents', [])])

    if preco_kit is None:  # Se o preço não foi passado, usar o preço total calculado
        preco_kit = preco_total_kit

    produto['price'] = preco_kit

    # 8. Mostrar JSON final
    print("\n✅ JSON FINAL ENVIADO (KIT):")
    print(json.dumps(produto, indent=2, ensure_ascii=False))

    # 9. POST para criar produto como kit
    post = requests.post(API_URL_POST, headers=HEADERS, data=json.dumps(produto))
    if post.status_code == 201:
        print(f"✅ Produto KIT {novo_sku} criado com sucesso!")
    else:
        print("❌ Erro ao criar KIT:", post.status_code, post.text)


# Execução via terminal
if __name__ == "__main__":
    print("=== Criador de KIT no AnyMarket ===")
    id_origem = input("Informe o ID do produto origem (id_prod_hub): ").strip()
    novo_sku = input("Informe o novo SKU do KIT: ").strip()
    novo_ean = input("Informe o novo EAN do KIT: ").strip()
    sku_composicao = input("Informe o SKU que vai compor o KIT: ").strip()
    preco_kit = input("Informe o preço do KIT (ou pressione Enter para calcular a partir dos componentes): ").strip()

    if preco_kit:
        preco_kit = float(preco_kit)
    else:
        preco_kit = None  # Calcular preço a partir dos componentes

    clonar_produto_como_kit(id_origem, novo_sku, novo_ean, sku_composicao, preco_kit)
