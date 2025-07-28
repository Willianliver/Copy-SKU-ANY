import requests
import json
from dotenv import load_dotenv
import os

load_dotenv()
# Configurações da API
API_URL_GET = "https://api.anymarket.com.br/v2/products/{id}"
API_URL_POST = "https://api.anymarket.com.br/v2/products"

TOKEN_ANY1 = os.getenv("ANY_1")  # ou ANY_2
TOKEN_ANY2 = os.getenv("ANY_2")  # ou ANY_1


HEADERS_ORIGEM = {
    "Content-Type": "application/json",
    "gumgaToken": TOKEN_ANY1
}

HEADERS_DESTINO = {
    "Content-Type": "application/json",
    "gumgaToken": TOKEN_ANY2
}

def clonar_produto(id_prod_hub, novo_sku, novo_ean):
    # 1. Buscar produto pelo ID
    url_get = API_URL_GET.format(id=id_prod_hub)
    response = requests.get(url_get, headers=HEADERS_ORIGEM)

    if response.status_code != 200:
        print("❌ Erro ao buscar produto:", response.status_code, response.text)
        return

    produto = response.json()

    # 2. Remover campos que não podem ser enviados
    for campo in ['id', 'creationDate', 'modificationDate', 'dataSource']:
        produto.pop(campo, None)

    # 3. Atualizar o sku principal
    if 'sku' in produto and isinstance(produto['sku'], dict):
        produto['sku']['partnerId'] = novo_sku
        produto['sku']['ean'] = novo_ean
    else:
        produto['sku'] = {
            'partnerId': novo_sku,
            'ean': novo_ean
        }

    # 4. Atualizar todos os SKUs dentro da lista 'skus', se existir
    if 'skus' in produto and isinstance(produto['skus'], list):
        for sku_item in produto['skus']:
            sku_item['partnerId'] = novo_sku
            sku_item['ean'] = novo_ean

    # 5. Mostrar o JSON final para conferência
    print("\n✅ JSON FINAL ENVIADO:")
    print(json.dumps(produto, indent=2, ensure_ascii=False))

    # 6. Enviar POST para criar novo produto
    post = requests.post(API_URL_POST, headers=HEADERS_DESTINO, data=json.dumps(produto))

    if post.status_code == 201:
        print(f"✅ Produto {novo_sku} criado com sucesso!")
    else:
        print("❌ Erro ao criar novo produto:", post.status_code, post.text)

# Execução via terminal
if __name__ == "__main__":
    print("=== Clonador de Produto AnyMarket ===")
    id_origem = input("Informe o ID do produto origem (id_prod_hub): ").strip()
    novo_sku = input("Informe o novo SKU: ").strip()
    novo_ean = input("Informe o novo EAN: ").strip()

    clonar_produto(id_origem, novo_sku, novo_ean)
