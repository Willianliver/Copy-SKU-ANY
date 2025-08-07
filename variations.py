import requests
import json

# Configurações da API
API_URL_GET = "https://api.anymarket.com.br/v2/products/{id}"
API_URL_POST = "https://api.anymarket.com.br/v2/products"
TOKEN = "MjU5MDI2OTI0Lg==.asoTJuVGMrSd0RgmE9g0t6/dr59T9NtemzSF5huGWX1FsZJJgrrsadK1JI41YmTeTswenQ7VaHd93r0Q52q7AQ=="  # Substitua pelo seu token real

HEADERS = {
    "Content-Type": "application/json",
    "gumgaToken": TOKEN
}

# Função para limpar campos que causam erro
def limpar_campos(produto):
    for campo in ['id', 'creationDate', 'modificationDate', 'dataSource']:
        produto.pop(campo, None)
    return produto

def clonar_produto_com_variacoes(id_prod_hub, novo_sku_pai, novo_ean_pai):
    # 1. Buscar produto original
    url_get = API_URL_GET.format(id=id_prod_hub)
    response = requests.get(url_get, headers=HEADERS)

    if response.status_code != 200:
        print("\u274c Erro ao buscar produto:", response.status_code, response.text)
        return

    produto = response.json()
    produto = limpar_campos(produto)

    # 2. Substituir SKU pai
    if 'sku' in produto and isinstance(produto['sku'], dict):
        produto['sku']['partnerId'] = novo_sku_pai
        produto['sku']['ean'] = novo_ean_pai
    else:
        produto['sku'] = {
            'partnerId': novo_sku_pai,
            'ean': novo_ean_pai
        }

    # 3. Processar SKUs de variação
    if 'skus' in produto and isinstance(produto['skus'], list):
        print(f"\n🔁 Produto tem {len(produto['skus'])} variação(oes):")
        for i, sku_item in enumerate(produto['skus'], start=1):
            print(f"\n🔠 Variação {i}/{len(produto['skus'])}")
            novo_sku = input("Digite o novo SKU: ").strip()
            novo_ean = input("Digite o novo EAN: ").strip()

            # Remover campos problemáticos
            for campo in ['id', 'idVariation', 'stockLocalId']:
                sku_item.pop(campo, None)

            # Corrigir estrutura de variations
            nova_variations = {}
            if 'variations' in sku_item:
                for var in sku_item['variations']:
                    if 'type' in var and 'description' in var:
                        variation_name = var['type']['name']
                        variation_value = var['description']
                        nova_variations[variation_name] = variation_value
                if nova_variations:
                    sku_item['variations'] = nova_variations

            # Atualizar SKU e EAN
            sku_item['partnerId'] = novo_sku
            sku_item['ean'] = novo_ean

    # 4. Marcar produto como com variações
    produto['hasVariations'] = True

    # 5. Mostrar JSON final para conferência
    print("\n📆 JSON FINAL ENVIADO:")
    print(json.dumps(produto, indent=2, ensure_ascii=False))

    # 6. Enviar POST para criar novo produto
    post = requests.post(API_URL_POST, headers=HEADERS, data=json.dumps(produto))

    if post.status_code == 201:
        print(f"\n✅ Produto com variações criado com sucesso!")
    else:
        print("\u274c Erro ao criar produto:", post.status_code, post.text)

# Execução via terminal
if __name__ == "__main__":
    print("=== CLONAR PRODUTO COM VARIAÇÕES ===")
    id_origem = input("Informe o ID do produto origem (id_prod_hub): ").strip()
    novo_sku_pai = input("Digite o novo SKU para o produto pai: ").strip()
    novo_ean_pai = input("Digite o novo EAN para o produto pai: ").strip()

    clonar_produto_com_variacoes(id_origem, novo_sku_pai, novo_ean_pai)
